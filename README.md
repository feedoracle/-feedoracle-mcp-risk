# FeedOracle Stablecoin Risk MCP Server

Deterministic operational risk scoring for stablecoins — 7 signals, 100-point scale, 3 verdicts.

An MCP server that gives AI agents real-time, evidence-grade stablecoin risk assessments. Built for regulated workflows — MiCA, DORA, RWA.

## What It Does

Any MCP-compatible AI agent can connect and ask:

- *"Is USDC safe to use as settlement collateral?"* → **SAFE** (6/100), 96% confidence
- *"Compare USDC vs USDT vs DAI for treasury operations"* → Side-by-side risk comparison
- *"Show me holder concentration for USDe"* → Top-holder %, HHI index, whale count
- *"Which stablecoins are safest right now?"* → Ranked leaderboard

No opinions. No financial advice. Just deterministic, auditable risk classification.

## Quick Connect

```json
{
  "mcpServers": {
    "stablecoin-risk": {
      "url": "https://feedoracle.io/mcp/risk/sse"
    }
  }
}
```

---

## Scoring System

100-point scale — **lower is safer.**

| Signal | Max Points | Weight | Data Source |
|--------|-----------|--------|-------------|
| Peg Stability | 25 | 25% | DefiLlama + FeedOracle Peg Monitor |
| Liquidity Depth | 15 | 15% | DefiLlama (mcap, volume) |
| Mint/Burn Flow | 10 | 10% | DefiLlama (7d supply delta) |
| Holder Concentration | 15 | 15% | Etherscan V2 (top holders) |
| Custody/Counterparty | 15 | 15% | FeedOracle Curated Registry |
| Redemption Friction | 10 | 10% | FeedOracle Curated Registry |
| Cross-Chain Risk | 10 | 10% | DefiLlama (chain breakdown) |

**Verdicts:**

| Verdict | Score | Meaning |
|---------|-------|---------|
| 🟢 SAFE | 0–25 | Low operational risk |
| 🟡 CAUTION | 26–55 | Elevated risk, review recommended |
| 🔴 AVOID | 56–100 | High operational risk |

---

## 13 MCP Tools

| Tool | Description |
|------|-------------|
| `ping` | Server connectivity and engine version |
| `risk_assessment` | Full 7-signal risk report with verdict and hint |
| `peg_status` | Current price deviation from peg |
| `peg_history` | 30-day peg stability with depeg events |
| `supply_flow` | Mint/burn analysis — 7-day supply changes |
| `holder_data` | Concentration metrics — HHI, top-holder %, whale count |
| `custody_data` | Custodian profile — SIFI status, attestation freshness |
| `redemption_data` | Redemption terms — settlement, fees, minimums |
| `cross_chain_data` | Chain distribution and bridge exposure |
| `leaderboard` | Ranked stablecoins by risk score |
| `compare` | Side-by-side comparison (up to 5 tokens) |
| `supported_tokens` | List all covered stablecoins |
| `methodology` | Scoring methodology and data sources |

---

## Curated Registries (Our Moat)

Hand-curated datasets that no public API provides:

| Token | Custodians | SIFI | Attestation |
|-------|-----------|------|-------------|
| USDC | BNY Mellon, BlackRock | ✅ | SOC2 + monthly |
| USDT | Cantor Fitzgerald | ❌ | Quarterly report |
| DAI | Decentralized | — | On-chain |
| BUIDL | BNY Mellon, BlackRock | ✅ | Daily NAV |
| USDe | Copper.co, Ceffu, Cobo | ❌ | Proof of reserves |

---

## Example Output

### `risk_assessment("USDC")`

```json
{
  "symbol": "USDC",
  "risk_score": 6,
  "verdict": "SAFE",
  "confidence": 0.96,
  "engine_version": "stablecoin-risk/1.0",
  "signals": {
    "peg_stability":        { "score": 0, "max": 25, "status": "STABLE" },
    "liquidity_depth":      { "score": 0, "max": 15, "status": "STRONG" },
    "mint_burn_flow":       { "score": 2, "max": 10, "status": "NORMAL" },
    "holder_concentration": { "score": 4, "max": 15, "status": "MODERATE" },
    "custody_counterparty": { "score": 0, "max": 15, "status": "KNOWN" },
    "redemption_friction":  { "score": 0, "max": 10, "status": "LOW" },
    "cross_chain_risk":     { "score": 0, "max": 10, "status": "DIVERSIFIED" }
  },
  "hint": "Operationally low-risk. Suitable for settlement workflows."
}
```

---

## Coverage

**Full 7 signals:** USDC, USDT, EURC, DAI, USDS, RLUSD, PYUSD, FRAX, LUSD, GHO, USDe, FDUSD, USD0, USDY, BUIDL, GUSD, USDP, BUSD, TUSD

**Market data only:** DOLA, crvUSD, sUSD, AUSD, M, USD1, EURE, EURT

---

## Live Endpoints

| Endpoint | URL |
|----------|-----|
| Health | https://feedoracle.io/mcp/risk/health |
| SSE | https://feedoracle.io/mcp/risk/sse |
| Messages | https://feedoracle.io/mcp/risk/messages/ |

---

## The FeedOracle MCP Ecosystem

| Server | URL | Purpose |
|--------|-----|---------|
| **Compliance Oracle** | `https://feedoracle.io/mcp/` | MiCA/DORA regulatory data + AI Evidence Layer (22 tools) |
| **Macro Oracle** | `https://feedoracle.io/mcp/macro/` | Fed/ECB economic indicators, 86 FRED series |
| **Stablecoin Risk** (this) | `https://feedoracle.io/mcp/risk/` | 7-signal stablecoin operational risk scoring |

> "May your agent trade this?" → Compliance Oracle  
> "Should your agent trade right now?" → Macro Oracle  
> "Is this stablecoin safe for settlement?" → Stablecoin Risk (this server)

---

**Disclaimer:** Operational risk classification only — not financial advice. Always perform your own due diligence.

**License:** MIT — see LICENSE

Built by [FeedOracle](https://feedoracle.io) · Evidence infrastructure for tokenized markets.
