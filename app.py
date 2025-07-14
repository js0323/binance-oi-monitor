# -*- coding: utf-8 -*-
"""
OKX USDT‑SWAP 持倉變化推播（Render 版，每 3 分鐘）
作者：ChatGPT
"""

import os
import time
import threading
from datetime import datetime, timezone

import requests
from flask import Flask

# === Discord Webhook ===
WEBHOOK_URL = (
    "https://discord.com/api/webhooks/"
    "1391850608499228712/jvExTuzWLb_iOrYjgu6ci4rVVIShDBH5kWwXYkfXD-cKEDIk3ZEvp9CaFcv47MULjIzF"
)

# === 全域參數 ===
SYMBOL_LIMIT = 50           # 前 N 大 24h 交易量
INTERVAL_SEC = 180          # 每 3 分鐘
OKX = "https://www.okx.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

prev_oi, pos_streak, neg_streak = {}, {}, {}

# ---------- 取得 OKX 永續 USDT‑SWAP 前 N 大 24h 交易量 ----------
def top_symbols(limit: int = 50):
    try:
        r = requests.get(f"{OKX}/api/v5/market/tickers",
                         params={"instType": "SWAP"},
                         headers=HEADERS, timeout=10)
        j = r.json()
        if j.get("code") != "0":
            print("⚠️ top_symbols 錯誤：", j)
            return []
        data = [d for d in j["data"] if d["instId"].endswith("-USDT-SWAP")]
        # volCcy24h：24h 币本位成交量（USDT）
        data.sort(key=lambda x: float(x["volCcy24h"]), reverse=True)
        return [d["instId"] for d in data[:limit]]
    except Exception as e:
        print("⚠️ top_symbols 例外：", e)
        return []

# ---------- 取得單一合約當前 Open Interest ----------
def fetch_oi(inst_id: str):
    try:
        r = requests.get(f"{OKX}/api/v5/public/open-interest",
                         params={"instId": inst_id},
                         headers=HEADERS, timeout=10)
        j = r.json()
        if j.get("code") != "0" or not j["data"]:
            return None
        # oiCcy：持倉量（USDT）
        return float(j["data"][0]["oiCcy"])
    except Exception as e:
        print(f"⚠️ fetch_oi {inst_id} 例外：", e)
        return None

# ---------- 推播 Discord ----------
def push(msg: str):
    try:
        r = requests.post(WEBHOOK_URL, json={"content": f"```{msg}```"}, timeout=10)
        print("📨 webhook status:", r.status_code, r.text, flush=True)   # ← 新增
    except Exception as e:
        print("⚠️ push 失敗：", e, flush=True)


# ---------- 監控主迴圈 ----------
def monitor_loop():
    while True:
        symbols = top_symbols(SYMBOL_LIMIT)
        print("🪪 取得幣種數量：", len(symbols), flush=True)

        snap, diff_pct = {}, {}
        for s in symbols:
            val = fetch_oi(s)
            if val is None:
                print(f"⚠️ 無 OI 資料：{s}", flush=True)
                continue
            snap[s] = val
            if s in prev_oi:
                pct = (val - prev_oi[s]) / prev_oi[s] * 100
                diff_pct[s] = pct
                if pct > 0:
                    pos_streak[s] = pos_streak.get(s, 0) + 1
                    neg_streak[s] = 0
                elif pct < 0:
                    neg_streak[s] = neg_streak.get(s, 0) + 1
                    pos_streak[s] = 0
            prev_oi[s] = val

        print("📊 本輪 snap 大小：", len(snap), flush=True)

        if snap:
            top_pos = sorted(
                ((s, p) for s, p in diff_pct.items() if p > 0),
                key=lambda x: x[1], reverse=True)[:10]
            top_neg = sorted(
                ((s, p) for s, p in diff_pct.items() if p < 0),
                key=lambda x: x[1])[:10]
            biggest5 = sorted(snap.items(),
                              key=lambda x: x[1], reverse=True)[:5]

            ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines = [f"🌀 OKX 持倉變化量排名（{ts}）"]
            for sym, val in biggest5:
                d = diff_pct.get(sym, 0)
                lines.append(f"{sym}: 持倉量(U): {val:,.2f} | 變化: {d:+.2f}%")
            lines += ["", "👍 正成長前十："]
            for sym, d in top_pos:
                lines.append(f"{sym:<15}| 變化:{d:+.2f}% | 正次數:{pos_streak.get(sym,0)}")
            lines += ["", "👎 負成長前十："]
            for sym, d in top_neg:
                lines.append(f"{sym:<15}| 變化:{d:+.2f}% | 負次數:{neg_streak.get(sym,0)}")
            push("\n".join(lines))

        time.sleep(INTERVAL_SEC)

# ---------- Flask Keep‑Alive ----------
app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
