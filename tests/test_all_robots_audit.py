"""Offline regression: the consolidated report covers 27 distinct PAPER slots."""
import unittest
from copy import deepcopy

from src.all_robots_audit import build, telegram_line, TOTAL, GROUP_SIZES
from src.gold_forward import STUDY
from src.leveraged_gold import CONFIG
from src.experimental_h1 import STRATEGIES, bot_key
from src.feed import MARKETS
from src.daily_digest import digest

NOW = 1791000000


def fixtures():
    g = {"paper_only": True, "books": {
        key: {"equity": 5000, "position": None, "closed": []} for key in STUDY}}
    lev = {"paper_only": True, "books": {
        key: {"equity": 5000, "position": None, "closed": [],
              "frozen": False, "peak_equity": 5000} for key in CONFIG}}
    h4 = {"paper_only": True, "last_h4_close_ts": NOW-3600,
          "robots": {key: {"status": "no_new_signal", "explanation": "sem setup"}
                     for key in list(STUDY)+list(CONFIG)}}
    h1 = {"paper_only": True, "experimental_only": True,
          "watermarks": {market: NOW-3600 for market in MARKETS},
          "unavailable": [], "books": {}}
    for m in MARKETS:
        for rule in STRATEGIES:
            h1["books"][bot_key(m, rule)] = {
                "equity": 1000, "closed": [], "entries": [],
                "position": None, "last_reason": "Aguardando setup H1",
                "diagnostics": {"no_setup": 1}}
    mtf = {"paper_only": True, "ticker": "CAD=X",
           "watermark_m15": NOW-900, "equity": 1000,
           "position": None, "closed": [],
           "last_reason": "Aguardando toque na SMA20"}
    mom = {"paper_only": True, "experimental_only": True,
           "h4_watermark": NOW-14400, "equity": 5000,
           "position": None, "closed": [], "entries": []}
    return g, lev, h4, h1, mtf, mom


class AllRobotsAuditTests(unittest.TestCase):
    def test_complete_census_27_no_mutations(self):
        src = fixtures()
        before = deepcopy(src)
        result = build(now=NOW,conventional=src[0],leveraged=src[1],
                       h4_result=src[2],h1_state=src[3],mtf_state=src[4],
                       momentum_state=src[5])
        self.assertEqual(src,before)
        self.assertEqual(result["planned_robots"],TOTAL)
        self.assertEqual(result["with_observed_state"],27)
        self.assertEqual(result["missing_or_invalid"],0)
        self.assertEqual(len(result["robots"]),27)
        self.assertEqual({g:sum(x["group"]==g for x in result["robots"].values())
                         for g in GROUP_SIZES},GROUP_SIZES)
        self.assertEqual(sum(result["status_counts"].values()),27)
        self.assertTrue(result["read_only"] and result["paper_only"])
        self.assertFalse(result["validated_for_real_money"])
        self.assertIn("27 previstos",telegram_line(result))

    def test_missing_status_never_zero_profit(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=h4,
                     h1_state=None,mtf_state=None,momentum_state=None,
                     errors={"h1":"fonte falhou"})
        self.assertEqual(result["with_observed_state"],10)
        self.assertEqual(result["missing_or_invalid"],17)
        self.assertEqual(result["robots"]["momentum60_h4:momentum60"]["net_realized_usd"],None)
        self.assertEqual(result["robots"]["usdcad_m15:bb20"]["entries_observed"],None)
        self.assertIsNone(result["robots"]["experimental_h1:EURUSD:rsi50"]["closed"])
        self.assertIn("17 indisponíveis",telegram_line(result))

    def test_one_missing_h1_market_only_marks_three_unknown(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        h1["unavailable"]=["XTIUSD"]
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=h4,
                     h1_state=h1,mtf_state=mtf,momentum_state=mom)
        self.assertEqual(result["with_observed_state"],24)
        self.assertEqual(result["missing_or_invalid"],3)
        self.assertEqual(result["robots"]["experimental_h1:XTIUSD:channel10"]["status"],"unavailable")
        self.assertEqual(result["robots"]["experimental_h1:USDJPY:channel10"]["status"],"no_new_signal")

    def test_open_position_realized_not_unrealized(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        key="EURUSD:rsi50"
        h1["books"][key]["position"]={"start":NOW-3600,"entry":100,"side":1}
        h1["books"][key]["equity"]=1003.
        h1["books"][key]["entries"]=[{"entry_ts":NOW-3600}]
        h1["books"][key]["closed"]=[{"entry_ts":NOW-7200,"net_usd":3,"cost_usd":.1}]
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=h4,
                     h1_state=h1,mtf_state=mtf,momentum_state=mom)
        bot=result["robots"]["experimental_h1:"+key]
        self.assertEqual(bot["net_realized_usd"],3.)
        self.assertEqual(bot["entries_observed"],1)
        self.assertEqual(bot["closed"],1)
        self.assertEqual(bot["status"],"in_position")

    def test_stale_is_not_new_signal(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        h1["watermarks"]["EURUSD"]=NOW-3600*26
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=h4,
                     h1_state=h1,mtf_state=mtf,momentum_state=mom)
        for rule in STRATEGIES:
            self.assertEqual(result["robots"][f"experimental_h1:EURUSD:{rule}"]["status"],"data_stale")

    def test_h4_audit_failure_never_claims_ten_valid_bots(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=None,
                     h1_state=h1,mtf_state=mtf,momentum_state=mom)
        self.assertEqual(result["missing_or_invalid"],10)
        self.assertEqual(result["with_observed_state"],17)

    def test_m15_entry_count_is_explicit_lower_bound(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        mtf["closed"]=[{"entry_ts":NOW-9000,"exit_ts":NOW-7200,"net_usd":-2.}]
        mtf["equity"]=998.
        result=build(now=NOW,conventional=g,leveraged=lev,h4_result=h4,
                     h1_state=h1,mtf_state=mtf,momentum_state=mom)
        rec=result["robots"]["usdcad_m15:bb20"]
        self.assertEqual(rec["entries_observed"],1)
        self.assertFalse(rec["entries_complete"])
        self.assertEqual(rec["net_realized_usd"],-2)

    def test_daily_report_27_planned_still_fits_telegram(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        day="2026-11-01"
        report=digest(day,g,lev,mtf_error="M15 sem dados",shadow=h1,
                      momentum60=mom,planned_robots=27)
        self.assertIn("27 robôs previstos",report)
        self.assertIn("Momentum60",report)
        self.assertIn("71,000",report)
        self.assertLess(len(report),4000)

    def test_invalid_timestamp_rejected(self):
        g,lev,h4,h1,mtf,mom=fixtures()
        with self.assertRaisesRegex(ValueError,"timestamp"):
            build(now=float("nan"),conventional=g,leveraged=lev,h4_result=h4,
                  h1_state=h1,mtf_state=mtf,momentum_state=mom)


if __name__=="__main__":
    unittest.main()
