import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
from src.market_quality import validate_bars
from src.feed import Asset, get_bars


def rows(n=245, t0=1800000000):
    t0 -= t0 % 3600
    return [{"time": t0+i*3600, "open": 100.0, "high": 102.0,
             "low": 99.0, "close": 101.0} for i in range(n)]


class Context(BytesIO):
    pass


class FeedQualityTest(unittest.TestCase):
    def test_valid_then_stale_and_open(self):
        data = rows()
        now = data[-1]["time"] + 3600 + 100
        self.assertEqual(validate_bars(data, now=now)["age_seconds"], 100)
        with self.assertRaisesRegex(ValueError, "desatualizada"):
            validate_bars(data, now=now+20000, max_age=10800)
        with self.assertRaisesRegex(ValueError, "aberto"):
            validate_bars(data, now=data[-1]["time"]+100)

    def test_corrupted_and_duplicate_bars_are_rejected(self):
        data = rows()
        with self.assertRaisesRegex(ValueError, "duplicados"):
            validate_bars(data + [dict(data[-1])],
                          now=data[-1]["time"]+4000)
        broken = rows()
        broken[-1]["high"] = 10.0
        with self.assertRaisesRegex(ValueError, "inconsistente"):
            validate_bars(broken, now=broken[-1]["time"]+4000)
        gap = rows()
        gap[-1]["time"] += 3600
        with self.assertRaisesRegex(ValueError, "lacuna"):
            validate_bars(gap, now=gap[-1]["time"]+4000, continuous=True)

    def test_yahoo_mirror_after_first_host_failure(self):
        candles = rows()
        now = candles[-1]["time"]+3600+1200
        values = {k: [x[k] for x in candles] for k in ("open", "high", "low", "close")}
        payload = {"chart": {"result": [{"timestamp": [x["time"] for x in candles],
                    "indicators": {"quote": [values]}}]}}
        requests = []
        def fake_urlopen(req, timeout):
            requests.append(req.full_url)
            if "query1." in req.full_url:
                raise URLError("host down")
            return Context(json.dumps(payload).encode("utf-8"))
        with patch("src.feed.urllib.request.urlopen", side_effect=fake_urlopen):
            got = get_bars(Asset("Synthetic FX", "EURUSD=X", "test"), now=now)
        self.assertEqual(len(got), 245)
        self.assertEqual(len(requests), 2)
        self.assertIn("query2", requests[-1])

    def test_feed_both_bad_fails_closed(self):
        with patch("src.feed.urllib.request.urlopen", side_effect=URLError("blocked")):
            with self.assertRaisesRegex(RuntimeError, "sem atualizar sinais"):
                get_bars(Asset("Synthetic FX", "EURUSD=X", "test"),
                         now=1800000000)


if __name__ == "__main__":
    unittest.main()
