"""Original Nexus Quant 27 paper strategies + ATLAS, each on XAUUSD M1/M5/M15.

NO new entry strategy. The Gold, Leveraged, H1 and Momentum engines are
called from the original production modules. BB20 uses its unchanged H1 trend
and SMA20 signal helpers but converts USD/CAD currency sizing to gold ounces.
ATLAS uses the original signal/engine on *quote-update* volume (not traded volume).

Input: actual public Dukascopy XAUUSD quotes (bid/ask), no broker credentials.
For research execution, OHLC is the quote midpoint and original project XAU
cost allowance (7 bps, 14 bps for leveraged) is charged. This is *not* actual
tick-level broker execution. Doubled-cost research stress is available.

Canonical 27: 5 conventional, 5 leveraged, 15 experimental H1 books (3 rules
originally repeated on 5 underlying markets), BB20 and Momentum60. If all
15 H1 instances are moved to the SAME gold feed, their 3 rules are identical
within the respective 5 book aliases. Never market them as 15 independent alphas.
The ATLAS #28 is additional and separately tagged with quote-volume limitations.

Usage:
 python -m research.xau_all_original_3tf --quotes tick.csv --day YYYYMMDD --out daily.json
 python -m research.xau_all_original_3tf --reports daily_dir --out comparison.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from bisect import bisect_right
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from research.backtest_27 import all_ids
from src.strategies import make_indicators
from src import gold_forward as gold
from src import leveraged_gold as lever
from src import experimental_h1 as h1
from src import momentum60_shadow as momentum
from src import bb_rebound_mtf as bb20
from src import atlas_vector as atlas

TIMEFRAMES = {"M1":60,"M5":300,"M15":900}
DAYS = (
    "20261005","20261006","20261007","20261008","20261009",
    "20261012","20261013","20261014","20261015","20261016",
    "20261019","20261020","20261021","20261022","20261023",
    "20261026","20261027","20261028","20261029","20261030",
    "20261102","20261103","20261104","20261105","20261106",
)
BASE_COST_BPS = 7.0
MAX_SPREAD_USD = 12.0
INITIAL_WARMUP = 241  # same initial reference warmup for ALL comparable books
EXPECTED_BOOKS = 28
EXPERIMENTAL_MARKETS = ("EURUSD","USDJPY","XAUUSD","US500","XTIUSD")


def _sha_file(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def load_quotes(path, day):
    """No synthetic candles or ticks; quarantine the whole invalid source day.

    Source price is midpoint (bid+ask)/2, the existing 7bps XAUUSD paper
    roundtrip charge remains in force. Tick updates count only as quotes.
    """
    if day not in DAYS:
        raise ValueError("Day not pre-registered")
    path = Path(path)
    if path.stat().st_size < 500:
        raise ValueError("No real XAUUSD ticks")
    summaries={}
    counts={}
    for tf in TIMEFRAMES:
        summaries[tf]={}
        counts[tf]=0
    prev_stamp=-1
    prev_quote=None
    count=0
    first=None
    last=None
    ignored=0
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not {"timestamp","askPrice","bidPrice"}.issubset(reader.fieldnames or []):
            raise ValueError("Missing official quote columns")
        for item in reader:
            count+=1
            if count>2_500_000:
                raise ValueError("Daily tick budget exceeded; quarantine whole session")
            try:
                ms=int(item["timestamp"])
                ask=float(item["askPrice"])
                bid=float(item["bidPrice"])
            except (KeyError,ValueError,TypeError,OverflowError) as exc:
                raise ValueError(f"Invalid bid/ask tick {count}") from exc
            if (ms<946684800000 or ms<prev_stamp or not
                    (math.isfinite(ask) and math.isfinite(bid) and
                     0 < bid < ask and 0 < ask-bid <= MAX_SPREAD_USD)):
                raise ValueError(f"Corrupted/unsorted bid/ask tick {count}")
            prev_stamp=ms
            ts=ms//1000
            date=datetime.fromtimestamp(ts,timezone.utc)
            if date.strftime("%Y%m%d") != day or not 12<=date.hour<23:
                raise ValueError("Mixed date or outside pre-registered 12-23 UTC window")
            first = ts if first is None else first
            last = ts
            if prev_quote==(bid,ask):
                ignored+=1
                continue
            prev_quote=(bid,ask)
            midpoint=(bid+ask)/2
            for tf,period in TIMEFRAMES.items():
                stamp=ts//period*period
                d=summaries[tf]
                item=d.get(stamp)
                if item is None:
                    d[stamp]={"time":stamp,"open":midpoint,
                              "high":midpoint,"low":midpoint,"close":midpoint,
                              "volume":1,"max_spread":ask-bid}
                else:
                    item["high"]=max(item["high"],midpoint)
                    item["low"]=min(item["low"],midpoint)
                    item["close"]=midpoint
                    item["volume"]+=1
                    item["max_spread"]=max(item["max_spread"],ask-bid)
    if not count or not first or not last:
        raise ValueError("No recorded XAUUSD quotes")
    dt0=datetime.fromtimestamp(first,timezone.utc)
    dt1=datetime.fromtimestamp(last,timezone.utc)
    if dt0.hour!=12 or dt1.hour!=22:
        raise ValueError("Missing morning/afternoon market coverage")
    output={}
    for tf,period in TIMEFRAMES.items():
        output[tf]=list(summaries[tf].values())
        expected=11*3600//period
        if len(output[tf])<int(expected*.90):
            raise ValueError(f"{tf}: incomplete observed candles {len(output[tf])}/{expected}")
        if any(output[tf][i]["time"]<=output[tf][i-1]["time"]
               for i in range(1,len(output[tf]))):
            raise ValueError("Non-monotonic OHLC")
    return {
        "day":day,"quarantined":False,"source":"XAUUSD Dukascopy bid/ask quotes",
        "source_sha256":_sha_file(path),"source_rows":count,
        "unchanged_quotes_ignored":ignored,"first_ts":first,"last_ts":last,
        "bars":output,
    }


def to_h1(bars,period):
    """Original BB20 H1 trend confirmation requires COMPLETE actual hours."""
    if 3600%period:
        raise ValueError("Cannot aggregate target interval to H1")
    buckets=defaultdict(list)
    for bar in bars:
        buckets[bar["time"]//3600*3600].append(bar)
    result=[]
    for stamp,group in sorted(buckets.items()):
        group.sort(key=lambda b:b["time"])
        if len(group)!=3600//period or any(
                b["time"]!=stamp+j*period for j,b in enumerate(group)):
            continue
        result.append({"time":stamp,"open":group[0]["open"],
            "high":max(x["high"] for x in group),
            "low":min(x["low"] for x in group),
            "close":group[-1]["close"]})
    return result


def _fee(qty,entry,exit,multiplier=1.):
    # Exactly project's conventional gold XAU 7bps paper allowance.
    return BASE_COST_BPS*multiplier/10000*qty*((entry+exit)/2)


def bb_book():
    return {"equity":bb20.CAPITAL, "position":None, "closed":[],
            "entries":0, "last_entry_h1":None}


def bb_step(book,bars,inds,i,hourly,hourly_inds,ends,tf,stress):
    """BB20 original H1 trend + M15 SMA20 touch adapted to target M1/M5/M15.

    Original USD/CAD quote->USD conversion and 1.5 CAD pip fee cannot be
    retained on XAUUSD. This adapter sizes in gold ounces, leaves BB20
    H1 confirmation and Bollinger-middle trigger unchanged, and charges
    the same gold price notional cost as other conventional books.
    """
    current=bars[i]
    pos=book["position"]
    if pos:
        side=pos["side"]
        touched=(current["low"]<=pos["stop"] if side==1
                 else current["high"]>=pos["stop"])
        if touched:
            exit_price=(min(current["open"],pos["stop"]) if side==1
                        else max(current["open"],pos["stop"]))
            gross=side*(exit_price-pos["entry"])*pos["qty"]
            cost=_fee(pos["qty"],pos["entry"],exit_price,stress)
            net=gross-cost
            book["equity"]+=net
            book["closed"].append({"entry_ts":pos["entry_ts"],"exit_ts":current["time"],
                "side":side,"entry":pos["entry"],"exit":exit_price,
                "net_usd":round(net,5),"cost_usd":round(cost,5),
                "exit_type":"TRAIL_STOP" if pos["updates"] else "STOP"})
            book["position"]=None
            return
        # Monotonic stop following the best closed candle; effective NEXT bar.
        close=current["close"]
        favorable=(max(pos["best_close"],close) if side==1 else
                   min(pos["best_close"],close))
        pos["best_close"]=favorable
        suggested=favorable-side*bb20.TRAIL_R*pos["initial_r"]
        new=(max(pos["stop"],suggested) if side==1 else
             min(pos["stop"],suggested))
        if new!=pos["stop"]:
            pos["stop"]=new
            pos["updates"]+=1
        return
    if i<INITIAL_WARMUP or i<21 or book["equity"]<=0:
        return
    period=TIMEFRAMES[tf]
    # New positions require uninterrupted bars; stops still assessed across gaps.
    if (current["time"]-bars[i-1]["time"]!=period or
            bars[i-1]["time"]-bars[i-2]["time"]!=period):
        return
    # Match original eligible H1 logic: H1 hour must end BEFORE the
    # prior (signal) bar OPEN. Never look at a forming H1 candle.
    prev_ts=bars[i-1]["time"]
    j=bisect_right(ends,prev_ts)-1
    if j<0:
        return
    h=hourly[j]
    closed_at=ends[j]
    if prev_ts>=closed_at+3600 or j<55:
        return
    if h["time"]==book["last_entry_h1"]:
        return
    side=bb20.h1_trend_confirmation(hourly,hourly_inds,j)
    if not side or not bb20.m15_sma20_pullback(bars,inds,i,side):
        return
    opening=current["open"]
    distance=max(bb20.STOP_ATR*hourly_inds[j]["atr"],6*bb20.PIP)
    qty=min(book["equity"]*bb20.RISK_FRACTION/distance,
            book["equity"]*bb20.MAX_NOTIONAL/opening)
    if qty<=0:
        return
    book["position"]={"entry":opening,"entry_ts":current["time"],
        "qty":qty,"side":side,"initial_r":distance,"best_close":opening,
        "stop":opening-side*distance,"updates":0}
    book["last_entry_h1"]=h["time"]
    book["entries"]+=1
    # Entry at this bar's OPEN. Its later low/high must also be checked.
    bb_step(book,bars,inds,i,hourly,hourly_inds,ends,tf,stress)


def _summary(book,capital):
    closed=book["closed"]
    pnl=[float(t["net_usd"]) for t in closed]
    gains=sum(x for x in pnl if x>0)
    losses=-sum(x for x in pnl if x<0)
    equity=capital
    peak=capital
    dd=0.
    for value in pnl:
        equity+=value
        peak=max(peak,equity)
        dd=max(dd,100*(peak-equity)/peak) if peak>0 else dd
    return {
        "entries":len(book.get("entries",[])) if isinstance(book.get("entries"),list)
                  else int(book.get("entries",len(closed))),
        "closed":len(closed),
        "wins":sum(x>0 for x in pnl),
        "losses":sum(x<0 for x in pnl),
        "net_usd":round(sum(pnl),2),
        "cost_usd":round(sum(float(x.get("cost_usd",x.get("transaction_cost",0.)))+
                              float(x.get("funding_cost",0.)) for x in closed),2),
        "profit_factor":round(gains/losses,3) if losses>0 else None,
        "win_rate_pct":round(100*sum(x>0 for x in pnl)/len(pnl),1) if pnl else None,
        "max_closed_dd_pct":round(dd,3),
        "open_at_end":book.get("position") is not None,
    }


def replay(bars,tf,stress=1.0):
    seconds=TIMEFRAMES[tf]
    if len(bars)<INITIAL_WARMUP+100:
        raise ValueError(f"Insufficient {tf} XAUUSD observed candles")
    if any(bars[i]["time"]<=bars[i-1]["time"] for i in range(1,len(bars))):
        raise ValueError("Unordered tick-derived candles")
    indicators=make_indicators(bars)
    h1bars=to_h1(bars,seconds)
    if len(h1bars)<205:
        raise ValueError("Insufficient complete H1 context for ORIGINAL BB20")
    h1ind=make_indicators(h1bars)
    h1ends=[x["time"]+3600 for x in h1bars]
    if len(h1ends)!=len(set(h1ends)):
        raise ValueError("Duplicate H1 context")
    normal={key:{"equity":gold.CAPITAL,"position":None,"closed":[]}
            for key in gold.STUDY}
    leveraged=lever.fresh(bars)["books"]
    experimental={key:h1.book() for key in h1.STRATEGIES}
    candidate=momentum.fresh(bars)
    bb=bb_book()
    atlas_book=atlas.initial(bars)
    # Explicit default: news guard off. No hindsight macro-calendar patch.
    with ExitStack() as stack:
        stack.enter_context(patch.object(gold,"COST_BPS",
              {**gold.COST_BPS,"XAUUSD":BASE_COST_BPS*stress}))
        stack.enter_context(patch.object(lever,"COST_BPS_ROUNDTRIP",
              lever.COST_BPS_ROUNDTRIP*stress))
        stack.enter_context(patch.object(h1,"COST_BPS",
              {**h1.COST_BPS,"XAUUSD":BASE_COST_BPS*stress}))
        stack.enter_context(patch.object(momentum,"COST_BPS",
              {**momentum.COST_BPS,"XAUUSD":BASE_COST_BPS*stress}))
        stack.enter_context(patch.object(atlas,"COST_BPS",
              {**atlas.COST_BPS,"XAUUSD":BASE_COST_BPS*stress}))
        for i in range(INITIAL_WARMUP,len(bars)):
            for key in gold.STUDY:
                gold.evaluate_bar(normal[key],key,bars,indicators,i)
            for key in lever.CONFIG:
                lever.one_bar(leveraged[key],key,bars,indicators,i,
                              mode=lever.LIVE_POLICY)
            for key in h1.STRATEGIES:
                h1.step(experimental[key],"XAUUSD",key,bars,indicators,i,
                        bar_seconds=seconds)
            momentum.step(candidate,bars,indicators,i)
            bb_step(bb,bars,indicators,i,h1bars,h1ind,h1ends,tf,stress)
            atlas.step(atlas_book,bars,i)
    results={}
    for key in gold.STUDY:
        results["gold_h4:"+key]=_summary(normal[key],gold.CAPITAL)
    for key in lever.CONFIG:
        results["leveraged_h4:"+key]=_summary(leveraged[key],lever.CAPITAL)
    for orig in EXPERIMENTAL_MARKETS:
        for rule in h1.STRATEGIES:
            r="experimental_h1:"+orig+":"+rule
            results[r]={**_summary(experimental[rule],h1.CAPITAL),
                        "duplicate_gold_signals_from_group":rule,
                        "original_market_label":orig}
    results["momentum60_h4:momentum60"]=_summary(candidate,momentum.CAPITAL)
    results["usdcad_m15:bb20"]={**_summary(bb,bb20.CAPITAL),
           "retargeting_note":"original H1 trend + SMA20 trigger; USD/CAD currency sizing converted to XAU ounces"}
    results["atlas_28:atlas"]={**_summary(atlas_book,atlas.CAPITAL),
           "volume_source":"Dukascopy observed quote-price updates (NOT traded volume)",
           "volume_proxy_not_same_as_original_traded_volume":True}
    if set(results) != set(all_ids())|{"atlas_28:atlas"}:
        raise AssertionError("Missing original robot identities")
    if len(results)!=EXPECTED_BOOKS:
        raise AssertionError("Expected 27+ATLAS")
    return {
        "tf":tf,"n_bars":len(bars),"n_common_warmup":INITIAL_WARMUP,
        "n_valid_hourly_bars":len(h1bars),
        "first_ts":bars[0]["time"],"last_ts":bars[-1]["time"],
        "paper_only":True,"cost_stress_multiplier":stress,
        "gold_symbol":"XAUUSD Dukascopy quote MID reference, not GC=F",
        "execution":"OHLC midpoint replay; original XAU bps paper cost, no true tick fills",
        "books":results,
    }


def aggregate(reports_folder,output):
    files=[]
    for day in DAYS:
        file=Path(reports_folder)/(day+".json")
        if not file.is_file():
            raise ValueError(f"Missing mandatory date {day}")
        row=json.loads(file.read_text(encoding="utf-8"))
        if row["day"]!=day:
            raise ValueError("Incorrect daily identity")
        files.append(row)
    good=[row for row in files if not row.get("quarantined")]
    if len(good)<21:
        raise ValueError("Too few full valid sessions for 200 H1 BB20 context")
    out={"study":"Original 27 Nexus Quant bots plus ATLAS, XAU only, M1/M5/M15",
        "paper_only":True,"promoted_to_live":False,
        "source":"XAUUSD public Dukascopy bid/ask; MID candles",
        "initial_banks_separate":True,
        "real_broker_fills":False,
        "timeframe_substitution_changes_original_bar_duration":True,
        "original_entry_strategies_preserved":True,
        "h1_repeated_three_rules_five_times":True,
        "h1_aliases_not_independent":True,
        "atlas_quote_volume_proxy_only":True,
        "samples_not_independent_holdout":True,
        "predeclared_dates":list(DAYS),
        "valid_dates":[r["day"] for r in good],
        "quarantined_dates":[{"date":r["day"],"reason":r.get("reason")} for r in files if r.get("quarantined")],
        "source_fingerprints":{r["day"]:r["source_sha256"] for r in good},
        "timeframes":{},
    }
    for tf in TIMEFRAMES:
        candles=[bar for doc in good for bar in doc["bars"][tf]]
        if len(candles)<400:
            raise ValueError(f"{tf}: insufficient observed candles")
        raw={}
        for mult in (1.0,2.0):
            report=replay(candles,tf,mult)
            raw[str(int(mult))+"x"]=report
        aligned={}
        for key,base in raw["1x"]["books"].items():
            stress=raw["2x"]["books"][key]
            aligned[key]={**base,"double_cost_net_usd":stress["net_usd"],
                         "double_cost_closed":stress["closed"]}
        out["timeframes"][tf]={
            "source_bars":len(candles),
            "start_utc":datetime.fromtimestamp(candles[0]["time"],timezone.utc).isoformat(),
            "end_utc":datetime.fromtimestamp(candles[-1]["time"],timezone.utc).isoformat(),
            "bb_h1_context_hours":raw["1x"]["n_valid_hourly_bars"],
            "unique_signal_families":5+5+3+1+1+1,
            "robot_slots":len(aligned),"books":aligned,
        }
    # One line per bot and timeframe, no shadow duplicates hidden.
    lines=[
        "# Nexus Quant — TODOS os 27 robôs originais + ATLAS, somente OURO",
        "",
        "Cada estratégia original é aplicada aos candles **M1, M5 e M15** do XAUUSD.",
        "A duração dos candles muda, mas a lógica de sinal NÃO foi substituída.",
        "Preços MID de bid/ask reais Dukascopy, execução OHLC hipotética, "
        "custos XAU convencionais de 7bps / alavancados 14bps e teste dobrado.",
        "NÃO são ordens MT5, não são custos contratados, nem lucro real.",
        "Bancas de cada livro independentes; jamais somar como se fosse uma conta.",
        "",
        "Os 15 livros experimentais eram somente **3 regras repetidas em 5 mercados**; "
        "ao colocar os 15 em ouro, as cinco cópias de cada regra ficam IGUAIS.",
        "ATLAS usa **número de mudanças de cotação** como volume substituto: "
        "não é volume financeiro negociado. BB20 mantém confirmação H1, gatilho SMA20 "
        "no período testado e a conversão da posição USD/CAD para ouro.",
        "",
        f"Dias válidos: {len(good)}/{len(DAYS)}. Quarentenados: {len(DAYS)-len(good)}.",
        "",
        "| Robô original | M1 (US$ / ops) | M5 (US$ / ops) | M15 (US$ / ops) |",
        "|---|---:|---:|---:|"
    ]
    names=list(out["timeframes"]["M1"]["books"])
    for key in names:
        vals=[]
        for tf in TIMEFRAMES:
            v=out["timeframes"][tf]["books"][key]
            vals.append(f"{v['net_usd']:+.2f} / {v['closed']}")
        lines.append("| "+key+" | "+" | ".join(vals)+" |")
    lines.extend(["","## Resultado com DOBRO dos custos","",
      "| Robô | M1 (US$) | M5 (US$) | M15 (US$) |",
      "|---|---:|---:|---:|"])
    for key in names:
        lines.append("| "+key+" | "+" | ".join(
            f"{out['timeframes'][tf]['books'][key]['double_cost_net_usd']:+.2f}"
            for tf in TIMEFRAMES)+" |")
    lines.extend(["","**Interpretação:** resultados históricos e não independentes, "
         "sem preços executáveis de uma corretora MT5. "
         "Não alterar ordem real, robôs aprovados, estado nem regras existentes.",
         ""])
    dest=Path(output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    dest.with_suffix(".md").write_text("\n".join(lines),encoding="utf-8")
    print("XAU_ALL_28_3_TF_RESULT",json.dumps({
        "valid_days":len(good),"quarantined_days":len(DAYS)-len(good),
        "matrix":{tf:{"n":len(x["books"]),
            "positive":sum(v["net_usd"]>0 for v in x["books"].values()),
            "negative":sum(v["net_usd"]<0 for v in x["books"].values()),
            "closed_total_including_H1_aliases":sum(v["closed"] for v in x["books"].values())}
            for tf,x in out["timeframes"].items()}
    },ensure_ascii=False),flush=True)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--quotes")
    parser.add_argument("--day")
    parser.add_argument("--reports")
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    if args.reports:
        aggregate(args.reports,args.out)
    else:
        if not args.quotes or args.day not in DAYS:
            parser.error("Supply predeclared --day and --quotes, or --reports")
        try:
            item=load_quotes(args.quotes,args.day)
        except (ValueError,OSError) as exc:
            item={"day":args.day,"quarantined":True,
                  "reason":type(exc).__name__+": "+str(exc)[:170]}
        dest=Path(args.out)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(item,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
        print("XAU_SOURCE_DAY",item["day"],"quarantined",item["quarantined"],
              "candles",{k:len(v) for k,v in item.get("bars",{}).items()},flush=True)


if __name__=="__main__":
    main()
