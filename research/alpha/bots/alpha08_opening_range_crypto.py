"""M5: UTC 00:00 opening-range proxy. Crypto 24/7: no exchange opening auction."""
TIMEFRAME=5
def signal(b,f,i):
    if i<20:return False
    minute=(b[i]["time"]%86400)//60
    if not 30<=minute<240:return False
    day=b[i]["time"]//86400
    early=[x for x in b[max(0,i-288):i] if x["time"]//86400==day and x["time"]%86400<1800]
    if len(early)!=6:return False
    level=max(x["high"] for x in early)
    return b[i]["close"]>level and b[i-1]["close"]<=level
