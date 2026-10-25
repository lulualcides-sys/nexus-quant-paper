import math
import unittest
from src.gold_forward import initial, update, summary, STUDY
from research.screen_v2 import aggregate_hourly_to_h4

T0=1729728000
def rows(n=1050):
    ret=[];p=2600.
    for i in range(n):
        q=p+0.24+math.sin(i/7)*0.12
        ret.append({"time":T0+i*3600,"open":p,"close":q,
                    "high":max(p,q)+0.5,"low":min(p,q)-0.5})
        p=q
    return ret

class GoldPaperTests(unittest.TestCase):
    def test_first_run_is_only_observation(self):
        h4=aggregate_hourly_to_h4(rows())
        self.assertGreaterEqual(len(h4),245)
        s=update(None,rows())
        self.assertEqual(s["h4_watermark"],h4[-1]["time"])
        self.assertEqual(len(s["books"]),5)
        self.assertTrue(all(not v["closed"] and v["position"] is None for v in s["books"].values()))
        self.assertTrue(s["paper_only"])
    def test_no_duplicate_entries_when_rescanned(self):
        data=rows(1050)
        first=update(None,data)
        again=update(first,data)
        self.assertEqual(first,again)
    def test_incremental_future_bars_only(self):
        old=rows(1050)
        s=update(None,old)
        mark=s["h4_watermark"]
        extra=rows(1100)
        s=update(s,extra)
        self.assertGreater(s["h4_watermark"],mark)
        self.assertEqual(set(s["books"]),set(STUDY))
        msg=summary(s,"2026-10-24")
        self.assertIn("VIRTUAIS",msg)
        self.assertIn("não FBS",msg)
    def test_requires_history(self):
        with self.assertRaises(ValueError):
            update(None,rows(300))

if __name__=="__main__":unittest.main()
