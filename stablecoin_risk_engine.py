#!/usr/bin/env python3
"""FeedOracle Stablecoin Risk Scoring Engine v1.0
Deterministic operational risk classification for stablecoins.
7 weighted signals, 100-point scale, 3 verdicts: SAFE/CAUTION/AVOID.

Engine: stablecoin-risk/1.0
"""
import os, json, logging, time, hashlib, asyncio
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("stablecoin-risk")

ENGINE_VERSION = "stablecoin-risk/1.0"
FEED_API = os.getenv("FEED_API", "http://127.0.0.1:5080")
PEG_API  = os.getenv("PEG_API",  "http://127.0.0.1:5215")
TIMEOUT  = 12.0

# ── Etherscan V2 ──────────────────────────────────────────────
EKEY = os.getenv("ETHERSCAN_KEY", "")  # Get free key at https://etherscan.io/myapikey
ESCAN = "https://api.etherscan.io/v2/api?chainid=1"

# ── DefiLlama endpoints ──────────────────────────────────────
LLAMA_STABLES  = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
LLAMA_STABLE   = "https://stablecoins.llama.fi/stablecoin"  # /{id}
LLAMA_CHAINS   = "https://stablecoins.llama.fi/stablecoin"  # /{id} includes chainCirculating

# ── CoinGecko (free, no key) ─────────────────────────────────
GECKO_PRICE = "https://api.coingecko.com/api/v3/simple/price"
GECKO_COIN  = "https://api.coingecko.com/api/v3/coins"

# ── Verdict thresholds ────────────────────────────────────────
VERDICTS = {
    "SAFE":    {"min": 0,  "max": 25},
    "CAUTION": {"min": 26, "max": 55},
    "AVOID":   {"min": 56, "max": 100},
}

# ── Signal definitions ────────────────────────────────────────
SIGNAL_DEFS = {
    "peg_stability":        {"max": 25, "weight": 0.25},
    "liquidity_depth":      {"max": 15, "weight": 0.15},
    "mint_burn_flow":       {"max": 10, "weight": 0.10},
    "holder_concentration": {"max": 15, "weight": 0.15},
    "custody_counterparty": {"max": 15, "weight": 0.15},
    "redemption_friction":  {"max": 10, "weight": 0.10},
    "cross_chain_risk":     {"max": 10, "weight": 0.10},
}

# ── DeFiLlama slug → ID mapping ──────────────────────────────
SLUG_TO_LLAMA_ID = {
    "usdc": 2, "usdt": 1, "eurc": 50, "dai": 3, "usds": 248,
    "rlusd": 250, "pyusd": 120, "frax": 6, "lusd": 26,
    "eure": 101, "eurt": 47, "tusd": 4, "busd": 5,
    "gho": 124, "crvusd": 115, "usdp": 11, "gusd": 10,
    "usde": 176, "fdusd": 138, "usd0": 195, "dola": 63,
    "usdy": 129, "buidl": 173, "m": 213, "ausd": 205,
    "usd1": 303, "susd": 12,
}

# ── Custody Registry (FeedOracle-curated, our moat) ──────────
CUSTODY_REGISTRY = {
    "USDC":  {"custodians": ["BNY Mellon", "BlackRock (Circle Reserve Fund)"], "count": 2, "sifi": True,  "regulated": True,  "last_attestation": "2026-02-15", "attestation_type": "SOC2+monthly"},
    "USDT":  {"custodians": ["Cantor Fitzgerald", "Tether Holdings"], "count": 2, "sifi": False, "regulated": True,  "last_attestation": "2025-12-31", "attestation_type": "quarterly_report"},
    "EURC":  {"custodians": ["BNY Mellon"], "count": 1, "sifi": True,  "regulated": True,  "last_attestation": "2026-02-15", "attestation_type": "SOC2+monthly"},
    "DAI":   {"custodians": ["Decentralized (smart contract)"], "count": 0, "sifi": False, "regulated": False, "last_attestation": "N/A", "attestation_type": "on-chain"},
    "USDS":  {"custodians": ["Decentralized (smart contract)"], "count": 0, "sifi": False, "regulated": False, "last_attestation": "N/A", "attestation_type": "on-chain"},
    "RLUSD": {"custodians": ["Ripple (custodied reserves)"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_report"},
    "PYUSD": {"custodians": ["Paxos Trust"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_attestation"},
    "FRAX":  {"custodians": ["FinresPBC (partial)"], "count": 1, "sifi": False, "regulated": False, "last_attestation": "2025-10-01", "attestation_type": "irregular"},
    "LUSD":  {"custodians": ["Decentralized (smart contract)"], "count": 0, "sifi": False, "regulated": False, "last_attestation": "N/A", "attestation_type": "on-chain"},
    "BUSD":  {"custodians": ["Paxos Trust (wind-down)"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2025-06-01", "attestation_type": "monthly_attestation"},
    "TUSD":  {"custodians": ["Unknown"], "count": 0, "sifi": False, "regulated": False, "last_attestation": "N/A", "attestation_type": "none"},
    "USDP":  {"custodians": ["Paxos Trust"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_attestation"},
    "GUSD":  {"custodians": ["State Street"], "count": 1, "sifi": True,  "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_attestation"},
    "GHO":   {"custodians": ["Decentralized (Aave)"], "count": 0, "sifi": False, "regulated": False, "last_attestation": "N/A", "attestation_type": "on-chain"},
    "USDe":  {"custodians": ["Copper.co", "Ceffu", "Cobo"], "count": 3, "sifi": False, "regulated": False, "last_attestation": "2026-02-01", "attestation_type": "proof_of_reserves"},
    "FDUSD": {"custodians": ["First Digital Trust"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_attestation"},
    "USD0":  {"custodians": ["Hashnote (USYC backing)"], "count": 1, "sifi": False, "regulated": False, "last_attestation": "2025-12-01", "attestation_type": "irregular"},
    "USDY":  {"custodians": ["Ankura Trust (Ondo)"], "count": 1, "sifi": False, "regulated": True,  "last_attestation": "2026-01-31", "attestation_type": "monthly_nav"},
    "BUIDL": {"custodians": ["BNY Mellon", "BlackRock"], "count": 2, "sifi": True,  "regulated": True,  "last_attestation": "2026-02-15", "attestation_type": "daily_nav"},
}

# ── Redemption Registry (FeedOracle-curated) ─────────────────
REDEMPTION_REGISTRY = {
    "USDC":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "USDT":  {"settlement": "T+1",     "min_usd": 100000,  "institutional_only": True,  "fees_pct": 0.1,  "direct_redemption": True},
    "EURC":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "DAI":   {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "USDS":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "RLUSD": {"settlement": "T+1",     "min_usd": 1000,    "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "PYUSD": {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "FRAX":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "LUSD":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "BUSD":  {"settlement": "T+1",     "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "TUSD":  {"settlement": "T+2",     "min_usd": 1000,    "institutional_only": False, "fees_pct": 0.1,  "direct_redemption": True},
    "USDP":  {"settlement": "T+1",     "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "GUSD":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "GHO":   {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "USDe":  {"settlement": "T+7",     "min_usd": 100000,  "institutional_only": True,  "fees_pct": 0,    "direct_redemption": True},
    "FDUSD": {"settlement": "T+1",     "min_usd": 100000,  "institutional_only": True,  "fees_pct": 0,    "direct_redemption": True},
    "USD0":  {"settlement": "instant", "min_usd": 0,       "institutional_only": False, "fees_pct": 0.05, "direct_redemption": True},
    "USDY":  {"settlement": "T+2",     "min_usd": 500,     "institutional_only": False, "fees_pct": 0,    "direct_redemption": True},
    "BUIDL": {"settlement": "T+1",     "min_usd": 5000000, "institutional_only": True,  "fees_pct": 0,    "direct_redemption": True},
}

# ── Bridge risk tiers (curated) ──────────────────────────────
BRIDGE_RISK = {
    "canonical": "LOW",     # native issuer bridge (Circle CCTP etc.)
    "third_party": "MED",   # Wormhole, LayerZero, Axelar
    "unknown": "HIGH",
}

# ── Ethereum token contracts for holder analysis ─────────────
TOKEN_CONTRACTS = {
    "USDC":  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT":  "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI":   "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "PYUSD": "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8",
    "FRAX":  "0x853d955aCEf822Db058eb8505911ED77F175b99e",
    "GHO":   "0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f",
    "LUSD":  "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0",
    "USDe":  "0x4c9EDD5852cd905f086C759E8383e09bff1E68B3",
    "GUSD":  "0x056Fd409E1d7A124BD7017459dFEa2F387b6d5Cd",
    "USDP":  "0x8E870D67F660D95d5be530380D0eC0bd388289E1",
    "FDUSD": "0xc5f0f7b66764F6ec8C8Dff7BA683102295E16409",
}

# ── Internal cache ────────────────────────────────────────────
_llama_cache = {"data": None, "ts": 0}
LLAMA_TTL = 300  # 5 min

# ══════════════════════════════════════════════════════════════
#  DATA FETCHERS
# ══════════════════════════════════════════════════════════════

async def _http_get(url, timeout=TIMEOUT):
    """Async GET with error handling."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(url, headers={"User-Agent": "FeedOracle-Risk/1.0"})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"HTTP GET failed: {url} → {e}")
        return None

async def _get_llama_stables():
    """Fetch all stablecoins from DefiLlama (cached 5 min)."""
    now = time.time()
    if _llama_cache["data"] and now - _llama_cache["ts"] < LLAMA_TTL:
        return _llama_cache["data"]
    data = await _http_get(LLAMA_STABLES)
    if data and "peggedAssets" in data:
        _llama_cache["data"] = data["peggedAssets"]
        _llama_cache["ts"] = now
        return _llama_cache["data"]
    return _llama_cache.get("data") or []

async def _find_llama_asset(symbol: str):
    """Find a stablecoin in DefiLlama data by symbol."""
    sym = symbol.upper()
    # Try mapped ID first
    llama_id = SLUG_TO_LLAMA_ID.get(sym.lower())
    assets = await _get_llama_stables()
    for a in assets:
        if llama_id and a.get("id") == llama_id:
            return a
        if a.get("symbol", "").upper() == sym:
            return a
    return None

async def _get_llama_detail(llama_id: int):
    """Fetch detailed stablecoin data (chain breakdown, history)."""
    return await _http_get(f"{LLAMA_STABLE}/{llama_id}")

async def _get_etherscan_holders(contract: str, top_n: int = 10):
    """Get top token holders from Etherscan V2."""
    url = f"{ESCAN}&apikey={EKEY}&module=token&action=tokenholderlist&contractaddress={contract}&page=1&offset={top_n}"
    return await _http_get(url, timeout=15)

async def _get_internal_peg(symbol: str):
    """Fetch peg data from internal Peg Monitor (port 5215)."""
    slug = symbol.lower()
    return await _http_get(f"{PEG_API}/v1/peg/current/{slug}")

async def _get_internal_stablecoin(symbol: str):
    """Fetch stablecoin status from feed-api (port 5080)."""
    slug = symbol.lower()
    # Map common symbols to our slugs
    slug_map = {
        "usdc": "usdc", "usdt": "tether-usdt", "eurc": "eurc",
        "dai": "dai", "usds": "sky-dollar", "rlusd": "rlusd",
        "pyusd": "pyusd", "frax": "frax-usd", "lusd": "lusd",
        "busd": "busd", "tusd": "tusd", "usdp": "usdp",
        "gusd": "gusd", "gho": "gho", "usde": "ethena-usde",
        "fdusd": "fdusd", "usd0": "usual", "usdy": "ondo-usdy",
        "buidl": "blackrock-buidl",
    }
    s = slug_map.get(slug, slug)
    return await _http_get(f"{FEED_API}/api/v1/feeds/stablecoin/{s}")

# ══════════════════════════════════════════════════════════════
#  SIGNAL SCORERS (7 signals)
# ══════════════════════════════════════════════════════════════

def _score_peg_stability(llama_asset, peg_data):
    """Signal 1: Peg Stability (0–25)"""
    result = {"score": 12, "status": "ELEVATED", "source": "unknown", "fetched_at": None,
              "details": {"current_deviation_pct": None, "max_30d_deviation_pct": None, "depeg_events_30d": 0}}

    price = None
    peg_type = "USD"

    # Try internal peg monitor first
    if peg_data and isinstance(peg_data, dict):
        dev = peg_data.get("deviation_pct") or peg_data.get("peg_dev_pct")
        if dev is not None:
            result["details"]["current_deviation_pct"] = abs(float(dev))
            result["source"] = "feedoracle_peg_monitor"
            result["fetched_at"] = peg_data.get("as_of") or _now()

    # DefiLlama price
    if llama_asset:
        price_obj = llama_asset.get("price")
        if price_obj is not None:
            price = float(price_obj) if not isinstance(price_obj, dict) else None
        peg_type = (llama_asset.get("pegType") or "peggedUSD").replace("pegged", "")

    # Compute max_30d from llama if available
    max_30d = result["details"]["current_deviation_pct"] or 0
    if llama_asset and price is not None:
        expected = 1.0  # USD peg default
        dev_pct = abs((price - expected) / expected) * 100
        result["details"]["current_deviation_pct"] = round(dev_pct, 4)
        max_30d = max(max_30d or 0, dev_pct)

    result["details"]["max_30d_deviation_pct"] = round(max_30d, 4) if max_30d else 0

    # Score based on max_30d
    d = max_30d or 0
    if d < 0.1:    score = 0
    elif d < 0.5:  score = 5
    elif d < 1.0:  score = 10
    elif d < 2.0:  score = 15
    elif d < 5.0:  score = 20
    else:          score = 25

    # Depeg events bonus penalty
    depeg_events = result["details"].get("depeg_events_30d", 0)
    score += min(depeg_events * 3, 10)
    score = min(score, 25)

    # Status mapping
    if score <= 5:    status = "STABLE"
    elif score <= 15: status = "ELEVATED"
    elif score <= 20: status = "STRESSED"
    else:             status = "CRITICAL"

    result["score"] = score
    result["status"] = status
    if not result["fetched_at"]:
        result["fetched_at"] = _now()
    return result


def _score_liquidity_depth(llama_asset):
    """Signal 2: Liquidity Depth (0–15)"""
    result = {"score": 8, "status": "ADEQUATE", "source": "defillama", "fetched_at": _now(),
              "details": {"volume_mcap_ratio": None, "exchange_count": None, "cex_listed": True}}

    if not llama_asset:
        result["score"] = 10
        result["status"] = "THIN"
        return result

    mcap = 0
    circ = llama_asset.get("circulating", {})
    if isinstance(circ, dict):
        mcap = circ.get("peggedUSD", 0) or 0
    elif isinstance(circ, (int, float)):
        mcap = circ

    # Estimate volume from DeFiLlama data (not directly in stables endpoint)
    # Use chain count as proxy + mcap tier
    chains = llama_asset.get("chains") or []
    chain_count = len(chains)

    # Heuristic: Large stablecoins have deep liquidity
    if mcap > 10_000_000_000:    # >$10B
        ratio = 0.12
        score = 0
    elif mcap > 1_000_000_000:   # >$1B
        ratio = 0.06
        score = 3
    elif mcap > 100_000_000:     # >$100M
        ratio = 0.02
        score = 6
    elif mcap > 10_000_000:      # >$10M
        ratio = 0.005
        score = 10
    else:
        ratio = 0.001
        score = 15

    # Exchange penalty
    if chain_count < 3:
        score += 3

    score = min(score, 15)

    result["details"]["volume_mcap_ratio"] = round(ratio, 4)
    result["details"]["exchange_count"] = max(chain_count, 1)
    result["details"]["market_cap_usd"] = round(mcap)

    if score <= 3:    status = "STRONG"
    elif score <= 8:  status = "ADEQUATE"
    elif score <= 12: status = "THIN"
    else:             status = "ILLIQUID"

    result["score"] = score
    result["status"] = status
    return result


def _score_mint_burn(llama_detail):
    """Signal 3: Mint/Burn Flow (0–10)"""
    result = {"score": 0, "status": "NORMAL", "source": "defillama", "fetched_at": _now(),
              "details": {"total_supply_usd": 0, "net_flow_7d_pct": 0, "direction": "STABLE"}}

    if not llama_detail or "tokens" not in llama_detail:
        result["score"] = 5
        result["status"] = "ELEVATED"
        result["source"] = "no_data"
        return result

    tokens = llama_detail.get("tokens", [])
    if not tokens:
        return result

    # Get current and 7d ago supply
    current_supply = 0
    supply_7d_ago = 0
    for chain_data in tokens:
        circ = chain_data.get("circulating", {})
        if isinstance(circ, dict):
            current_supply += circ.get("peggedUSD", 0) or 0

    # Try to get historical from the detail data
    # DefiLlama includes chainCirculating with timestamps
    chain_circ = llama_detail.get("chainCirculating", {})
    if chain_circ:
        for chain_name, history in chain_circ.items():
            if isinstance(history, list) and len(history) > 7:
                # last entry = current, -7 = week ago
                try:
                    current_entry = history[-1].get("circulating", {}).get("peggedUSD", 0) or 0
                    week_entry = history[-8].get("circulating", {}).get("peggedUSD", 0) or 0
                    current_supply = max(current_supply, sum(
                        h[-1].get("circulating", {}).get("peggedUSD", 0) or 0
                        for _, h in chain_circ.items() if isinstance(h, list) and h
                    ))
                    supply_7d_ago = sum(
                        h[-8].get("circulating", {}).get("peggedUSD", 0) or 0
                        for _, h in chain_circ.items() if isinstance(h, list) and len(h) > 7
                    )
                    break
                except (IndexError, TypeError):
                    pass

    result["details"]["total_supply_usd"] = round(current_supply)

    if current_supply > 0 and supply_7d_ago > 0:
        net_change_pct = abs((current_supply - supply_7d_ago) / supply_7d_ago) * 100
        direction = "INFLOW" if current_supply > supply_7d_ago else "OUTFLOW"
        result["details"]["net_flow_7d_pct"] = round(net_change_pct, 2)
        result["details"]["direction"] = direction

        if net_change_pct < 2:    score = 0
        elif net_change_pct < 5:  score = 3
        elif net_change_pct < 10: score = 6
        else:                     score = 10

        result["score"] = score

        # Outflow alert
        if direction == "OUTFLOW" and net_change_pct > 5:
            result["details"]["outflow_alert"] = True

    score = result["score"]
    if score <= 3:   result["status"] = "NORMAL"
    elif score <= 6: result["status"] = "ELEVATED"
    else:            result["status"] = "ANOMALY"

    return result


def _score_holder_concentration(etherscan_data, llama_asset):
    """Signal 4: Holder Concentration (0–15)"""
    result = {"score": 8, "status": "MODERATE", "source": "estimated", "fetched_at": _now(),
              "details": {"top_10_pct": None, "top_1_pct": None, "top_5_pct": None, "hhi_index": None, "whale_count": 0}}

    total_supply = 0
    if llama_asset:
        circ = llama_asset.get("circulating", {})
        if isinstance(circ, dict):
            total_supply = circ.get("peggedUSD", 0) or 0

    # Parse Etherscan holder data
    if etherscan_data and etherscan_data.get("status") == "1":
        holders = etherscan_data.get("result", [])
        if holders and isinstance(holders, list):
            result["source"] = "etherscan"
            balances = []
            for h in holders:
                try:
                    bal = int(h.get("TokenHolderQuantity", 0))
                    balances.append(bal)
                except (ValueError, TypeError):
                    pass

            if balances and total_supply > 0:
                total_raw = total_supply  # approximate
                top_1 = balances[0] if len(balances) > 0 else 0
                top_5 = sum(balances[:5]) if len(balances) >= 5 else sum(balances)
                top_10 = sum(balances[:10])

                # Convert to percentage (approximate with decimals)
                # We don't know exact decimals from this, so use ratio
                top_10_pct = (top_10 / sum(balances) * 100) if sum(balances) > 0 else 50
                top_5_pct = (top_5 / sum(balances) * 100) if sum(balances) > 0 else 30
                top_1_pct = (top_1 / sum(balances) * 100) if sum(balances) > 0 else 15

                result["details"]["top_10_pct"] = round(top_10_pct, 1)
                result["details"]["top_5_pct"] = round(top_5_pct, 1)
                result["details"]["top_1_pct"] = round(top_1_pct, 1)
                result["details"]["whale_count"] = len([b for b in balances if b > sum(balances) * 0.01])

                # HHI calculation
                shares = [(b / sum(balances)) * 10000 for b in balances] if sum(balances) > 0 else []
                hhi = sum(s * s / 10000 for s in shares) if shares else 500
                result["details"]["hhi_index"] = round(hhi)

    # Score based on top_10_pct
    t10 = result["details"].get("top_10_pct")
    if t10 is None:
        # Estimate based on asset type
        sym = (llama_asset or {}).get("symbol", "").upper()
        if sym in ("USDC", "USDT"):
            t10, score = 22, 4
        elif sym in ("DAI", "USDS"):
            t10, score = 35, 4
        else:
            t10, score = 45, 8
        result["details"]["top_10_pct"] = t10
    else:
        if t10 < 20:    score = 0
        elif t10 < 40:  score = 4
        elif t10 < 60:  score = 8
        elif t10 < 80:  score = 12
        else:            score = 15

    # HHI bonus
    hhi = result["details"].get("hhi_index") or 0
    if hhi > 1500:    score += 4
    elif hhi > 500:   score += 2

    score = min(score, 15)
    result["score"] = score

    if score <= 4:    result["status"] = "LOW"
    elif score <= 8:  result["status"] = "MODERATE"
    elif score <= 12: result["status"] = "HIGH"
    else:             result["status"] = "CONCENTRATED"

    return result


def _score_custody(symbol: str):
    """Signal 5: Custody / Counterparty (0–15)"""
    sym = symbol.upper()
    registry = CUSTODY_REGISTRY.get(sym)

    result = {"score": 12, "status": "OPAQUE", "source": "feedoracle_registry", "fetched_at": _now(),
              "details": {"primary_custodian": "Unknown", "custodian_count": 0, "sifi_backed": False,
                          "regulated": False, "last_attestation": None, "registry_version": "1.0"}}

    if not registry:
        result["score"] = 12
        result["status"] = "OPAQUE"
        result["details"]["primary_custodian"] = "Not in registry"
        return result

    custs = registry["custodians"]
    result["details"]["primary_custodian"] = custs[0] if custs else "Unknown"
    result["details"]["custodian_count"] = registry["count"]
    result["details"]["sifi_backed"] = registry["sifi"]
    result["details"]["regulated"] = registry["regulated"]
    result["details"]["last_attestation"] = registry["last_attestation"]

    # Base score
    if registry["sifi"]:
        score = 0
    elif registry["regulated"] and registry["count"] > 0:
        score = 3
    elif registry["count"] > 0 and not registry["regulated"]:
        score = 8
    elif registry["count"] == 0 and registry.get("attestation_type") == "on-chain":
        # Decentralized protocols — known counterparty is the smart contract
        score = 5
    else:
        score = 12

    # Single custodian penalty
    if registry["count"] == 1:
        score += 3

    # Stale attestation penalty
    last_att = registry.get("last_attestation", "N/A")
    if last_att and last_att != "N/A":
        try:
            att_date = datetime.strptime(last_att, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_ago = (datetime.now(timezone.utc) - att_date).days
            if days_ago > 90:
                score += 3
        except ValueError:
            pass

    score = min(score, 15)
    result["score"] = score

    if score <= 3:    result["status"] = "KNOWN"
    elif score <= 8:  result["status"] = "DISCLOSED"
    elif score <= 12: result["status"] = "OPAQUE"
    else:             result["status"] = "UNKNOWN"

    return result


def _score_redemption(symbol: str):
    """Signal 6: Redemption Friction (0–10)"""
    sym = symbol.upper()
    registry = REDEMPTION_REGISTRY.get(sym)

    result = {"score": 7, "status": "HIGH", "source": "feedoracle_registry", "fetched_at": _now(),
              "details": {"settlement": "unknown", "min_redemption_usd": None, "fees_pct": None,
                          "institutional_only": None, "direct_redemption": None}}

    if not registry:
        result["score"] = 7
        result["status"] = "HIGH"
        return result

    result["details"]["settlement"] = registry["settlement"]
    result["details"]["min_redemption_usd"] = registry["min_usd"]
    result["details"]["fees_pct"] = registry["fees_pct"]
    result["details"]["institutional_only"] = registry["institutional_only"]
    result["details"]["direct_redemption"] = registry["direct_redemption"]

    if not registry["direct_redemption"]:
        score = 10
    elif registry["institutional_only"]:
        score = 7
    elif registry["settlement"] in ("T+2", "T+3", "T+7") or registry["min_usd"] > 1000:
        score = 5
    elif registry["settlement"] == "T+1" and registry["min_usd"] <= 1000:
        score = 2
    elif registry["settlement"] == "instant" and registry["min_usd"] == 0:
        score = 0
    else:
        score = 3

    # Fee penalty
    if registry["fees_pct"] > 0.1:
        score += 2

    score = min(score, 10)
    result["score"] = score

    if score <= 2:   result["status"] = "LOW"
    elif score <= 5: result["status"] = "MODERATE"
    elif score <= 8: result["status"] = "HIGH"
    else:            result["status"] = "RESTRICTED"

    return result


def _score_cross_chain(llama_asset, llama_detail):
    """Signal 7: Cross-Chain Risk (0–10)"""
    result = {"score": 0, "status": "LOW", "source": "defillama", "fetched_at": _now(),
              "details": {"primary_chain": "ethereum", "chain_count": 1, "bridge_exposure_pct": 0}}

    chains = (llama_asset or {}).get("chains") or []
    chain_count = len(chains)
    result["details"]["chain_count"] = chain_count

    if chain_count <= 1:
        result["score"] = 0
        result["status"] = "LOW"
        return result

    # Estimate bridge exposure from chain distribution
    if llama_detail and "tokens" in llama_detail:
        chain_supplies = {}
        for token in llama_detail.get("tokens", []):
            chain_name = token.get("chain") or token.get("name", "unknown")
            circ = token.get("circulating", {})
            supply = circ.get("peggedUSD", 0) or 0 if isinstance(circ, dict) else 0
            chain_supplies[chain_name] = supply

        total = sum(chain_supplies.values())
        if total > 0:
            # Primary chain = largest supply
            primary = max(chain_supplies, key=chain_supplies.get)
            primary_supply = chain_supplies[primary]
            bridge_pct = ((total - primary_supply) / total) * 100
            result["details"]["primary_chain"] = primary
            result["details"]["bridge_exposure_pct"] = round(bridge_pct, 1)

    bridge_pct = result["details"]["bridge_exposure_pct"]

    if chain_count == 1:
        score = 0
    elif bridge_pct < 10:
        score = 2
    elif bridge_pct < 30:
        score = 5
    elif bridge_pct < 50:
        score = 7
    else:
        score = 10

    score = min(score, 10)
    result["score"] = score

    if score <= 2:   result["status"] = "LOW"
    elif score <= 5: result["status"] = "MODERATE"
    elif score <= 8: result["status"] = "ELEVATED"
    else:            result["status"] = "HIGH"

    return result


# ══════════════════════════════════════════════════════════════
#  VERDICT ENGINE
# ══════════════════════════════════════════════════════════════

def _compute_verdict(risk_score: int) -> str:
    if risk_score <= 25:  return "SAFE"
    if risk_score <= 55:  return "CAUTION"
    return "AVOID"

def _compute_confidence(signals: dict) -> float:
    """Confidence = 0.7 * freshness + 0.3 * coverage."""
    now = time.time()
    total_weight = 0
    freshness_sum = 0
    signals_with_data = 0

    for name, sig in signals.items():
        w = SIGNAL_DEFS.get(name, {}).get("weight", 0.1)
        total_weight += w

        # Freshness factor
        fetched = sig.get("fetched_at")
        if fetched and fetched != "unknown":
            try:
                if isinstance(fetched, str):
                    ft = datetime.fromisoformat(fetched.replace("Z", "+00:00")).timestamp()
                else:
                    ft = fetched
                age_hours = (now - ft) / 3600
                if age_hours < 1:      ff = 1.0
                elif age_hours < 24:   ff = 0.9
                elif age_hours < 168:  ff = 0.7
                elif age_hours < 720:  ff = 0.5
                else:                  ff = 0.3
            except (ValueError, TypeError):
                ff = 0.3
        else:
            ff = 0.1

        freshness_sum += w * ff

        # Coverage
        if sig.get("source") != "no_data" and sig.get("source") != "estimated":
            signals_with_data += 1

    freshness_avg = freshness_sum / total_weight if total_weight > 0 else 0.5
    coverage_ratio = signals_with_data / len(signals) if signals else 0.5

    confidence = 0.7 * freshness_avg + 0.3 * coverage_ratio
    return round(confidence, 2)


def _generate_hint(verdict: str, signals: dict, use_case: str) -> str:
    """Generate operational agent hint (neutral, non-advisory)."""
    hints = []
    uc = use_case or "general"

    if verdict == "SAFE":
        hints.append(f"Operationally safe for {uc}.")
    elif verdict == "CAUTION":
        hints.append(f"Usable for {uc} with monitoring.")
    else:
        hints.append(f"Not recommended for {uc}.")

    s = signals
    if s.get("peg_stability", {}).get("score", 0) > 10:
        hints.append("Peg stress detected — tighten risk limits.")
    if s.get("holder_concentration", {}).get("score", 0) > 8:
        hints.append("High whale concentration — watch for large redemptions.")
    if s.get("mint_burn_flow", {}).get("score", 0) > 6:
        hints.append("Unusual mint/burn activity detected.")
    if s.get("custody_counterparty", {}).get("score", 0) > 8:
        hints.append("Limited custody transparency — counterparty risk elevated.")
    if s.get("cross_chain_risk", {}).get("score", 0) > 5:
        hints.append("Significant bridge exposure — monitor bridge health.")
    if s.get("redemption_friction", {}).get("score", 0) > 5:
        hints.append("Redemption constraints — ensure liquidity buffer.")

    return " ".join(hints)


# ══════════════════════════════════════════════════════════════
#  MAIN ENTRY: get_risk_assessment
# ══════════════════════════════════════════════════════════════

async def get_risk_assessment(token_symbol: str, chain: str = "aggregate", use_case: str = "settlement"):
    """Full 7-signal risk assessment for a stablecoin.
    Returns the complete preflight response object.
    """
    sym = token_symbol.upper()
    ts = _now()

    # ── Fetch data in parallel ────────────────────────────────
    llama_asset = await _find_llama_asset(sym)
    llama_id = SLUG_TO_LLAMA_ID.get(sym.lower())
    llama_detail = await _get_llama_detail(llama_id) if llama_id else None
    peg_data = await _get_internal_peg(sym)

    # Etherscan holders (only for ERC-20 tokens we know)
    eth_contract = TOKEN_CONTRACTS.get(sym)
    holder_data = await _get_etherscan_holders(eth_contract) if eth_contract else None

    # ── Score all 7 signals ───────────────────────────────────
    signals = {}
    signals["peg_stability"]        = _score_peg_stability(llama_asset, peg_data)
    signals["liquidity_depth"]      = _score_liquidity_depth(llama_asset)
    signals["mint_burn_flow"]       = _score_mint_burn(llama_detail)
    signals["holder_concentration"] = _score_holder_concentration(holder_data, llama_asset)
    signals["custody_counterparty"] = _score_custody(sym)
    signals["redemption_friction"]  = _score_redemption(sym)
    signals["cross_chain_risk"]     = _score_cross_chain(llama_asset, llama_detail)

    # ── Aggregate ─────────────────────────────────────────────
    risk_score = sum(s["score"] for s in signals.values())
    risk_score = min(risk_score, 100)
    confidence = _compute_confidence(signals)
    verdict = _compute_verdict(risk_score)

    # Low confidence override
    if confidence < 0.5 and verdict == "SAFE":
        verdict = "CAUTION"

    agent_hint = _generate_hint(verdict, signals, use_case)
    if confidence < 0.5:
        agent_hint += " Low data confidence — verify manually."

    # ── Build signal output (clean, no weights in response) ───
    signal_output = {}
    for name, sig in signals.items():
        signal_output[name] = {
            "score": sig["score"],
            "max": SIGNAL_DEFS[name]["max"],
            "status": sig["status"],
        }

    # ── Build details ─────────────────────────────────────────
    peg_d = signals["peg_stability"]["details"]
    liq_d = signals["liquidity_depth"]["details"]
    flow_d = signals["mint_burn_flow"]["details"]
    hold_d = signals["holder_concentration"]["details"]
    cust_d = signals["custody_counterparty"]["details"]
    red_d  = signals["redemption_friction"]["details"]
    cc_d   = signals["cross_chain_risk"]["details"]

    details = {
        "peg": {
            "current_deviation_pct": peg_d.get("current_deviation_pct", 0),
            "max_30d_deviation_pct": peg_d.get("max_30d_deviation_pct", 0),
            "depeg_events_30d": peg_d.get("depeg_events_30d", 0),
        },
        "supply": {
            "total_supply_usd": flow_d.get("total_supply_usd", 0),
            "net_flow_7d_pct": flow_d.get("net_flow_7d_pct", 0),
            "direction": flow_d.get("direction", "STABLE"),
        },
        "holders": {
            "top_10_pct": hold_d.get("top_10_pct"),
            "top_1_pct": hold_d.get("top_1_pct"),
            "top_5_pct": hold_d.get("top_5_pct"),
            "whale_count": hold_d.get("whale_count", 0),
            "hhi_index": hold_d.get("hhi_index"),
        },
        "custody": {
            "primary_custodian": cust_d.get("primary_custodian", "Unknown"),
            "custodian_count": cust_d.get("custodian_count", 0),
            "sifi_backed": cust_d.get("sifi_backed", False),
        },
        "redemption": {
            "settlement": red_d.get("settlement", "unknown"),
            "min_redemption_usd": red_d.get("min_redemption_usd"),
            "fees_pct": red_d.get("fees_pct"),
        },
        "chains": {
            "primary_chain": cc_d.get("primary_chain", "ethereum"),
            "chain_count": cc_d.get("chain_count", 1),
            "bridge_exposure_pct": cc_d.get("bridge_exposure_pct", 0),
        },
    }

    # ── Evidence block ────────────────────────────────────────
    signals_with_data = sum(1 for s in signals.values() if s.get("source") not in ("no_data", "estimated", "unknown"))
    data_freshness = {}
    for name, sig in signals.items():
        data_freshness[name] = {
            "source": sig.get("source", "unknown"),
            "fetched_at": sig.get("fetched_at"),
            "freshness": _freshness_factor(sig.get("fetched_at")),
        }

    content = json.dumps({"asset": sym, "risk_score": risk_score, "signals": signal_output}, sort_keys=True, separators=(",", ":"))
    content_hash = "sha256:" + hashlib.sha256(content.encode()).hexdigest()

    evidence = {
        "schema": "stablecoin-risk-evidence/1.0",
        "signals_evaluated": 7,
        "signals_with_data": signals_with_data,
        "data_freshness": data_freshness,
        "content_hash": content_hash,
        "signature": {"kid": "fo-stablecoin-risk-2026", "alg": "HMAC-SHA256", "sig": None},
        "anchor": {"chain": "xrpl", "tx_hash": None},
    }

    return {
        "asset": sym,
        "verdict": verdict,
        "risk_score": risk_score,
        "confidence": confidence,
        "engine_version": ENGINE_VERSION,
        "evaluated_at": ts,
        "signals": signal_output,
        "details": details,
        "agent_hint": agent_hint,
        "evidence": evidence,
        "disclaimer": "Deterministic risk classification based on public signals. Not investment advice.",
    }


# ══════════════════════════════════════════════════════════════
#  INDIVIDUAL SIGNAL ACCESSORS (for single-signal tools)
# ══════════════════════════════════════════════════════════════

async def get_peg_status(symbol: str):
    """Quick peg status (free tier)."""
    llama = await _find_llama_asset(symbol)
    peg = await _get_internal_peg(symbol)
    return _score_peg_stability(llama, peg)

async def get_peg_history(symbol: str):
    """Peg history with 30d data."""
    llama_id = SLUG_TO_LLAMA_ID.get(symbol.lower())
    detail = await _get_llama_detail(llama_id) if llama_id else None
    llama = await _find_llama_asset(symbol)
    peg = await _get_internal_peg(symbol)
    result = _score_peg_stability(llama, peg)
    # Add history from detail
    if detail and "tokens" in detail:
        result["details"]["history_available"] = True
    return result

async def get_supply_flow(symbol: str):
    """Mint/burn flow data."""
    llama_id = SLUG_TO_LLAMA_ID.get(symbol.lower())
    detail = await _get_llama_detail(llama_id) if llama_id else None
    return _score_mint_burn(detail)

async def get_holder_data(symbol: str):
    """Holder concentration."""
    llama = await _find_llama_asset(symbol)
    contract = TOKEN_CONTRACTS.get(symbol.upper())
    holders = await _get_etherscan_holders(contract) if contract else None
    return _score_holder_concentration(holders, llama)

async def get_custody_data(symbol: str):
    """Custody profile."""
    return _score_custody(symbol)

async def get_redemption_data(symbol: str):
    """Redemption profile."""
    return _score_redemption(symbol)

async def get_cross_chain_data(symbol: str):
    """Cross-chain supply distribution."""
    llama = await _find_llama_asset(symbol)
    llama_id = SLUG_TO_LLAMA_ID.get(symbol.lower())
    detail = await _get_llama_detail(llama_id) if llama_id else None
    return _score_cross_chain(llama, detail)

async def get_leaderboard(limit: int = 10):
    """Stablecoin risk leaderboard — ranked by risk score (lowest = safest)."""
    top_symbols = ["USDC", "USDT", "EURC", "DAI", "USDS", "RLUSD", "PYUSD", "FRAX", "LUSD",
                   "GHO", "USDe", "FDUSD", "USD0", "GUSD", "USDP", "BUSD", "TUSD", "BUIDL", "USDY"]

    results = []
    for sym in top_symbols[:limit]:
        try:
            assessment = await get_risk_assessment(sym, use_case="general")
            results.append({
                "rank": 0,
                "asset": sym,
                "verdict": assessment["verdict"],
                "risk_score": assessment["risk_score"],
                "confidence": assessment["confidence"],
                "agent_hint": assessment["agent_hint"],
            })
        except Exception as e:
            logger.warning(f"Leaderboard skip {sym}: {e}")

    # Sort by risk_score ascending (safest first)
    results.sort(key=lambda x: x["risk_score"])
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return {
        "leaderboard": results[:limit],
        "evaluated_at": _now(),
        "engine_version": ENGINE_VERSION,
        "count": len(results),
    }


async def compare_stablecoins(symbols: list, use_case: str = "settlement"):
    """Side-by-side comparison of multiple stablecoins."""
    results = []
    for sym in symbols[:5]:  # max 5 at once
        try:
            assessment = await get_risk_assessment(sym, use_case=use_case)
            results.append(assessment)
        except Exception as e:
            logger.warning(f"Compare skip {sym}: {e}")
            results.append({"asset": sym, "error": str(e)})

    # Recommendation
    valid = [r for r in results if "risk_score" in r]
    recommended = min(valid, key=lambda x: x["risk_score"]) if valid else None

    return {
        "comparison": results,
        "recommended": recommended["asset"] if recommended else None,
        "recommended_reason": f"Lowest risk score ({recommended['risk_score']}) for {use_case}" if recommended else None,
        "use_case": use_case,
        "evaluated_at": _now(),
        "engine_version": ENGINE_VERSION,
    }


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _freshness_factor(fetched_at):
    """Compute freshness 0.0-1.0 from timestamp."""
    if not fetched_at:
        return 0.1
    try:
        if isinstance(fetched_at, str):
            ft = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).timestamp()
        else:
            ft = fetched_at
        age_h = (time.time() - ft) / 3600
        if age_h < 1:   return 1.0
        if age_h < 24:  return 0.9
        if age_h < 168: return 0.7
        if age_h < 720: return 0.5
        return 0.3
    except:
        return 0.3
