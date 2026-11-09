"""Other-contract replication on pinned WINJ26 M1 public Profit export.

Not an untouched holdout for strategy design; no real broker executions.
The source is an independent contract, not adjusted WINFUT. A sample with
<30 closed trades per candidate is explicitly labeled insufficient.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research.win_price_data import _number, _tick_check, read_win_csv, TZ
import research.win_price_action as pa
from research.win_price_action import Settings
from research.win_pa_variant_screen import candidate_variant

SYMBOL = "WINJ26"
SOURCE_URL = (
    "https://raw.githubusercontent.com/wesleyzilva/tradetech/main/"
    "dados/candles/2024-2025/WINJ26_F_0_1min.csv"
)
SOURCE_BLOB = "7fcc91ebde3e674f910ac82eef00b6bf19541151"


def read_source(path):
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent":"nexus-quant-research/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload=resp.read(1_500_000)
    if not payload or len(payload) >= 1_500_000:
        raise ValueError("WINJ26 source missing or bigger than download ceiling")
    git_hash=hashlib.sha1(b"blob "+str(len(payload)).encode()+b"\x00"+payload).hexdigest()
    if git_hash != SOURCE_BLOB:
        raise ValueError("WINJ26 source mutated; immutable hash mismatch")
    text=payload.decode("utf-8-sig",errors="replace")
    rows=[]
    for j,cells in enumerate(csv.reader(io.StringIO(text), delimiter=";"),1):
        if not cells or all(not q.strip() for q in cells):
            continue
        if cells[0].strip().lower()=="ativo":
            continue
        if len(cells)!=9:
            raise ValueError(f"Unexpected format at line {j}: {len(cells)} cells")
        symbol=cells[0].strip().upper()
        if symbol!=SYMBOL:
            raise ValueError(f"Unexpected instrument at line {j}: {symbol}")
        stamp=datetime.strptime(cells[1].strip()+" "+cells[2].strip(), "%d/%m/%Y %H:%M:%S")
        if stamp.replace(tzinfo=TZ).timestamp()>datetime.now(timezone.utc).timestamp():
            raise ValueError("Future timestamp")
        o,h,l,c=(_number(q) for q in cells[3:7])
        for price in (o,h,l,c):
            _tick_check(price)
        if l>min(o,c) or h<max(o,c) or l>h:
            raise ValueError("Inconsistent OHLC")
        volume=_number(cells[8])
        if int(volume)!=volume or volume<=0:
            raise ValueError("Non-integral quantity of contracts")
        rows.append((stamp,symbol,o,h,l,c,volume))
    rows.sort()
    if len(rows)<100:
        raise ValueError("Insufficient WINJ26 M1 prices")
    if any(rows[i][0]<=rows[i-1][0] for i in range(1,len(rows))):
        raise ValueError("Duplicate timestamps")
    p=Path(path)
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,delimiter=";")
        w.writerow(("Ativo","Data","Hora","Open","High","Low","Close","Volume"))
        for stamp,sym,o,h,l,c,qty in rows:
            w.writerow((sym,stamp.strftime("%d/%m/%Y"),stamp.strftime("%H:%M:%S"),int(o),int(h),int(l),int(c),int(qty)))
    imported=read_win_csv(p,expected_symbol=SYMBOL)
    return imported, {
        "url":SOURCE_URL,"git_blob_sha1":SOURCE_BLOB,
        "sha256":hashlib.sha256(payload).hexdigest(),
        "rows":len(rows),
        "start":rows[0][0].isoformat(),
        "end":rows[-1][0].isoformat(),
    }


def compare(bars, provenance):
    variant_specs = {
        "baseline":(Settings(), "baseline"),
        "break_only":(Settings(), "break_only"),
        "break_volume":(Settings(), "break_volume"),
        "break_rr1_5":(Settings(reward_risk=1.5), "break_rr1_5"),
    }
    result = {
        "status":"INDEPENDENT_CONTRACT_RESEARCH_NOT_LIVE_VALIDATION",
        "source":provenance,
        "market":"WINJ26",
        "note":"Different expiry from WINQ26; not a future chronological holdout",
        "one_contract_only":True, "capital_brl":2000,
        "estimated_roundtrip_cost":6, "daily_stop":False,
        "variants":{}, "approved_real_money":False,
    }
    original=pa.candidate
    for name,(cfg,variant) in variant_specs.items():
        outcomes={}
        for slip in (0,1,2):
            from dataclasses import replace
            with patch.object(pa,"candidate",side_effect=candidate_variant(original,variant)):
                stats=pa.simulate(bars,replace(cfg,slip_ticks_per_side=slip))
            outcomes[f"slip_{slip}"]={
                "trades":stats["closed"],"net_brl":stats["net_brl"],
                "winrate_pct":stats["win_rate_pct"],"profit_factor":stats["profit_factor"],
                "max_realized_drawdown_pct":stats["max_realized_drawdown_pct"],
                "max_sequential_reds":max((len(s) for s in "".join("L" if t["net_brl"]<0 else "W"
                                                    for t in stats["trades"]).split("W")),default=0),
                "sample_sufficient":stats["closed"]>=30,
                "open_at_end":stats["open_at_end"],
            }
        result["variants"][name]=outcomes
    return result


def markdown(result):
    lines = [
        "# Replicação do WIN Price Action no contrato WINJ26",
        "",
        "**Teste histórico em outro vencimento, sem execução real.**",
        f"- Arquivo original: {result['source']['url']}",
        f"- SHA1 fixo Git: {result['source']['git_blob_sha1']}",
        f"- Candles M1: {result['source']['rows']}; datas: {result['source']['start']} a {result['source']['end']}",
        "- Banca R$2.000; 1 WIN; custos assumidos R$4 por operação + 1 tick/lado na coluna-base; não há trava diária.",
        "",
        "| Variante | Trades (1 tick) | R$ líquido (1 tick) | PF (1 tick) | R$ líquido (2 ticks) | Amostra >=30? |",
        "|---|---:|---:|---:|---:|---|"
    ]
    for name,v in result["variants"].items():
        a,b=v["slip_1"],v["slip_2"]
        lines.append(
            f"| {name} | {a['trades']} | {a['net_brl']:+.2f} | "
            f"{a['profit_factor'] if a['profit_factor'] is not None else 'N/D'} | "
            f"{b['net_brl']:+.2f} | {'sim' if a['sample_sufficient'] else 'não'} |")
    lines += ["","Mesmo um resultado positivo não pode ser aprovado sem vários períodos, mais negócios, custos de corretora e teste prospectivo com ordens verificáveis.",
              "Qualidade de fonte: terceiros atribuem série ao Profit; negociação B3 não auditada de forma independente.",""]
    return "\n".join(lines)


def main():
    with tempfile.TemporaryDirectory() as td:
        data,prov=read_source(Path(td)/"WINJ26_M1.csv")
        result=compare(data["bars"],prov)
    out=Path("research/results");out.mkdir(parents=True,exist_ok=True)
    (out/"win_pa_winj26_research.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    md=markdown(result)
    (out/"win_pa_winj26_research.md").write_text(md+"\n",encoding="utf-8")
    print("WINJ26_REPLICATION_START",flush=True);print(md,flush=True);print("WINJ26_REPLICATION_END",flush=True)


if __name__=="__main__":
    main()
