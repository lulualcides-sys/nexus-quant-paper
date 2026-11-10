"""Offline tests: independent WIN flow-exhaustion model without orders.

Synthetic trades validate mechanics, NOT original Tracker equivalence or
profitability. A real broker tick feed is still necessary for a live chart.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import unittest

from research.win_flow_exhaustion_reference import (
    BUY_FLAG,SELL_FLAG,VOLUME_FLAG,LAST_FLAG,ResearchPolicy,price_candidate,
    classified_flow,classify_closed_bar,fibonacci_levels,economic_note
)

T0=datetime(2026,11,9,12,10,tzinfo=timezone.utc)

def bars_buy():
    x=[{"time":int((T0+timedelta(minutes=i)).timestamp()),
        "open":100050.0,"high":100100.0,"low":100000.0,
        "close":100050.0,"real_volume":100.0} for i in range(20)]
    x.append({"time":int((T0+timedelta(minutes=20)).timestamp()),
              "open":100020.0,"high":100090.0,"low":99985.0,
              "close":100050.0,"real_volume":150.0})
    return x

def bars_sell():
    x=bars_buy()
    x[-1].update({"open":100080.,"high":100115.,"low":100010.,
                  "close":100050.,"real_volume":150.})
    return x

def ticks(start,*,selling=True,unknown_volume=0):
    t=[]
    for i in range(25):
        ms=start*1000+2000+i*2300
        if ms>start*1000+60000:
            raise AssertionError("invalid synthetic tick time")
        if selling:
            direction=SELL_FLAG if i<20 else BUY_FLAG
        else:
            direction=BUY_FLAG if i<20 else SELL_FLAG
        t.append({"time_msc":ms,"flags":direction|VOLUME_FLAG,
                  "volume_real":5.0,"last":100005.0})
    # First=+2s, last=+57.2s => both sides of bar covered.
    if unknown_volume:
        t.append({"time_msc":start*1000+32000,"flags":VOLUME_FLAG,
                  "volume_real":unknown_volume,"last":100005.0})
    return t

class IndependentFlowTests(unittest.TestCase):
    def test_buy_requires_actual_selling_aggression_and_closed_reclaim(self):
        b=bars_buy()
        self.assertEqual(price_candidate(b,20),1)
        result=classify_closed_bar(b,20,ticks(b[20]["time"]))
        self.assertEqual(result["side"],1)
        self.assertEqual(result["flow"]["sell_volume"],100.0)
        self.assertEqual(result["flow"]["buy_volume"],25.0)
        self.assertAlmostEqual(result["flow"]["contra_share"],.8)
        self.assertEqual(result["status"],
                         "INDEPENDENT_RESEARCH_SIGNAL_NOT_BROKER_ORDER")

    def test_sell_is_symmetrical_against_buying_aggression(self):
        b=bars_sell()
        self.assertEqual(price_candidate(b,20),-1)
        result=classify_closed_bar(b,20,ticks(b[20]["time"],selling=False))
        self.assertEqual(result["side"],-1)
        self.assertEqual(result["flow"]["buy_volume"],100.0)

    def test_wrong_direction_delta_is_rejected(self):
        b=bars_buy()
        self.assertIsNone(classify_closed_bar(b,20,ticks(b[20]["time"],selling=False)))

    def test_missing_trade_side_flags_never_creates_imaginary_aggression(self):
        b=bars_buy()
        trade=[{"time_msc":q["time_msc"],"flags":VOLUME_FLAG,
                "volume_real":q["volume_real"],"last":q["last"]} for q in ticks(b[20]["time"])]
        self.assertIsNone(classified_flow(trade,b[20]["time"]))
        self.assertIsNone(classify_closed_bar(b,20,trade))

    def test_quote_only_last_price_and_side_flags_never_become_trade(self):
        b=bars_buy()
        tape=ticks(b[20]["time"])
        for q in tape:
            q["flags"]=4 | (q["flags"] & (BUY_FLAG|SELL_FLAG))  # ASK=4, no trade event
        self.assertIsNone(classify_closed_bar(b,20,tape))

    def test_real_candle_volume_mismatch_fails_closed(self):
        b=bars_buy()
        tape=ticks(b[20]["time"])
        b[-1]["real_volume"]=700  # 125 traded vs 700 in M1, >20% divergence
        self.assertIsNone(classify_closed_bar(b,20,tape))
        self.assertIsNone(classified_flow(tape,b[20]["time"],bar_real_volume=700))

    def test_both_trade_sides_count_as_unknown_not_valid_flow(self):
        b=bars_buy()
        tape=ticks(b[20]["time"])
        for q in tape[:15]:
            q["flags"] |= BUY_FLAG|SELL_FLAG
        self.assertIsNone(classify_closed_bar(b,20,tape))

    def test_tick_volume_only_is_not_exchange_contract_size(self):
        b=bars_buy()
        trade=[{**q,"volume_real":0.0,"tick_volume":50000} for q in ticks(b[20]["time"])]
        self.assertIsNone(classified_flow(trade,b[20]["time"]))

    def test_unclassified_volume_low_coverage_rejected(self):
        b=bars_buy()
        trade=ticks(b[20]["time"],unknown_volume=400)
        self.assertIsNone(classified_flow(trade,b[20]["time"]))
        x=classified_flow(trade,b[20]["time"],ResearchPolicy(min_classified_share=.2))
        self.assertIsNotNone(x)
        self.assertLess(x["coverage"],.6)

    def test_same_bar_no_coverage_at_end_is_rejected(self):
        b=bars_buy()
        trade=ticks(b[20]["time"])
        for x in trade:x["time_msc"]-=17000 # end has >15 seconds with no classified trades
        self.assertIsNone(classified_flow(trade,b[20]["time"]))

    def test_incomplete_bar_or_next_bars_do_not_repaint_previous_signal(self):
        b=bars_buy()
        t=ticks(b[20]["time"])
        first=classify_closed_bar(b,20,t)
        b+=[{"time":b[-1]["time"]+60,"open":100050.,
             "high":101500.,"low":98500.,"close":99500.,
             "real_volume":100000.}]
        self.assertEqual(first,classify_closed_bar(b,20,t))
        self.assertIsNone(price_candidate(b,0))

    def test_cross_session_training_not_allowed(self):
        b=bars_buy()
        b[0]["time"]-=86400
        self.assertIsNone(price_candidate(b,20))

    def test_missing_actual_bar_volume_fail_closed(self):
        b=bars_buy()
        b[-1]["real_volume"]=0
        self.assertIsNone(price_candidate(b,20))

    def test_public_fibo_geometry_and_net_payoff(self):
        result=classify_closed_bar(bars_buy(),20,ticks(bars_buy()[-1]["time"]))
        levels=result["levels"]
        self.assertEqual(levels,{"0":99985.0,"50":100040.0,
                                 "100":100090.0,"200":100195.0,"-100":99880.0})
        # Levels rounded to WIN 5-point grid => sometimes 5pt asymmetry.
        economy=economic_note(result,cost_roundtrip_brl=6.)
        self.assertEqual(economy["planned_net_loss_brl"],38.0)
        self.assertEqual(economy["net_reward_brl"],25.0)
        self.assertTrue(economy["exceeds_one_win_risk_budget"])
        self.assertFalse(economy["approved_for_live"])

    def test_no_order_routing_software_or_hardcoded_proprietary_claim(self):
        m=Path("indicators/mt5/NQ_Win_Exaustao_Fluxo_Research.mq5").read_text(encoding="utf-8")
        self.assertIn("CopyTicksRange(_Symbol,trades,COPY_TICKS_TRADE",m)
        self.assertIn("TICK_FLAG_BUY",m)
        self.assertIn("TICK_FLAG_SELL",m)
        self.assertIn("volume_real",m)
        self.assertIn("BufferBuy[0]=EMPTY_VALUE",m)
        self.assertIn("gBarOpen!=time[0]",m)
        self.assertIn("NAO E O TRACKER ORIGINAL",m)
        for banned in ("OrderSend(", "CTrade ", "trade.Buy(", "trade.Sell(",
                       "WebRequest(", "FileOpen("):
            self.assertNotIn(banned,m)

if __name__=="__main__":unittest.main()
