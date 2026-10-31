import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src import crypto_runner
from tests.test_crypto_paper import rows


class CryptoRunnerTest(unittest.TestCase):
    def test_scan_silent_and_report_only_once(self):
        msgs = []
        def fetch(symbol, now):
            return rows(265, shift=100 if symbol == "ETHUSDT" else 0)
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            opts = dict(now=1800950000, get=fetch,
                        send=lambda s: msgs.append(s) or True,
                        state_path=path/"state.json", reports=path/"reports",
                        marker=path/"sent.json")
            crypto_runner.run("scan", **opts)
            self.assertEqual(msgs, [])
            crypto_runner.run("report", **opts)
            crypto_runner.run("report", **opts)
            self.assertEqual(len(msgs), 1)
            self.assertIn("4 robos", msgs[0])
            self.assertTrue((path/"sent.json").exists())

    def test_failed_market_reports_missing_not_zero(self):
        def fetch(symbol, now):
            if symbol == "BTCUSDT":
                raise RuntimeError("blocked")
            return rows(265)
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            out = crypto_runner.run("scan", now=1800950000, get=fetch,
                                    state_path=path/"state.json")
            self.assertIn("BTCUSDT", out["unavailable"])
            from src.crypto_paper import digest
            self.assertIn("DADOS INDISPONIVEIS", digest(out,"2026-10-31"))


if __name__ == "__main__":
    unittest.main()
