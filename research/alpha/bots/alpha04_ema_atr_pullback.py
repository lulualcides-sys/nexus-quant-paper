"""M5: EMA-aligned pullback with ATR-governed shared position sizing."""
TIMEFRAME=5
def signal(b,f,i):
    if i<210:return False
    return (f["ema20"][i]>f["ema50"][i]>f["ema200"][i]
            and b[i-1]["low"]<=f["ema20"][i-1]
            and b[i]["close"]>f["ema20"][i] and b[i]["close"]>b[i]["open"])
