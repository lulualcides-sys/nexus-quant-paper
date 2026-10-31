"""Fail-closed validation of indicative candle feeds before paper decisions."""
from math import isfinite

def validate_bars(bars, *, now, interval=3600, min_bars=245,
                  max_age=10800, continuous=False):
    if len(bars) < min_bars:
        raise ValueError("historico insuficiente: %s candles" % len(bars))
    last = None
    for row in bars:
        ts = row["time"]
        if not isinstance(ts, int) or ts % interval:
            raise ValueError("timestamp desalinhado")
        if last is not None:
            if ts <= last:
                raise ValueError("candles duplicados ou fora de ordem")
            if continuous and ts - last != interval:
                raise ValueError("lacuna entre candles")
        last = ts
        o, h, l, c = (row[key] for key in ("open", "high", "low", "close"))
        if not all(isinstance(x, (int, float)) and isfinite(x) and x > 0
                   for x in (o, h, l, c)):
            raise ValueError("preco invalido")
        if l > min(o, c) or h < max(o, c) or h < l:
            raise ValueError("OHLC inconsistente")
    age = now - (last + interval)
    if age < 0:
        raise ValueError("candle ainda aberto")
    if age > max_age:
        raise ValueError("cotacao desatualizada: %ss" % age)
    return {"last_closed": last + interval, "age_seconds": age, "candles": len(bars)}
