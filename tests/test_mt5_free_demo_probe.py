"""Tests: official MT5 guest demo / fresh Windows terminal probe only.

Never register a fictitious identity, place a broker order, or treat
non-B3 demo instruments as WIN with classified trades.
"""
from pathlib import Path
import unittest
from types import SimpleNamespace

from research.probe_public_mt5_demo import summarize_visible
from research.probe_mt5_native_without_login import diagnose

class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO=0
    def __init__(self,*,initialize=True,connected=False,symbols=(),trade_mode=0):
        self.initialized=initialize
        self.connected=connected
        self.symbols=symbols
        self.mode=trade_mode
        self.shutdowns=0
        self.call_log=[]
    def initialize(self,*args,**kwargs):
        self.call_log.append("initialize")
        return self.initialized
    def terminal_info(self):
        return SimpleNamespace(connected=self.connected)
    def account_info(self):
        return SimpleNamespace(trade_mode=self.mode)
    def symbols_get(self,query):
        self.call_log.append("symbols_get")
        return [SimpleNamespace(name=s) for s in self.symbols]
    def symbol_info(self,name):
        self.call_log.append("symbol_info")
        return SimpleNamespace(trade_tick_size=5.) if name in self.symbols else None
    def shutdown(self):
        self.shutdowns+=1
    def order_send(self,*args,**kwargs):
        raise AssertionError("NO ORDER OF ANY KIND")
    def login(self,*args,**kwargs):
        raise AssertionError("NO ACCOUNT LOGIN OR FAKE ID")

class MT5DemoProbeTests(unittest.TestCase):
    def test_public_demo_page_requires_exact_win_contract_not_generic_word(self):
        a=summarize_visible("Demo trading MetaTrader WINTER demo portfolio")
        self.assertEqual(a["target_symbols_visible_text_only"],[])
        self.assertFalse(a["text_exposes_trade_by_trade_aggressor_flag"])
    def test_demo_page_can_detect_win_symbol_but_not_claim_b3_feed(self):
        a=summarize_visible("Trial, symbol WINZ26, BUY SELL")
        self.assertEqual(a["target_symbols_visible_text_only"],["WINZ26"])
        self.assertFalse(a["text_exposes_trade_by_trade_aggressor_flag"])
        self.assertTrue(a["visible_text_not_api_level_evidence"])
    def test_native_no_account_reports_not_connected(self):
        mt5=FakeMT5(initialize=False)
        d=diagnose(mt5,"C:\\test\\terminal64.exe")
        self.assertEqual(d["status"],"FRESH_MT5_COULD_NOT_INITIALIZE_ACCOUNT_OR_HEADLESS_ENVIRONMENT")
        self.assertEqual(mt5.shutdowns,1)
        self.assertNotIn("login",mt5.call_log)
        self.assertFalse(d["account_created_by_probe"])
    def test_native_initialized_but_not_connected_does_not_fetch_symbols(self):
        mt5=FakeMT5(connected=False)
        d=diagnose(mt5,"terminal64.exe")
        self.assertEqual(d["status"],"MT5_TERMINAL_OPEN_BUT_NO_BROKER_SESSION")
        self.assertNotIn("symbols_get",mt5.call_log)
    def test_native_connected_demo_with_no_win_is_not_win_data(self):
        mt5=FakeMT5(connected=True,symbols=["EURUSD","USDJPY"])
        d=diagnose(mt5,"terminal64.exe")
        self.assertTrue(d["account_type_is_demo"])
        self.assertEqual(d["status"],"CONNECTED_TO_DEMO_BUT_WINZ26_UNAVAILABLE")
        self.assertFalse(d["winz26_genuine_tick_history_confirmed"])
        self.assertNotIn("order_send",mt5.call_log)
    def test_even_symbol_name_and_5pt_is_not_proof_of_real_tick_flow(self):
        mt5=FakeMT5(connected=True,symbols=["WINZ26"])
        d=diagnose(mt5,"terminal64.exe")
        self.assertEqual(d["status"],"WINZ26_NAME_AND_5PT_GRID_SEEN_NOT_YET_AUTHENTICATED")
        self.assertFalse(d["winz26_genuine_tick_history_confirmed"])
        self.assertTrue(d["listed_requested_contract"])
    def test_static_security_no_secrets_or_order_apis(self):
        for name in ("research/probe_mt5_native_without_login.py",
                     "research/probe_public_mt5_demo.py"):
            s=Path(name).read_text(encoding="utf-8")
            for forbidden in ("order_send(", "order_check(", "mt5.login(",
                              "password=", "order_buy(", "order_sell(",
                              "credit_card", "username=", "phone="):
                self.assertNotIn(forbidden,s)
if __name__=="__main__":
    unittest.main()
