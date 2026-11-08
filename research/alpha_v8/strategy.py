"""V8 tests only structure after observing V7's non-transferable volume veto.

Market-independent, CLOSED M5 gate. Thresholds were already defined in V7
before the four earlier markets' outcome analysis. Exits, risk and H1/H4
entry regimes are unmodified from V5 continuous benchmark.
"""
from research.alpha.indicators import prior_high
from research.alpha_v5.strategy import ConfirmedRegime
from research.alpha_v7.strategy import (BREAKOUT_MIN_ATR,
                             RETEST_MIN_CLOSE_RANGE_FRACTION,BOT)

class StructureRetest(ConfirmedRegime):
    def __init__(self,name,m1):
        if name!=BOT:raise ValueError("only ALPHA02 is permitted in V8")
        super().__init__(name,m1)
        if self.minutes!=5:raise AssertionError("ALPHA02 M5 only")

    def filter(self,i):
        original=super().filter(i)
        if original!="accepted":return original
        if i<32:return "not_enough_m5_history"
        level=prior_high(self.bars,i-1,20)
        breakout=self.bars[i-1]
        retest=self.bars[i]
        atr=self.f["atr"][i-1]
        if atr<=0:return "bad_m5_atr"
        if breakout["close"]-level<BREAKOUT_MIN_ATR*atr:
            return "weak_breakout"
        span=retest["high"]-retest["low"]
        if span<=0 or (retest["close"]-retest["low"])/span<RETEST_MIN_CLOSE_RANGE_FRACTION:
            return "weak_retest_close"
        return "accepted"
