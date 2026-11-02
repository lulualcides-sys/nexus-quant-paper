"""Point-in-time economic release guard, PAPER ONLY, standard-library-only.

Features:
* Uses ONLY official, manually verified calendar snapshots.
* No access to future schedules before the recorded observation timestamp.
* Local America/New_York conversion handles EST/EDT automatically.
* Blocks NEW entries only; existing stops/exits are never postponed.
* Fail-closed for stale/absent/revised calendars if expressly enabled.
* Existing 27-bot behavior unchanged unless NEXUS_NEWS_GUARD_ENABLED=1.
* No news sentiment, generated headlines, fabricated surprises, or live orders.

This is a risk/calendar blackout hypothesis, NOT a proven profit filter.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from functools import lru_cache
from math import isfinite
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import json
import os

CALENDAR=Path("research/news_calendar_2026_11.json")
TZ=ZoneInfo("America/New_York")
MARKETS=frozenset(("EURUSD","USDJPY","XAUUSD","US500","XTIUSD","USDCAD"))
TRUSTED_DOMAINS=frozenset(("www.bls.gov","www.bea.gov","bea.gov","www.federalreserve.gov"))
BEFORE_MINUTES=60
AFTER_MINUTES=45
_MAX_EVENTS=500

def _parse_stamp(value, name):
    if not isinstance(value,str):
        raise ValueError(name+" must be ISO datetime")
    try:
        ts=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError(name+" malformed") from None
    if ts.tzinfo is None:
        raise ValueError(name+" must have explicit UTC offset")
    return ts.astimezone(timezone.utc)

def _require_int_ts(ts):
    if not isinstance(ts,(int,float)) or not isfinite(ts):
        raise ValueError("Timestamp must be finite")
    return datetime.fromtimestamp(ts,timezone.utc)

def validate(payload):
    """Validate and return sorted immutable blackout intervals.

    Manual source verification is separate from schema validation. URLs are
    provenance references, not fetched at run time.
    """
    if not isinstance(payload,dict) or payload.get("schema")!=1 or payload.get("paper_only") is not True:
        raise ValueError("Unknown or unsafe calendar format")
    if payload.get("timezone")!="America/New_York":
        raise ValueError("Calendar must use ET with automatic DST")
    observed=_parse_stamp(payload.get("observed_at_utc"),"observed_at_utc")
    fresh=_parse_stamp(payload.get("fresh_until_utc"),"fresh_until_utc")
    start=_parse_stamp(payload.get("coverage_start_utc"),"coverage_start_utc")
    end=_parse_stamp(payload.get("coverage_end_utc"),"coverage_end_utc")
    if not (start >= observed and end>start and observed<fresh<=end):
        raise ValueError("Invalid point-in-time coverage/freshness window")
    events=payload.get("events")
    if not isinstance(events,list) or not 1<=len(events)<=_MAX_EVENTS:
        raise ValueError("Invalid events count")
    ids=set()
    intervals=[]
    for raw in events:
        if not isinstance(raw,dict):
            raise ValueError("Event is not a dictionary")
        id=raw.get("id")
        if not isinstance(id,str) or not id or id in ids:
            raise ValueError("Missing/duplicate event ID")
        ids.add(id)
        title=raw.get("title")
        if not isinstance(title,str) or not title.strip():
            raise ValueError("Event title missing")
        if raw.get("impact")!="high":
            raise ValueError("Only verified high-impact event hypotheses accepted")
        scope=raw.get("affected_markets")
        if not isinstance(scope,list) or not scope or set(scope)-MARKETS:
            raise ValueError("Invalid market scope")
        if len(scope)!=len(set(scope)):
            raise ValueError("Duplicate market scope")
        source=raw.get("source")
        if not isinstance(source,str):
            raise ValueError("Official-source HTTPS URL required")
        parsed=urlparse(source)
        if parsed.scheme!="https" or parsed.hostname not in TRUSTED_DOMAINS:
            raise ValueError("Official-source URL required")
        try:
            day=date.fromisoformat(raw["date"])
        except (KeyError,TypeError,ValueError):
            raise ValueError("Invalid official release date") from None
        precision=raw.get("timing_precision")
        if precision=="minute":
            value=raw.get("time_et")
            if (not isinstance(value,str) or len(value)!=5 or value[2]!=":"
                    or not value[:2].isdigit() or not value[3:].isdigit()
                    or int(value[:2])>23 or int(value[3:])>59):
                raise ValueError("Event minute unknown/invalid; use full local day")
            local=datetime(day.year,day.month,day.day,
                           int(value[:2]),int(value[3:]),tzinfo=TZ)
            # Calendared minute, never hindsight price release time.
            since=local-timedelta(minutes=BEFORE_MINUTES)
            until=local+timedelta(minutes=AFTER_MINUTES)
        elif precision=="day":
            if "time_et" in raw:
                raise ValueError("Do not invent a time for date-only event")
            since=datetime(day.year,day.month,day.day,tzinfo=TZ)
            until=since+timedelta(days=1)
        else:
            raise ValueError("Timing precision required")
        # All events should belong to coverage: otherwise typos can secretly
        # extend/shorten risk blackout boundaries.
        if since.astimezone(timezone.utc)>end or until.astimezone(timezone.utc)<start:
            raise ValueError("Event outside coverage")
        intervals.append({
            "id":id,"title":title,"scope":frozenset(scope),
            "start":since.astimezone(timezone.utc),
            "end":until.astimezone(timezone.utc),
            "source":source,
        })
    intervals.sort(key=lambda x:(x["start"],x["id"]))
    return {"observed":observed,"fresh":fresh,"start":start,
            "end":end,"intervals":intervals}


@lru_cache(maxsize=4)
def load(path=str(CALENDAR)):
    """Cache per process. GitHub Actions uses a fresh process each scan."""
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def evaluate(market, decision_ts, *, calendar=None):
    """Status is clear, blocked_high_impact, or unknown. Unknown is NOT clear.

    Decision timestamp is the OPEN of the contemplated new position.
    Any calendar with observed_at later than that decision is hindsight and
    never admissible for research/backtesting.
    """
    when=_require_int_ts(decision_ts)
    if market not in MARKETS:
        raise ValueError("Unrecognized market: no implicit fallbacks")
    if calendar is None:
        try:
            calendar=load()
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            return {"allowed":False,"status":"unknown","reason":"calendar_missing_or_invalid",
                    "event_ids":[]}
    else:
        calendar=validate(calendar) if "schema" in calendar else calendar
    if when<calendar["observed"] or when<calendar["start"]:
        return {"allowed":False,"status":"unknown",
                "reason":"calendar_not_known_at_decision_time","event_ids":[]}
    if when>calendar["fresh"] or when>calendar["end"]:
        return {"allowed":False,"status":"unknown",
                "reason":"calendar_expired_or_outside_coverage","event_ids":[]}
    matching=[e["id"] for e in calendar["intervals"]
              if market in e["scope"] and e["start"]<=when<e["end"]]
    return {"allowed":not matching,
            "status":"blocked_high_impact" if matching else "clear",
            "reason":"scheduled_official_release" if matching else "no_matching_blackout",
            "event_ids":matching}


def entry_permission(market, decision_ts, *, enabled=None, calendar=None):
    """Opt-in gate used strictly at signal-to-new-position boundary.

    OFF by default while PR is awaiting merge/review. When ON, fail-closed
    blocks only new entries on unknown calendar; exits remain live.
    """
    if enabled is None:
        enabled=os.environ.get("NEXUS_NEWS_GUARD_ENABLED","0").strip()=="1"
    if not enabled:
        return True
    return evaluate(market,decision_ts,calendar=calendar)["allowed"]


def upcoming(now_ts, *, horizon_hours=168):
    """Read-only insight for the existing DAILY Telegram report."""
    when=_require_int_ts(now_ts)
    try:
        c=load()
    except (ValueError,OSError,json.JSONDecodeError):
        return {"status":"unknown","next":[]}
    if when<c["observed"] or when>c["fresh"]:
        return {"status":"unknown","next":[]}
    end=when+timedelta(hours=horizon_hours)
    selected=[{"id":e["id"],"event":e["title"],
               "starts_utc":e["start"].isoformat(),"ends_utc":e["end"].isoformat()}
              for e in c["intervals"] if when<=e["start"]<=end]
    return {"status":"known","next":selected}
