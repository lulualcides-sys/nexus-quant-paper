"""H1 trend confirmation calculated from LAST COMPLETED H1 candle.

The ten original ALPHA signals are unchanged. No interpolation or partial H1.
"""
from importlib import import_module
from research.alpha.run import BOTS
from research.alpha.indicators import History
from research.alpha_v4.data import aggregate
from research.alpha.indicators import build

H1_WARMUP=210
RSI_MIN=48.
RSI_MAX=76.
MIN_VOLUME_FACTOR=.7
TARGET_H1_ATR=4.0
STOP_H1_ATR=1.5
MAX_HOLD_HOURS=72
COOLDOWN_HOURS=24
MIN_TARGET_COST_MULTIPLIER=3.0
MAIN_COST_ROUNDTRIP_BPS=32.0

class MultiTimeframe:
    def __init__(self,name,m1):
        if name not in BOTS:raise ValueError("unapproved ALPHA entry")
        self.name=name
        self.original=import_module("research.alpha.bots."+name)
        self.minutes=self.original.TIMEFRAME
        self.m1=m1
        self.bars=m1 if self.minutes==1 else aggregate(m1,5)
        self.f=build(self.bars)
        self.h1=aggregate(m1,60)
        self.hf=build(self.h1)

    def last_closed_h1(self,i):
        # i is a CLOSED signal-bar index. An H1 bar contributes only if its
        # 60th child M1 candle has CLOSED before the signal decision.
        divisor=60//self.minutes
        return (i+1)//divisor-1

    def filter(self,i):
        if i<240 or i>=len(self.bars):
            return "warmup_or_outside"
        h=self.last_closed_h1(i)
        if h<H1_WARMUP:
            return "h1_incomplete_or_warmup"
        b=self.bars[i]
        if not self.original.signal(History(self.bars,i+1),self.f,i):
            return "original_entry_absent"
        hi=self.h1[h]
        last=self.hf
        if not (last["ema50"][h]>last["ema200"][h] and
                last["ema50"][h]>last["ema50"][h-12] and
                hi["close"]>last["ema20"][h]):
            return "h1_no_uptrend"
        if not RSI_MIN<=last["rsi"][h]<=RSI_MAX:
            return "h1_rsi_outside"
        avg=self.f["vol_avg"][i-1]
        if avg<=0 or b["volume"]<MIN_VOLUME_FACTOR*avg:
            return "insufficient_volume"
        target_bps=10000*TARGET_H1_ATR*last["atr"][h]/b["close"]
        if target_bps<MAIN_COST_ROUNDTRIP_BPS*MIN_TARGET_COST_MULTIPLIER:
            return "target_insufficient_after_cost"
        return "accepted"

    def signal(self,i):
        return self.filter(i)=="accepted"

    def h1_exiting(self,i):
        h=self.last_closed_h1(i)
        return h>=H1_WARMUP and self.h1[h]["close"]<self.hf["ema50"][h]
