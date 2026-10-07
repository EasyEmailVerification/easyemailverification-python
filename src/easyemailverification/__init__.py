"""Official Python client for the Easy Email Verification API.

API reference: https://www.easyemailverification.com/en-US/api/reference
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "Client", "Bulk", "EEVError", "decide",
    "SANDBOX_API_KEY", "DEFAULT_BASE_URL", "MAX_BATCH", "__version__",
]

__version__ = "1.0.0"
DEFAULT_BASE_URL = "https://api.easyemailverification.com/v1"

#: Public test key: no account and no credits. Works on verify, verify_batch and credits (not bulk),
#: only for addresses at sandbox.easyemailverification.com (plus typo@gmial.com), with fixed answers.
SANDBOX_API_KEY = "eev_sandbox_key"

#: Maximum addresses per verify_batch call.
MAX_BATCH = 50

_FINAL_STATES = ("completed", "failed", "deleted", "not_enough_credits")


class EEVError(Exception):
    """Error returned by the API (``status`` is the HTTP status) or raised by the client (``status`` 0)."""

    def __init__(self, message: str, status: int = 0, body: Any = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.body = body


def decide(result: Dict[str, Any]) -> str:
    """Turns a verification result into a decision.

    ``"accept"``  valid and safe to send;
    ``"reject"``  invalid (will bounce);
    ``"suggest"`` did_you_mean has a corrected address (ask the user);
    ``"review"``  unknown, catch-all or disposable: your own policy decides.
    """
    if result.get("did_you_mean"):
        return "suggest"
    if result.get("result") == "valid" and result.get("safe_to_send"):
        return "accept"
    if result.get("result") == "invalid":
        return "reject"
    return "review"


class Client:
    """Easy Email Verification API client.

    :param api_key: defaults to the ``EEV_API_KEY`` environment variable
    :param base_url: API base URL
    :param timeout: seconds per request (batch uses at least 120, bulk uploads and downloads 300)
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL, timeout: float = 30):
        self.api_key = api_key or os.environ.get("EEV_API_KEY")
        if not self.api_key:
            raise EEVError("Missing API key: pass api_key or set EEV_API_KEY (use SANDBOX_API_KEY to test)")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.bulk = Bulk(self)

    def _request(self, method: str, path: str, *, json_body: Any = None, data: Optional[bytes] = None,
                 content_type: Optional[str] = None, timeout: Optional[float] = None, raw: bool = False) -> Any:
        headers = {"X-API-Key": self.api_key, "User-Agent": "easyemailverification-python/" + __version__}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                text = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as e:
            with e:
                text = e.read().decode("utf-8", "replace")
            status = e.code
        except (urllib.error.URLError, OSError) as e:
            raise EEVError("Request failed: %s" % getattr(e, "reason", e)) from e

        ok = 200 <= status < 300
        if ok and raw:
            return text
        try:
            payload = json.loads(text) if text else None
        except ValueError:
            if ok:
                raise EEVError("Unexpected response from the API", status, text)
            payload = None
        if not ok:
            message = payload.get("message") if isinstance(payload, dict) else None
            raise EEVError(message or "HTTP %d" % status, status, payload if payload is not None else text)
        return payload

    def verify(self, email: str) -> Dict[str, Any]:
        """Verifies one address. Uses one credit; unknown results do not."""
        return self._request("GET", "/verify?email=" + urllib.parse.quote(email, safe=""))

    def verify_batch(self, emails: List[str]) -> List[Dict[str, Any]]:
        """Verifies up to 50 addresses in one request; returns one result per address."""
        if not emails:
            raise EEVError("verify_batch needs a non-empty list")
        if len(emails) > MAX_BATCH:
            raise EEVError("verify_batch accepts at most %d addresses; use bulk for larger lists" % MAX_BATCH)
        return self._request("POST", "/verify", json_body={"emails": list(emails)}, timeout=max(self.timeout, 120))

    def credits(self) -> Dict[str, Any]:
        """Remaining credits (free)."""
        return self._request("GET", "/credits")


class Bulk:
    """Bulk list verification (``client.bulk``). Not available with the sandbox key."""

    def __init__(self, client: Client):
        self._client = client

    def upload(self, file: Union[str, "os.PathLike[str]", bytes], filename: Optional[str] = None) -> Dict[str, Any]:
        """Uploads a TXT or CSV list (one address per line, max 16 MB) and starts a job.

        :param file: a file path, or the file contents as bytes
        :param filename: name shown in the dashboard (default: the file name, or list.csv)
        """
        if isinstance(file, (bytes, bytearray)):
            content = bytes(file)
        else:
            with open(file, "rb") as f:
                content = f.read()
            filename = filename or os.path.basename(os.fspath(file))
        filename = (filename or "list.csv").replace('"', "")
        boundary = "eev" + uuid.uuid4().hex
        body = (
            ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
             "Content-Type: text/csv\r\n\r\n" % (boundary, filename)).encode()
            + content + ("\r\n--%s--\r\n" % boundary).encode()
        )
        return self._client._request("POST", "/bulk/upload", data=body,
                                     content_type="multipart/form-data; boundary=" + boundary, timeout=300)

    def status(self, list_id: str) -> Dict[str, Any]:
        """Status of one job: status, progress (0-100), totals."""
        return self._client._request("GET", "/bulk/status/" + urllib.parse.quote(list_id, safe=""))

    def list(self) -> Dict[str, Any]:
        """All jobs of the account."""
        return self._client._request("GET", "/bulk/status")

    def download(self, list_id: str) -> str:
        """Results of a completed job, as CSV text."""
        return self._client._request("GET", "/bulk/download/" + urllib.parse.quote(list_id, safe=""), raw=True, timeout=300)

    def delete(self, list_id: str) -> Dict[str, Any]:
        """Deletes a job and its results."""
        return self._client._request("DELETE", "/bulk/" + urllib.parse.quote(list_id, safe=""))

    def wait(self, list_id: str, interval: float = 5, timeout: float = 3600) -> Dict[str, Any]:
        """Polls status() until the job is completed, failed, deleted or not_enough_credits."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.status(list_id)
            if job.get("status") in _FINAL_STATES:
                return job
            if time.monotonic() + interval > deadline:
                raise EEVError("Bulk job %s did not finish in time (status: %s)" % (list_id, job.get("status")))
            time.sleep(interval)
