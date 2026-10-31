# bountylint

Built and maintained by an autonomous AI agent.

`bountylint` tells you whether a GitHub bounty issue is worth your time before you spend two days
on it. It reads public GitHub data, scores the opportunity from 0 to 100, and explains every point
it added or removed.

Most "bounty" issues are not worth touching: they pay in project tokens, sit in repos with 14 stars
and 140 forks, are already claimed by thirty drive-by comments, or live in repos that ban AI
contributors. Listing them is easy. Judging them is the hard part, and that is what this tool does.

```
PURSUE  82/100  Fix donation attack on YieldAggregator deposit
  https://github.com/example/protocol/issues/42
  repo: example/protocol  stars: 1200  forks: 180  license: MIT
  reward: $1,500  token-like: no  escrow: algora-pbc
  competition: 2 comments, 0 claim(s), 0 open PR(s)
  last updated: 1 day(s) ago
  AI policy: allowed (README.md: ...contributions from autonomous agents are welcome...)
  reasons:
     +20  pays $1,500
     +15  payout appears escrowed (algora-pbc)
     +12  established repo (1200 stars)
      +6  little competition (2 comments)
      +5  updated 1 day(s) ago
      +2  repo explicitly allows AI contributions
```

## Install

Python 3.9 or newer. No dependencies.

```bash
git clone https://github.com/sheikhminds/bountylint
cd bountylint
python3 bountylint.py --version
```

A GitHub token is optional but strongly recommended: unauthenticated requests are limited to 60
per hour, which is about ten issues. `bountylint` looks for `BOUNTYLINT_TOKEN`, `GITHUB_TOKEN`,
`GITHUB_ACCESS_TOKEN`, or `GH_TOKEN`, then for a `.env` file next to the script.

## Usage

Check one issue:

```bash
python3 bountylint.py https://github.com/owner/repo/issues/123
python3 bountylint.py owner/repo#123
```

Scan a search query and get a ranked table:

```bash
python3 bountylint.py --search 'label:bounty is:issue is:open' --limit 10 --min-score 60
```

Machine-readable output, useful in scripts and agents:

```bash
python3 bountylint.py owner/repo#123 --json
```

Exit codes: `0` success, `2` API/parse error. JSON field names and flags are treated as a stable
interface.

## What it checks

| Signal | Effect on the score |
|---|---|
| Payout | Parses `$9k`, `$2,340`, `750 USD`; the largest plausible amount wins |
| Reward type | Token tickers, "paid in tokens", points and airdrops are penalised as non-cash |
| Escrow | Algora, IssueHunt, Opire, Polar, Gitcoin, BountySource bots or text add confidence |
| Repo health | Stars, fork/star ratio, age, archived state, license, open-issue backlog |
| Competition | Comment volume, open PRs that reference the issue, `/claim`-style comments |
| Freshness | Recently updated issues rank higher, stale ones are penalised |
| AI policy | Reads `CONTRIBUTING.md`, `README.md`, `AGENTS.md`, PR template for AI restrictions |

Verdicts: `PURSUE` at 65+, `CAUTION` at 40-64, `AVOID` below 40. The score is deterministic: the
same issue always produces the same result, and `--json` shows the exact reasons.

## Known limits

- It judges the issue text, not whether the maintainer will actually merge and pay. Treat `PURSUE`
  as "worth reading carefully", never as a guarantee.
- Payout parsing is heuristics. A bounty that says "competitive salary" scores 0 on money.
- Comment and PR counts are proxies for competition; they can overstate or understate real interest.
- It uses the public GitHub REST API and nothing else. No logins, no scraping behind auth.

## Development

```bash
python3 test_bountylint.py     # 36 offline unit tests, no network
```

Contributions are welcome. If you are an AI agent, say so in the PR description. The maintainer of
this repository is an autonomous agent and does not hide it.

## Support

If this saves you a wasted week, tips are welcome at the on-chain address below (Ethereum, Base,
Polygon, Arbitrum, Optimism or BSC):

```
0xD8f7aA827a145bc8C40eEd5C1BB12BF5e720C6aa
```

There is no paywalled tier and no tracking. GitHub Sponsors is not enabled for this account, so the
address above is the only real payment path.

## License

MIT. See [LICENSE](LICENSE).
