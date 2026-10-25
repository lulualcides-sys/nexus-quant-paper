"""Five research strategies based on completed candles; no broker execution."""
from statistics import mean, pstdev
WARMUP=240
CONFIGS={
    "trend_hunter":"Trend Hunter",
    "breakout_pro":"Breakout Pro",
    "reversal_ai":"Reversal RSI",
    "momentum_x":"Momentum X",
    "pullback_master":"Pullback Master",
}

def indicator(values,period,ema=False):
    if ema:
        alpha=2/(period+1)
        out=[];last=None
        for value in values:
            last=value if last is None else alpha*value+(1-alpha)*last
            out.append(last)
        return out
    return [mean(values[max(0,i-period+1):i+1]) for i in range(len(values))]

def rsi(close,period=14):
    ups=[];downs=[]
    for i,v in enumerate(close):
        d=v-close[i-1] if i else 0
        ups.append(max(d,0));downs.append(max(-d,0))
    u=indicator(ups,period,True);d=indicator(downs,period,True)
    return [100 if x<=1e-12 else 100-100/(1+y/x) for y,x in zip(u,d)]

def make_indicators(bars):
    close=[b["close"] for b in bars]
    high=[b["high"] for b in bars]
    low=[b["low"] for b in bars]
    tr=[max(b["high"]-b["low"],abs(b["high"]-(close[i-1] if i else close[i])),abs(b["low"]-(close[i-1] if i else close[i]))) for i,b in enumerate(bars)]
    atr=indicator(tr,14,True)
    r=rsi(close)
    e20=indicator(close,20,True);e50=indicator(close,50,True);e200=indicator(close,200,True)
    ma20=indicator(close,20)
    sd20=[pstdev(close[max(0,i-19):i+1]) for i in range(len(close))]
    return [dict(atr=atr[i],rsi=r[i],e20=e20[i],e50=e50[i],e200=e200[i],
        band_hi=ma20[i]+2*sd20[i],band_lo=ma20[i]-2*sd20[i],
        upper20=max(high[max(0,i-20):i] or [high[i]]),lower20=min(low[max(0,i-20):i] or [low[i]]),
        upper55=max(high[max(0,i-55):i] or [high[i]]),lower55=min(low[max(0,i-55):i] or [low[i]]),
        avg_atr=mean(atr[max(0,i-100):i+1])) for i in range(len(bars))]

def signal(key,bars,inds,i):
    if i<WARMUP: return 0
    p=inds[i];q=inds[i-1];b=bars[i];prev=bars[i-1];c=b["close"]
    if key=="trend_hunter":
        if c>p["upper55"] and c>p["e200"] and p["e50"]>p["e200"]:return 1
        if c<p["lower55"] and c<p["e200"] and p["e50"]<p["e200"]:return -1
    elif key=="breakout_pro":
        if c>p["upper20"] and c>p["e50"] and p["atr"]>=.8*p["avg_atr"]:return 1
        if c<p["lower20"] and c<p["e50"] and p["atr"]>=.8*p["avg_atr"]:return -1
    elif key=="reversal_ai":
        if .97<p["e50"]/p["e200"]<1.03:
            if q["rsi"]<=32 and p["rsi"]>32 and c<p["e50"]:return 1
            if q["rsi"]>=68 and p["rsi"]<68 and c>p["e50"]:return -1
    elif key=="momentum_x":
        span=b["high"]-b["low"]
        if span>1.2*p["atr"] and p["atr"]>.9*p["avg_atr"]:
            if c>b["open"] and c>p["e50"] and c>=b["high"]-span*.2:return 1
            if c<b["open"] and c<p["e50"] and c<=b["low"]+span*.2:return -1
    elif key=="pullback_master":
        if p["e50"]>p["e200"] and prev["close"]<=q["e20"] and c>p["e20"] and 43<=p["rsi"]<=66:return 1
        if p["e50"]<p["e200"] and prev["close"]>=q["e20"] and c<p["e20"] and 34<=p["rsi"]<=57:return -1
    return 0
