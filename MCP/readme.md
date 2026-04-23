#  CryptoMind — MCP Crypto Chatbot

A focused MCP chatbot using **Gemini** as the LLM and **CoinGecko** for live crypto prices and coin comparisons.
No keyword matching. No rule-based routing. Gemini decides when to call the tool.

---

## 📁 Files

```
mcp_crypto/
├── app.py                ← Streamlit UI
├── mcp_orchestrator.py   ← MCP core (Gemini + tool loop)
├── requirements.txt
├── .env
└── README.md
```

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key
cp .env.example .env
# Edit .env → paste your GOOGLE_API_KEY

# 3. Run
streamlit run app.py
```

**Only one API key needed:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (free)

CoinGecko needs no key.

---

##  MCP Flow

```
User: "What's the price of Bitcoin?"
  ↓
Gemini receives query + tool schema
  ↓
Gemini decides → call get_crypto_price(coin="bitcoin")
  ↓
CoinGecko API → { price: $65000, change: +2.3% }
  ↓
Result sent back to Gemini
  ↓
Gemini formats: "Bitcoin is trading at $65,000 📈 (+2.3% today)"
  ↓
User sees clean, natural response
```

---

##  Test Queries

| Type | Example |
|------|---------|
| Price | `Bitcoin price`, `How much is ETH?`, `Solana value` |
| Compare | `BTC vs ETH`, `Compare solana and cardano`, `Which is higher, DOGE or XRP?` |
| Alias | `BTC price`, `DOGE worth`, `What's SOL at?` |
| General | `What is blockchain?`, `Explain DeFi` |

---

##  Coin Aliases Supported

`BTC → bitcoin`, `ETH → ethereum`, `SOL → solana`, `DOGE → dogecoin`,
`BNB → binancecoin`, `XRP → ripple`, `ADA → cardano`, `SHIB → shiba-inu`, `MATIC`, `AVAX`

---

##  Phases

- **Phase 1 ✅** — Single crypto tool, Gemini LLM, Streamlit UI, chat history
- **Phase 2 ✅** — Multi-coin comparisons (`BTC vs ETH`)
- **Phase 3** — Price charts
