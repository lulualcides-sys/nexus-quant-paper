"""Ex-ante ALPHA V2 filters. No use of retrospective P&L to choose thresholds.

Require plausible gross target travel versus all-in two-sided friction, verified
OHLCV activity, and directionally consistent causal market regime. The original
10 entry hypotheses are unchanged; filter is a pure wrapper.
"""
from importlib import import_module
from research.alpha.engine import TAKER_FEE_BPS, HALF_SPREAD_BPS
from research.alpha.run import BOTS

PRIMARY_SLIP_BPS=5.0
COST_MULTIPLIER=2.0  # gross target >= twice assumed full round trip friction
ROUNDTRIP_BPS=2*(TAKER_FEE_BPS+HALF_SPREAD_BPS+PRIMARY_SLIP_BPS)
BULLISH={"alpha02_breakout_retest","alpha04_ema_atr_pullback",
         "alpha06_volatility_momentum","alpha08_opening_range_crypto",
         "alpha09_consolidation_continuation","alpha10_adaptive_regime"}
RECOVERY={"alpha01_volume_exhaustion","alpha03_vwap_deviation",
          "alpha05_liquidity_rejection_proxy","alpha07_regime_mean_revert"}
assert set(BOTS)==BULLISH|RECOVERY

class Filtered:
    def __init__(self, name):
        if name not in BOTS:
            raise ValueError("unknown ALPHA candidate")
        self.name=name
        self.base=import_module("research.alpha.bots."+name)
        self.TIMEFRAME=self.base.TIMEFRAME

    def diagnose(self,h,f,i):
        if not self.base.signal(h,f,i):
            return "no_raw_signal"
        # Signal confirmed at i close only. All indicators at i are causal.
        close=h[i]["close"]
        atr=f["atr"][i]
        if atr<=0 or close<=0:
            return "invalid_risk"
        stop_dist=max(1.5*atr,close*0.001)
        potential_target_bps=10000*(1.8*stop_dist)/close
        if potential_target_bps<ROUNDTRIP_BPS*COST_MULTIPLIER:
            return "cost_to_target"
        if h[i]["volume"]<0.6*f["vol_avg"][i-1] or f["vol_avg"][i-1]<=0:
            return "low_volume"
        # Veto violent outliers: normal OHLCV does not establish depth/slippage.
        if atr/close>.018:
            return "volatility_outlier"
        if i<240:
            return "regime_warmup"
        ema50=f["ema50"][i]
        ema200=f["ema200"][i]
        if self.name in BULLISH:
            if not (ema50>ema200 and ema200>f["ema200"][i-24]):
                return "unfavorable_trend"
            if f["rsi"][i]>78:
                return "overextended"
        else:
            if not (ema50>=ema200*.997 and ema200>f["ema200"][i-24]*.999):
                return "unfavorable_regime"
            if f["rsi"][i]<14:
                return "extreme_down_move"
        return "accepted"

    def signal(self,h,f,i):
        return self.diagnose(h,f,i)=="accepted"
