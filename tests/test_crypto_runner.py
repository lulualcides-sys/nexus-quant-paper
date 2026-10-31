import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from src import crypto_runner
import math
T0 = 1800000000 - 1800000000 % 3600
def rows(n=265, shift=0):
    out=[]
    for i in range(n):
        p=300.0+shift+.05*i+math.sin(i/9)
        o,c=p-.15,p+.12
        out.append({"time":T0+i*3600,"open":o,"high":max(o,c)+.3,
                    "low":min(o,c)-.3,"close":c})
    return out


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
