#!/usr/bin/env python3
"""每天 23:00(台北)由 GitHub Actions 執行,用 LINE 推播融資水位最新結果。

不用開電腦:跑在 GitHub 的免費伺服器上。
資料來源:同一個 repo 的 docs/data.json(每天 22:00 由 update-data workflow 從證交所抓回來);
若本地檔不存在,改抓 GitHub Pages 上的 data.json。

設定方法:
  1. 把 notify_line.py 放到 repo 根目錄,.github/workflows/notify.yml 放到對應位置,commit 並 push。
  2. GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret,
     新增 LINE_CHANNEL_ACCESS_TOKEN(在 LINE Developers 按 Issue 取得)與 LINE_USER_ID(你的 U 開頭 ID)。
  3. Actions 分頁 -> notify-line -> Run workflow 可手動測試一次(不加 --dry-run 會真的發送)。
  4. 之後每天 23:00 自動發送;假日或資料未公布時改推最近一筆並註明日期。

本地測試: LINE_CHANNEL_ACCESS_TOKEN=x LINE_USER_ID=Uxxx python notify_line.py --dry-run
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_URL = "https://rf5523.github.io/margin-monitor/data.json"
PAGE_URL = "https://rf5523.github.io/margin-monitor/"
PUSH_URL = "https://api.line.me/v2/bot/message/push"
TW = timezone(timedelta(hours=8))


def load_data():
    local = Path(__file__).resolve().parent / "docs" / "data.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0 (margin-notify)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_message(rec, today=None):
    today = today or datetime.now(TW).date().isoformat()
    stale = rec["date"] != today
    lines = [
        "【融資水位日報】" + rec["date"],
        "融資餘額: %s 億" % format(rec["margin"], ",.2f"),
        "加權指數: %s" % format(rec["index"], ",.2f"),
        "水位差 X-Y: %s(%s)" % (format(rec["diff"], "+.2f"), rec["label"]),
        "判斷: >=30 極度危險、>=26 危險、<26 觀察",
    ]
    if stale:
        lines.insert(1, "注意: 今日尚無新資料(休市或尚未公布),以下為最近一筆 " + rec["date"] + " 的資料")
    lines.append("詳細: " + PAGE_URL)
    lines.append("資料來源: 臺灣證券交易所")
    return "\n".join(lines)


def push(token, to, text):
    body = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        PUSH_URL, data=body, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("LINE API 回 %s: %s" % (e.code, detail))


def main():
    ap = argparse.ArgumentParser(description="融資水位每日 23:00 LINE 推播(GitHub Actions 用)")
    ap.add_argument("--dry-run", action="store_true", help="只印出訊息,不發送")
    args = ap.parse_args()

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    users = [x.strip() for x in os.environ.get("LINE_USER_ID", "").split(",") if x.strip()]
    if not token or not users:
        print("缺少 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID(請設在 repo Settings -> Secrets)", file=sys.stderr)
        return 2
    try:
        data = load_data()
        rec = data[max(data)]
        msg = format_message(rec)
    except Exception as e:
        print("抓資料失敗: %s" % e, file=sys.stderr)
        return 1
    if args.dry_run:
        print(msg)
        return 0
    for to in users:
        push(token, to, msg)
    print("已發送(收件者 %d 位)" % len(users))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
