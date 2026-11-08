"""M1: exhaustion with observed candle volume; no order-flow inference."""
from research.alpha.indicators import prior_low, bullish, wick_low
TIMEFRAME=1
def signal(b,f,i):
    if i<40:return False
    x=b[i]
    return (bullish(x) and x["low"]<prior_low(b,i,30)
            and wick_low(x)>.50 and x["volume"]>2.0*f["vol_avg"][i-1])
