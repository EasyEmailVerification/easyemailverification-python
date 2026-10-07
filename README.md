# Easy Email Verification for Python

Official Python client for the [Easy Email Verification API](https://www.easyemailverification.com/en-US/api): check whether email addresses exist and are safe to send to, one by one, in batches of 50 or as bulk lists of up to 16 MB. No email is sent to the addresses you verify.

- No dependencies (standard library only), Python 3.8+
- Type hints included
- Free sandbox key to test without an account or credits

## Install

```bash
pip install easyemailverification
```

## Quick start

```python
from easyemailverification import Client, SANDBOX_API_KEY, decide

# Use SANDBOX_API_KEY to try it, or your own key (by default read from EEV_API_KEY)
eev = Client(SANDBOX_API_KEY)

result = eev.verify("valid@sandbox.easyemailverification.com")
print(result["result"], result["reason"], result["safe_to_send"])  # valid accepted_email True
print(decide(result))  # accept
```

Get your API key in the dashboard under [API settings](https://dashboard.easyemailverification.com/apisettings) and keep it on the server, in the `EEV_API_KEY` environment variable.

## Results

Every verification returns `result` (`valid`, `invalid` or `unknown`), a `reason` and risk signals:

| Field | Meaning |
| --- | --- |
| `result` | `valid`: the mail server accepted the mailbox. `invalid`: it will bounce. `unknown`: no reliable answer (not invalid). |
| `reason` | Why, for example `accepted_email`, `rejected_email`, `invalid_domain`, `no_mx_record`, `timeout`. |
| `safe_to_send` | Overall recommendation. `False` for invalid and unknown results, catch-all domains and disposable addresses. |
| `did_you_mean` | Corrected address when a typo is detected (`gmial.com` → `gmail.com`), otherwise `""`. |
| `disposable`, `accept_all`, `role`, `free` | Risk signals: temporary inbox, catch-all domain, role address (info@), free provider. |

`decide(result)` turns a result into `"accept"`, `"reject"`, `"suggest"` (show `did_you_mean`) or `"review"` (unknown, catch-all or disposable: your policy decides). Every result code is explained at [easyemailverification.com/en-US/help/result-codes](https://www.easyemailverification.com/en-US/help/result-codes).

## Batch: up to 50 addresses

```python
for r in eev.verify_batch(["anna@example.com", "mark@gmial.com"]):
    print(r["email"], decide(r))
```

## Bulk lists

For files with thousands of addresses (TXT or CSV, one address per line, up to 16 MB). The account needs enough credits for every address. Bulk does not work with the sandbox key.

```python
job = eev.bulk.upload("leads.csv")          # a path, or bytes with the contents
done = eev.bulk.wait(job["list_id"])        # polls until completed (or failed)
if done["status"] == "completed":
    csv_text = eev.bulk.download(job["list_id"])  # Email,Result,Reason,...,IsSafeToSend,DidYouMean,...
eev.bulk.list()                             # all jobs of the account
eev.bulk.delete(job["list_id"])             # results are also deleted after 30 days
```

## Credits

```python
print(eev.credits()["credits_remaining"])  # free call
```

Each verified address uses one credit; unknown results do not. The free plan includes 50 verifications a day. See [pricing](https://www.easyemailverification.com/en-US/pricing).

## Errors

API errors raise `EEVError` with the HTTP `status` and the API `message`:

```python
from easyemailverification import EEVError

try:
    eev.verify("someone@example.com")
except EEVError as e:
    if e.status == 402:
        ...  # no credits left
```

| Status | Meaning |
| --- | --- |
| 400 | Missing key or parameter, or a non-sandbox address with the sandbox key |
| 401 | Unknown key, or a widget-only key |
| 402 | No credits left |
| 404 | Bulk job not found |
| 429 | Sandbox rate limit |
| 0 | Raised by the client (network error, timeout, more than 50 addresses in a batch) |

Do not retry verifications in a tight loop: a request that timed out may already have used a credit.

## Sandbox addresses

With `SANDBOX_API_KEY`, these addresses return fixed answers: `valid@`, `invalid@`, `unknown@`, `disposable@`, `catchall@`, `role@`, `quota@` (402) and `ratelimit@` (429) at `sandbox.easyemailverification.com`, plus `typo@gmial.com` (did you mean). Sandbox calls are limited to 60 per minute per IP.

## Links

- [Email verification API](https://www.easyemailverification.com/en-US/api) and [API reference](https://www.easyemailverification.com/en-US/api/reference)
- [How to validate an email address in Python](https://www.easyemailverification.com/en-US/guides/validate-email-python)
- [OpenAPI specification](https://www.easyemailverification.com/openapi.json)
- [MCP server for AI assistants](https://www.easyemailverification.com/en-US/mcp)
- Support: support@easyemailverification.com

## License

MIT
