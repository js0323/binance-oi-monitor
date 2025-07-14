# -*- coding: utf-8 -*-
"""
OKX USDT‑SWAP 持倉變化推播（Render 版，每 5 分鐘，3 組 Webhook 輪替）
"""

import os, time, threading, requests
from datetime import datetime, timezone
from flask import Flask

# === Discord Webhook 3 組（輪流使用，避免 1015 Rate Limit） ===
WEBHOOKS = [
    "https://discord.com/api/webhooks/1391850608499228712/jvExTuzWLb_iOrYjgu6ci4rVVIShDBH5kWwXYkfXD-cKEDIk3ZEvp9CaFcv47MULjIzF",
    "https://discord.com/api/webhooks/1394402678079094794/lfoAz17vpmW6ZuCtdtSxG7CoNzuujOCyB2tWyQ9oraHLI_olDHO5JwgG9kVnCK70hQUn",
    "https://discord.com/api/webhooks/1394403286748102787/HJTZ5Rx2U3NEJOhAhpvFY5k0ynQvh6WpnW9C-R8MN--RKHtYjpA_imjLZ4zPfS-nua6m",
]
_webhook_idx = 0

# === 全域參數 ===
SYMBOL_LIMIT = 50
INTERVAL_SEC = 300          # 每 5 分鐘
OKX = "https://www.okx.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

prev_oi, pos_streak, neg_streak = {}, {}, {}

# ---------- API ----------
def top_symbols(limit=50):
    try:
        r = requests.get(f"{OKX}/api/v5/market/tickers",
                         params={"instType": "SWAP"},
                         headers=HEADERS, timeout=10)
        j = r.json()
        if j.get("code") != "0":
            print("⚠️ top_symbols 錯誤：", j, flush=True)
            return []
        data = [d for d in j["data"] if d["instId"].endswith("-USDT-SWAP")]
        data.sort(key=lambda x: float(x["volCcy24h"]), reverse=True)
        return [d["instId"] for d in data[:limit]]
    except Exception as e:
        print("⚠️ top_symbols 例外：", e, flush=True)
        return []

def fetch_oi(inst_id):
    try:
        r = requests.get(f"{OKX}/api/v5/public/open-interest",
                         params={"instId": inst_id},
                         headers=HEADERS, timeout=10)
        j = r.json()
        if j.get("code") != "0" or not j["data"]:
            return None
        return float(j["data"][0]["oiCcy"])
    except Exception as e:
        print(f"⚠️ fetch_oi {inst_id} 例外：", e, flush=True)
        return None

# ---------- Discord ----------
def push(msg):
    global _webhook_idx
    url = WEBHOOKS[_webhook_idx % len(WEBHOOKS)]
    _webhook_idx += 1
    try:
        r = requests.post(url, json={"content": f"```{msg}```"}, timeout=10)
        print("📨 webhook status:", r.status_code, r.text, flush=True)
    except Exception as e:
        print("⚠️ push 失敗：", e, flush=True)

# ---------- 主迴圈 ----------
def monitor_loop():
    while True:
        symbols = top_symbols(SYMBOL_LIMIT)
        print("🪪 幣種數量：", len(symbols), flush=True)

        snap, diff_pct = {}, {}
        for s in symbols:
            val = fetch_oi(s)
            if val is None:
                continue
            snap[s] = val
            if s in prev_oi:
                pct = (val - prev_oi[s]) / prev_oi[s] * 100
                diff_pct[s] = pct
                if pct > 0:
                    pos_streak[s] = pos_streak
