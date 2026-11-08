"""Frozen entry refinement: H1 alignment + 4H trend confirmation.

No changes to ALPHA original signals, exit engine, fees, slippage, stop or
target. Only COMPLETED H1/H4 bars can enter decisions. Does not tune on 2025
SOL historical P&L (those files are fetched only after code is committed).
"""
from research.alpha.indicators import build
from research.alpha_v4.data import aggregate
from research.alpha_v4.strategy import MultiTimeframe

H4_WARMUP=60
H4_SLOPE_LAG=12

class ConfirmedRegime(MultiTimeframe):
    def __init__(self,name,m1):
        super().__init__(name,m1)
        self.h4=aggregate(m1,240)
        self.h4_features=build(self.h4)

    def last_closed_h4(self,i):
        # Exactly 240 M1 (or 48 M5) candles must have closed before the
        # H4 candle is available to the signal at i close. No partial H4.
        return (i+1)//(240//self.minutes)-1

    def filter(self,i):
        original=super().filter(i)
        if original!="accepted":
            return original
        h=self.last_closed_h1(i)
        h1=self.hf
        # Fix contradictory entry: the old filter could buy when price was
        # already below EMA50, then trigger its own bearish exit immediately.
        if not (h1["ema20"][h]>h1["ema50"][h] and
                self.h1[h]["close"]>h1["ema50"][h]):
            return "h1_exit_contradicts_entry"
        j=self.last_closed_h4(i)
        if j<H4_WARMUP:
            return "h4_not_completed_or_warmup"
        f=self.h4_features
        if not (f["ema20"][j]>f["ema50"][j] and
                f["ema50"][j]>f["ema50"][j-H4_SLOPE_LAG] and
                self.h4[j]["close"]>f["ema20"][j]):
            return "h4_downtrend_or_range"
        return "accepted"
