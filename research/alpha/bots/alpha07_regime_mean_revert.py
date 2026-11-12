"""M5: buy deviations only under low EMA separation (weak trend proxy)."""
TIMEFRAME=5
def signal(b,f,i):
    if i<70:return False
    regime=abs(f["ema20"][i]-f["ema50"][i])/b[i]["close"]
    return (regime<.004 and f["rsi"][i]<35
            and b[i]["low"]<f["ema20"][i]-1.3*f["atr"][i]
            and b[i]["close"]>b[i]["open"])
