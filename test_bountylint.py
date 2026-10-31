#!/usr/bin/env python3
"""Offline tests for bountylint. No network access required."""

import unittest
from datetime import datetime, timezone

import bountylint


class ParseAmountTests(unittest.TestCase):
    def test_short_hand_thousands(self):
        self.assertEqual(bountylint.parse_amount("[ Bounty $9k ] Solidity fix"), 9000)

    def test_plain_with_commas(self):
        self.assertEqual(bountylint.parse_amount("[BOUNTY] WearOS Support [$2,340]"), 2340)

    def test_currency_suffix(self):
        self.assertEqual(bountylint.parse_amount("reward: 750 USD on merge"), 750)

    def test_double_dollar_artifact(self):
        self.assertEqual(bountylint.parse_amount("Bounty Seguro ($$750)"), 750)

    def test_picks_largest(self):
        self.assertEqual(bountylint.parse_amount("$50 for triage, $500 for the fix"), 500)

    def test_none_and_noise(self):
        self.assertEqual(bountylint.parse_amount(""), 0)
        self.assertEqual(bountylint.parse_amount("help wanted, no money here"), 0)

    def test_ignores_tiny_amounts(self):
        self.assertEqual(bountylint.parse_amount("$1 coffee"), 0)


class TokenRewardTests(unittest.TestCase):
    def test_ticker_reward(self):
        text = "Bounty: 50,000 $ROBIN_MCP for implementing the native token"
        self.assertTrue(bountylint.looks_like_token_reward(text))

    def test_project_token_word(self):
        self.assertTrue(bountylint.looks_like_token_reward("Bounty: 200 RTC (~$20)"))

    def test_points_reward(self):
        self.assertTrue(bountylint.looks_like_token_reward("paid in tokens after review"))

    def test_stablecoin_is_cash(self):
        self.assertFalse(bountylint.looks_like_token_reward("Pays $500 in USDC"))

    def test_plain_cash(self):
        self.assertFalse(bountylint.looks_like_token_reward("[Bounty $9,000] fix accounting bug"))


class ReferenceTests(unittest.TestCase):
    def test_full_url(self):
        self.assertEqual(
            bountylint.parse_issue_reference("https://github.com/microg/GmsCore/issues/2340"),
            ("microg", "GmsCore", 2340),
        )

    def test_hash_form(self):
        self.assertEqual(bountylint.parse_issue_reference("microg/GmsCore#2340"), ("microg", "GmsCore", 2340))

    def test_repo_only_has_no_number(self):
        self.assertEqual(bountylint.parse_issue_reference("microg/GmsCore"), ("microg", "GmsCore", None))

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            bountylint.parse_issue_reference("not a repo")


class DaysSinceTests(unittest.TestCase):
    def test_known_delta(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(bountylint.days_since("2026-10-29T12:00:00Z", now), 2)

    def test_missing_and_bad(self):
        self.assertIsNone(bountylint.days_since(None))
        self.assertIsNone(bountylint.days_since("not-a-date"))


class PolicyTests(unittest.TestCase):
    def test_restrictive(self):
        policy, evidence = bountylint.classify_ai_policy(
            {"CONTRIBUTING.md": "We do not accept AI-generated pull requests."}
        )
        self.assertEqual(policy, "restricted")
        self.assertIn("CONTRIBUTING.md", evidence)

    def test_permissive(self):
        policy, _ = bountylint.classify_ai_policy({"README.md": "Autonomous agents are welcome here."})
        self.assertEqual(policy, "allowed")

    def test_unknown(self):
        policy, evidence = bountylint.classify_ai_policy({"README.md": "A tiny utility."})
        self.assertEqual((policy, evidence), ("unknown", ""))


class CommentSignalTests(unittest.TestCase):
    def test_claimants_are_deduplicated(self):
        comments = [
            {"user": {"login": "a"}, "body": "/claim"},
            {"user": {"login": "a"}, "body": "still working on this"},
            {"user": {"login": "b"}, "body": "assign me please"},
            {"user": {"login": "c"}, "body": "nice issue"},
        ]
        self.assertEqual(bountylint.count_claim_comments(comments), 2)

    def test_escrow_detected_from_bot(self):
        comments = [{"user": {"login": "algora-pbc"}, "body": "bounty is live"}]
        self.assertEqual(bountylint.find_escrow(comments), "algora-pbc")

    def test_escrow_detected_from_text(self):
        self.assertEqual(bountylint.find_escrow([], "This bounty is escrowed by the org"), "escrowed")

    def test_no_escrow(self):
        self.assertIsNone(bountylint.find_escrow([{"user": {"login": "human"}, "body": "hello"}]))


class RepoHealthTests(unittest.TestCase):
    def test_farm_shape_is_penalised(self):
        adjustments = bountylint.repo_health(
            {"stargazers_count": 14, "forks_count": 140, "license": None, "open_issues_count": 215},
            age_days=200,
        )
        deltas = [delta for delta, _ in adjustments]
        self.assertIn(-15, deltas)
        self.assertIn(-8, deltas)

    def test_mature_repo_is_rewarded(self):
        adjustments = bountylint.repo_health(
            {"stargazers_count": 15000, "forks_count": 3000, "license": {"spdx_id": "MIT"}}, age_days=4000
        )
        self.assertEqual(adjustments[0][0], 12)
        self.assertTrue(all(delta >= 0 for delta, _ in adjustments))


class ScoringTests(unittest.TestCase):
    def test_good_bounty_pursue(self):
        signals = {
            "amount_usd": 1500,
            "token_reward": False,
            "escrow": "algora-pbc",
            "is_open": True,
            "repo_adjustments": bountylint.repo_health(
                {"stargazers_count": 900, "forks_count": 120, "license": {"spdx_id": "MIT"}}, 900
            ),
            "comment_count": 1,
            "open_prs": 0,
            "claimants": 0,
            "updated_days": 2,
            "ai_policy": "allowed",
        }
        result = bountylint.score_issue(signals)
        self.assertEqual(result["verdict"], "PURSUE")
        self.assertGreaterEqual(result["score"], 65)

    def test_farm_bounty_avoid(self):
        signals = {
            "amount_usd": 9000,
            "token_reward": True,
            "escrow": None,
            "is_open": True,
            "repo_adjustments": bountylint.repo_health(
                {"stargazers_count": 14, "forks_count": 140, "license": None, "open_issues_count": 215}, 160
            ),
            "comment_count": 30,
            "open_prs": 2,
            "claimants": 3,
            "updated_days": 1,
            "ai_policy": "restricted",
        }
        result = bountylint.score_issue(signals)
        self.assertEqual(result["verdict"], "AVOID")
        self.assertLess(result["score"], 40)

    def test_score_is_bounded(self):
        signals = {
            "amount_usd": 5000,
            "token_reward": True,
            "escrow": None,
            "is_open": False,
            "repo_adjustments": [(-50, "worse than possible")],
            "comment_count": 100,
            "open_prs": 9,
            "claimants": 9,
            "updated_days": 400,
            "ai_policy": "restricted",
        }
        self.assertEqual(bountylint.score_issue(signals)["score"], 0)

    def test_no_payout_is_penalised(self):
        signals = {
            "amount_usd": 0,
            "token_reward": False,
            "escrow": None,
            "is_open": True,
            "repo_adjustments": [],
            "comment_count": 0,
            "open_prs": 0,
            "claimants": 0,
            "updated_days": 1,
            "ai_policy": "unknown",
        }
        result = bountylint.score_issue(signals)
        self.assertEqual(result["verdict"], "CAUTION")

    def test_contested_bounty_is_not_pursued(self):
        """A rich, escrowed bounty with 13 open PRs is busy work, not an opportunity."""
        signals = {
            "amount_usd": 2340,
            "token_reward": False,
            "escrow": "algora-pbc",
            "is_open": True,
            "repo_adjustments": bountylint.repo_health(
                {"stargazers_count": 15137, "forks_count": 3312, "license": {"spdx_id": "Apache-2.0"},
                 "open_issues_count": 1475},
                4000,
            ),
            "comment_count": 212,
            "open_prs": 13,
            "claimants": 4,
            "updated_days": 0,
            "ai_policy": "unknown",
        }
        result = bountylint.score_issue(signals)
        self.assertNotEqual(result["verdict"], "PURSUE")
        self.assertLess(result["score"], 65)

    def test_open_prs_penalty_is_capped(self):
        reasons = bountylint.score_issue(
            {
                "amount_usd": 100,
                "repo_adjustments": [],
                "comment_count": 0,
                "open_prs": 40,
                "claimants": 0,
                "updated_days": 1,
            }
        )["reasons"]
        pr_reason = next(r for r in reasons if "open PR" in r["reason"])
        self.assertEqual(pr_reason["delta"], -24)


class FakeGitHub:
    """Stands in for the network so analyse() is covered offline."""

    def issue(self, owner, repo, number):
        return {
            "title": "Improve CSV export",
            "body": "Bounty: $750 USD paid on merge.",
            "state": "open",
            "html_url": f"https://github.com/{owner}/{repo}/issues/{number}",
            "labels": [{"name": "bounty"}],
            "comments": 2,
            "updated_at": "2026-10-30T00:00:00Z",
        }

    def repository(self, owner, repo):
        return {
            "stargazers_count": 420,
            "forks_count": 40,
            "license": {"spdx_id": "MIT"},
            "archived": False,
            "created_at": "2023-01-01T00:00:00Z",
            "open_issues_count": 30,
        }

    def comments(self, owner, repo, number):
        return [{"user": {"login": "algora-pbc"}, "body": "bounty is funded"}]

    def open_pull_requests(self, owner, repo, number):
        return 0

    def file_text(self, owner, repo, path):
        return "Contributions welcome. AI-assisted contributions are welcome." if path == "README.md" else ""


class AnalyseTests(unittest.TestCase):
    def test_analyse_end_to_end_offline(self):
        result = bountylint.analyse(FakeGitHub(), "acme", "widgets", 7)
        self.assertEqual(result["url"], "https://github.com/acme/widgets/issues/7")
        self.assertEqual(result["amount_usd"], 750)
        self.assertEqual(result["ai_policy"], "allowed")
        self.assertEqual(result["escrow"], "algora-pbc")
        self.assertIn(result["verdict"], {"PURSUE", "CAUTION"})

    def test_detail_output_contains_reasons(self):
        text = bountylint.format_detail(bountylint.analyse(FakeGitHub(), "acme", "widgets", 7))
        self.assertIn("750", text)
        self.assertIn("reasons:", text)

    def test_table_output(self):
        table = bountylint.format_table([bountylint.analyse(FakeGitHub(), "acme", "widgets", 7)])
        self.assertIn("SCORE", table)
        self.assertIn("Improve CSV export", table)


NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


class SuperteamNormaliseTests(unittest.TestCase):
    def raw(self, **overrides):
        base = {
            "title": "Ship a Solana indexer",
            "slug": "ship-a-solana-indexer",
            "rewardAmount": 150000,
            "token": "USDC",
            "deadline": "2026-11-10T12:00:00.000Z",
            "agentAccess": "AGENT_ALLOWED",
            "sponsor": {"name": "Acme Labs"},
            "_count": {"Submission": 2},
        }
        base.update(overrides)
        return [base]

    def test_cents_are_converted_to_dollars(self):
        record = bountylint.normalise_superteam(self.raw(), now=NOW)[0]
        self.assertEqual(record["amount_usd"], 1500)

    def test_agent_access_is_normalised(self):
        record = bountylint.normalise_superteam(self.raw(), now=NOW)[0]
        self.assertEqual(record["agent_access"], "allowed")
        blocked = bountylint.normalise_superteam(self.raw(agentAccess="HUMAN_ONLY"), now=NOW)[0]
        self.assertEqual(blocked["agent_access"], "human_only")

    def test_non_cash_token_scores_zero_money(self):
        record = bountylint.normalise_superteam(self.raw(token="POINTS"), now=NOW)[0]
        self.assertEqual(record["amount_usd"], 0)

    def test_deadline_days_are_computed(self):
        record = bountylint.normalise_superteam(self.raw(), now=NOW)[0]
        self.assertEqual(record["deadline_days"], 10)

    def test_bad_deadline_is_unknown_not_a_crash(self):
        record = bountylint.normalise_superteam(self.raw(deadline="not-a-date"), now=NOW)[0]
        self.assertIsNone(record["deadline_days"])

    def test_url_is_built_from_slug(self):
        record = bountylint.normalise_superteam(self.raw(), now=NOW)[0]
        self.assertIn("ship-a-solana-indexer", record["url"])


class OpireNormaliseTests(unittest.TestCase):
    def test_cent_prices_are_converted(self):
        raw = [{"title": "Add export", "url": "https://github.com/a/b/issues/1",
                "pendingPrice": {"value": 4200, "unit": "USD_CENT"},
                "claimerUsers": [], "tryingUsers": [{"id": 1}],
                "organization": {"name": "acme"}, "project": {"isBotInstalled": False}}]
        record = bountylint.normalise_opire(raw, now=NOW)[0]
        self.assertEqual(record["amount_usd"], 42)
        self.assertEqual(record["competition"], 1)

    def test_dollar_prices_are_left_alone(self):
        raw = [{"title": "Add export", "pendingPrice": {"value": 300, "unit": "USD"}}]
        self.assertEqual(bountylint.normalise_opire(raw, now=NOW)[0]["amount_usd"], 300)


class ListingScoreTests(unittest.TestCase):
    def base(self, **overrides):
        record = {
            "source": "superteam", "title": "Write docs", "url": "https://x",
            "org": "acme", "amount_usd": 500, "currency": "USDC",
            "agent_access": "allowed", "kyc": None, "competition": 0,
            "deadline_days": 10, "policy_risk": False,
        }
        record.update(overrides)
        return record

    def test_clean_agent_job_is_pursued(self):
        result = bountylint.score_listing(self.base())
        self.assertEqual(result["verdict"], "PURSUE")
        self.assertGreaterEqual(result["score"], 65)

    def test_human_only_is_never_pursued(self):
        result = bountylint.score_listing(self.base(agent_access="human_only"))
        self.assertEqual(result["verdict"], "AVOID")

    def test_kyc_is_disqualifying(self):
        self.assertEqual(bountylint.score_listing(self.base(kyc=True))["verdict"], "AVOID")

    def test_policy_risk_is_disqualifying(self):
        result = bountylint.score_listing(self.base(policy_risk=True))
        self.assertEqual(result["verdict"], "AVOID")

    def test_expired_deadline_is_penalised(self):
        self.assertLess(
            bountylint.score_listing(self.base(deadline_days=-1))["score"],
            bountylint.score_listing(self.base(deadline_days=10))["score"],
        )

    def test_flooded_competition_drops_score(self):
        self.assertLess(
            bountylint.score_listing(self.base(competition=400))["score"],
            bountylint.score_listing(self.base(competition=0))["score"],
        )

    def test_score_is_clamped(self):
        worst = bountylint.score_listing(
            self.base(amount_usd=0, agent_access="human_only", kyc=True,
                      policy_risk=True, competition=999, deadline_days=-3)
        )
        self.assertGreaterEqual(worst["score"], 0)
        self.assertLessEqual(bountylint.score_listing(self.base())["score"], 100)

    def test_reasons_are_recorded(self):
        result = bountylint.score_listing(self.base())
        self.assertTrue(result["reasons"])
        self.assertTrue(all(isinstance(r[0], int) for r in result["reasons"]))

    def test_policy_risk_pattern_matches_captcha_work(self):
        self.assertTrue(bountylint.POLICY_RISK_RE.search("Auto Solve hcapcha"))
        self.assertTrue(bountylint.POLICY_RISK_RE.search("bypass the login wall"))

    def test_policy_risk_pattern_ignores_normal_work(self):
        self.assertIsNone(bountylint.POLICY_RISK_RE.search("Fix CSV export in the dashboard"))

    def test_radar_table_lists_both_platforms(self):
        rows = [bountylint.score_listing(self.base()),
                bountylint.score_listing(self.base(source="opire", title="Fix parser"))]
        table = bountylint.format_radar_table(rows)
        self.assertIn("superteam", table)
        self.assertIn("opire", table)
        self.assertIn("SCORE", table)


if __name__ == "__main__":
    unittest.main(verbosity=2)
