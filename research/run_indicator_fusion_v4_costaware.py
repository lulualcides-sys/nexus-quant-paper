"""Run V4 XAU GOLD lot+spread feasibility; never broker orders."""
from __future__ import annotations
import json,hashlib
from datetime import datetime, timezone
from pathlib import Path
from research.atlas_mtf_comparison import download_m5
from research.indicator_fusion_v4_costaware import run


def main():
    bars=download_m5()
    snapshot_sha=hashlib.sha256(json.dumps(bars,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result=run(bars)
    result['observed_bars_sha256']=snapshot_sha
    result['run_utc']=datetime.now(timezone.utc).isoformat()
    for name,x in result['cost_scenarios'].items():
        print('V4',name,'trades',x['closed_trades'],'monthly_rate_est',x['trades_per_30_calendar_days_estimate'],
              'net',x['net_usd'],'gross',x['gross_usd'],'fees',x['fees_usd'],
              'dd',x['max_realized_drawdown_pct'],'per_bot',x['entered_by_type'],flush=True)
    print('V4_FOLDS',result['folds'],flush=True)
    print('V4_ABLATION',result['posthoc_ablation_no_momentum'],flush=True)
    path=Path('research/results/indicator_fusion_v4_costaware_latest.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('V4_WRITTEN',path,flush=True)

if __name__=='__main__':main()