"""M1: range contraction followed by close beyond prior 12-bar ceiling."""
from research.alpha.indicators import prior_high
TIMEFRAME=1
def signal(b,f,i):
    if i<35:return False
    q=b[i-12:i]
    width=max(x["high"] for x in q)-min(x["low"] for x in q)
    return (width<2.3*f["atr"][i-1] and b[i]["close"]>prior_high(b,i,12)
            and b[i]["volume"]>1.2*f["vol_avg"][i-1]
            and f["ema20"][i]>f["ema50"][i])
