<div align="center">

# FeedOracle Stablecoin Risk MCP

**Deterministic operational risk scoring for stablecoins.**

7 signals. 105+ tokens. SAFE / CAUTION / AVOID verdicts.

[![Server](https://img.shields.io/badge/server-live-10B898?style=flat-square)](https://feedoracle.io/mcp/risk/health)
[![Tools](https://img.shields.io/badge/tools-13-3B82F6?style=flat-square)](https://feedoracle.io/mcp.html)
[![Tokens](https://img.shields.io/badge/tokens-105+-8A9DB4?style=flat-square)](https://feedoracle.io)
[![Free](https://img.shields.io/badge/free-100_calls%2Fday-10B898?style=flat-square)](https://feedoracle.io/pricing.html)

[Website](https://feedoracle.io) · [All MCP Tools](https://feedoracle.io/mcp.html) · [Docs](https://feedoracle.io/docs.html) · [Main Repo](https://github.com/feedoracle/feedoracle-mcp)

</div>

---

## What this does

Any MCP-compatible AI agent can ask:

- *"Is USDC safe for settlement?"* → **SAFE** (6/100)
- *"Compare USDC vs USDT for treasury"* → Side-by-side risk comparison
- *"Which stablecoins are safest now?"* → Ranked leaderboard

No opinions. No financial advice. Deterministic, auditable risk classification. Every response cryptographically signed.

[![FeedOracle Risk MCP server](https://glama.ai/mcp/servers/feedoracle/-feedoracle-mcp-risk/badges/card.svg)](https://glama.ai/mcp/servers/feedoracle/-feedoracle-mcp-risk)

## Quick start

```bash
claude mcp add --transport sse feedoracle-risk https://feedoracle.io/mcp/risk/sse
```

No API key needed.

## 7-signal scoring

100-point scale – lower is safer.

| Signal | Weight | Source |
|--------|--------|--------|
| Peg Stability | 25% | DefiLlama + FeedOracle |
| Liquidity Depth | 15% | DefiLlama |
| Mint/Burn Flow | 10% | DefiLlama |
| Holder Concentration | 15% | Etherscan |
| Custody/Counterparty | 15% | Curated Registry |
| Redemption Friction | 10% | Curated Registry |
| Cross-Chain Risk | 10% | DefiLlama |

| Verdict | Score | Meaning |
|---------|-------|---------|
| SAFE | 0-25 | Low operational risk |
| CAUTION | 26-55 | Elevated, review recommended |
| AVOID | 56-100 | High operational risk |

## 13 tools

| Tool | Description |
|------|-------------|
| `risk_assessment` | Full 7-signal risk report with verdict |
| `peg_status` | Current peg deviation |
| `peg_history` | 30-day stability + depeg events |
| `supply_flow` | Mint/burn activity, anomaly detection |
| `holder_data` | Concentration, HHI, whale count |
| `custody_data` | Custodian, SIFI status, attestation |
| `redemption_data` | Settlement terms, fees, friction |
| `cross_chain_data` | Bridge exposure, chain distribution |
| `leaderboard` | Risk-ranked stablecoin list |
| `compare` | Side-by-side comparison (up to 5) |
| `supported_tokens` | All 105+ monitored tokens |
| `methodology` | Scoring model + data sources |
| `ping` | Health check |

## The FeedOracle ecosystem

| Server | Tools | Purpose |
|--------|-------|---------|
| [Compliance Oracle](https://github.com/feedoracle/feedoracle-mcp) | 27 | MiCA, DORA, evidence packs, audit trail |
| [Macro Intelligence](https://github.com/feedoracle/feedoracle-macro-mcp) | 13 | Fed/ECB indicators, regime classification |
| **Stablecoin Risk** (this) | 13 | 7-signal operational risk scoring |

---

<div align="center">

**FeedOracle turns compliance documents into compliance evidence.**

[feedoracle.io](https://feedoracle.io) · *Evidence by Design.*

</div>