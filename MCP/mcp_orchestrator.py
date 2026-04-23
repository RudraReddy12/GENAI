"""
mcp_orchestrator.py
Core MCP logic: Gemini LLM + CoinGecko crypto tool.
"""

import os
import re
import requests
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

# ─────────────────────────────────────────────
# Tool Implementation — CoinGecko (no key needed)
# ─────────────────────────────────────────────

ALIASES = {
    "btc": "bitcoin", "eth": "ethereum", "sol": "solana",
    "doge": "dogecoin", "bnb": "binancecoin", "xrp": "ripple",
    "ada": "cardano", "dot": "polkadot", "ltc": "litecoin",
    "avax": "avalanche-2", "matic": "matic-network", "shib": "shiba-inu",
}


def _normalize_coin_name(coin: str) -> str:
    """Normalize common tickers to CoinGecko IDs."""
    return ALIASES.get(coin.lower().strip(), coin.lower().strip())


def _fetch_coin_data(*coins: str) -> dict:
    """Fetch market data for one or more coins from CoinGecko."""
    normalized_coins = [_normalize_coin_name(coin) for coin in coins]

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(normalized_coins),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_last_updated_at": "true",
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return {"error": "CoinGecko API timed out. Please try again.", "requested": normalized_coins}
    except Exception as e:
        return {"error": f"Unable to fetch price right now: {str(e)}", "requested": normalized_coins}

    if not data:
        return {"error": "No market data returned from CoinGecko.", "requested": normalized_coins}

    formatted = {}
    missing = []
    for coin in normalized_coins:
        if coin not in data:
            missing.append(coin)
            continue
        coin_data = data[coin]
        change = round(coin_data.get("usd_24h_change", 0), 2)
        formatted[coin] = {
            "coin": coin,
            "price_usd": coin_data.get("usd"),
            "change_24h_pct": change,
            "market_cap_usd": coin_data.get("usd_market_cap"),
            "trend": "up" if change >= 0 else "down",
        }

    if missing:
        missing_names = ", ".join(f"'{coin}'" for coin in missing)
        return {
            "error": f"Coin {missing_names} not found. Try using the full name like 'bitcoin' or 'ethereum'.",
            "requested": normalized_coins,
            "found": formatted,
        }

    return {"coins": formatted}


def get_crypto_price(coin: str) -> dict:
    """Fetch live crypto price from CoinGecko free API."""
    result = _fetch_coin_data(coin)
    if result.get("error"):
        return result
    normalized_coin = _normalize_coin_name(coin)
    return result["coins"][normalized_coin]


def compare_crypto_prices(coin_a: str, coin_b: str) -> dict:
    """Compare two cryptocurrencies using live CoinGecko data."""
    result = _fetch_coin_data(coin_a, coin_b)
    if result.get("error"):
        return result

    first = result["coins"][_normalize_coin_name(coin_a)]
    second = result["coins"][_normalize_coin_name(coin_b)]
    price_a = first.get("price_usd")
    price_b = second.get("price_usd")
    market_cap_a = first.get("market_cap_usd")
    market_cap_b = second.get("market_cap_usd")

    comparison = {
        "coin_a": first,
        "coin_b": second,
        "price_gap_usd": None,
        "price_ratio": None,
        "higher_priced_coin": None,
        "larger_market_cap_coin": None,
    }

    if price_a is not None and price_b is not None:
        comparison["price_gap_usd"] = abs(price_a - price_b)
        if price_a > 0 and price_b > 0:
            comparison["price_ratio"] = round(max(price_a, price_b) / min(price_a, price_b), 2)
        comparison["higher_priced_coin"] = first["coin"] if price_a >= price_b else second["coin"]

    if market_cap_a is not None and market_cap_b is not None:
        comparison["larger_market_cap_coin"] = (
            first["coin"] if market_cap_a >= market_cap_b else second["coin"]
        )

    return comparison


# ─────────────────────────────────────────────
# Gemini Tool Schema
# ─────────────────────────────────────────────

CRYPTO_TOOL = Tool(function_declarations=[
    FunctionDeclaration(
        name="get_crypto_price",
        description=(
            "Get the current real-time price of a cryptocurrency in USD from CoinGecko. "
            "Use this tool whenever the user asks about the price, value, cost, or worth "
            "of any cryptocurrency such as Bitcoin, Ethereum, Solana, Dogecoin, etc. "
            "Also use it for questions like 'how much is X', 'what is X trading at', "
            "or 'current X price'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "coin": {
                    "type": "string",
                    "description": (
                        "The CoinGecko coin ID in lowercase. Examples: 'bitcoin', 'ethereum', "
                        "'solana', 'dogecoin', 'shiba-inu', 'cardano'. "
                        "Convert abbreviations: BTC→bitcoin, ETH→ethereum, SOL→solana."
                    ),
                }
            },
            "required": ["coin"],
        },
    ),
    FunctionDeclaration(
        name="compare_crypto_prices",
        description=(
            "Compare two cryptocurrencies using live CoinGecko data. "
            "Use this tool whenever the user asks to compare coins, asks which coin is higher, "
            "asks for 'X vs Y', or wants to know differences in price or market cap between two coins."
        ),
        parameters={
            "type": "object",
            "properties": {
                "coin_a": {
                    "type": "string",
                    "description": (
                        "The first coin's CoinGecko ID in lowercase. "
                        "Convert abbreviations like BTC→bitcoin, ETH→ethereum, SOL→solana."
                    ),
                },
                "coin_b": {
                    "type": "string",
                    "description": (
                        "The second coin's CoinGecko ID in lowercase. "
                        "Convert abbreviations like BTC→bitcoin, ETH→ethereum, SOL→solana."
                    ),
                },
            },
            "required": ["coin_a", "coin_b"],
        },
    )
])


# ─────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are CryptoMind, a sharp and friendly AI crypto assistant.

You have TWO real-time tools:
- get_crypto_price: fetches a live price for one cryptocurrency from CoinGecko.
- compare_crypto_prices: compares two cryptocurrencies using live CoinGecko data.

Rules:
1. ALWAYS call get_crypto_price when the user asks about any crypto price, value, or worth.
2. ALWAYS call compare_crypto_prices when the user asks to compare two crypto coins, including questions like 'BTC vs ETH', 'compare bitcoin and solana', or 'which is higher, doge or xrp?'.
3. Never guess or make up prices — always use the tool for live data.
4. For general crypto questions (what is blockchain, how does ethereum work, etc.) answer from your own knowledge.
5. Format price responses naturally: mention price, 24h change with an emoji (📈/📉), and a brief comment.
6. Be concise, warm, and direct. No filler phrases.
7. If the tool returns an error, apologize briefly and suggest the user check the coin name.
"""


def _format_price_response(result: dict) -> str:
    """Format tool output locally to avoid an extra Gemini call for simple price lookups."""
    if result.get("error"):
        return f"Sorry, I couldn't fetch that price right now. {result['error']}"

    coin_name = result["coin"].replace("-", " ").title()
    price = result.get("price_usd")
    change = result.get("change_24h_pct", 0)
    emoji = "📈" if change >= 0 else "📉"

    if price is None:
        return f"Sorry, I couldn't fetch the current price for {coin_name}."

    return f"{coin_name} is trading at ${price:,.2f} {emoji} ({change:+.2f}% in the last 24h)."


def _format_comparison_response(result: dict) -> str:
    """Format two-coin comparison output locally."""
    if result.get("error"):
        return f"Sorry, I couldn't compare those coins right now. {result['error']}"

    first = result["coin_a"]
    second = result["coin_b"]

    first_name = first["coin"].replace("-", " ").title()
    second_name = second["coin"].replace("-", " ").title()
    first_change = first.get("change_24h_pct", 0)
    second_change = second.get("change_24h_pct", 0)
    first_emoji = "📈" if first_change >= 0 else "📉"
    second_emoji = "📈" if second_change >= 0 else "📉"
    first_price = first.get("price_usd")
    second_price = second.get("price_usd")

    lines = [
        (
            f"{first_name}: ${first_price:,.2f} {first_emoji} ({first_change:+.2f}% 24h)"
            if first_price is not None
            else f"{first_name}: price unavailable right now."
        ),
        (
            f"{second_name}: ${second_price:,.2f} {second_emoji} ({second_change:+.2f}% 24h)"
            if second_price is not None
            else f"{second_name}: price unavailable right now."
        ),
    ]

    higher_priced_coin = result.get("higher_priced_coin")
    price_ratio = result.get("price_ratio")
    price_gap = result.get("price_gap_usd")
    if higher_priced_coin and price_ratio and price_gap is not None:
        higher_name = higher_priced_coin.replace("-", " ").title()
        lines.append(
            f"{higher_name} is higher priced by ${price_gap:,.2f}, about {price_ratio}x versus the other coin."
        )

    larger_market_cap_coin = result.get("larger_market_cap_coin")
    if larger_market_cap_coin:
        market_cap_name = larger_market_cap_coin.replace("-", " ").title()
        lines.append(f"{market_cap_name} also has the larger market cap right now.")

    return "\n\n".join(lines)


def _extract_retry_seconds(message: str) -> int | None:
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message, flags=re.IGNORECASE)
    if not match:
        return None
    return max(1, round(float(match.group(1))))


# ─────────────────────────────────────────────
# Gemini Client
# ─────────────────────────────────────────────

def _get_model():
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment variables.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=[CRYPTO_TOOL],
    )


# ─────────────────────────────────────────────
# MCP Orchestrator — Main Entry Point
# ─────────────────────────────────────────────

def run_mcp(user_query: str, chat_history: list = None) -> str:
    """
    MCP loop with Gemini:
    1. Send query + tool schema to Gemini.
    2. If Gemini wants to call a tool → execute → send result back.
    3. Return final natural-language answer.

    Args:
        user_query: The user's message.
        chat_history: List of {"role": "user"|"model", "parts": [...]} dicts.

    Returns:
        Final response string.
    """
    model = _get_model()

    # Build history for multi-turn context
    history = []
    if chat_history:
        for entry in chat_history[-8:]:  # Last 4 turns
            history.append({"role": entry["role"], "parts": [entry["content"]]})

    chat = model.start_chat(history=history)

    # Step 1: Send user query
    try:
        response = chat.send_message(user_query)
    except Exception as e:
        error_message = str(e)
        if "429" in error_message or "quota exceeded" in error_message.lower():
            retry_seconds = _extract_retry_seconds(error_message)
            if retry_seconds:
                return (
                    f"Gemini rate limit reached on the free tier. Please wait about {retry_seconds} seconds "
                    "and try again."
                )
            return "Gemini rate limit reached on the free tier. Please wait a moment and try again."
        raise

    part = response.candidates[0].content.parts[0]

    # Step 2: Check for tool call
    if hasattr(part, "function_call") and part.function_call.name:
        fn = part.function_call
        tool_name = fn.name
        tool_args = dict(fn.args)

        print(f"[MCP] Tool called: {tool_name}({tool_args})")

        # Step 3: Execute tool
        if tool_name == "get_crypto_price":
            result = get_crypto_price(**tool_args)
            return _format_price_response(result)
        if tool_name == "compare_crypto_prices":
            result = compare_crypto_prices(**tool_args)
            return _format_comparison_response(result)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
            return f"Sorry, I couldn't complete that request. {result['error']}"

    # No tool call — direct answer
    return part.text
