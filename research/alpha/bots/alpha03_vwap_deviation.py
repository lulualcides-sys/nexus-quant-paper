"""M1: statistical dislocation below current UTC-day VWAP."""
TIMEFRAME=1
def signal(b,f,i):
    if i<40:return False
    return (b[i]["time"]//86400==b[i-30]["time"]//86400
            and b[i-1]["close"]<f["vwap"][i-1]-1.5*f["vwap_std"][i-1]
            and b[i]["close"]>b[i-1]["close"] and b[i]["close"]>b[i]["open"]
            and b[i]["close"]<f["vwap"][i])
