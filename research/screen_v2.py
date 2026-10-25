"""Pre-registered slower-timeframe strategy screening (2024-2026).

Data: observed 60-minute OHLC, aggregated to complete 4-hour bars.
Model: next-bar-open fills, conservative intrabar exits, fixed cost allowances,
0.5% planned stop risk, max 2x notional; NO FBS execution.
Selection uses only development period before 2025-10-24; later data not used
for candidate ranking. Caution: this period has already been inspected in
previous Nexus Quant research, so it is not truly unseen research.
"""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite
import json

from src.feed import MARKETS
from src.strategies import make_indicators
from research.backtest_year import get_history, COST_BPS

UTC=timezone.utc
def ts(date):
    return int(datetime.strptime(date,"%Y-%m-%d").replace(tzinfo=UTC).timestamp())

TRAIN_START=ts("2024-10-24")
CUTOFF=ts("2025-10-24")
TEST_END=ts("2026-10-25")
CAPITAL=5000.
RISK=0.005
MAX_LEVERAGE=2.
ATR_STOP=2.
ATR_TARGET=3.5
MAX_HOLD=90
MIN_TRADES=8
STRATEGIES=[
 "channel55", "channel20", "ema20_50", "ema50_200", "pullback20",
 "rsi_trend", "momentum40", "momentum100", "vol_breakout",
 "bollinger_revert", "trend_long_only",
]

def aggregate_hourly_to_h4(hourly):
    # Require four consecutive 60m candles, and no partial bars.
    buckets=defaultdict(list)
    for b in hourly:
        buckets[(int(b["time"])//14400)*14400].append(b)
    bars=[]
    for stamp in sorted(buckets):
        b=sorted(buckets[stamp],key=lambda r:r["time"])
        if len(b)!=4 or [v["time"] for v in b]!=[stamp+3600*k for k in range(4)]:
            continue
        bars.append({"time":stamp,"open":b[0]["open"],"high":max(v["high"] for v in b),
             "low":min(v["low"] for v in b),"close":b[-1]["close"]})
    return bars

def sign(strategy,b,ind,i):
    if i<240:return 0
    p=ind[i];q=ind[i-1];c=b[i]["close"];pc=b[i-1]["close"]
    bull=p["e50"]>p["e200"];bear=p["e50"]<p["e200"]
    r=p["rsi"];oldr=q["rsi"]
    if strategy=="channel55":
        if bull and c>p["upper55"] and p["atr"]>.6*p["avg_atr"]:return 1
        if bear and c<p["lower55"] and p["atr"]>.6*p["avg_atr"]:return -1
    if strategy=="channel20":
        if bull and c>p["upper20"] and p["atr"]>.8*p["avg_atr"]:return 1
        if bear and c<p["lower20"] and p["atr"]>.8*p["avg_atr"]:return -1
    if strategy=="ema20_50":
        if bull and q["e20"]<=q["e50"] and p["e20"]>p["e50"]:return 1
        if bear and q["e20"]>=q["e50"] and p["e20"]<p["e50"]:return -1
    if strategy=="ema50_200":
        if q["e50"]<=q["e200"] and bull:return 1
        if q["e50"]>=q["e200"] and bear:return -1
    if strategy=="pullback20":
        if bull and pc<q["e20"] and c>p["e20"] and 50<r<70:return 1
        if bear and pc>q["e20"] and c<p["e20"] and 30<r<50:return -1
    if strategy=="rsi_trend":
        if bull and oldr<=55 and r>55 and c>p["e20"]:return 1
        if bear and oldr>=45 and r<45 and c<p["e20"]:return -1
    if strategy=="momentum40":
        move=(c-b[i-40]["close"])/p["atr"] if p["atr"] else 0
        old=(pc-b[i-41]["close"])/q["atr"] if q["atr"] else 0
        if bull and old<=2 and move>2:return 1
        if bear and old>=-2 and move< -2:return -1
    if strategy=="momentum100":
        move=(c-b[i-100]["close"])/p["atr"] if p["atr"] else 0
        old=(pc-b[i-101]["close"])/q["atr"] if q["atr"] else 0
        if bull and old<=4 and move>4:return 1
        if bear and old>=-4 and move< -4:return -1
    if strategy=="vol_breakout":
        if b[i]["high"]-b[i]["low"]>1.35*p["atr"] and p["atr"]>p["avg_atr"]:
            if bull and c>b[i]["open"] and c>p["upper20"]:return 1
            if bear and c<b[i]["open"] and c<p["lower20"]:return -1
    if strategy=="bollinger_revert":
        flat=abs(p["e50"]/p["e200"]-1)<.012
        if flat and oldr<=30 and r>30 and c<p["band_lo"]:return 1
        if flat and oldr>=70 and r<70 and c>p["band_hi"]:return -1
    if strategy=="trend_long_only":
        if bull and c>p["upper55"] and p["e20"]>p["e50"]:return 1
    return 0

def evaluate(bars,inds,strategy,market,start,end,cost_multiplier=1.):
    # Closed positions are force-liquidated at boundary, so no train data PnL
    # crosses the cutoff.
    balance=CAPITAL;peak=CAPITAL;dd=0.;pos=None;trades=[];monthly=defaultdict(float)
    for i in range(241,len(bars)):
        row=bars[i];time=row["time"]
        if time<start:continue
        if time>=end:break
        current=row["open"]
        if pos:
            direction=pos["side"]
            stop=pos["stop"];target=pos["target"]
            if direction==1:
                stophit=row["low"]<=stop;targethit=row["high"]>=target
                stopfill=min(current,stop)
            else:
                stophit=row["high"]>=stop;targethit=row["low"]<=target
                stopfill=max(current,stop)
            reason=None
            if stophit:
                fill=stopfill;reason="stop"
            elif targethit:
                fill=target;reason="target"
            elif i-pos["opened_idx"]>=MAX_HOLD:
                fill=row["close"];reason="time"
            if reason:
                pnl=direction*(fill-pos["entry"])*pos["qty"]
                fee=cost_multiplier*COST_BPS[market]/10000*pos["qty"]*((fill+pos["entry"])/2)
                balance+=pnl-fee
                month=datetime.fromtimestamp(time,UTC).strftime("%Y-%m")
                monthly[month]+=pnl-fee
                trades.append({"entry_ts":pos["opened"],"exit_ts":time,"side":direction,
                 "pnl":round(pnl-fee,4),"fee":round(fee,4),"reason":reason})
                pos=None
        if pos is None and time>=start and time<end:
            s=sign(strategy,bars,inds,i-1)
            previous=sign(strategy,bars,inds,i-2)
            # Prevent continuous-signal churn: only a fresh crossing triggers.
            if s and s!=previous:
                atr=inds[i-1]["atr"]
                if isfinite(atr) and atr>0 and balance>0 and current>0:
                    amount=min(RISK*balance/(ATR_STOP*atr),MAX_LEVERAGE*balance/current)
                    if amount>0:
                        pos={"side":s,"entry":current,"opened":time,
                             "opened_idx":i,"qty":amount,
                             "stop":current-s*ATR_STOP*atr,
                             "target":current+s*ATR_TARGET*atr}
        unrealized=0
        if pos:
            unrealized=(row["close"]-pos["entry"])*pos["side"]*pos["qty"]
            unrealized-=COST_BPS[market]/10000*pos["qty"]*((row["close"]+pos["entry"])/2)*cost_multiplier
        equity=balance+unrealized
        peak=max(peak,equity)
        dd=max(dd,100*(peak-equity)/peak if peak>0 else 0)
    if pos:
        # Liquidate at the last observed bar strictly before evaluation boundary.
        eligible=[b for b in bars if start<=b["time"]<end]
        if eligible:
            last=eligible[-1];fill=last["close"]
            pnl=pos["side"]*(fill-pos["entry"])*pos["qty"]
            fee=cost_multiplier*COST_BPS[market]/10000*pos["qty"]*((fill+pos["entry"])/2)
            balance+=pnl-fee
            month=datetime.fromtimestamp(last["time"],UTC).strftime("%Y-%m")
            monthly[month]+=pnl-fee
            trades.append({"entry_ts":pos["opened"],"exit_ts":last["time"],
              "side":pos["side"],"pnl":round(pnl-fee,4),"fee":round(fee,4),"reason":"split_end"})
    wins=sum(t["pnl"]>0 for t in trades)
    grossgain=sum(t["pnl"] for t in trades if t["pnl"]>0)
    grossloss=-sum(t["pnl"] for t in trades if t["pnl"]<0)
    return {"trades":len(trades),"wins":wins,
      "win_pct":round(100*wins/len(trades),2) if trades else None,
      "pnl_usd":round(balance-CAPITAL,2),"return_pct":round((balance/CAPITAL-1)*100,2),
      "max_dd_pct":round(dd,2),"fees_usd":round(sum(t["fee"] for t in trades),2),
      "pf":round(grossgain/grossloss,3) if grossloss else None,
      "monthly":{k:round(v,2) for k,v in sorted(monthly.items())},
      "ledger":trades}

def training_gate(d):
    return (d["trades"]>=MIN_TRADES and d["return_pct"]>0 and
            (d["pf"] or 0)>=1.15 and d["max_dd_pct"]<=20)

def admission(d,double):
    # Only actual paper-monitor qualification for future research; NOT real money approval.
    return (d["trades"]>=MIN_TRADES and d["return_pct"]>0 and
            d["max_dd_pct"]<=15 and (d["pf"] or 0)>=1.1 and
            double["pnl_usd"]>0)

def render(result):
    lines=[
      "# Nexus Quant: pesquisa cronológica — H4, cinco mercados",
      "",
      "Não são resultados reais da FBS. Não há lucro garantido.",
      "",
      "**Desenvolvimento:** 24/10/2024–23/10/2025; **avaliação posterior:** 24/10/2025–24/10/2026.",
      "A janela posterior já foi examinada em pesquisa anterior: não é um holdout intocado.",
      "Regras escritas antes de executar esta comparação. Total de "+str(len(STRATEGIES)*len(MARKETS))+" candidatos.",
      "Candle H4 completo, entrada na abertura seguinte, stop 2 ATR, alvo 3,5 ATR, limite 90 barras, risco de 0,5% por operação, máximo 2x nocional.",
      "Custos de 3–10 pontos-base por ida e volta e teste adicional com custos dobrados. Não contempla execução FBS, rollover, swap, impostos.",
      "",
      "## Escolhidos EXCLUSIVAMENTE com dados de desenvolvimento",
      "",
      "| Mercado | Estratégia selecionada no desenvolvimento | Desenvolvimento | 12 meses seguintes | Drawdown posterior | Operações posteriores | Custos dobrados | Admissão |",
      "|---|---|---:|---:|---:|---:|---:|---|"]
    picks=result["selection"]
    for market in MARKETS:
        data=picks[market]
        if data["strategy"] is None:
            lines.append(f"| {market} | Nenhuma passou nos critérios de treino | — | — | — | — | — | Não |")
        else:
            tr=data["train"];te=data["test"];stress=data["cost_x2"]
            lines.append(f'| {market} | {data["strategy"]} | {tr["return_pct"]:+.2f}% | {te["return_pct"]:+.2f}% | '
              f'{te["max_dd_pct"]:.2f}% | {te["trades"]} | US$ {stress["pnl_usd"]:+,.2f} | '
              f'{"Sim, apenas para pesquisa futura" if data["admitted"] else "Não"} |')
    lines+=["", "## Cobertura dos candidatos por mercado", "",
      "| Mercado | Candidatos em treino positivos | Candidatos com treino aprovado | Candidatos positivos na avaliação |",
      "|---|---:|---:|---:|"]
    for m in MARKETS:
        a=[trial for trial in result["trials"] if trial["market"]==m]
        lines.append(f'| {m} | {sum(x["train"]["pnl_usd"]>0 for x in a)}/{len(a)} | '
        f'{sum(x["train_pass"] for x in a)}/{len(a)} | '
        f'{sum(x["test"]["pnl_usd"]>0 for x in a)}/{len(a)} |')
    lines+=["", "## Decisão",
      "",
      "**Não promover para dinheiro real nenhuma estratégia**. Mesmo uma candidata admitida para acompanhamento precisará de meses de operações novas, custos específicos da corretora, confiabilidade do feed e verificação regulatória.",
      "",
      "O arquivo JSON completo lista cada teste, sem ocultar as perdas.",
      "Fonte de preços: Yahoo Finance, câmbio indicativo e futuros contínuos de referência; não equivalem aos CFDs da FBS.",
      "Pesquisa acadêmica: Moskowitz/Ooi/Pedersen (2012), Bailey/López de Prado (2014)."
    ]
    return "\n".join(lines)+"\n"

def main():
    data={};indicators={};coverage={}
    for m,a in MARKETS.items():
        bars=aggregate_hourly_to_h4(get_history(a))
        if not bars or bars[0]["time"]>TRAIN_START+20*86400:
            raise RuntimeError(f"{m}: 2 anos incompletos, não fabricar amostra")
        ntrain=sum(TRAIN_START<=b["time"]<CUTOFF for b in bars)
        ntest=sum(CUTOFF<=b["time"]<TEST_END for b in bars)
        if min(ntrain,ntest)<850:
            raise RuntimeError(f"{m}: menos de 850 candles H4 em uma janela ({ntrain}/{ntest})")
        data[m]=bars;indicators[m]=make_indicators(bars)
        coverage[m]={"symbol":a.ticker,"h4_training_candles":ntrain,
                     "h4_eval_candles":ntest,"first_h4":bars[0]["time"],
                     "last_h4":bars[-1]["time"]}
        print(m,coverage[m],flush=True)
    trials=[]
    for m in MARKETS:
        for strat in STRATEGIES:
            train=evaluate(data[m],indicators[m],strat,m,TRAIN_START,CUTOFF)
            test=evaluate(data[m],indicators[m],strat,m,CUTOFF,TEST_END)
            doubled=evaluate(data[m],indicators[m],strat,m,CUTOFF,TEST_END,2)
            trial={"market":m,"strategy":strat,"train":train,"test":test,
                   "cost_x2":doubled,"train_pass":training_gate(train)}
            trials.append(trial)
            print(m,strat,"train",train["return_pct"],"test",test["return_pct"],
                  "n",test["trades"],flush=True)
    selection={}
    for m in MARKETS:
        all_choices=[x for x in trials if x["market"]==m and x["train_pass"]]
        # Deliberately select using train data only (not the later year's profits).
        if not all_choices:
            selection[m]={"strategy":None,"admitted":False}
            continue
        chosen=max(all_choices,key=lambda x:(x["train"]["return_pct"],
                                          -x["train"]["max_dd_pct"]))
        selection[m]={"strategy":chosen["strategy"],"train":chosen["train"],
                      "test":chosen["test"],"cost_x2":chosen["cost_x2"],
                      "admitted":admission(chosen["test"],chosen["cost_x2"])}
    result={"description":"Chronological research, not broker-executed trades",
      "source":"Yahoo Finance H1 bars aggregated to H4; indicative futures/FX",
      "research_is_not_truly_untouched":True,
      "training_range":["2024-10-24","2025-10-24"],
      "evaluation_range":["2025-10-24","2026-10-25"],
      "protocol":{"risk_fraction":RISK,"max_leverage":MAX_LEVERAGE,
        "stop_atr":ATR_STOP,"takeprofit_atr":ATR_TARGET,"max_holding_h4_bars":MAX_HOLD,
        "base_cost_bps":COST_BPS,"candidate_count":len(STRATEGIES)*len(MARKETS),
        "min_trades_train":MIN_TRADES},
      "coverage":coverage,"selection":selection,"trials":trials}
    dest=Path("research/results");dest.mkdir(parents=True,exist_ok=True)
    (dest/"strategy_screen_v2.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (dest/"strategy_screen_v2.md").write_text(render(result),encoding="utf8")
    print("STRATEGY_SCREEN_V2_COMPLETE",flush=True)

if __name__=="__main__":
    main()
