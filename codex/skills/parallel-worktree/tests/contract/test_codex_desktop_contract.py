#!/usr/bin/env python3

"""Opt-in gate that keeps codex_managed disabled without a verified harness."""

import os
import unittest


class DesktopContractTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("PW_RUN_CODEX_DESKTOP_CONTRACT") == "1", "desktop contract is opt-in")
    def test_contract_harness_must_report_verified(self) -> None:
        self.assertEqual(
            os.environ.get("PW_CODEX_DESKTOP_CONTRACT_RESULT"),
            "verified",
            "codex_managed remains disabled until the desktop harness reports verified",
        )


if __name__ == "__main__":
    unittest.main()
