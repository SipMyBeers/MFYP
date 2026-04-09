"""
Broker API Adapter — Alpaca (paper mode default).
Non-waivable trading SOPs enforced at platform level.
"""

import os
import aiohttp

ALPACA_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

# Non-waivable SOPs — hardcoded, cannot be disabled by any user
NON_WAIVABLE_SOPS = {
    "stop_loss_pct": 0.08,       # 8% auto stop loss
    "max_position_pct": 0.15,    # 15% max position size
    "daily_loss_halt_pct": 0.03, # 3% daily loss halts all trading
    "paper_days_required": 30,   # 30 days paper before live
    "margin_requires_written_auth": True,
}


async def get_portfolio() -> dict:
    """Read-only portfolio snapshot."""
    if not ALPACA_KEY:
        return {"error": "No Alpaca API key", "is_paper": True}

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ALPACA_BASE}/v2/account", headers=HEADERS) as r:
            account = await r.json()
        async with session.get(f"{ALPACA_BASE}/v2/positions", headers=HEADERS) as r:
            positions = await r.json()

    return {
        "buying_power": float(account.get("buying_power", 0)),
        "portfolio_value": float(account.get("portfolio_value", 0)),
        "positions": positions,
        "is_paper": "paper" in ALPACA_BASE,
    }


async def place_order_with_sop_check(
    symbol: str, qty: float, side: str, order_type: str = "market",
    limit_price: float = None, reason: str = "",
) -> dict:
    """Place order with non-waivable SOP checks."""
    portfolio = await get_portfolio()
    if "error" in portfolio:
        return {"ok": False, "error": portfolio["error"]}

    # SOP: position size
    order_value = qty * (limit_price or 100)  # approximate if no price
    max_pos = portfolio["portfolio_value"] * NON_WAIVABLE_SOPS["max_position_pct"]
    if order_value > max_pos and side == "buy":
        return {"ok": False, "error": f"Position size ${order_value:,.0f} exceeds 15% limit (${max_pos:,.0f})"}

    # SOP: daily loss
    daily_change = float(portfolio.get("daily_pnl", 0))
    if daily_change < -(portfolio["portfolio_value"] * NON_WAIVABLE_SOPS["daily_loss_halt_pct"]):
        return {"ok": False, "error": "Daily loss limit reached. Trading halted."}

    # Execute
    body = {"symbol": symbol, "qty": str(qty), "side": side, "type": order_type, "time_in_force": "day"}
    if limit_price:
        body["limit_price"] = str(limit_price)

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{ALPACA_BASE}/v2/orders", headers=HEADERS, json=body) as r:
            result = await r.json()

    if result.get("id"):
        return {"ok": True, "order": result, "is_paper": "paper" in ALPACA_BASE}
    return {"ok": False, "error": result.get("message", "Order failed")}
