# FeedOracle Stablecoin Risk MCP Server

**Deterministic operational risk scoring for stablecoins — 7 signals, 100-point scale, 3 verdicts.**

[![Engine](https://img.shields.io/badge/engine-stablecoin--risk%2F1.0-blue)]()
[![MCP](https://img.shields.io/badge/protocol-MCP%20(SSE)-green)]()
[![Tools](https://img.shields.io/badge/tools-13-orange)]()
[![Coverage](https://img.shields.io/badge/stablecoins-28%2B-purple)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

> An [MCP](https://modelcontextprotocol.io/) server that gives AI agents real-time, evidence-grade stablecoin risk assessments. Built for regulated workflows — MiCA, DORA, CSRD.

---

## What It Does

Any MCP-compatible AI agent can connect to this server and ask:

- *"Is USDC safe to use as settlement collateral?"* → **SAFE (6/100), 96% confidence**
- *"Compare USDC vs USDT vs DAI for treasury operations"* → Side-by-side risk comparison
- *"Show me holder concentration for USDe"* → Top-holder %, HHI index, whale count
- *"Which stablecoins are safest right now?"* → Ranked leaderboard

No opinions. No financial advice. Just deterministic, auditable risk classification.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client (AI Agent)              │
│              Claude / GPT / Custom Agent             │
└──────────────────────┬──────────────────────────────┘
                       │ SSE (Model Context Protocol)
                       ▼
┌─────────────────────────────────────────────────────┐
│             feedoracle_mcp_risk.py                    │
│             13 MCP Tools · Port 5252                 │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           stablecoin_risk_engine.py                   │
│           7-Signal Scoring Engine                    │
│                                                      │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐ │
│  │   Peg   │ │Liquidity │ │ Holder │ │  Custody  │ │
│  │Stability│ │  Depth   │ │Concent.│ │Counterpty │ │
│  │  0-25   │ │  0-15    │ │  0-15  │ │   0-15    │ │
│  └────┬────┘ └────┬─────┘ └───┬────┘ └─────┬─────┘ │
│  ┌────┴────┐ ┌────┴─────┐ ┌───┴────┐               │
│  │Mint/Burn│ │Redemption│ │ Cross- │               │
│  │  Flow   │ │ Friction │ │ Chain  │               │
│  │  0-10   │ │   0-10   │ │  0-10  │               │
│  └─────────┘ └──────────┘ └────────┘               │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌────────────┐ ┌─────────┐ ┌──────────┐
   │ DefiLlama  │ │Etherscan│ │FeedOracle│
   │  (price,   │ │  V2     │ │  Internal│
   │  supply,   │ │(holders)│ │(peg mon.)│
   │  chains)   │ │         │ │          │
   └────────────┘ └─────────┘ └──────────┘
```

---

## Scoring System

**100-point scale** — lower is safer.

| Signal | Max Points | Weight | Data Source |
|---|---|---|---|
| Peg Stability | 25 | 25% | DefiLlama + FeedOracle Peg Monitor |
| Liquidity Depth | 15 | 15% | DefiLlama (mcap, volume) |
| Mint/Burn Flow | 10 | 10% | DefiLlama (7d supply delta) |
| Holder Concentration | 15 | 15% | Etherscan V2 (top holders) |
| Custody/Counterparty | 15 | 15% | FeedOracle Curated Registry |
| Redemption Friction | 10 | 10% | FeedOracle Curated Registry |
| Cross-Chain Risk | 10 | 10% | DefiLlama (chain breakdown) |

**Verdicts:**

| Verdict | Score Range | Meaning |
|---|---|---|
| 🟢 **SAFE** | 0–25 | Low operational risk |
| 🟡 **CAUTION** | 26–55 | Elevated risk, review recommended |
| 🔴 **AVOID** | 56–100 | High operational risk |

**Confidence** = 0.7 × data freshness + 0.3 × signal coverage (0.0–1.0)

---

## 13 MCP Tools

| Tool | Description |
|---|---|
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

The custody and redemption registries are hand-curated, research-backed datasets that no public API provides:

**Custody Registry** — 19 stablecoins with custodian names, SIFI classification, regulatory status, attestation type and freshness date.

**Redemption Registry** — 19 stablecoins with settlement speed, minimum amounts, fee structures, and institutional access restrictions.

Examples:

| Token | Custodians | SIFI | Attestation |
|---|---|---|---|
| USDC | BNY Mellon, BlackRock | ✅ | SOC2 + monthly |
| USDT | Cantor Fitzgerald | ❌ | Quarterly report |
| DAI | Decentralized | — | On-chain |
| BUIDL | BNY Mellon, BlackRock | ✅ | Daily NAV |
| USDe | Copper.co, Ceffu, Cobo | ❌ | Proof of reserves |

---

## Quick Start

### Prerequisites

- Python 3.10+
- `httpx` (async HTTP)
- `mcp` (MCP SDK)
- `starlette` + `uvicorn` (ASGI)

### Install

```bash
git clone https://github.com/FeedOracle/feedoracle-mcp-risk.git
cd feedoracle-mcp-risk
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your Etherscan API key
```

### Run

```bash
python feedoracle_mcp_risk.py
# Server starts on port 5252
# Health: http://localhost:5252/health
# SSE:    http://localhost:5252/sse
```

### Connect from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stablecoin-risk": {
      "url": "https://feedoracle.io/mcp/risk/sse"
    }
  }
}
```

### Production (systemd)

```bash
sudo cp systemd/feedoracle-mcp-risk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now feedoracle-mcp-risk
```

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
    "peg_stability":        { "score": 0,  "max": 25, "status": "STABLE" },
    "liquidity_depth":      { "score": 0,  "max": 15, "status": "STRONG" },
    "mint_burn_flow":       { "score": 2,  "max": 10, "status": "NORMAL" },
    "holder_concentration": { "score": 4,  "max": 15, "status": "MODERATE" },
    "custody_counterparty": { "score": 0,  "max": 15, "status": "KNOWN" },
    "redemption_friction":  { "score": 0,  "max": 10, "status": "LOW" },
    "cross_chain_risk":     { "score": 0,  "max": 10, "status": "DIVERSIFIED" }
  },
  "hint": "Operationally low-risk. Suitable for settlement workflows."
}
```

---

## Coverage

28+ stablecoins with varying signal depth:

**Full coverage** (all 7 signals): USDC, USDT, EURC, DAI, USDS, RLUSD, PYUSD, FRAX, LUSD, GHO, USDe, FDUSD, USD0, USDY, BUIDL, GUSD, USDP, BUSD, TUSD

**Market data only** (peg, liquidity, supply, chains): DOLA, crvUSD, sUSD, AUSD, M, USD1, EURE, EURT

---

## Live Endpoints

| Endpoint | URL |
|---|---|
| Health | `https://feedoracle.io/mcp/risk/health` |
| SSE | `https://feedoracle.io/mcp/risk/sse` |
| Messages | `https://feedoracle.io/mcp/risk/messages/` |

---

## Part of FeedOracle

This is one of three MCP servers in the [FeedOracle](https://feedoracle.io) ecosystem:

| Server | Port | Purpose |
|---|---|---|
| **Compliance Oracle** | 5250 | MiCA/DORA regulatory data |
| **Macro Oracle** | 5251 | Fed/ECB economic indicators |
| **Stablecoin Risk** | 5252 | Stablecoin operational risk scoring |

---

## Disclaimer

This tool provides **operational risk classification** — not financial advice. Verdicts are deterministic outputs of a scoring algorithm based on publicly available data and curated registries. Always perform your own due diligence.

---

## License

MIT — see [LICENSE](LICENSE)

Built by [FeedOracle](https://feedoracle.io) · Evidence infrastructure for tokenized markets.
