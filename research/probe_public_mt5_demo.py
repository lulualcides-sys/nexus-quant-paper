"""Safe exploration of official MetaQuotes WEB DEMO with no registration.

A browser demo is not a broker account, does not grant B3 WIN market data,
and cannot identify aggressor flags from screenshot text. No trades, no
credentials, no fake identity, no purchase, no scraping of exchange feeds.

Runs only on CI ephemeral headless Chrome to inspect public guest capability.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OFFICIAL="https://web.metatrader.app/terminal?lang=en&mode=demo"
TARGET_SYMBOLS=("WINZ26","WINV26","WINQ26")
BAN_WORDS=("password", "account number", "access token","session token")
def summarize_visible(text):
    """No raw terminal payload is saved; presence is not proof of quotes."""
    text=str(text or "")
    symbols=sorted({name for name in TARGET_SYMBOLS if re.search(
        r"(?<![A-Z0-9])"+re.escape(name)+r"(?![A-Z0-9])",text,re.I)})
    # WIN partial tokens cannot establish a live symbol or traded contract.
    return {
        "target_symbols_visible_text_only":symbols,
        "trial_or_demo_word_visible":bool(re.search(r"\b(?:DEMO|TRIAL|VIRTUAL)\b",text,re.I)),
        "login_or_registration_words_visible":bool(re.search(
            r"\b(?:LOGIN|REGISTER|SIGN IN|OPEN ACCOUNT|CREATE ACCOUNT)\b",text,re.I)),
        "buy_sell_button_words_visible":bool(re.search(r"\b(?:BUY|SELL)\b",text,re.I)),
        "text_exposes_trade_by_trade_aggressor_flag":bool(re.search(
            r"TICK_FLAG_(?:BUY|SELL)",text,re.I)),
        "visible_text_not_api_level_evidence":True,
    }

def run_browser_probe(*,output="research/results/mt5_official_guest_demo_probe.json"):
    result={
        "source":"OFFICIAL_METAQUOTES_WEB_GUEST_DEMO",
        "official_url":OFFICIAL,
        "no_identity_fabricated":True,"no_registration_attempted":True,
        "no_broker_orders":True,"no_account_credentials_collected":True,
        "win_volume_and_aggressor_history_verified":False,
        "eligibility_for_win_tracker_validation":False,
        "status":"NOT_STARTED",
    }
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=None
        errors=[]
        for channel in ("chrome","msedge"):
            try:
                browser=p.chromium.launch(channel=channel,headless=True,
                                          args=["--no-sandbox"])
                result["browser_channel"]=channel
                break
            except Exception as e:
                errors.append(type(e).__name__)
        if browser is None:
            result["status"]="NO_CHROME_BROWSER_AVAILABLE"
            result["browser_errors"]=errors
        else:
            try:
                page=browser.new_page(locale="en-US",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36")
                try:
                    page.goto(OFFICIAL,wait_until="domcontentloaded",timeout=60000)
                    page.wait_for_timeout(16000)
                    text=page.locator("body").inner_text(timeout=20000)
                    # Read-only: no clicking market orders, no buy, sell,
                    # registration or accepting any payments.
                    observation=summarize_visible(text)
                    result.update(observation)
                    result["status"]="GUEST_PAGE_READ_ONLY_OBSERVED"
                    result["page_url_is_official"]=page.url.startswith(
                        "https://web.metatrader.app/")
                    result["web_title_length"]=len(page.title())
                    result["win_symbol_observed_in_ui"]=bool(
                        observation["target_symbols_visible_text_only"])
                    result["b3_aggressor_ticks_confirmed"]=False
                except Exception as e:
                    result["status"]="WEB_DEMO_PAGE_NOT_READABLE"
                    result["browser_error_type"]=type(e).__name__
            finally:
                browser.close()
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OFFICIAL_MT5_WEB_DEMO_PROBE_START")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print("OFFICIAL_MT5_WEB_DEMO_PROBE_END")
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="research/results/mt5_official_guest_demo_probe.json")
    args=ap.parse_args()
    run_browser_probe(output=args.output)

if __name__=="__main__":
    main()
