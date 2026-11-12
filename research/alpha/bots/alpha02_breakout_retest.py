"""M5: closed breakout then confirmed pullback/retest."""
from research.alpha.indicators import prior_high
TIMEFRAME=5
def signal(b,f,i):
    if i<30:return False
    level=prior_high(b,i-1,20)
    return (b[i-1]["close"]>level and b[i-2]["close"]<=level
            and b[i]["low"]<=level*1.001 and b[i]["close"]>level
            and b[i]["close"]>b[i]["open"])
