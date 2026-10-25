"""Somente pesquisa retrospectiva: resumo verificável de observações da nuvem NEXUS."""
from collections import Counter
from datetime import datetime, timezone

MARKET_FAMILIES = 27
MARKET_ALIAS = {
    "1x2": "match_odds", "btts": "both_teams_to_score",
    "over_under_05": "total_goals", "over_under_15": "total_goals",
    "over_under_25": "total_goals", "over_under_35": "total_goals",
    "over_under_45": "total_goals", "over_under_55": "total_goals",
    "over_under_65": "total_goals", "ah_0": "asian_handicap",
    "ah_m05": "asian_handicap", "ah_p05": "asian_handicap", "ah_m1": "asian_handicap",
}

def time_of(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None

def liquidity_status(observations):
    # Apenas volume negociado genuíno BRL com fonte, horário e tipo.
    below = False
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        item = obs.get("liquidity") or {}
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        if (not isinstance(amount, (int, float)) or isinstance(amount, bool)
                or item.get("currency") != "BRL"
                or item.get("kind") not in ("matched_volume", "total_matched")
                or not item.get("source") or time_of(item.get("observed_at")) is None):
            continue
        if item.get("status") == "qualified" and amount >= 3000:
            return "qualified"
        if item.get("status") == "below" and 0 <= amount < 3000:
            below = True
    return "below" if below else "unknown"

def quote_ok(quote, kickoff):
    if not isinstance(quote, dict) or not quote.get("source") or not quote.get("bookmaker"):
        return False
    try:
        odds = float(quote.get("odds"))
        start = float(kickoff)
    except (TypeError, ValueError, OverflowError):
        return False
    at = time_of(quote.get("captured_at"))
    if not (1.01 < odds < 1000) or at is None or at > datetime.now(timezone.utc).timestamp() + 120:
        return False
    if quote.get("scope") == "pregame":
        return at < start
    if quote.get("scope") == "live":
        return at >= start
    return False

def summarize(document, day):
    if not isinstance(document, dict) or document.get("day") != day:
        raise ValueError("Dia de coleta divergente")
    games = document.get("games")
    if not isinstance(games, dict):
        raise ValueError("Arquivo multimercado sem games")
    statuses, outcomes, markets, books = Counter(), Counter(), Counter(), Counter()
    prices, priced_games, qualified_quote_keys = set(), set(), set()
    finished = 0
    for match_id, record in games.items():
        if not isinstance(record, dict):
            continue
        snapshots = record.get("observations") or []
        if not isinstance(snapshots, list) or not snapshots:
            statuses["unknown"] += 1
            continue
        liq_status = liquidity_status(snapshots)
        statuses[liq_status] += 1
        last = snapshots[-1]
        settlement = last.get("settlement") or {}
        if (last.get("phase") == "finished" and isinstance(settlement, dict)
                and settlement.get("match_odds") in ("home", "draw", "away")):
            finished += 1
            outcomes["1x2_" + settlement["match_odds"]] += 1
            for field, label, cutoff in (("total_goals", "over_2_5", 2.5),
                                         ("total_corners", "corners_9_5", 9.5),
                                         ("total_yellow_cards", "cards_4_5", 4.5),
                                         ("total_shots_on_target", "sot_7_5", 7.5)):
                total = settlement.get(field)
                if isinstance(total, (int, float)) and not isinstance(total, bool):
                    outcomes[label + ("_yes" if total > cutoff else "_no")] += 1
            btts = settlement.get("both_teams_to_score")
            if isinstance(btts, bool):
                outcomes["btts_yes" if btts else "btts_no"] += 1
        for sample in snapshots:
            if not isinstance(sample, dict):
                continue
            for quote in sample.get("odds") or []:
                if not quote_ok(quote, record.get("kickoff_unix")):
                    continue
                key = (str(match_id), str(quote.get("market")), str(quote.get("selection")),
                       str(quote.get("source")), str(quote.get("bookmaker")),
                       str(quote.get("captured_at")), str(quote.get("scope")), float(quote["odds"]))
                if key in prices:
                    continue
                prices.add(key)
                if liq_status == "qualified":
                    qualified_quote_keys.add(key)
                priced_games.add(str(match_id))
                market = str(quote.get("market") or "unclassified")
                markets[MARKET_ALIAS.get(market, market)] += 1
                books[str(quote.get("bookmaker"))[:70]] += 1
    return {
        "schema": 2, "day": day, "generated_at": datetime.now(timezone.utc).isoformat(),
        "games": len(games), "finished": finished,
        "quotes_verified": len(prices), "games_with_verified_odds": len(priced_games),
        "qualified_game_quotes_verified": len(qualified_quote_keys),
        "liquidity_minimum_brl": 3000, "liquidity_qualified_games": statuses["qualified"],
        "liquidity_below_games": statuses["below"], "liquidity_unknown_games": statuses["unknown"],
        "market_families_catalogued": MARKET_FAMILIES,
        "market_families_with_verified_prices": len(markets),
        "market_families_quoted": dict(markets.most_common()),
        "bookmakers": dict(books.most_common()), "results": dict(outcomes),
        "note": "Estudo de mercado; não é lucro nem operação real."
    }
