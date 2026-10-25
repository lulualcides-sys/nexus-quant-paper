"""Delayed, cost-aware GREEN trailing stop for virtual leveraged gold orders.

OHLC H4 does not tell us whether the high happened before the low.
Safety rule: evaluate stop and target using levels that already existed at the
start of the closed candle; update stops only AFTER its entire candle closes,
so a tightened stop becomes executable no earlier than the next H4 candle.
"""
from __future__ import annotations

MODES={
  "fixed":{"trigger_r":None,"trail_trigger_r":None,"trail_distance_r":None,"target":True},
  "green_fixed":{"trigger_r":1.00,"trail_trigger_r":1.50,"trail_distance_r":1.00,"target":True},
  "green_runner":{"trigger_r":1.00,"trail_trigger_r":1.50,"trail_distance_r":1.00,"target":False},
  "green_wide":{"trigger_r":1.25,"trail_trigger_r":2.00,"trail_distance_r":1.35,"target":False},
}
MIN_LOCK_R=0.10

def check_mode(mode):
    if mode not in MODES:raise ValueError("Unknown stop management mode: "+str(mode))
    return MODES[mode]

def update_after_close(position,completed_bar,now,roundtrip_bps,annual_borrow_apr):
    """Only makes a stop more protective AFTER this H4 candle has finished.

    Losses in the triggering candle are checked against the PRIOR stop first
    by the caller. No current-bar high/low can create a same-bar profitable exit.
    """
    mode=position.get("mode","fixed")
    cfg=check_mode(mode)
    if mode=="fixed":
        return False
    entry=position["entry"]
    side=position["side"]
    r=position.get("entry_risk",abs(entry-position["stop"]))
    qty=position["qty"]
    if r<=0 or qty<=0:
        return False
    best=(completed_bar["high"]-entry if side>0
          else entry-completed_bar["low"])
    peak=max(position.get("peak_favorable",0),best)
    position["peak_favorable"]=peak
    if peak+1e-8<cfg["trigger_r"]*r:
        return False

    # Estimated net green floor. In the next bar the exact future funding
    # will be higher; this is an estimate, never a guaranteed profit.
    hours=max(0,(now-position["start"])/3600)
    fees_per_unit=(roundtrip_bps/10000)*entry
    carry_per_unit=(position["borrowed"]*annual_borrow_apr*hours/8760)/qty
    min_lock=max(MIN_LOCK_R*r,fees_per_unit+carry_per_unit+0.02*r)

    locked_distance=min_lock
    if peak>=cfg["trail_trigger_r"]*r:
        locked_distance=max(locked_distance,
            peak-cfg["trail_distance_r"]*r)
    old=position["stop"]
    proposed=entry+side*locked_distance
    if side>0 and proposed>old:
        position["stop"]=proposed
        position["green_protected"]=True
        return True
    if side<0 and proposed<old:
        position["stop"]=proposed
        position["green_protected"]=True
        return True
    return False
