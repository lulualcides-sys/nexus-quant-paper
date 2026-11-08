"""V3 frozen swing exits, two new backward months. NOT forward/live trading."""
import argparse,json
from pathlib import Path
from importlib import import_module
from research.alpha.data import download_month,load_symbol,aggregate_5m,SYMBOLS
from research.alpha.engine import build,backtest,stats
from research.alpha.run import BOTS,write_ledger,daily_block_ci
from research.alpha_v2.filters import Filtered
from research.alpha_v3.swing import SwingFilter,test_engine

PERIODS=(("2026-05","backward_unseen_may"),("2026-06","backward_unseen_june"),
         ("2026-08","development_seen_aug"),("2026-09","development_seen_sep"))
SLIPS=(0.,5.,10.)

def run(out):
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    result=[];source=[];source_errors={}
    for symbol in SYMBOLS:
        history={}
        # Recent months were already seen. New backward months are checked ONLY after
        # code and parameters have been frozen in the branch commit.
        try:
            old,manifests=load_symbol(symbol)
            source+=manifests
            from research.alpha.data import month_seconds
            for month in ("2026-08","2026-09"):
                a,b=month_seconds(month)
                history[month]=[x for x in old if a<=x["time"]<b]
        except Exception as exc:
            source_errors[symbol+":prior"]=type(exc).__name__+": "+str(exc)
        for month in ("2026-05","2026-06"):
            try:
                bars,m=download_month(symbol,month)
                history[month]=bars
                source.append(m)
            except Exception as exc:
                source_errors[symbol+":"+month]=type(exc).__name__+": "+str(exc)
        for name in BOTS:
            model=SwingFilter(name)
            orig=import_module("research.alpha.bots."+name)
            filtered=Filtered(name)
            rec=dict(robot=name,symbol=symbol,timeframe="M"+str(model.TIMEFRAME),periods={})
            for month,label in PERIODS:
                if month not in history:
                    rec["periods"][label]=dict(status="NOT_VALIDATED",reason=source_errors.get(symbol+":"+month,"missing archive"))
                    continue
                try:
                    bars=history[month] if model.TIMEFRAME==1 else aggregate_5m(history[month])
                    feat=build(bars)
                    s={}
                    for slip in SLIPS:
                        run3=test_engine(bars,model,model.TIMEFRAME,slip,features=feat)
                        metr=stats(run3)
                        if abs(sum(row["net_usdt"] for row in run3["ledger"])-
                               (run3["equity"]-5000))>0.03:
                            raise AssertionError("V3 ledger/equity mismatch")
                        metr.update(scenario_slippage_bps_per_side=slip,
                                    signals=run3["signals_seen"],
                                    open_at_end=run3["open_at_period_end"],
                                    mark_open_usdt=run3["final_open_mark_to_market_usdt"],
                                    bootstrap_daily_block_ci_95_usdt=daily_block_ci(run3["ledger"]))
                        path=f"ledgers/{symbol}_{name}_{label}_{int(slip)}bps_swing.csv"
                        write_ledger(root/path,run3["ledger"])
                        metr["ledger"]=path
                        s[str(int(slip))]=metr
                    control=backtest(bars,orig,model.TIMEFRAME,241,len(bars),5.,features=feat)
                    v2=backtest(bars,filtered,model.TIMEFRAME,241,len(bars),5.,features=feat)
                    a=stats(control);b=stats(v2)
                    for tag,raw,d in (("original",control,a),("filtered_v2",v2,b)):
                        path=f"ledgers/{symbol}_{name}_{label}_5bps_{tag}.csv"
                        write_ledger(root/path,raw["ledger"])
                        d["ledger"]=path
                    rec["periods"][label]=dict(month=month,original=a,filtered_v2=b,swing_v3=s)
                except Exception as exc:
                    rec["periods"][label]=dict(status="NOT_VALIDATED",
                                              reason=type(exc).__name__+": "+str(exc))
            rec["status"]="INCONCLUSIVE_NOT_APPROVED"
            result.append(rec)
    summary=dict(experiment="ALPHA-V3-LONGER-HOLD-FROZEN-BEFORE-MAY-JUNE",
                 quote_currency="USDT",paper_only=True,approved=0,
                 expected_combinations=20,completed_combinations=len(result),
                 timeline_note="May/June are unseen BACKWARD retrospective windows; not forward evidence.",
                 original_and_v2_rules_unchanged=True,source_manifests=source,
                 source_failures=source_errors,results=result,
                 costs=dict(fee_bps_each_side=10,halfspread_bps_each_side=1,
                            slippage_bps_per_side=list(SLIPS),capital_usdt_per_pair=5000,
                            theoretical_max_risk_fraction=.0075),
                 exit_model=dict(target_atr=8,stop_atr=2,max_hold_hours=12,
                                 time_exit="next candle open",intrabar="stop first"),
                 limitations=["No intra-bar path or live orderbook/fills",
                              "Stops may gap beyond 0.75% theoretical no-gap risk",
                              "Open end-of-month positions excluded from realized ledger",
                              "No positive paper-forward evidence; do not promote"])
    (root/"results.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    (root/"source_manifest.json").write_text(json.dumps(dict(manifests=source,failures=source_errors),
                                           ensure_ascii=False,indent=2)+"\n")
    cols=["# ALPHA V3 — frozen trend/volatility/cost gate + 8ATR swing target",
          "","Observed results are hypothetical spot fills. No version is approved.",
          "May/June are backward unseen tests, not forward or real trading.",
          "","| Robot | Symbol | May closed | May net V3 5bps | June closed | June net V3 5bps | June V2 net | June original net | June 0bps | June 10bps |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in result:
        may=item["periods"].get("backward_unseen_may",{})
        jun=item["periods"].get("backward_unseen_june",{})
        m=may.get("swing_v3",{}).get("5",{})
        j=jun.get("swing_v3",{}).get("5",{})
        v2=jun.get("filtered_v2",{});base=jun.get("original",{})
        zero=jun.get("swing_v3",{}).get("0",{})
        ten=jun.get("swing_v3",{}).get("10",{})
        def num(x):return str(x) if x is not None else "N/V"
        cols.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"%
             (item["robot"],item["symbol"],m.get("trades","N/V"),num(m.get("net_usdt")),
              j.get("trades","N/V"),num(j.get("net_usdt")),
              num(v2.get("net_usdt")),num(base.get("net_usdt")),
              num(zero.get("net_usdt")),num(ten.get("net_usdt"))))
    cols.extend(["","## Source failures"]+[f"- {k}: {v}" for k,v in source_errors.items()])
    cols+=["","All trade ledgers, costs, confidence intervals and monthly metrics in artifact results.json."]
    (root/"results.md").write_text("\n".join(cols)+"\n")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="artifacts/alpha-v3")
    args=p.parse_args()
    report=run(args.out)
    print("ALPHA-V3 pairs=%s source failures=%s approved=0"%
          (len(report["results"]),report["source_failures"]))
    if not report["results"]:raise SystemExit(2)
