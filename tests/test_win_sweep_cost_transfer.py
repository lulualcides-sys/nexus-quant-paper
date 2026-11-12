"""Deterministic tests of second-expiry source and fixed broker-cost scenarios."""
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from research.win_j26_pinned import canonicalize_payload,git_blob_hash
from research.win_sweep_cross_contract_costs import SCENARIOS,GATES,run_one


def source_rows(n=120,*,symbol="WINJ26",contracts=50):
    start=datetime(2025,8,22,9,10)
    header="Ativo;Data;Hora;Open;High;Low;Close;Volume;Quantidade\n"
    body=[]
    for i in range(n):
        x=start+timedelta(minutes=i)
        body.append(f"{symbol};{x:%d/%m/%Y};{x:%H:%M:%S};100000;100010;99990;100005;123456;{contracts}\n")
    return (header+"".join(body)).encode()


class WinTransferTests(unittest.TestCase):
    def test_pinned_hash_changes_with_one_bit(self):
        raw=source_rows()
        with tempfile.TemporaryDirectory() as tmp:
            canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))
            with self.assertRaisesRegex(ValueError,"pinned blob"):
                canonicalize_payload(raw+b"\n",Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))

    def test_parser_quantity_is_contracts_not_financial_volume(self):
        raw=source_rows()
        with tempfile.TemporaryDirectory() as tmp:
            data,prov=canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))
            self.assertEqual(data["symbol"],"WINJ26")
            self.assertEqual(len(data["bars"]),120)
            self.assertEqual(data["bars"][0]["volume"],50)
            self.assertEqual(data["timeframe_seconds"],60)
            self.assertEqual(prov["quantity_column"],"Quantidade")

    def test_legacy_profit_cp1252_headers_are_strictly_decoded(self):
        raw=source_rows().replace(b"Hora;", "Horário;".encode("cp1252"), 1)
        with tempfile.TemporaryDirectory() as tmp:
            data,provenance=canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))
            self.assertEqual(len(data["bars"]),120)
            self.assertEqual(provenance["git_blob_sha1"],git_blob_hash(raw))

    def test_reject_symbol_mismatch_even_with_matching_hash(self):
        raw=source_rows(symbol="WINQ26")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"wrong symbol"):
                canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))

    def test_reject_impossible_traded_quantity(self):
        raw=source_rows(contracts=-1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"invalid traded quantity"):
                canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))

    def test_unadjusted_tick_validation(self):
        raw=source_rows().replace(b"100010;99990;100005",b"100011;99990;100005",1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"grade"):
                canonicalize_payload(raw,Path(tmp)/"j26.csv",expect_hash=git_blob_hash(raw))

    def test_economic_fee_scenarios_and_base_are_distinct(self):
        self.assertEqual(round(SCENARIOS["old_r6_1tick"][0]+2*SCENARIOS["old_r6_1tick"][1],2),6.00)
        self.assertEqual(round(SCENARIOS["rico_no_rlp_1tick"][0]+2*SCENARIOS["rico_no_rlp_1tick"][1],2),3.40)
        self.assertEqual(round(SCENARIOS["rico_no_rlp_2tick"][0]+2*SCENARIOS["rico_no_rlp_2tick"][1],2),5.40)
        self.assertEqual(GATES,{"baseline":0.0,"min_net_rr_1":1.0})

    def test_empty_signal_fixture_proves_zero_not_profit(self):
        dt=datetime(2025,8,22,9,10,tzinfo=ZoneInfo("America/Sao_Paulo"))
        data=[{"time":int((dt+timedelta(minutes=i)).timestamp()),
               "open":100000.0,"high":100010.0,"low":99990.0,
               "close":100005.0,"volume":50.0}
              for i in range(110)]
        report=run_one(data,label="fixture")
        self.assertEqual(len(report["variants"]),8)
        self.assertFalse(any(x["research_sufficient"] for x in report["variants"].values()))
        self.assertTrue(all(x["net_brl"]==0 and x["trades"]==0 for x in report["variants"].values()))


if __name__ == "__main__":
    unittest.main()
