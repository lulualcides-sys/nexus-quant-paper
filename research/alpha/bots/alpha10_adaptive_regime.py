"""M5: ex-ante trend-or-range switch; neither branch fitted on final test."""
from research.alpha.indicators import prior_high
TIMEFRAME=5
def signal(b,f,i):
    if i<210:return False
    trend=(f["ema50"][i]>f["ema200"][i] and
           f["ema50"][i]>f["ema50"][i-10] and
           abs(f["ema20"][i]-f["ema50"][i])/b[i]["close"]>.002)
    if trend:
        return b[i]["close"]>prior_high(b,i,20) and b[i]["volume"]>f["vol_avg"][i-1]
    return (abs(f["ema20"][i]-f["ema50"][i])/b[i]["close"]<.003
            and f["rsi"][i-1]<38 and f["rsi"][i]>f["rsi"][i-1]
            and b[i]["close"]>b[i]["open"])
