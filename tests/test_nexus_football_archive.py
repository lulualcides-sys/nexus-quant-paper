import unittest
from src.nexus_football_archive import summarize, liquidity_status

class ArchiveQualityTests(unittest.TestCase):
    def test_mixed_quotes_and_liquidity(self):
        good = {"status": "qualified", "amount": 3550, "currency": "BRL",
                "kind": "matched_volume", "source": "Exchange API",
                "observed_at": "2026-10-25T12:00:00+00:00"}
        price = {"market": "btts", "selection": "yes", "odds": 1.95,
                 "source": "OddsPapi", "bookmaker": "Pinnacle",
                 "captured_at": "2026-10-25T10:00:00+00:00", "scope": "pregame"}
        archive = {"day": "2026-10-25", "games": {
            "g": {"kickoff_unix": 1793000000,
                  "observations": [
                    {"phase": "scheduled", "odds": [price], "liquidity": good},
                    {"phase": "finished", "odds": [price],
                     "liquidity": {"status": "unknown"}, "settlement": {
                         "match_odds": "home", "total_goals": 3,
                         "both_teams_to_score": True, "total_corners": 10}}
                  ]},
            "n": {"kickoff_unix": 1793000000,
                  "observations": [
                    {"phase": "finished", "odds": [], "settlement": {
                        "match_odds": "draw", "total_goals": 0,
                        "both_teams_to_score": False},
                     "liquidity": {"status": "unknown"}}
                  ]}
        }}
        data = summarize(archive, "2026-10-25")
        self.assertEqual(data["liquidity_qualified_games"], 1)
        self.assertEqual(data["liquidity_unknown_games"], 1)
        self.assertEqual(data["finished"], 2)
        self.assertEqual(data["results"]["over_2_5_yes"], 1)
        self.assertEqual(data["results"]["over_2_5_no"], 1)
        self.assertEqual(data["quotes_verified"], 1)
        self.assertNotIn("roi", data)

    def test_unknown_volume_is_not_three_thousand(self):
        self.assertEqual(liquidity_status([{"liquidity": {"amount": 10000,
                          "currency": "GBP", "kind": "matched_volume",
                          "source": "X", "observed_at": "2026-10-25T10:00:00Z",
                          "status": "qualified"}}]), "unknown")

if __name__ == "__main__":
    unittest.main()
