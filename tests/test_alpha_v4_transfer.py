"""Source allow-list regression only; synthetic data cannot prove trading profit."""
import unittest
from unittest.mock import patch
from research.alpha_v4.data import MONTHS,TRANSFER_MONTHS,month
from research.alpha_v4.transfer import SYMBOL,SLIPS
from research.alpha.run import BOTS

class TransferTests(unittest.TestCase):
    def test_new_months_reach_network_gate_not_unapproved_month(self):
        for m in TRANSFER_MONTHS:
            with patch("research.alpha_v4.data.retrieve",
                       side_effect=RuntimeError("network-simulated")):
                with self.assertRaisesRegex(RuntimeError,"network-simulated"):
                    month(SYMBOL,m)

    def test_original_holdout_unchanged(self):
        self.assertEqual(MONTHS,("2026-07","2026-08","2026-09","2026-10"))
        self.assertEqual(TRANSFER_MONTHS,("2026-01","2026-02","2026-03",
                                          "2026-04","2026-05","2026-06"))
        self.assertEqual(len(BOTS),10)
        self.assertEqual(SLIPS,(0.,5.,10.))

if __name__=="__main__":
    unittest.main()
