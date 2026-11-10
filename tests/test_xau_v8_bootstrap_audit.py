import unittest
from datetime import datetime,timezone,timedelta
from research.xau_v8_bootstrap_audit import bootstrap_days,format_markdown


class V8BootstrapTests(unittest.TestCase):
    def sample(self,n=30):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        return [{'exit_ts':int((start+timedelta(days=i)).timestamp()),'net':(-20 if i%3==0 else 15)} for i in range(n)]
    def test_determinism(self):
        a=bootstrap_days(self.sample(),samples=500,seed=20261110)
        b=bootstrap_days(self.sample(),samples=500,seed=20261110)
        self.assertEqual(a,b)
    def test_ledger_total(self):
        x=bootstrap_days(self.sample(),samples=100)
        self.assertAlmostEqual(x['observed_net'],sum(r['net'] for r in self.sample()))
        self.assertEqual(x['trades'],30)
    def test_insufficient_days_not_made_up(self):
        x=bootstrap_days(self.sample(3),samples=100)
        self.assertEqual(x['status'],'too_few_exit_days')
        self.assertIsNone(x['interval_95'])
    def test_refuses_small_bootstrap(self):
        with self.assertRaises(ValueError):bootstrap_days(self.sample(),samples=10)

if __name__=='__main__':unittest.main()