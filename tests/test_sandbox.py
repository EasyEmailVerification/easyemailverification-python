"""Live tests against the public sandbox (no account, no credits)."""
import os
import unittest

from easyemailverification import SANDBOX_API_KEY, Client, EEVError, decide

S = "sandbox.easyemailverification.com"


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.eev = Client(SANDBOX_API_KEY)

    def test_verify_answers_and_decisions(self):
        cases = {"valid": ("valid", "accept"), "invalid": ("invalid", "reject"), "unknown": ("unknown", "review"),
                 "catchall": ("valid", "review"), "disposable": ("valid", "review")}
        for local, (result, decision) in cases.items():
            r = self.eev.verify("%s@%s" % (local, S))
            self.assertEqual(r["result"], result, local)
            self.assertEqual(decide(r), decision, local)
        typo = self.eev.verify("typo@gmial.com")
        self.assertEqual(typo["did_you_mean"], "typo@gmail.com")
        self.assertEqual(decide(typo), "suggest")

    def test_plus_is_kept(self):
        self.assertEqual(self.eev.verify("valid+tag@" + S)["email"], "valid+tag@" + S)

    def test_batch(self):
        r = self.eev.verify_batch(["valid@" + S, "typo@gmial.com"])
        self.assertEqual([decide(x) for x in r], ["accept", "suggest"])

    def test_batch_limit(self):
        with self.assertRaises(EEVError):
            self.eev.verify_batch(["valid@" + S] * 51)

    def test_credits(self):
        self.assertIsInstance(self.eev.credits()["credits_remaining"], int)

    def test_errors(self):
        with self.assertRaises(EEVError) as ctx:
            self.eev.verify("quota@" + S)
        self.assertEqual(ctx.exception.status, 402)
        with self.assertRaises(EEVError) as ctx:
            Client("wrong-key").verify("valid@" + S)
        self.assertEqual(ctx.exception.status, 401)

    def test_missing_key(self):
        saved = os.environ.pop("EEV_API_KEY", None)
        try:
            with self.assertRaises(EEVError):
                Client()
        finally:
            if saved is not None:
                os.environ["EEV_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main()
