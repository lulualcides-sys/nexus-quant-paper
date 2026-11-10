"""Unit tests for real tick bid/ask entry/exit ordering and cost handling.

These fixtures are SYNTHETIC to prove simulator mechanics, not profitability.
The CI integrates the SAME code with historical Dukascopy quotes independently.
"""
from datetime import datetime, timezone
import unittest

from research.xau_quote_execution_backtest import (
    ExecutionAssumptions, simulate_quote_execution,
)

BASE=int(datetime(2026,10,29,12,0,tzinfo=timezone.utc).timestamp()*1000)


def signal(side=1, at=BASE+60000, entry=100., stop=95., target=105.):
    return {"eligible_ms":at,"signal_ms":at-60000,
            "side":side,"entry":entry,"stop":stop,"target":target}


def data(rows):
    return ((BASE + int(seconds*1000), float(bid), float(ask))
            for seconds,bid,ask in rows)


def simulate(rows, signals=None, **kwargs):
    return simulate_quote_execution(data(rows),signals or [signal()],
                                    ExecutionAssumptions(**kwargs))


class TickExecutionTests(unittest.TestCase):
    def test_buy_can_never_fill_on_bid_alone(self):
        # Bid <= limit, but ask remains >limit (actual buy is at ask).
        report=simulate([(61,99.90,100.10),(65,99.80,100.04),(250,104,104.2)])
        self.assertEqual(report["filled"],0)
        self.assertEqual(report["closed"],0)
        self.assertEqual(report["unfilled_expired"],1)

    def test_buy_fills_on_ask_and_exits_on_bid_target(self):
        r=simulate([(59,94,94.1),(61,99.7,100.),(80,104.8,105.4),
                    (90,105.0,105.2)])
        self.assertEqual(r["closed"],1)
        trade=r["ledger"][0]
        self.assertEqual(trade["reason"],"TARGET")
        self.assertEqual(trade["executed_entry_assumed"],100.)
        self.assertEqual(trade["exit_price_assumed"],105.)
        self.assertAlmostEqual(r["net_usd_per_oz"],5.)

    def test_never_enters_on_quote_before_signal_bar_closes(self):
        r=simulate([(10,99,99.5),(30,98,99),(65,101,102),(251,99,100)])
        self.assertEqual(r["closed"],0)
        self.assertEqual(r["filled"],0)

    def test_long_stops_on_bid_not_ask_and_gap_worse_than_stop(self):
        r=simulate([(61,99.8,100.),(90,94.,96.)])
        self.assertEqual(r["ledger"][0]["reason"],"STOP")
        self.assertEqual(r["ledger"][0]["exit_price_assumed"],94.)
        self.assertAlmostEqual(r["net_usd_per_oz"],-6.)

    def test_sell_limit_only_fills_at_bid(self):
        r=simulate([(61,98.8,100.2),(65,99.9,100.3),
                    (66,100.,100.2),(70,94.4,94.9)],
                   [signal(-1,entry=100.,target=95.,stop=105.)])
        self.assertEqual(r["closed"],1)
        self.assertEqual(r["ledger"][0]["reason"],"TARGET")
        self.assertEqual(r["net_usd_per_oz"],5.)

    def test_short_stop_uses_ask_and_gaps_worsen_result(self):
        r=simulate([(61,100.0,100.2),(64,106.0,107.0)],
                   [signal(-1,entry=100.,target=95.,stop=105.)])
        self.assertEqual(r["ledger"][0]["reason"],"STOP")
        self.assertAlmostEqual(r["net_usd_per_oz"],-7.)

    def test_zero_spread_crossed_quote_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"Reordered"):
            simulate_quote_execution([(BASE+61000,100,100.2),
                                      (BASE+60000,99,100)],
                                     [signal()])

    def test_expiry_prevents_retroactive_fill(self):
        r=simulate([(61,101,101.2),(180,100.1,100.3),
                    (240,99,99.1)],ttl_bars=3)
        self.assertEqual(r["filled"],0)
        self.assertEqual(r["unfilled_expired"],1)

    def test_insufficient_history_gives_no_fabricated_positions(self):
        r=simulate_quote_execution(data([(1,100,100.2)]),[])
        self.assertEqual(r["planned_signals"],0)
        self.assertEqual(r["net_usd_per_oz"],0)
        self.assertIsNone(r["expectancy_usd_per_oz"])
        self.assertIsNone(r["profit_factor"])

    def test_costs_are_adverse_and_always_in_usd_per_oz(self):
        r=simulate([(61,99.8,100),(90,105,105.2)],
                   commission_roundtrip_usd_per_oz=0.4,
                   slippage_usd_per_side=0.2)
        self.assertAlmostEqual(r["ledger"][0]["executed_entry_assumed"],100.)
        self.assertAlmostEqual(r["ledger"][0]["exit_price_assumed"],105.)
        self.assertAlmostEqual(r["net_usd_per_oz"],4.6)

    def test_stop_and_market_exits_slip_but_target_limits_do_not(self):
        stopped=simulate([(61,99.8,100.),(90,94.,96.)],
                         slippage_usd_per_side=0.2)
        self.assertEqual(stopped["ledger"][0]["executed_entry_assumed"],100.)
        self.assertEqual(stopped["ledger"][0]["exit_price_assumed"],93.8)
        target=simulate([(61,99.8,100.),(90,106.,106.2)],
                        slippage_usd_per_side=0.2)
        self.assertEqual(target["ledger"][0]["reason"],"TARGET")
        self.assertEqual(target["ledger"][0]["exit_price_assumed"],105.)
        self.assertEqual(target["net_usd_per_oz"],5.)

    def test_stop_on_entry_tick_has_priority_to_prevent_fabricated_win(self):
        r=simulate([(61,90.,99.)])
        self.assertEqual(r["closed"],1)
        self.assertEqual(r["ledger"][0]["reason"],"STOP_SAME_TICK")
        self.assertEqual(r["net_usd_per_oz"],-10.)

    def test_pending_blocks_overlapping_signal_and_gap_recovery(self):
        r=simulate([(61,101,101.2),(121,101,101.2),
                    (125,99.8,100.0),(190,105,105.2)],
                   [signal(),signal(at=BASE+120000,entry=100,stop=95,target=105)])
        self.assertEqual(r["filled"],1)
        self.assertEqual(r["skipped_busy_or_unseen"],1)

    def test_position_forced_closed_on_last_quote(self):
        r=simulate([(61,99.9,100.0),(70,101.0,101.2)])
        self.assertEqual(r["ledger"][0]["reason"],"SESSION_END")
        self.assertEqual(r["net_usd_per_oz"],1.)

    def test_hold_time_and_invalid_geometry(self):
        r=simulate([(61,99.9,100.),(122,101,101.2)],
                   max_hold_bars=1)
        self.assertEqual(r["ledger"][0]["reason"],"TIME")
        with self.assertRaisesRegex(ValueError,"Wrong-way"):
            simulate([(61,99,100)],[signal(stop=110,target=90)])

    def test_late_signal_does_not_fill_or_use_future_tick(self):
        r=simulate([(61,99.8,100.)],
                   [signal(at=BASE+120000)])
        self.assertEqual(r["filled"],0)
        self.assertEqual(r["skipped_busy_or_unseen"],1)


if __name__=="__main__":
    unittest.main()
