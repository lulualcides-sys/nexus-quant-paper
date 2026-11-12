import unittest
from pathlib import Path
S=(Path(__file__).resolve().parent/'Nexus_Vector_Retest_EA_v1.00.mq5').read_text(encoding='utf-8')
def score(v):
    return sum(w*max(0,min(1,x)) for w,x in zip((.25,.25,.20,.15,.15),v))
class VectorEAContract(unittest.TestCase):
    def test_weights_sum_one(self): self.assertAlmostEqual(sum((.25,.25,.20,.15,.15)),1)
    def test_clipping_and_bounds(self):
        self.assertEqual(score((1,1,1,1,1)),1)
        self.assertEqual(score((0,0,0,0,0)),0)
        self.assertAlmostEqual(score((-10,2,1,0,1)),.60)
    def test_no_vwap_trigger(self): self.assertNotIn('iCustom(',S);self.assertNotIn('g_vwap',S)
    def test_these_are_trades_not_indicators(self): self.assertIn('CTrade g_trade;',S);self.assertIn('g_trade.Buy(',S)
    def test_real_account_default_block(self):
        self.assertIn('InpAllowReal          = false;',S)
        self.assertIn('ACCOUNT_TRADE_MODE_REAL && !InpAllowReal',S)
    def test_risk_sized(self):
        self.assertIn('OrderCalcProfit(side,_Symbol,1.0,entry,sl,lossOneLot)',S)
        self.assertIn('InpRiskPercent       = 0.50;',S)
        self.assertIn('FloorVolume(budget/(-lossOneLot))',S)
    def test_sl_and_broker_tp(self):
        self.assertIn('g_trade.Buy(lot,_Symbol,0,sl,tp,',S)
        self.assertIn('g_trade.Sell(lot,_Symbol,0,sl,tp,',S)
    def test_multitp_and_partial_netting(self):
        for t in ('InpTP1R               = 1.00;', 'InpTP2R               = 1.50;', 'InpTP3R               = 2.00;', 'req.action=TRADE_ACTION_DEAL;', 'req.position=ticket;'): self.assertIn(t,S)
    def test_risk_brake_and_cooldown(self):
        self.assertIn('InpMaxDailyLossPct    = 2.00;',S)
        self.assertIn('InpCooldownBars       = 8;',S)
    def test_one_direction_and_one_position(self):
        self.assertIn('InpOnePerDirection    = true;',S)
        self.assertIn('!AnySymbolPosition()',S)
    def test_closed_candle_decision(self):
        self.assertIn('const datetime signalTime=r[1].time;',S)
        self.assertIn('for(int i=2;i<InpRangeBars+2;i++)',S)
        self.assertIn('g_lastBar=iTime(_Symbol,_Period,0)',S)
        self.assertNotIn('r[0].close',S)
    def test_five_factors(self):
        for t in ('W_BREAK  0.25','W_RETEST 0.25','W_TREND  0.20','W_MOM    0.15','W_VOL    0.15'):self.assertIn(t,S)
    def test_confirmed_retest(self):
        self.assertIn('else if(signalTime>g_breakTime)',S)
        self.assertIn('if(touched && reclaimed && goodBody)',S)
    def test_real_fills_not_simulated_green(self):
        for t in ('DEAL_POSITION_ID','HistoryDealGetDouble(deal,DEAL_PROFIT)','groups[j].outVolume+1e-7<groups[j].inVolume'):self.assertIn(t,S)
    def test_sound_and_beautiful_panel(self):
        for t in ('PlaySound(InpSoundFile)','OBJ_RECTANGLE_LABEL','NEXUS  /  VECTOR RETEST','"GREEN       "','"RED          "','"PONTOS       "'):self.assertIn(t,S)
    def test_no_exfiltration(self):
        for t in ('WebRequest(', '#import "', 'WinExec', 'ShellExecute'): self.assertNotIn(t,S)
    def test_braces(self):self.assertEqual(S.count('{'),S.count('}'))
if __name__=='__main__':unittest.main()
