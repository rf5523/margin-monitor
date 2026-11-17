#!/usr/bin/env python3
"""每天 22:00(台北)抓取證交所資料,計算融資水位差,寫入 docs/data.json。

資料來源(皆為證交所官網公開 JSON,不用爬儀表板 HTML,那頁是 JS 動態載入):
  融資餘額: https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date=YYYYMMDD&selectType=ALL
    -> 第 1 張表「信用交易統計」中「融資金額(仟元)」列的「今日餘額」,
       單位仟元,除以 100,000 換算成「億」。
  加權指數: https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date=YYYYMMDD
    -> 當月每日資料中,日期相符那列的「發行量加權股價指數」。

計算:
  X = 融資餘額(億) / 2100 * 100
  Y = 加權指數 / 17306 * 100
  差值 = X - Y
  差值 >= 30          -> 極度危險
  差值 >= 26          -> 危險
  差值 <  26          -> 觀察

用法:
  python fetch_margin.py                 # 抓最近一個有資料的交易日(今天沒公布就往前找)
  python fetch_margin.py --date 20261116 # 只抓指定日期
  python fetch_margin.py --backfill-days 30  # 回補最近 30 天的歷史
  python fetch_margin.py --dry-run       # 只印出結果,不寫檔

只用 Python 標準函式庫,不用 pip 安裝任何套件。
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

MARGIN_URL = ("https://www.twse.com.tw/exchangeReport/MI_MARGN"
              "?response=json&date={yyyymmdd}&selectType=ALL")
INDEX_URL = ("https://www.twse.com.tw/exchangeReport/FMTQIK"
             "?response=json&date={yyyymmdd}")

MARGIN_BASE = 2100.0   # 融資餘額基準(億)
INDEX_BASE = 17306.0   # 加權指數基準
HEADERS = {"User-Agent": "Mozilla/5.0 (margin-monitor; contact: repo owner)"}
TIMEOUT = 30


def get_json(url, tries=3):
    """抓一個 JSON,失敗重試 3 次(間隔 5 秒)。"""
    last_err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - 重試時只記錄最後一次錯誤
            last_err = e
            if i < tries - 1:
                time.sleep(5)
    raise RuntimeError("抓 %s 失敗: %s" % (url, last_err))


def parse_margin(payload):
    """從 MI_MARGN 回傳中取出融資餘額(億)。找不到/當日無資料回傳 None。"""
    if not isinstance(payload, dict) or payload.get("stat") != "OK":
        return None
    for table in payload.get("tables", []):
        for row in table.get("data", []):
            if row and str(row[0]).startswith("融資金額"):
                try:
                    thousand_ntd = float(str(row[-1]).replace(",", ""))
                except (ValueError, IndexError):
                    return None
                return round(thousand_ntd / 100000.0, 2)  # 仟元 -> 億
    return None


def parse_index(payload, target):
    """從 FMTQIK 回傳中取出指定日期的加權指數。找不到回傳 None。

    target 是 datetime.date;證交所日期是民國年格式,如 115/11/16。
    """
    if not isinstance(payload, dict) or payload.get("stat") != "OK":
        return None
    roc = "%d/%02d/%02d" % (target.year - 1911, target.month, target.day)
    for row in payload.get("data", []):
        if row and str(row[0]).strip() == roc:
            try:
                return float(str(row[4]).replace(",", ""))
            except (ValueError, IndexError):
                return None
    return None


def classify(diff):
    if diff >= 30:
        return "極度危險", "extreme"
    if diff >= 26:
        return "危險", "danger"
    return "觀察", "watch"


def fetch_one(target):
    """抓某一天的兩筆資料,算出完整紀錄;當日無資料回傳 None。"""
    yyyymmdd = target.strftime("%Y%m%d")
    margin = parse_margin(get_json(MARGIN_URL.format(yyyymmdd=yyyymmdd)))
    if margin is None:
        return None
    index = parse_index(get_json(INDEX_URL.format(yyyymmdd=yyyymmdd)), target)
    if index is None:
        return None
    # 差值用未四捨五入的 X、Y 相減再取兩位小數,才會跟線上 data.json 一致
    # (先把 X、Y 各自四捨五入再相減,會差 0.01~0.02)
    x_raw = margin / MARGIN_BASE * 100
    y_raw = index / INDEX_BASE * 100
    x = round(x_raw, 2)
    y = round(y_raw, 2)
    diff = round(x_raw - y_raw, 2)
    label, level = classify(diff)
    return {
        "date": target.isoformat(),
        "margin": margin,
        "index": index,
        "x": x,
        "y": y,
        "diff": diff,
        "label": label,
        "level": level,
    }


def find_latest(start, lookback=10):
    """從 start 往前找最近一個兩筆資料都有的交易日。"""
    for i in range(lookback):
        day = start - timedelta(days=i)
        try:
            rec = fetch_one(day)
        except RuntimeError:
            raise
        if rec is not None:
            return rec
        time.sleep(1)
    return None


def load_data(path):
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def main():
    ap = argparse.ArgumentParser(description="抓取證交所融資餘額與加權指數,計算水位差")
    ap.add_argument("--date", help="指定日期 YYYYMMDD,預設為最近有資料的交易日")
    ap.add_argument("--backfill-days", type=int, default=0,
                    help="回補最近 N 天的歷史(每天各抓一次)")
    ap.add_argument("--data", default="docs/data.json", help="data.json 路徑")
    ap.add_argument("--dry-run", action="store_true", help="只印出結果,不寫檔")
    args = ap.parse_args()

    data_path = Path(args.data)
    data = load_data(data_path)
    today = date.today()
    new_recs = []

    if args.backfill_days > 0:
        for i in range(args.backfill_days - 1, -1, -1):
            day = today - timedelta(days=i)
            try:
                rec = fetch_one(day)
            except RuntimeError as e:
                print("抓 %s 失敗: %s" % (day, e), file=sys.stderr)
                continue
            if rec is not None:
                new_recs.append(rec)
            time.sleep(1)
    elif args.date:
        try:
            target = date(int(args.date[0:4]), int(args.date[4:6]), int(args.date[6:8]))
        except ValueError:
            print("--date 格式錯誤,請用 YYYYMMDD,例如 20261116", file=sys.stderr)
            return 2
        try:
            rec = fetch_one(target)
        except RuntimeError as e:
            print("抓取失敗: %s" % e, file=sys.stderr)
            return 1
        if rec is None:
            print("%s 沒有資料(休市或尚未公布)" % target.isoformat())
            return 0
        new_recs.append(rec)
    else:
        try:
            rec = find_latest(today)
        except RuntimeError as e:
            print("抓取失敗: %s" % e, file=sys.stderr)
            return 1
        if rec is None:
            print("最近 10 天都沒有資料,可能為連假或證交所未公布")
            return 0
        new_recs.append(rec)

    for rec in new_recs:
        data[rec["date"]] = rec
        print("%s 融資 %.2f 億 指數 %.2f X=%.2f Y=%.2f 差值 %+.2f(%s)" % (
            rec["date"], rec["margin"], rec["index"],
            rec["x"], rec["y"], rec["diff"], rec["label"]))

    if args.dry_run:
        print("(dry-run,不寫檔)")
        return 0
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("已寫入 %s,共 %d 筆" % (data_path, len(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
