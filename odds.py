#!/usr/bin/env python3
"""
surebets_global.py — Surebets Over/Under (totals) con las principales ligas del mundo.
Filtra por casas accesibles en Perú (Betsson, Pinnacle, Coolbet, etc.).

Ejemplo:
    pip install requests
    python surebets_global.py --bankroll 300 --min-roi 0.3
"""

import argparse
import sys
from typing import Dict, List, Tuple, Any
import requests

API_KEY = "90c10370e72b2e0880972b196f12e50c"
API_BASE = "https://api.the-odds-api.com/v4"

PERU_BOOKMAKERS = [
    "betsson", "onexbet", "coolbet", "pinnacle", "marathonbet",
    "williamhill", "betonlineag", "mybookieag", "everygame", "betanysports"
]

# Ligas principales del mundo 🌍
GLOBAL_LEAGUES = [
    # Internacionales
    "soccer_fifa_world_cup",
    # "soccer_uefa_champions_league",
    "soccer_uefa_europa_league",
    # "soccer_uefa_conference_league",
    "soccer_conmebol_copa_libertadores",
    # Europa
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    # "soccer_efl_championship", 
    "soccer_fa_cup",
    # América
    "soccer_brazil_campeonato", "soccer_argentina_primera_division",
    # "soccer_mexico_liga_mx", 
    "soccer_usa_mls", "soccer_chile_campeonato",
    # "soccer_peru_primera_division"
]

def effective_decimal_odds(odds: float, commission_pct: float = 0.0) -> float:
    return odds if commission_pct <= 0 else odds * (1 - commission_pct / 100.0)

def fetch_totals(api_key: str, sport_key: str, bookmakers: List[str]) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "markets": "totals",
        "oddsFormat": "decimal",
        "bookmakers": ",".join(bookmakers),
        "dateFormat": "iso",
    }
    r = requests.get(url, params=params, timeout=25)
    if r.status_code != 200:
        print(f"[{sport_key}] Error HTTP {r.status_code}: {r.text[:100]}", file=sys.stderr)
        return []
    return r.json()

def best_over_under_by_line(event: Dict[str, Any], commission_pct: float = 0.0) -> Dict[float, Dict[str, Tuple[str, float]]]:
    by_line: Dict[float, Dict[str, Tuple[str, float]]] = {}
    for book in event.get("bookmakers", []):
        book_name = book.get("title") or book.get("key") or "unknown"
        for market in book.get("markets", []):
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name")
                price = outcome.get("price")
                point = outcome.get("point")
                if name not in ("Over", "Under") or price is None or point is None:
                    continue
                eff_odds = effective_decimal_odds(float(price), commission_pct)
                # line = float(point)
                line = round(float(point), 2)
                if line not in by_line:
                    by_line[line] = {}
                prev = by_line[line].get(name)
                if prev is None or eff_odds > prev[1]:
                    by_line[line][name] = (book_name, eff_odds)
    return {ln: sides for ln, sides in by_line.items() if "Over" in sides and "Under" in sides}

def compute_surebet(odds_over: float, odds_under: float):
    K = (1.0 / odds_over) + (1.0 / odds_under)
    return (K < 1.0), K

def stake_split(bankroll: float, odds_over: float, odds_under: float):
    K = (1.0 / odds_over) + (1.0 / odds_under)
    stake_over = bankroll * (1.0 / odds_over) / K
    stake_under = bankroll * (1.0 / odds_under) / K
    payout = bankroll / K
    profit = payout - bankroll
    return stake_over, stake_under, payout, profit

def human_roi(profit: float, bankroll: float) -> float:
    return 0.0 if bankroll <= 0 else (profit / bankroll) * 100.0

def scan_sport(sport_key: str, bookmakers: List[str], commission_pct: float,
               bankroll: float, min_roi: float, verbose: bool) -> int:
    events = fetch_totals(API_KEY, sport_key, bookmakers)
    if not events:
        return 0
    count = 0
    for ev in events:
        home = ev.get("home_team", "Home")
        away = ev.get("away_team", "Away")
        title = f"{home} vs {away}"
        ko = ev.get("commence_time", "?")
        by_line = best_over_under_by_line(ev, commission_pct)
        for line, sides in sorted(by_line.items()):
            book_over, odds_over = sides["Over"]
            book_under, odds_under = sides["Under"]
            is_sure, K = compute_surebet(odds_over, odds_under)
            if not is_sure:
                continue
            s_over, s_under, payout, profit = stake_split(bankroll, odds_over, odds_under)
            roi = human_roi(profit, bankroll)
            if roi >= min_roi:
                count += 1
                print("=" * 70)
                print(f"SPORT: {sport_key} | EVENT: {title} | KO: {ko}")
                print(f"LINE: {line:+.1f} totals (Over/Under)")
                print(f"Over:  {odds_over:.3f} @ {book_over}")
                print(f"Under: {odds_under:.3f} @ {book_under}")
                print(f"K = {K:.6f}  → SUREBET ✅")
                print(f"Stake split (bankroll {bankroll:.2f}): Over={s_over:.2f} | Under={s_under:.2f}")
                print(f"Payout: {payout:.2f}  | Profit: {profit:.2f}  | ROI: {roi:.2f}%")
                if verbose:
                    print(f"DEBUG: event_id={ev.get('id')}")
    return count

def parse_args():
    p = argparse.ArgumentParser(description="Surebets globales Over/Under con principales ligas del mundo.")
    p.add_argument("--sports", nargs="+", default=GLOBAL_LEAGUES, help="Lista de ligas a escanear.")
    p.add_argument("--bankroll", type=float, default=100.0, help="Capital total.")
    p.add_argument("--min-roi", type=float, default=0.0, help="ROI mínimo para mostrar.")
    p.add_argument("--commission", type=float, default=0.0, help="Comisión (%%).")
    p.add_argument("--bookmakers", type=str, default="", help="Lista manual de casas (coma).")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug.")
    return p.parse_args()

def main():
    args = parse_args()
    bm = [b.strip() for b in args.bookmakers.split(",") if b.strip()] or PERU_BOOKMAKERS
    total = 0
    for sport in args.sports:
        found = scan_sport(sport, bm, args.commission, args.bankroll, args.min_roi, args.verbose)
        total += found
    if total == 0:
        print("⚠️ No se encontraron surebets con los filtros actuales. Intenta en horario de jornada o baja --min-roi.")

if __name__ == "__main__":
    main()
