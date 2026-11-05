"""ATLAS progressive loss diagnosis: rank worst to best on comparable M5 WIN.

A descriptive rank is NOT a deployable strategy, a forward result, nor a
guarantee. Previously reviewed M26/Q26 months are NOT pristine holdouts.
Source pinned authentic-contract third-party Profit exports (NOT B3 audit).
Do not add test period data to the signal's lookback from a future candle.

Cross-contract research bank R$30,000 on ALL scenarios, risk 0.75% / trade,
at most three contracts, fee R$4/contract round trip, 0/1/2 tick slippage
on EACH side. Four calendar-month combinations are ranked; incomplete
calendar months are shown as diagnostics only and cannot affect ranks.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import urllib.request
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from statistics import median
from unittest.mock import patch

from research.atlas_winm26_v4_transfer import (
    SOURCE_URL as M26_URL,
    SOURCE_GIT_SHA as M26_BLOB,
    fetch_source as m26_fetch,
    canonicalize as m26_canonicalize,
)
from research.atlas_v5_cost_aware import ALL_MODELS, v5_candidate
from research.win_price_data import _number,_tick_check,read_win_csv,local_day,win_session,TZ
from research import atlas_win_backtest as simulator

RESEARCH_CAPITAL_BRL=30000.0
FEE_BRL=4.0
SLIPPAGE_TICKS=(0,1,2)
RAW_Q26_PATH="dados/candles/2026-2S_Q26/WINQ26_F_0_5min.csv"
RAW_Q26_BLOB="fe06f08f87183db468bc2a05ec080cda661660e9"
RAW_Q26_URL="https://raw.githubusercontent.com/wesleyzilva/tradetech/main/"+RAW_Q26_PATH

# Ranked windows do not overlap in calendar time. All rank bank sizes identical.
WINDOWS=(
    ("WINM26_2026_03","WINM26","2026-03-01","2026-04-01",True),
    ("WINM26_2026_04","WINM26","2026-04-01","2026-05-01",True),
    ("WINQ26_2026_05","WINQ26","2026-05-01","2026-06-01",True),
    ("WINQ26_2026_06","WINQ26","2026-06-01","2026-07-01",True),
    ("WINQ26_2026_07_PARTIAL","WINQ26","2026-07-01","2026-08-01",False),
)

def _fetch_pinned(url,pinned,path):
    request=urllib.request.Request(url,headers={"User-Agent":"ATLAS-loss-attribution-research/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        body=response.read(5_000_001)
    if not body or len(body)>5_000_000:
        raise ValueError("Missing or excessive Q26 data source")
    sha=hashlib.sha1(b"blob "+str(len(body)).encode()+bytes([0])+body).hexdigest()
    if sha!=pinned:
        raise ValueError("Public Q26 contract source changed: pinned git blob mismatch")
    Path(path).write_bytes(body)
    return {"url":url,"git_sha":sha,"sha256":hashlib.sha256(body).hexdigest(),
            "bytes":len(body),"not_audited_by_B3":True}

def canonicalize_q26_m5(raw,out):
    """Strict genuine Q26 M5 contract, no adjusted WINFUT or synthetic M5."""
    rows=[]
    with Path(raw).open(encoding="utf-8-sig",newline="") as stream:
        for line,fields in enumerate(csv.reader(stream,delimiter=";"),1):
            if not fields or not any(s.strip() for s in fields):continue
            if fields[0].strip().lower()=="ativo":continue
            if len(fields)!=9 or fields[0].strip().upper()!="WINQ26":
                raise ValueError(f"Q26 line {line}: expected 9 fields and exact WINQ26")
            timestamp=datetime.strptime(fields[1].strip()+" "+fields[2].strip(),
                                        "%d/%m/%Y %H:%M:%S")
            o,h,l,c=[_number(x) for x in fields[3:7]]
            for p in (o,h,l,c):_tick_check(p)
            monetary_volume,contracts=_number(fields[7]),_number(fields[8])
            if l>min(o,c) or h<max(o,c) or monetary_volume<=0 or contracts<=0 or int(contracts)!=contracts:
                raise ValueError(f"Q26 line {line}: bad candle / volume")
            rows.append((timestamp,o,h,l,c,int(contracts)))
    if len(rows)<1000:
        raise ValueError("Q26 M5 third-party file insufficient")
    rows.sort(key=lambda r:r[0])
    if any(rows[i][0]<=rows[i-1][0] for i in range(1,len(rows))):
        raise ValueError("Q26 M5 duplicate timestamp")
    with Path(out).open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter=";")
        writer.writerow(["Ativo","Data","Hora","Open","High","Low","Close","Volume"])
        for ts,o,h,l,c,q in rows:
            writer.writerow(["WINQ26",ts.strftime("%d/%m/%Y"),ts.strftime("%H:%M:%S"),
                             int(o),int(h),int(l),int(c),q])
    imported=read_win_csv(out,expected_symbol="WINQ26")
    if imported["timeframe_seconds"]!=300 or len(imported["bars"])!=len(rows):
        raise ValueError("Q26 must be genuine native M5")
    return imported

def _month_cut(bars,start,end):
    matched=[i for i,b in enumerate(bars) if start<=local_day(b["time"])<end]
    if not matched or matched[0]<160:
        return None
    return bars[matched[0]-160:matched[-1]+1]

def _coverage(bars,start,end):
    by_day=defaultdict(int)
    for b in bars:
        day=local_day(b["time"])
        if start<=day<end and win_session(b["time"]):
            by_day[day]+=1
    count=list(by_day.values())
    return {"days":len(count),"days_with_65_m5":sum(n>=65 for n in count),
            "total_session_m5":sum(count),
            "median_m5_per_day":median(count) if count else None,
            "minimum_m5_per_day":min(count) if count else None}

def _session_bucket(ts):
    stamp=datetime.fromtimestamp(ts,timezone.utc).astimezone(TZ)
    minute=stamp.hour*60+stamp.minute
    if minute<12*60:return "morning_before_12"
    if minute<15*60:return "midday_12_to_15"
    return "late_after_15"

def _loss_analysis(result):
    ledger=result.get("closed_ledger",[])
    reasons=defaultdict(lambda:{"count":0,"net_brl":0.0,"gross_brl":0.0,
                                 "cost_brl":0.0})
    windows=defaultdict(lambda:{"count":0,"net_brl":0.0,"losing":0})
    for t in ledger:
        net=t["net_brl"]
        cost=t["estimated_cost_brl"]
        reason=t["reason"]
        v=reasons[reason]
        v["count"]+=1
        v["net_brl"]+=net
        v["cost_brl"]+=cost
        v["gross_brl"]+=net+cost
        bucket=windows[_session_bucket(t["signal_ts"])]
        bucket["count"]+=1
        bucket["net_brl"]+=net
        bucket["losing"]+=int(net<0)
    worst=sorted((t for t in ledger if t["net_brl"]<0),key=lambda x:x["net_brl"])[:5]
    return {
        "closed_trades":len(ledger),
        "stop_count":sum(t["reason"].startswith("STOP") for t in ledger),
        "same_bar_uncertain_exits":result.get("uncertain_same_bar_exits",0),
        "total_estimated_cost_brl":round(sum(t["estimated_cost_brl"] for t in ledger),2),
        "gross_before_estimated_costs_brl":round(sum(t["net_brl"]+t["estimated_cost_brl"] for t in ledger),2),
        "net_brl":round(sum(t["net_brl"] for t in ledger),2),
        "worst_5_losses": [{
            "signal_local":datetime.fromtimestamp(t["signal_ts"],timezone.utc).astimezone(TZ).isoformat(),
            "side":t["side"],"reason":t["reason"],
            "net_brl":t["net_brl"],"contracts":t["contracts"]
        } for t in worst],
        "reasons":{k:{n:round(x,2) if isinstance(x,float) else x for n,x in v.items()}
                   for k,v in reasons.items()},
        "market_time_buckets":{k:{"count":v["count"],"losing":v["losing"],
                                   "net_brl":round(v["net_brl"],2)}
                              for k,v in windows.items()},
    }

def study(imported,source):
    out={"scope":"WIN M5, identical virtual R$30000 capital, 0.75pct risk",
         "source":source,
         "fee_brl_per_contract_roundtrip":FEE_BRL,
         "slip_ticks_each_side":list(SLIPPAGE_TICKS),
         "models_frozen":list(ALL_MODELS),
         "bank_brl_reset_per_period":RESEARCH_CAPITAL_BRL,
         "current_test_not_prospective":True,
         "do_not_autopromote":True,
         "periods":{}}
    for name,symbol,start,end,completed in WINDOWS:
        bars=imported[symbol]["bars"]
        quality=_coverage(bars,start,end)
        month=_month_cut(bars,start,end)
        part={"symbol":symbol,"start":start,"end_exclusive":end,
              "full_calendar_month":completed,"data_quality":quality,
              "variants":{},"attribution":{},"signal_counts":{}}
        out["periods"][name]=part
        if month is None or quality["days_with_65_m5"]<8:
            part["status"]="INSUFFICIENT_M5_FOR_MEANINGFUL_COMPARISON"
            continue
        part["status"]="BACKTESTED"
        eligible=[start<=local_day(b["time"])<end for b in month]
        for model in ALL_MODELS:
            signals=[v5_candidate(month,i,model) if i>=100 and eligible[i] else 0
                     for i in range(len(month))]
            with patch.object(simulator,"CAPITAL_BRL",RESEARCH_CAPITAL_BRL):
                with patch.object(simulator,"candidate",
                                  side_effect=lambda b,i,v,s=signals:s[i]):
                    results={str(k):simulator.simulate(month,timeframe="M5",
                                                       variant="original",fee_brl=FEE_BRL,
                                                       slip_ticks=k)
                             for k in SLIPPAGE_TICKS}
            part["variants"][model]=results
            part["attribution"][model]=_loss_analysis(results["2"])
            part["signal_counts"][model]={
                "total_signals":sum(s!=0 for s in signals),
                "buy_signals":sum(s==1 for s in signals),
                "sell_signals":sum(s==-1 for s in signals),
                "filled_entries_stress":results["2"]["entries"],
                "cancellations_or_unfilled_stress":results["2"]["unfilled_or_cancelled"],
            }
    out["worst_to_best"]=rank(out)
    return out

def rank(out):
    """Describe comparable full months; all ranks observational, not deployment."""
    leaderboard=[]
    for model in ALL_MODELS:
        periods=[]
        unavailable=[]
        for period_name,period in out["periods"].items():
            if not period["full_calendar_month"]:
                continue
            if period["status"]!="BACKTESTED":
                unavailable.append(period_name)
                continue
            base=period["variants"][model]["1"]
            stress=period["variants"][model]["2"]
            periods.append((period_name,base,stress))
        stress_net=sum(p[2]["net_brl"] for p in periods)
        baseline_net=sum(p[1]["net_brl"] for p in periods)
        n=sum(p[2]["closed"] or 0 for p in periods)
        positive=sum(p[2]["net_brl"]>0 for p in periods)
        traded_months=sum((p[2]["closed"] or 0)>=8 for p in periods)
        worst=min((p[2]["net_brl"] for p in periods), default=None)
        max_dd=max((p[2]["max_realized_drawdown_pct"] or 0 for p in periods),
                   default=None)
        cost_total=sum(out["periods"][p[0]]["attribution"][model]["total_estimated_cost_brl"] for p in periods)
        # Eligibility is only a floor for meaningful descriptive ranking, NOT
        # evidence of statistical significance and never an activation gate.
        enough=len(periods)>=3 and n>=40 and traded_months>=3
        leftover=sum(int(p[2].get("open_at_end") or p[2].get("pending_at_end")) for p in periods)
        leaderboard.append({
            "variant":model,"completed_months_backtested":len(periods),
            "unavailable_full_months":unavailable,
            "closed_under_2_ticks":n,"months_with_8plus_trades":traded_months,
            "stress_positive_full_months":positive,
            "stress_total_brl_sum_independent_monthly_resets":round(stress_net,2),
            "baseline_1tick_total_brl_sum":round(baseline_net,2),
            "stress_return_sum_pct_of_30k_monthly_bank":round(100*stress_net/RESEARCH_CAPITAL_BRL,3),
            "stress_worst_full_month_brl":worst,
            "stress_max_closed_drawdown_pct":max_dd,
            "estimated_costs_on_2tick_closed_trades_brl":round(cost_total,2),
            "open_or_pending_month_ends":leftover,
            "meaningful_descriptive_rank":enough and not unavailable and not leftover,
            "promoted":False,
            "periods":[{"period":name,"closed":p2["closed"],
                       "net_brl_1tick":p1["net_brl"],"net_brl_2ticks":p2["net_brl"],
                       "profit_factor_2ticks":p2["profit_factor"]}
                      for name,p1,p2 in periods],
        })
    # Sorting from worst to best by cost-stressed outcomes, not selective winrate.
    leaderboard.sort(key=lambda r:(r["stress_total_brl_sum_independent_monthly_resets"],
                                   r["stress_worst_full_month_brl"] if r["stress_worst_full_month_brl"] is not None else -1e20,
                                   r["closed_under_2_ticks"]))
    for i,item in enumerate(leaderboard,1):
        item["order_worst_to_best"]=i
    return leaderboard

def report(out):
    lines=[
        "# ATLAS — do pior ao melhor: atribuição de perdas e revisão V5",
        "",
        "**Ranking DESCRITIVO, não recomendação financeira nem versão operacional aprovada.**",
        "Todos os modelos usam M5, banco virtual R$30.000 por mês, risco 0,75%, até 3 contratos.",
        "Fonte Profit de terceiros com Git SHA1 pinado; não são ordens auditadas da B3.",
        "Regra de execução e taxas constantes: R$4 ida/volta/contrato, entrada 50%, alvo 200%, stop -100%.",
        "Ranking usa **2 ticks de slippage por lado**, soma de P&L entre períodos com reinício da banca; NÃO é retorno de curva contínua.",
        "A classificação pode mudar com preços, custos ou outra amostra; meses previamente observados NÃO são holdout virgem.",
        "",
        "## Ranking do pior ao melhor — meses completos",
        "| Ordem | Modelo | M5 meses avaliados | Trades | Meses positivos sob 2 ticks | Resultado sob 1 tick R$ | Resultado sob 2 ticks R$ | Pior mês R$ | Amostra mínima? |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in out["worst_to_best"]:
        lines.append("| "+" | ".join(map(str,[
            row["order_worst_to_best"],row["variant"],
            row["completed_months_backtested"],row["closed_under_2_ticks"],
            row["stress_positive_full_months"],row["baseline_1tick_total_brl_sum"],
            row["stress_total_brl_sum_independent_monthly_resets"],
            row["stress_worst_full_month_brl"],
            "SIM (apenas ranking)" if row["meaningful_descriptive_rank"] else "NÃO"
        ]))+" |")
    lines+=["","## Auditoria do prejuízo: apenas negócio encerrado, estresse de 2 ticks",
            "As perdas abaixo são classificadas por motivo de saída e horário de GERAÇÃO de sinal, não por parâmetros treinados.",
            "| Contrato/mês | Modelo | Trades | STOP | Stop no candle da entrada | Custos totais R$ | Bruto pré-custos R$ | Líquido R$ |",
            "|---|---|---:|---:|---:|---:|---:|---:|"]
    for key,p in out["periods"].items():
        if not p["full_calendar_month"] or p["status"]!="BACKTESTED":
            continue
        for model in ALL_MODELS:
            a=p["attribution"][model]
            lines.append("| "+" | ".join(map(str,[
                key,model,a["closed_trades"],a["stop_count"],
                a["same_bar_uncertain_exits"],a["total_estimated_cost_brl"],
                a["gross_before_estimated_costs_brl"],a["net_brl"]
            ]))+" |")
    lines+=["","## Decisão e cautelas",
            "- Linhas sem trade não vencem um ranking; todas são marcadas com suficiência de amostra.",
            "- Não construir novos filtros a partir do horário das piores operações e então reutilizar estes mesmos meses como se fossem teste limpo.",
            "- V5 adiciona duas hipóteses FIXAS antes de ver qualquer resultado: custo de 2 ticks + taxas <=12% do alvo bruto nominal; variante adicional evita candles fora de ATR 0,65–1,8 e exige liquidez mínima/horário.",
            "- A soma de resultados entre contratos e períodos independentes NÃO representa rentabilidade contínua nem execução por corretora.",
            "- Todos os registros dos negócios encerrados, incluindo top-5 prejuízos por cenário e agregação por motivo/horário, estão no JSON do job.",
            "- Sem promoção ao robô paper/real, alteração em 27 outros robôs ou alteração de risco.",
            "- Próxima validação exige novos meses, vencimentos, custos reais e execução prospectiva independente.",
            ""]
    return "\n".join(lines)

def main():
    with tempfile.TemporaryDirectory() as folder:
        base=Path(folder)
        m26raw=base/"m26raw.csv";m26norm=base/"m26m5.csv"
        q26raw=base/"q26raw.csv";q26norm=base/"q26m5.csv"
        m26_source=m26_fetch(m26raw)
        m26=m26_canonicalize(m26raw,m26norm)
        q26_source=_fetch_pinned(RAW_Q26_URL,RAW_Q26_BLOB,q26raw)
        q26=canonicalize_q26_m5(q26raw,q26norm)
        output=study({"WINM26":m26,"WINQ26":q26},
                     {"WINM26":m26_source,"WINQ26":q26_source})
    text_report=report(output)
    print("ATLAS_V5_RANK_START",flush=True)
    print(text_report,flush=True)
    print("ATLAS_V5_RANK_END",flush=True)
    path=Path("research/results")
    path.mkdir(parents=True,exist_ok=True)
    (path/"atlas_v5_worst_to_best_latest.json").write_text(
        json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (path/"atlas_v5_worst_to_best_latest.md").write_text(text_report+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
