#!/usr/bin/env python3
"""FeedOracle Stablecoin Risk MCP Server v1.0
13 tools for stablecoin operational risk scoring via SSE transport.
Port: 5252, Engine: stablecoin-risk/1.0
"""
import os, json, logging, asyncio
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from mcp.server.sse import SseServerTransport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-risk")

# Import engine
from stablecoin_risk_engine import (
    get_risk_assessment, get_peg_status, get_peg_history,
    get_supply_flow, get_holder_data, get_custody_data,
    get_redemption_data, get_cross_chain_data,
    get_leaderboard, compare_stablecoins,
    CUSTODY_REGISTRY, REDEMPTION_REGISTRY, SLUG_TO_LLAMA_ID,
    ENGINE_VERSION, SIGNAL_DEFS, VERDICTS
)

mcp = FastMCP("FeedOracle Stablecoin Risk")

# ── Tool 1: ping ──
@mcp.tool()
async def ping() -> str:
    """Server connectivity test. Returns engine version and status."""
    supported = sorted(set(
        list(CUSTODY_REGISTRY.keys()) +
        list(REDEMPTION_REGISTRY.keys()) +
        [s.upper() for s in SLUG_TO_LLAMA_ID.keys()]
    ))
    return json.dumps({
        "status": "ok",
        "engine": ENGINE_VERSION,
        "supported_count": len(supported),
        "signals": list(SIGNAL_DEFS.keys()),
        "verdicts": list(VERDICTS.keys())
    }, indent=2)

# ── Tool 2: risk_assessment ──
@mcp.tool()
async def risk_assessment(symbol: str, chain: str = "aggregate", use_case: str = "settlement") -> str:
    """Full 7-signal risk report for a stablecoin.
    Args:
        symbol: Token symbol (e.g. USDC, USDT, DAI)
        chain: Chain filter or aggregate (default: aggregate)
        use_case: Context for hint generation (settlement, collateral, treasury, payment)
    Returns: Complete risk assessment with score, verdict, signals, and operational hint.
    """
    result = await get_risk_assessment(symbol, chain, use_case)
    return json.dumps(result, indent=2, default=str)

# ── Tool 3: peg_status ──
@mcp.tool()
async def peg_status(symbol: str) -> str:
    """Quick peg check for a stablecoin. Shows current price and deviation."""
    result = await get_peg_status(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 4: peg_history ──
@mcp.tool()
async def peg_history(symbol: str) -> str:
    """30-day peg history. Shows max deviation, depeg events, trend."""
    result = await get_peg_history(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 5: supply_flow ──
@mcp.tool()
async def supply_flow(symbol: str) -> str:
    """Mint/burn flow analysis. Shows 7d supply changes and direction."""
    result = await get_supply_flow(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 6: holder_data ──
@mcp.tool()
async def holder_data(symbol: str) -> str:
    """Holder concentration metrics. Top holder %, HHI index, whale count."""
    result = await get_holder_data(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 7: custody_data ──
@mcp.tool()
async def custody_data(symbol: str) -> str:
    """Custodian profile. Shows custodians, SIFI status, attestation freshness."""
    result = await get_custody_data(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 8: redemption_data ──
@mcp.tool()
async def redemption_data(symbol: str) -> str:
    """Redemption terms. Settlement time, minimums, fees, institutional restrictions."""
    result = await get_redemption_data(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 9: cross_chain_data ──
@mcp.tool()
async def cross_chain_data(symbol: str) -> str:
    """Cross-chain distribution. Chain count, bridge exposure, primary chain."""
    result = await get_cross_chain_data(symbol)
    return json.dumps(result, indent=2, default=str)

# ── Tool 10: leaderboard ──
@mcp.tool()
async def leaderboard(limit: int = 10) -> str:
    """Stablecoin risk leaderboard. Ranked by risk score (lowest = safest).
    Args:
        limit: Number of results (default 10, max 20)
    """
    result = await get_leaderboard(min(limit, 20))
    return json.dumps(result, indent=2, default=str)

# ── Tool 11: compare ──
@mcp.tool()
async def compare(symbols: str, use_case: str = "settlement") -> str:
    """Side-by-side comparison of up to 5 stablecoins.
    Args:
        symbols: Comma-separated symbols (e.g. USDC,USDT,DAI)
        use_case: Context (settlement, collateral, treasury, payment)
    """
    sym_list = [s.strip().upper() for s in symbols.split(",")][:5]
    result = await compare_stablecoins(sym_list, use_case)
    return json.dumps(result, indent=2, default=str)

# ── Tool 12: supported_tokens ──
@mcp.tool()
async def supported_tokens() -> str:
    """List all supported stablecoins with coverage info."""
    tokens = {}
    all_syms = sorted(set(
        list(CUSTODY_REGISTRY.keys()) +
        list(REDEMPTION_REGISTRY.keys()) +
        [s.upper() for s in SLUG_TO_LLAMA_ID.keys()]
    ))
    for sym in all_syms:
        tokens[sym] = {
            "has_custody_data": sym in CUSTODY_REGISTRY,
            "has_redemption_data": sym in REDEMPTION_REGISTRY,
            "has_llama_data": sym.lower() in SLUG_TO_LLAMA_ID,
        }
    return json.dumps({"engine": ENGINE_VERSION, "count": len(tokens), "tokens": tokens}, indent=2)

# ── Tool 13: methodology ──
@mcp.tool()
async def methodology() -> str:
    """Explain scoring methodology. Signal weights, verdict thresholds, data sources."""
    return json.dumps({
        "engine": ENGINE_VERSION,
        "scale": "0-100 (lower = safer)",
        "signals": {k: {"max_points": v["max"], "weight": v["weight"]} for k, v in SIGNAL_DEFS.items()},
        "verdicts": VERDICTS,
        "confidence": "0.7 * freshness + 0.3 * coverage",
        "data_sources": [
            "DefiLlama (price, supply, chain breakdown)",
            "Etherscan V2 (top token holders)",
            "FeedOracle peg-monitor (real-time peg tracking)",
            "FeedOracle curated registries (custody, redemption)"
        ],
        "disclaimer": "Operational risk classification only. Not financial advice."
    }, indent=2)


# ── SSE Transport & ASGI App ──
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp._mcp_server.run(
            streams[0], streams[1], mcp._mcp_server.create_initialization_options()
        )

async def health(request):
    return JSONResponse({"status": "ok", "engine": ENGINE_VERSION, "server": "stablecoin-risk-mcp", "tools": 13})

app = Starlette(
    debug=False,
    routes=[
        Route("/health", health),
        Route("/sse", handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5252"))
    logger.info(f"Starting Stablecoin Risk MCP on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
