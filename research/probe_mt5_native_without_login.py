"""Accountless MT5 Windows probe; never invent credentials.

Does NOT create a demo account (no documented Python API for it).
Does NOT place any orders or trade virtual currency. Observes whether a
fresh genuine MetaTrader 5 terminal spontaneously has a connected demo,
and if connected whether the correct B3 contract WINZ26 exists.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def diagnose(mt5, path):
    results={
        "probe":"FRESH_OFFICIAL_MT5_NATIVE_WITHOUT_LOGIN",
        "credentials_entered":False,
        "account_created_by_probe":False,
        "no_orders_sent":True,
        "winz26_genuine_tick_history_confirmed":False,
        "tracker_original_reproduced":False,
        "status":"NOT_CONNECTED",
    }
    try:
        initialized=bool(mt5.initialize(path,timeout=20000))
        results["terminal_initialized"]=initialized
        if not initialized:
            results["status"]="FRESH_MT5_COULD_NOT_INITIALIZE_ACCOUNT_OR_HEADLESS_ENVIRONMENT"
            return results
        info=mt5.terminal_info()
        connected=bool(info is not None and info.connected)
        results["terminal_connected_to_server"]=connected
        if not connected:
            results["status"]="MT5_TERMINAL_OPEN_BUT_NO_BROKER_SESSION"
            return results
        acc=mt5.account_info()
        if acc is not None:
            results["account_type_is_demo"]=(
                acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
            )
            # Never display account numbers, names, passwords or balances.
        symbols=mt5.symbols_get("WIN*")
        results["number_win_prefixed_symbols"]=len(symbols or [])
        results["listed_requested_contract"]=any(
            s.name.upper()=="WINZ26" for s in (symbols or [])
        )
        symbol=mt5.symbol_info("WINZ26")
        if symbol is None:
            results["status"]="CONNECTED_TO_DEMO_BUT_WINZ26_UNAVAILABLE"
        elif abs(float(symbol.trade_tick_size)-5.)>1e-8:
            results["status"]="A_SYMBOL_NAMED_WINZ26_EXISTS_BUT_NOT_B3_5PT"
        else:
            # Trade/event tick availability still requires explicit
            # server provision and validation of actual flags/volumes.
            results["status"]="WINZ26_NAME_AND_5PT_GRID_SEEN_NOT_YET_AUTHENTICATED"
            results["winz26_symbol_visible"]=True
    except Exception as error:
        results["status"]="MT5_CLIENT_PROBE_FAILED"
        results["exception_type"]=type(error).__name__
    finally:
        try:mt5.shutdown()
        except Exception:pass
    return results

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--terminal-exe",required=True)
    p.add_argument("--output",default="research/results/mt5_native_accountless_probe.json")
    args=p.parse_args()
    import MetaTrader5 as mt5
    result=diagnose(mt5,args.terminal_exe)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MT5_ACCOUNTLESS_PROBE_START")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print("MT5_ACCOUNTLESS_PROBE_END")

if __name__=="__main__":
    main()
