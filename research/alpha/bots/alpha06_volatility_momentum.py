"""M5: volume-confirmed momentum during above-average true-range expansion."""
from research.alpha.indicators import prior_high
TIMEFRAME=5
def signal(b,f,i):
    if i<40:return False
    tr=max(b[i]["high"]-b[i]["low"],abs(b[i]["high"]-b[i-1]["close"]),
           abs(b[i]["low"]-b[i-1]["close"]))
    return (b[i]["close"]>prior_high(b,i,15) and tr>1.5*f["atr"][i-1]
            and b[i]["volume"]>f["vol_avg"][i-1]
            and f["ema20"][i]>f["ema50"][i])
