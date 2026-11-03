#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓證交所融資餘額與加權指數，寫入 docs/data.json（給 GitHub Actions 每天執行）。
X = 融資餘額(億)/2100*100 ; Y = 加權指數/17306*100 ; 差 = X-Y
差>=30 極度危險 ; >=26 危險 ; <26 觀察
用法：python fetch_data.py            # 抓今天（資料不足時自動補抓近45天）
      python fetch_data.py --date 20261030
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

MARGIN_BASE = 2100
INDEX_BASE = 17306
DANGER, EXTREME = 26, 30
RETRY_TIMES, RETRY_WAIT = 3, 300
DATA_FILE = Path(__file__).parent / "docs" / "data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (margin-monitor)"}
URL_MARGIN = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
URL_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
TW = timezone(timedelta(hours=8))


def to_float(s):
    return float(str(s).replace(",", "").strip())


def fetch_margin(d):
    r = requests.get(URL_MARGIN, headers=HEADERS, timeout=30,
                     params={"date": d, "selectType": "MS", "response": "json"})
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK":
        return None
    tables = j.get("tables") or [{"data": j.get("creditList", [])}]
    for t in tables:
        for row in t.get("data", []):
            if "融資金額" in str(row[0]):
                return to_float(row[-1]) / 100000.0   # 仟元 -> 億元
    return None


def fetch_index(d):
    r = requests.get(URL_INDEX, headers=HEADERS, timeout=30,
                     params={"date": d, "response": "json"})
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK":
        return None
    fields = j.get("fields", [])
    col = next((i for i, f in enumerate(fields) if "加權股價指數" in f), 4)
    for row in j.get("data", []):
        y, m, dd = row[0].split("/")
        if f"{int(y) + 1911}{int(m):02d}{int(dd):02d}" == d:
            return to_float(row[col])
    return None


def classify(diff):
    if diff >= EXTREME:
        return "極度危險", "extreme"
    if diff >= DANGER:
        return "危險", "danger"
    return "觀察", "watch"


def load():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}


def save(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def update_one(d, retry):
    for i in range(1, (RETRY_TIMES if retry else 1) + 1):
        try:
            margin, index = fetch_margin(d), fetch_index(d)
            if margin is not None and index is not None:
                x, y = margin / MARGIN_BASE * 100, index / INDEX_BASE * 100
                diff = x - y
                label, level = classify(diff)
                key = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                rec = {"date": key, "margin": round(margin, 2), "index": round(index, 2),
                       "x": round(x, 2), "y": round(y, 2), "diff": round(diff, 2),
                       "label": label, "level": level}
                data = load()
                data[key] = rec
                save(data)
                print(f"{key} 融資={rec['margin']}億 指數={rec['index']} 差={rec['diff']} {label}")
                return True
            print(f"[{d}] 第{i}次：查無資料（休市或尚未公布）")
        except Exception as e:
            print(f"[{d}] 第{i}次失敗：{e}")
        if retry and i < RETRY_TIMES:
            time.sleep(RETRY_WAIT)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    args = ap.parse_args()

    if args.date:
        update_one(args.date, retry=False)
        return

    now = datetime.now(TW)
    if len(load()) < 10:                      # 第一次執行：補抓近 45 天
        for n in range(45, 0, -1):
            d = now - timedelta(days=n)
            if d.weekday() < 5:
                update_one(d.strftime("%Y%m%d"), retry=False)
                time.sleep(3)
    if now.weekday() < 5:
        update_one(now.strftime("%Y%m%d"), retry=True)


if __name__ == "__main__":
    main()
