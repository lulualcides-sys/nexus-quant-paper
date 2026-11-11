"""Daily Telegram roster for ALL distinct historically positive XAU signal families.

Reads only previously persisted PAPER books; archived historical profits are not
reported as current profits. Never places orders, imports broker credentials,
replays historical positions, or alters another strategy's journal.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Sao_Paulo')
ORIGINAL = Path('research/preserved/xau_all_positive_original_robots_20261110.json')
V8 = Path('research/preserved/xau_v8_all_positive_h4_snapshots_20261110.json')
MARKER = Path('state/xau_positive_daily_sent.json')
REPORTS = Path('reports/xau_positive_daily')
MAPPING = {
    'gold_h4:channel20': ('H4 Channel20', 'selected_gold_v2.json', 'channel20', 5000),
    'gold_h4:channel55': ('H4 Channel55', 'selected_gold_v2.json', 'channel55', 5000),
    'gold_h4:momentum100': ('H4 Momentum100', 'selected_gold_v2.json', 'momentum100', 5000),
    'gold_h4:pullback20': ('H4 Pullback20', 'selected_gold_v2.json', 'pullback20', 5000),
    'gold_h4:rsi_trend': ('H4 RSI Trend', 'selected_gold_v2.json', 'rsi_trend', 5000),
    'leveraged_h4:lev_channel20': ('H4 Channel20-L', 'leveraged_gold_v1.json', 'lev_channel20', 5000),
    'leveraged_h4:lev_channel55': ('H4 Channel55-L', 'leveraged_gold_v1.json', 'lev_channel55', 5000),
    'leveraged_h4:lev_momentum100': ('H4 Momentum100-L', 'leveraged_gold_v1.json', 'lev_momentum100', 5000),
    'leveraged_h4:lev_momentum40': ('H4 Momentum40-L', 'leveraged_gold_v1.json', 'lev_momentum40', 5000),
    'leveraged_h4:lev_trend_long': ('H4 Trend Long-L', 'leveraged_gold_v1.json', 'lev_trend_long', 5000),
    'experimental_h1:XAUUSD:ema20_retest': ('H1 EMA20 Retest', 'experimental_h1_v1.json', 'XAUUSD:ema20_retest', 1000),
    'experimental_h1:XAUUSD:channel10': ('H1 Channel10', 'experimental_h1_v1.json', 'XAUUSD:channel10', 1000),
    'experimental_h1:XAUUSD:rsi50': ('H1 RSI50', 'experimental_h1_v1.json', 'XAUUSD:rsi50', 1000),
    'momentum60_h4:momentum60': ('H4 Momentum60', 'momentum60_shadow_v1.json', None, 5000),
    # Historic M1 XAU adaptation is NOT the actual live USD/CAD BB20 engine.
    'usdcad_m15:bb20': ('M1 BB20 adaptado XAU', None, None, None),
}


def local_day(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(TZ).date().isoformat()


def roster(root: Path):
    older = json.loads((root / ORIGINAL).read_text(encoding='utf-8'))
    newer = json.loads((root / V8).read_text(encoding='utf-8'))
    if not (older.get('paper_only') is True and newer.get('paper_only') is True):
        raise ValueError('Archives are not paper-only')
    if older.get('archived_positive_scenario_slots') != 52 or newer.get('historical_positive_scenarios') != 30:
        raise ValueError('Positive archive counts changed; stop, do not silently omit families')
    original = {x.get('original_rule_id') or x['id']
                for snapshot in older['snapshots'] for x in snapshot['entries']}
    v8 = {'gold_h4:' + x['family'] for x in newer['entries']}
    all_keys = original | v8
    if all_keys != set(MAPPING):
        raise ValueError('Positive family roster not complete: ' + repr(sorted(all_keys ^ set(MAPPING))))
    if not original.issubset(all_keys) or len(original) != 14 or len(v8) != 5:
        raise ValueError('Historic strategy family mismatch')
    return sorted(all_keys), len(original), len(newer['entries'])


def read_book(root: Path, file_name: str, key: str | None):
    path = root / 'state' / file_name
    if not path.is_file():
        return None, None, 'estado ausente'
    state = json.loads(path.read_text(encoding='utf-8'))
    if state.get('paper_only') is not True:
        raise ValueError('Non-paper state refused: ' + file_name)
    if key is None:
        book = state
    else:
        book = (state.get('books') or {}).get(key)
    if not isinstance(book, dict):
        return None, None, 'livro ausente'
    if file_name == 'experimental_h1_v1.json':
        watermark = (state.get('watermarks') or {}).get('XAUUSD')
    else:
        watermark = state.get('h4_watermark')
    if not isinstance(watermark, int) or watermark <= 0:
        return None, None, 'timestamp de dados ausente'
    return book, watermark, None


def row_for_book(day, label, book, initial):
    closed = book.get('closed', [])
    if not isinstance(closed, list) or not isinstance(book.get('equity'), (float, int)):
        raise ValueError('Invalid virtual journal: ' + label)
    realized = [t for t in closed if local_day(t['exit_ts']) == day]
    entries = book.get('entries')
    # Count observed entries in the same virtual journal only, not backtest snapshots.
    stamps = ({int(x['entry_ts']) for x in entries} if isinstance(entries, list) else
              {int(x['entry_ts']) for x in closed})
    p = book.get('position')
    if p is not None:
        ts = p.get('start', p.get('entry_ts'))
        if ts is not None:
            stamps.add(int(ts))
    today_entries = sum(local_day(ts) == day for ts in stamps)
    today_pnl = sum(float(t['net_usd']) for t in realized)
    total = float(book['equity']) - initial
    pos = 'ABERTA' if p is not None else 'livre'
    return (f'{label}: {today_entries} ent., {len(realized)} saídas; '
            f'hoje {today_pnl:+.2f}; acum. {total:+.2f} USD; {pos}')


def build(day: str, root: Path, now: int):
    keys, orig_n, v8_n = roster(root)
    rows = [f'NEXUS GOLD | POSITIVOS NO HISTÓRICO | {day}',
            'PAPER APENAS — Yahoo GC=F; NÃO são ordens FBS.',
            f'52 cenários antigos ({orig_n} famílias) + {v8_n} V8 (5 famílias).',
            f'{len(keys)} famílias ÚNICAS. Lucro histórico NÃO entra no P/L diário.', '']
    available = 0; unavailable = []; fresh = []
    for ident in keys:
        label, filename, key, capital = MAPPING[ident]
        if filename is None:
            rows.append(f'PENDENTE {label}: adaptação histórica não tem livro XAU em acompanhamento.')
            unavailable.append(ident)
            continue
        book, stamp, error = read_book(root, filename, key)
        if error is not None:
            rows.append(f'INDISP. {label}: {error} — P/L desconhecido')
            unavailable.append(ident)
            continue
        # Stale data are not presented as confirmed *current* observation.
        age = now - stamp
        if age > 18 * 3600:
            freshness = ' [DADO ANTIGO]'
        else:
            freshness = ''
        if age < -3600:
            raise ValueError('Future watermark in paper state: ' + label)
        rows.append(row_for_book(day, label, book, capital) + freshness)
        available += 1
        fresh.append(stamp)
    rows.extend(['', f'Livros virtuais disponíveis {available}/{len(keys)}; pendentes/ausentes {len(unavailable)}.',
                 'Alguns sinais usam o mesmo ativo: NÃO somar saldos como carteira única.',
                 'Variantes M5 de saída e recortes M1/M15/M30 históricos NÃO são bots extras ativos.',
                 'Zero ordens reais; custo/execução da corretora não auditados.'])
    if fresh:
        earliest = datetime.fromtimestamp(min(fresh), timezone.utc).astimezone(TZ)
        rows.append('Candle mais antigo entre livros: ' + earliest.strftime('%d/%m %H:%M') + ' BRT')
    message = '\n'.join(rows)
    if len(message) > 3900:
        raise ValueError('Telegram positive roster over length limit')
    return message, {'day':day,'paper_only':True,'historical_snapshots_old':52,
                     'historical_snapshots_v8':30,'unique_families':len(keys),
                     'available':available,'unavailable':unavailable,
                     'data_watermark_min':min(fresh) if fresh else None}


def run(*, root=Path('.'), now=None, send=None):
    now = int(now if now is not None else datetime.now(timezone.utc).timestamp())
    day = local_day(now)
    marker_path = root / MARKER
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
        if marker.get('last_sent_day') == day:
            print('GOLD positive roster already sent:', day)
            return False
    message, metadata = build(day, root, now)
    if send is None:
        from src.runner import telegram
        send = telegram
    if not send(message):
        raise RuntimeError('Telegram did not confirm GOLD positive digest')
    report = root / REPORTS / (day + '.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps({'last_sent_day':day,'paper_only':True},indent=2)+'\n',encoding='utf-8')
    print('GOLD positive roster Telegram confirmed:',day,'families:',metadata['unique_families'])
    return True

if __name__ == '__main__':
    run()