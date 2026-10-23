---
kind: api_pytest
base_url: https://api.crypto.com
setup: none
healing: false
timeout_default: 30
cases:
  - id: L-01
    method: GET
    path: /v1/symbols
    no_auth: true
    expect_status: 200
    expect_body_substrings: ["symbol", "base_coin", "price_precision"]
    expect_max_response_ms: 10000
    extract_vars:
      symbol: data.0.symbol
  - id: P-01
    method: GET
    path: /v1/symbols
    no_auth: true
    expect_status: 200
    expect_body_substrings: ["symbol"]
  - id: L-02
    method: GET
    path: /v1/tickers
    no_auth: true
    expect_status: 200
    expect_body_substrings: ["symbol", "last"]
  - id: L-03
    method: GET
    path: /v1/ticker/price
    no_auth: true
    expect_status: 200
  - id: D-01
    depends_on: [L-01]
    method: GET
    path: /v1/ticker?symbol=${symbol}
    no_auth: true
    expect_status: 200
    expect_body_substrings: ["high", "last", "low"]
  - id: F-02
    depends_on: [L-01]
    method: GET
    path: /v1/klines?symbol=${symbol}&period=1
    no_auth: true
    expect_status: 200
  - id: D-02
    depends_on: [L-01]
    method: GET
    path: /v1/depth?symbol=${symbol}&type=step0
    no_auth: true
    expect_status: 200
    expect_body_substrings: ["asks", "bids"]
  - id: F-04
    depends_on: [L-01]
    method: GET
    path: /v1/trades?symbol=${symbol}
    no_auth: true
    expect_status: 200
---

# Crypto Exchange Market API pytest

Public GET only. No API key, no `setup` init, no teardown.

| Case | Layer | Call |
|------|-------|------|
| L-01 | H + P | `GET /v1/symbols`, then save `data.0.symbol` |
| P-01 | S | same call with no auth headers |
| L-02 | H | `GET /v1/tickers` |
| L-03 | H | `GET /v1/ticker/price` |
| D-01 | H | `GET /v1/ticker?symbol=${symbol}` after L-01 |
| F-02 | H | `GET /v1/klines?symbol=${symbol}&period=1` |
| D-02 | H | `GET /v1/depth?symbol=${symbol}&type=step0` |
| F-04 | H | `GET /v1/trades?symbol=${symbol}` |

`expect_max_response_ms: 10000` on L-01 is a single-call sanity ceiling, not a load-test SLA.

Not generated until the open questions are closed:

- V-01, V-02, V-05, V-06: error status is 400, 404, or 499 (T-05)
- V-04: kline parameter sentences conflict (T-03)
- V-08: "no parameter is allowed" vs a still-successful list
- N-01: 11th request in one second should be 429 (T-07). This runner executes one request per case.

```bash
./generate.sh templates/crypto_market_api.md
python3 -m py_compile output/crypto_market_api.py
./run_pytest.sh output/crypto_market_api.py --collect-only -q
```

Live run:

```bash
export TEST_BASE_URL=https://api.crypto.com
./run_pytest.sh output/crypto_market_api.py -v
```
