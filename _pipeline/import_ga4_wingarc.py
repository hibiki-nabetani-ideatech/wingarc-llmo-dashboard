#!/usr/bin/env python3
"""
WingArc GA4 CSV インポーター（複数ファイル対応）

期待する CSV 形式:
- ヘッダ前にコメント行（# で始まる）
- "# 開始日: YYYYMMDD" と "# 終了日: YYYYMMDD" 行から期間取得
- データ行: ユーザーの最初の参照元 / メディア,月(01-12),総ユーザー数,...,キーイベント,...

入力: raw/ga4/*_sessions_monthly_v2.csv （複数可）
出力: data_v3.json の flow フィールドを更新
"""
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data_v3.json"
RAW_DIR = ROOT.parent / "raw" / "ga4"

# AI流入ソース判定（参照元 / メディア の文字列）
AI_SOURCES = {
    "ChatGPT":    [r"chatgpt\.com", r"openai", r"chat\.openai\.com"],
    "Claude":     [r"claude\.ai", r"anthropic"],
    "Perplexity": [r"perplexity\.ai", r"perplexity"],
    "Gemini":     [r"gemini\.google\.com", r"bard\.google"],
    "Copilot":    [r"copilot\.microsoft", r"copilot\.cloud", r"copilot\.com"],
}

ORGANIC_KEYWORDS = [r"/\s*organic"]


def parse_file_period(path):
    """ファイル先頭のコメントから '開始日'/'終了日' (YYYYMMDD) を抽出"""
    start, end = None, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "開始日:" in line:
                m = re.search(r"(\d{8})", line)
                if m:
                    start = m.group(1)
            elif "終了日:" in line:
                m = re.search(r"(\d{8})", line)
                if m:
                    end = m.group(1)
            elif not line.startswith("#"):
                break
    return start, end


def infer_year(month_str, period_start, period_end):
    """月番号 (01-12) から年を推定。期間内で月が一意に決まる"""
    mm = int(month_str)
    sy, sm = int(period_start[:4]), int(period_start[4:6])
    ey, em = int(period_end[:4]), int(period_end[4:6])
    # 期間内の (year, month) リストを構築
    candidates = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        if m == mm:
            candidates.append(y)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return candidates[0] if candidates else sy


def detect_ai_brand(source_medium):
    s = str(source_medium).lower()
    for brand, patterns in AI_SOURCES.items():
        if any(re.search(p, s) for p in patterns):
            return brand
    return None


def is_organic(source_medium):
    s = str(source_medium).lower()
    return any(re.search(p, s) for p in ORGANIC_KEYWORDS)


def load_csv_skip_comments(path):
    import pandas as pd
    skip = 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.startswith("#") and "," in line and "ユーザー" in line:
                skip = i
                break
    return pd.read_csv(path, skiprows=skip, dtype={"月": str})


def main():
    files = sorted(RAW_DIR.glob("*sessions_monthly_v2.csv"))
    if not files:
        print(f"ERROR: no CSV in {RAW_DIR}")
        return

    print(f"Found {len(files)} CSV file(s)")

    # YYYY-MM -> {site_total, organic, ai_total, by_ai{brand:val}, cv_total, cv_organic, cv_ai}
    by_month = defaultdict(lambda: {
        "site_total": 0, "organic": 0, "ai_total": 0,
        "by_ai": defaultdict(int),
        "cv_total": 0, "cv_organic": 0, "cv_ai": 0,
        "cv_by_ai": defaultdict(int),
    })

    for path in files:
        start, end = parse_file_period(path)
        if not (start and end):
            print(f"  SKIP {path.name}: period not found")
            continue
        print(f"  {path.name}: {start} → {end}")
        df = load_csv_skip_comments(path)

        for _, row in df.iterrows():
            month_str = str(row["月"]).zfill(2)
            if not month_str.isdigit():
                continue
            year = infer_year(month_str, start, end)
            ym = f"{year:04d}-{month_str}"

            src = row.get("ユーザーの最初の参照元 / メディア", "")
            users = int(row.get("総ユーザー数", 0)) if str(row.get("総ユーザー数", 0)).strip().lstrip("-").isdigit() else 0
            cv = int(row.get("キーイベント", 0)) if str(row.get("キーイベント", 0)).strip().lstrip("-").isdigit() else 0

            d = by_month[ym]
            d["site_total"] += users
            d["cv_total"] += cv
            if is_organic(src):
                d["organic"] += users
                d["cv_organic"] += cv
            ai = detect_ai_brand(src)
            if ai:
                d["ai_total"] += users
                d["by_ai"][ai] += users
                d["cv_ai"] += cv
                d["cv_by_ai"][ai] += cv

    # Sort months
    months = sorted(by_month.keys())
    if not months:
        print("ERROR: no parsed months")
        return

    print(f"\nMonths: {months[0]} → {months[-1]} ({len(months)} months)")

    site_total = [by_month[m]["site_total"] for m in months]
    organic = [by_month[m]["organic"] for m in months]
    ai_total = [by_month[m]["ai_total"] for m in months]
    ai_ratio = [round(at / st * 100, 3) if st else 0.0 for at, st in zip(ai_total, site_total)]

    cv_total = [by_month[m]["cv_total"] for m in months]
    cv_organic = [by_month[m]["cv_organic"] for m in months]
    cv_ai_total = [by_month[m]["cv_ai"] for m in months]

    # AI brand groups (sessions)
    all_ais = set()
    for m in months:
        all_ais.update(by_month[m]["by_ai"].keys())

    flow_groups = []
    cv_groups = []
    BRAND_ORDER = ["ChatGPT", "Claude", "Gemini", "Perplexity", "Copilot"]
    for ai in sorted(all_ais, key=lambda x: BRAND_ORDER.index(x) if x in BRAND_ORDER else 99):
        s_monthly = [by_month[m]["by_ai"].get(ai, 0) for m in months]
        c_monthly = [by_month[m]["cv_by_ai"].get(ai, 0) for m in months]
        flow_groups.append({
            "label": f"{ai}",
            "total": sum(s_monthly),
            "llms": [{"name": ai, "values": s_monthly}],
        })
        cv_groups.append({
            "label": f"{ai}",
            "total": sum(c_monthly),
            "llms": [{"name": ai, "values": c_monthly}],
        })

    # Update data
    data = json.load(DATA_PATH.open(encoding="utf-8"))
    data["flow"]["months"] = months
    data["flow"]["series"] = {
        "site_total": site_total,
        "organic": organic,
        "ai_total": ai_total,
        "ai_ratio": ai_ratio,
    }
    data["flow"]["flow_groups"] = flow_groups
    data["flow"]["cv_total"] = cv_total
    data["flow"]["cv_organic"] = cv_organic
    data["flow"]["cv_ai_total"] = cv_ai_total
    data["flow"]["cv_site_total"] = cv_total  # 全体CV
    data["flow"]["cv_groups"] = cv_groups

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    print(f"\n=== サマリ ===")
    print(f"全期間 サイト総ユーザー数: {sum(site_total):,}")
    print(f"全期間 オーガニック検索:   {sum(organic):,}")
    print(f"全期間 AI流入合計:        {sum(ai_total):,}")
    print(f"全期間 全体CV:            {sum(cv_total):,}")
    print(f"全期間 オーガニックCV:    {sum(cv_organic):,}")
    print(f"全期間 AI流入CV:          {sum(cv_ai_total):,}")
    print(f"\nAI別流入（合計）:")
    for fg in flow_groups:
        print(f"  {fg['label']:<12} sessions={fg['total']:,}  CV={[g for g in cv_groups if g['label']==fg['label']][0]['total']}")
    print(f"\n直近月 ({months[-1]}):")
    print(f"  全体: {site_total[-1]:,}  organic: {organic[-1]:,}  AI: {ai_total[-1]:,} ({ai_ratio[-1]}%)")
    print(f"\nUpdated {DATA_PATH}")


if __name__ == "__main__":
    main()
