"""Causal, completed-bar indicators (standard library only)."""
from collections import deque
from math import sqrt

class History:
    """A constant-time, read-only prefix of candles. Future bars are inaccessible."""
    def __init__(self, bars, end):
        self.bars, self.end = bars, end
    def __len__(self):
        return self.end
    def __getitem__(self, key):
        if isinstance(key, slice):
            a,b,s = key.indices(self.end)
            return self.bars[a:b:s]
        j = key if key >= 0 else self.end + key
        if j < 0 or j >= self.end:
            raise IndexError("future bar inaccessible")
        return self.bars[j]

def build(bars):
    """All features at index i depend solely on bars[0:i+1]."""
    output = {k: [] for k in ("ema20","ema50","ema200","atr","rsi","vwap","vwap_std","vol_avg")}
    ema20 = ema50 = ema200 = None
    atr = avg_up = avg_down = None
    vol_q, price_q = deque(), deque()
    day = None
    sum_pv = sum_v = 0.
    prev_close = None
    for i, bar in enumerate(bars):
        c,h,l,v = (bar[k] for k in ("close","high","low","volume"))
        ema20 = c if ema20 is None else ema20 + 2/21*(c-ema20)
        ema50 = c if ema50 is None else ema50 + 2/51*(c-ema50)
        ema200 = c if ema200 is None else ema200 + 2/201*(c-ema200)
        tr = h-l if prev_close is None else max(h-l,abs(h-prev_close),abs(l-prev_close))
        atr = tr if atr is None else (13*atr+tr)/14
        delta = 0 if prev_close is None else c-prev_close
        avg_up = max(delta,0) if avg_up is None else (13*avg_up+max(delta,0))/14
        avg_down = max(-delta,0) if avg_down is None else (13*avg_down+max(-delta,0))/14
        if avg_down < 1e-12:
            rsi = 100.
        else:
            rsi = 100-100/(1+avg_up/avg_down)
        utc_day = bar["time"]//86400
        if day != utc_day:
            day = utc_day
            sum_pv=sum_v=0.
        typical = (h+l+c)/3
        sum_pv += typical*v
        sum_v += v
        vol_q.append(v)
        if len(vol_q)>20: vol_q.popleft()
        price_q.append(c)
        if len(price_q)>30: price_q.popleft()
        average = sum(price_q)/len(price_q)
        sd = sqrt(sum((x-average)**2 for x in price_q)/len(price_q))
        vals = (ema20,ema50,ema200,atr,rsi,sum_pv/sum_v if sum_v else c,sd,sum(vol_q)/len(vol_q))
        for key,value in zip(output,vals):
            output[key].append(value)
        prev_close=c
    return output

def prior_high(bars,i,n):
    return max(b["high"] for b in bars[max(0,i-n):i])

def prior_low(bars,i,n):
    return min(b["low"] for b in bars[max(0,i-n):i])

def bullish(b):
    return b["close"] > b["open"]

def wick_low(b):
    rng=b["high"]-b["low"]
    return (min(b["open"],b["close"])-b["low"])/rng if rng else 0.
