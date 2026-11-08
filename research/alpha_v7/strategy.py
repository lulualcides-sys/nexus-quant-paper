"""Single frozen hypothesis: reject weak and unsustained retests before entry.

The original ALPHA02 breakout/retest, V5 H1/H4 regime, all V6 continuous
execution, fixed cost/stop/target/risk and equity carry remain unchanged.

This entry veto uses ONLY two CLOSED M5 bars and their CAUSAL M5 ATR/volume
history. It never uses trade duration or future stop/target outcomes.
"""
from research.alpha.indicators import prior_high
from research.alpha_v5.strategy import ConfirmedRegime

BREAKOUT_MIN_ATR=.20
BREAKOUT_MIN_REL_VOLUME=1.20
RETEST_MIN_CLOSE_ABOVE_LEVEL_ATR=.12
RETEST_MIN_CLOSE_RANGE_FRACTION=.60
RETEST_MAX_CHASE_ATR=1.50
BOT="alpha02_breakout_retest"

class QualityRetest(ConfirmedRegime):
    def __init__(self,name,m1):
        if name!=BOT:raise ValueError("ALPHA V7 only evaluates alpha02")
        super().__init__(name,m1)
        if self.minutes!=5:
            raise AssertionError("ALPHA02 must remain M5")

    def filter(self,i):
        base=super().filter(i)
        if base!="accepted":
            return base
        # The original signal already verifies closed breakout i-1 and
        # bullish retest i. Do not add any new candle beyond i.
        if i<32:
            return "insufficient_breakout_history"
        level=prior_high(self.bars,i-1,20)
        breakout=self.bars[i-1]
        retest=self.bars[i]
        atr=self.f["atr"][i-1]  # completed breakout candle ATR
        baseline_volume=self.f["vol_avg"][i-2]  # 20 bars before breakout
        if atr<=0 or baseline_volume<=0 or level<=0:
            return "bad_volatility_volume"
        if breakout["close"]-level<BREAKOUT_MIN_ATR*atr:
            return "unconvincing_breakout"
        if breakout["volume"]<BREAKOUT_MIN_REL_VOLUME*baseline_volume:
            return "no_volume_confirmation"
        if retest["close"]-level<RETEST_MIN_CLOSE_ABOVE_LEVEL_ATR*atr:
            return "failed_retest_close"
        span=retest["high"]-retest["low"]
        if span<=0 or (retest["close"]-retest["low"])/span<RETEST_MIN_CLOSE_RANGE_FRACTION:
            return "weak_retest_close_location"
        if retest["close"]-level>RETEST_MAX_CHASE_ATR*atr:
            return "late_chase"
        return "accepted"
