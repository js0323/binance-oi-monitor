# -*- coding: utf-8 -*-
"""
Binance OI 自動推播系統 - Render 版（每 3 分鐘推送一次）
作者：ChatGPT 為 蔡定緯 製作，部署 Render 用
"""
import os, time, threading, requests
from datetime import datetime, timezone
from flask import Flask

# ✅ Discord Webhook（你提供的）
WEBHOOK_URL = "https://discord.com/api/webhooks/1391850608499228712/jvExTuzWLb_iOrYjgu6ci4rVVIShDBH5kWwXYkfXD-cKEDIk3ZEvp9CaFcv47MULjIzF"

# === 設定參數 ===
SYMBOL_LIMIT = 50
INTERVAL_SEC = 180  # 每3分鐘

UM_BASE = "https://fapi.binance.com"
prev_oi, pos_streak, neg_streak = {}, {}, {}

def top_symbols(limit=50):
    r = requests.get(f"{UM_BASE}/fapi/v1/ticker/24hr", timeout=10)
    data = [d for d in r.json() if d["symbol"].endswith("USDT")]
    data.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
    return [d["symbol"] for d in data[:limit]]

def fetch_oi_usdt(symbol):
    params = {"symbol": symbol, "period": "5m", "limit": 1}
    r = requests.get(f"{UM_BASE}/futures/data/openInterestHist", params=params, timeout=10)
    j = r.json()
    return float(j[0]["sumOpenInterestValue"]) if j else None

def push(msg):
    requests.post(WEBHOOK_URL, json={"content": f"```{msg}```"}, timeout=10)

def monitor_loop():
    symbols = top_symbols(SYMBOL_LIMIT)
    while True:
        snap, diff_pct = {}, {}
        for s in symbols:
            val = fetch_oi_usdt(s)
            if val is None:
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

        if diff_pct:
            top_pos = sorted(((s, p) for s, p in diff_pct.items() if p > 0), key=lambda x: x[1], reverse=True)[:10]
            top_neg = sorted(((s, p) for s, p in diff_pct.items() if p < 0), key=lambda x: x[1])[:10]
            biggest5 = sorted(snap.items(), key=lambda x: x[1], reverse=True)[:5]

            ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines = [f"🌀 Binance 持倉變化量排名（{ts}）"]
            for sym, val in biggest5:
                d = diff_pct.get(sym, 0)
                lines.append(f"{sym}: 持倉量(U): {val:,.2f} | 持倉變化: {d:+.2f}%")
            lines += ["", "👍 持倉正成長前十："]
            for sym, d in top_pos:
                lines.append(f"{sym:<10}| 持倉量(U): {snap[sym]:,.2f} | 持倉變化: {d:+.2f}% | 正成長次數:{pos_streak[sym]}")
            lines += ["", "👎 持倉負成長前十："]
            for sym, d in top_neg:
                lines.append(f"{sym:<10}| 持倉量(U): {snap[sym]:,.2f} | 持倉變化: {d:+.2f}% | 負成長次數:{neg_streak[sym]}")
            push("\n".join(lines))

        time.sleep(INTERVAL_SEC)

# === Flask App for Render Keep-Alive ===
app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
