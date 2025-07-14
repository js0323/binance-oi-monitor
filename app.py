# -*- coding: utf-8 -*-
"""
Binance OI 自動推播系統（Render 版，每 3 分鐘）
作者：ChatGPT
"""

import os
import time
import threading
from datetime import datetime, timezone

import requests
from flask import Flask

# === Discord Webhook（你的） ===
WEBHOOK_URL = (
    "https://discord.com/api/webhooks/"
    "1391850608499228712/jvExTuzWLb_iOrYjgu6ci4rVVIShDBH5kWwXYkfXD-cKEDIk3ZEvp9CaFcv47MULjIzF"
)

# === 全域設定 ===
SYMBOL_LIMIT = 50          # 前 N 大成交量
INTERVAL_SEC = 180         # 每 3 分鐘
UM_BASE = "https://fapi.binance.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

prev_oi, pos_streak, neg_streak = {}, {}, {}

# ---------- 取得前 50 大成交量幣種 ----------
def top_symbols(limit: int = 50):
    try:
        r = requests.get(f"{UM_BASE}/fapi/v1/ticker/24hr",
                         headers=HEADERS, timeout=10)
        j = r.json()
        if not isinstance(j, list):
            print("⚠️ top_symbols 回傳非 list：", j)
            return []
        data = [d for d in j if d["symbol"].endswith("USDT")]
        data.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [d["symbol"] for d in data[:limit]]
    except Exception as e:
        print("⚠️ top_symbols 例外：", e)
        return []

# ---------- 取得單一幣種 5m OI ----------
def fetch_oi_usdt(symbol: str):
    try:
        params = {"symbol": symbol, "period": "5m", "limit": 1}
        r = requests.get(f"{UM_BASE}/futures/data/openInterestHist",
                         params=params, headers=HEADERS, timeout=10)
        j = r.json()
        return float(j[0]["sumOpenInterestValue"]) if j else None
    except Exception as e:
        print(f"⚠️ fetch_oi_usdt {symbol} 例外：", e)
        return None

# ---------- 推播到 Discord ----------
def push(msg: str):
    try:
        requests.post(WEBHOOK_URL, json={"content": f"```{msg}```"}, timeout=10)
    except Exception as e:
        print("⚠️ push 失敗：", e)

# ---------- 監控主迴圈 ----------
def monitor_loop():
    while True:
        symbols = top_symbols(SYMBOL_LIMIT)
        print("🪪 取得幣種數量：", len(symbols))

        snap, diff_pct = {}, {}
        for s in symbols:
            val = fetch_oi_usdt(s)
            if val is None:
                print(f"⚠️ 無 OI 資料：{s}")
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

        print("📊 本輪 snap 大小：", len(snap))

        if snap:  # 第一次也會推播
            top_pos = sorted(
                ((s, p) for s, p in diff_pct.items() if p > 0),
                key=lambda x: x[1], reverse=True)[:10]
            top_neg = sorted(
                ((s, p) for s, p in diff_pct.items() if p < 0),
                key=lambda x: x[1])[:10]
            biggest5 = sorted(snap.items(),
                              key=lambda x: x[1], reverse=True)[:5]

            ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines = [f"🌀 Binance 持倉變化量排名（{ts}）"]
            for sym, val in biggest5:
                d = diff_pct.get(sym, 0)
                lines.append(f"{sym}: 持倉量(U): {val:,.2f} | 變化: {d:+.2f}%")
            lines += ["", "👍 正成長前十："]
            for sym, d in top_pos:
                lines.append(
                    f"{sym:<10}| 變化:{d:+.2f}% | 正次數:{pos_streak.get(sym,0)}")
            lines += ["", "👎 負成長前十："]
            for sym, d in top_neg:
                lines.append(
                    f"{sym:<10}| 變化:{d:+.2f}% | 負次數:{neg_streak.get(sym,0)}")
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
