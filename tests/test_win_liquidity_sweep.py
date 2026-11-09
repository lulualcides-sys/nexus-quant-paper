"""WIN Liquidity Sweep tests: synthetic fixtures prove code, NOT profitability."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from research.win_liquidity_sweep import Parameters, signal, simulate
from research.win_price_data import local_day

SP = ZoneInfo("America/Sao_Paulo")


def fixture(n=180):
    start = datetime(2026, 11, 9, 9, 10, tzinfo=SP)
    return [{"time": int((start+timedelta(minutes=j)).timestamp()),
             "open":100000.0,"high":100015.0,"low":99985.0,
             "close":100000.0,"volume":100.0} for j in range(n)]


class LiquiditySweepTests(unittest.TestCase):
    def test_confirmed_downside_sweep_and_next_bar_signal(self):
        data=fixture()
        data[100].update(open=99990.0,low=99970.0,high=100015.0,
                         close=100005.0,volume=160.0)
        opts=Parameters(require_vwap_context=False)
        got=signal(data,100,opts)
        self.assertEqual(got["side"],1)
        self.assertEqual(got["stop"],99965.0)
        self.assertEqual(got["signal_time"],data[100]["time"])
        self.assertEqual(got["swept_level"],99985.0)
        self.assertEqual(got,signal(data[:101],100,opts))
        self.assertIsNone(signal(data,99,opts))

    def test_confirmed_upside_sweep(self):
        data=fixture()
        data[100].update(open=100010.0,high=100030.0,low=99985.0,
                         close=99995.0,volume=160.0)
        got=signal(data,100,Parameters(require_vwap_context=False))
        self.assertEqual(got["side"],-1)
        self.assertEqual(got["stop"],100035.0)
        self.assertEqual(got["swept_level"],100015.0)

    def test_low_volume_or_wick_rejection_does_not_pass(self):
        data=fixture()
        data[100].update(open=99990.0,low=99970.0,high=100015.0,
                         close=100005.0,volume=50.0)
        self.assertIsNone(signal(data,100,Parameters(require_vwap_context=False)))
        data[100]["volume"]=160.0
        data[100]["close"]=99980.0
        self.assertIsNone(signal(data,100,Parameters(require_vwap_context=False)))

    def test_future_data_does_not_change_past_signal(self):
        data=fixture()
        data[100].update(open=99990.0,low=99970.0,high=100015.0,
                         close=100005.0,volume=160.0)
        opts=Parameters(require_vwap_context=False)
        first=signal(data,100,opts)
        data[120].update(open=110000.0,high=110000.0,
                         low=110000.0,close=110000.0)
        self.assertEqual(first,signal(data,100,opts))

    def test_single_position_reopens_after_multiple_losses(self):
        bars=fixture()
        for j in (102,112,122,132):
            bars[j].update(low=99940.0,high=100015.0)
        trade_signals={100,110,120,130}
        def fake(_bars,i,_cfg):
            if i not in trade_signals:
                return None
            return {"setup":"liquidity_sweep_reclaim","side":1,
                    "stop":99950.0,"signal_time":bars[i]["time"],
                    "swept_level":99985.0}
        with patch("research.win_liquidity_sweep.signal",side_effect=fake):
            report=simulate(bars)
        self.assertEqual(report["trades"],4)
        self.assertTrue(report["no_daily_loss_limit"])
        self.assertTrue(report["one_contract_only"])
        self.assertEqual(report["net_brl"],-64.0)
        self.assertEqual({q["why"] for q in report["ledger"]},{"STOP_RED"})
        self.assertEqual([q["entry_time"] for q in report["ledger"]],
                         [bars[i+1]["time"] for i in sorted(trade_signals)])
        self.assertLess(report["equity_closed_brl"],1960)

    def test_ambiguity_stop_precedes_target(self):
        bars=fixture()
        bars[101].update(low=99940.0,high=100150.0)
        def fake(_bars,i,_cfg):
            return ({"setup":"liquidity_sweep_reclaim","side":1,
                     "stop":99950.0,"signal_time":bars[100]["time"],
                     "swept_level":99985.0} if i==100 else None)
        with patch("research.win_liquidity_sweep.signal",side_effect=fake):
            report=simulate(bars)
        self.assertEqual(report["trades"],1)
        self.assertEqual(report["ledger"][0]["why"],"STOP_RED_ENTRY")
        self.assertTrue(report["ledger"][0]["ambiguous_stop_before_target"])
        self.assertEqual(report["net_brl"],-16.0)

    def test_win_exit_has_cost_and_next_bar(self):
        bars=fixture()
        bars[102].update(high=100095.0)
        def fake(_bars,i,_cfg):
            return ({"setup":"liquidity_sweep_reclaim","side":1,
                     "stop":99950.0,"signal_time":bars[100]["time"],
                     "swept_level":99985.0} if i==100 else None)
        with patch("research.win_liquidity_sweep.signal",side_effect=fake):
            report=simulate(bars)
        self.assertEqual(report["ledger"][0]["entry_time"],bars[101]["time"])
        self.assertEqual(report["ledger"][0]["why"],"STOP_WIN")
        self.assertEqual(report["ledger"][0]["net_brl"],12.0)
        self.assertEqual(report["ledger"][0]["planned_net_reward_brl"],12.0)
        self.assertEqual(report["ledger"][0]["planned_net_loss_brl"],16.0)
        self.assertEqual(report["ledger"][0]["planned_net_rr"],0.75)

    def test_missing_candle_while_position_open_invalidates_backtest_quality(self):
        bars = fixture()
        # A real 1-minute data hole occurs AFTER entry, not during signal scan.
        for b in bars[102:]:
            b["time"] += 60
        def fake(_bars, i, _cfg):
            return ({"setup":"liquidity_sweep_reclaim","side":1,
                     "stop":99950.0,"signal_time":bars[100]["time"],
                     "swept_level":99985.0} if i==100 else None)
        with patch("research.win_liquidity_sweep.signal", side_effect=fake):
            result=simulate(bars)
        self.assertEqual(result["unverifiable_position_gap_exits"], 1)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["why"], "UNVERIFIABLE_DATA_GAP")
        self.assertEqual(result["status"], "BACKTEST_HAS_UNVERIFIABLE_POSITION_GAPS")
        self.assertEqual(result["net_brl"], -16.0)

    def test_open_position_marked_but_not_fabricated_as_closed_trade(self):
        bars=fixture()
        def fake(_bars, i, _cfg):
            return ({"setup":"liquidity_sweep_reclaim","side":1,
                     "stop":99950.0,"signal_time":bars[178]["time"],
                     "swept_level":99985.0} if i==178 else None)
        with patch("research.win_liquidity_sweep.signal",side_effect=fake):
            report=simulate(bars)
        self.assertEqual(report["trades"],0)
        self.assertTrue(report["open_at_end"])
        self.assertEqual(report["net_brl"],0.0)
        self.assertEqual(report["open_position_mark_to_market_net_brl"],-6.0)
        self.assertEqual(report["equity_including_open_mark_brl"],1994.0)

    def test_no_fabricated_trades_and_bad_arguments(self):
        report=simulate(fixture())
        self.assertEqual(report["trades"],0)
        self.assertIsNone(report["winrate_pct"])
        self.assertEqual(report["net_brl"],0)
        with self.assertRaises(ValueError):
            simulate(fixture(),Parameters(per_trade_risk=-0.01))
        with self.assertRaises(ValueError):
            simulate(fixture(50))

    def test_expiry_and_session_boundaries_do_not_contaminate_lookback(self):
        bars=fixture()
        bars[100].update(open=99990.0,low=99970.0,high=100015.0,
                         close=100005.0,volume=160.0)
        bars[99]["time"]-=300
        self.assertIsNone(signal(bars,100,Parameters(require_vwap_context=False)))


if __name__ == "__main__":
    unittest.main()
