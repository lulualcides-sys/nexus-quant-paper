"""M1: OHLCV rejection proxy; cannot detect actual bid/ask absorption."""
from research.alpha.indicators import prior_low, wick_low, bullish
TIMEFRAME=1
def signal(b,f,i):
    if i<30:return False
    x=b[i]
    return (x["low"]<prior_low(b,i,20) and bullish(x)
            and wick_low(x)>.65 and x["close"]>x["low"]+.75*(x["high"]-x["low"])
            and x["volume"]>1.5*f["vol_avg"][i-1])
