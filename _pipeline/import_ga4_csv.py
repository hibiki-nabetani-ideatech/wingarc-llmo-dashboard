#!/usr/bin/env python3
"""
import_ga4_csv.py — GA4 CSV エクスポートを data_v3.json の `flow` フィールドに取り込む

## 使い方

1. GA4 (https://analytics.google.com/) にアクセス
2. 「レポート」→「集客」→「ユーザー獲得」 で、左上のディメンションを「セッションのデフォルトチャネルグループ」または「セッションの参照元 / メディア」に変更
3. 期間を「過去24か月」程度に設定
4. 右上の「共有」→「ファイルをダウンロード」→「CSV をダウンロード」
5. ダウンロードした CSV を以下のディレクトリに配置:
       <repo>/raw/ga4/sessions_YYYYMMDD.csv

   さらに、コンバージョン CSV も同様に:
       <repo>/raw/ga4/conversions_YYYYMMDD.csv

6. このスクリプトを実行:
       cd _pipeline
       python3 import_ga4_csv.py

7. data_v3.json が更新される。続けて build_html_v3.py で HTML を再生成。

## 期待する CSV 形式（GA4 標準エクスポート）

GA4 の CSV は冒頭に何行かのコメント行が入ります。スクリプトは "#" 始まりの行を読み飛ばし、本文を pandas で読み込みます。

最低限必要な列：
- 期間/月: "年月" / "月" / "Date" のいずれか
- セッション数: "セッション" / "Sessions"
- 参照元: 行ごとに「Organic Search」「ChatGPT」「Gemini」などのチャネル/参照元名

スクリプトは "ChatGPT", "Claude", "Perplexity", "Gemini" を含む参照元を AI流入として集計します。

## 出力

data_v3.json の以下フィールドを更新:
- flow.months
- flow.series.site_total
- flow.series.organic
- flow.series.ai_total
- flow.series.ai_ratio
- flow.flow_groups (LLM別流入)
- flow.cv_* (conversions_*.csv がある場合)
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data_v3.json"
RAW_DIR = ROOT.parent / "raw" / "ga4"

# AI流入の判定キーワード（参照元名 or 参照元/メディア に含まれる）
AI_SOURCES = {
    "ChatGPT": ["chatgpt", "openai"],
    "Claude": ["claude", "anthropic"],
    "Perplexity": ["perplexity"],
    "Gemini": ["gemini", "bard"],
    "Copilot": ["copilot", "bing.com/chat"],
}

ORGANIC_KEYWORDS = ["organic search", "オーガニック検索", "google / organic", "yahoo / organic"]


def load_csv_skip_comments(path):
    """GA4 CSV はヘッダ前にコメント行が入る → 読み飛ばし"""
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas が必要です: pip3 install pandas --break-system-packages")

    # Find start of actual table (line starting with non-#)
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    skip = 0
    for i, line in enumerate(lines):
        # Heuristic: header row contains comma and at least one alphabetical char
        if "," in line and not line.strip().startswith("#") and len(line.strip()) > 5:
            skip = i
            break
    return pd.read_csv(path, skiprows=skip)


def parse_month(value):
    """'202501', '2025年01月', '2025-01', '2025/01', 'Jan 2025' などから YYYY-MM 抽出"""
    s = str(value).strip()
    # YYYY-MM
    m = re.match(r"(\d{4})[-年/]?(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    # YYYYMM
    if re.match(r"^\d{6}$", s):
        return f"{s[:4]}-{s[4:]}"
    return None


def detect_ai_brand(source_name):
    """参照元文字列から AI ブランド検出 ('ChatGPT' など) or None"""
    s = str(source_name).lower()
    for brand, keywords in AI_SOURCES.items():
        if any(k in s for k in keywords):
            return brand
    return None


def is_organic(source_name):
    s = str(source_name).lower()
    return any(k in s for k in ORGANIC_KEYWORDS)


def import_sessions(csv_path):
    """sessions_*.csv を読み、月別の {site_total, organic, ai_total, by_ai} を返す"""
    df = load_csv_skip_comments(csv_path)
    print(f"  Loaded {csv_path.name}: {len(df)} rows, columns={list(df.columns)}")

    # Detect column names heuristically
    month_col = next((c for c in df.columns if any(k in c.lower() for k in ["月", "month", "date", "年"])), None)
    sessions_col = next((c for c in df.columns if any(k in c.lower() for k in ["セッション", "session"])), None)
    source_col = next((c for c in df.columns if any(k in c.lower() for k in ["参照元", "チャネル", "source", "channel"])), None)

    if not (month_col and sessions_col and source_col):
        print(f"  WARN: missing required columns; need month/sessions/source")
        return None

    # Aggregate
    by_month = defaultdict(lambda: {"site_total": 0, "organic": 0, "ai_total": 0, "by_ai": defaultdict(int)})
    for _, row in df.iterrows():
        m = parse_month(row[month_col])
        if not m:
            continue
        sessions = int(row[sessions_col]) if str(row[sessions_col]).strip().isdigit() else 0
        src = row[source_col]

        by_month[m]["site_total"] += sessions
        if is_organic(src):
            by_month[m]["organic"] += sessions
        ai = detect_ai_brand(src)
        if ai:
            by_month[m]["ai_total"] += sessions
            by_month[m]["by_ai"][ai] += sessions

    return dict(by_month)


def main():
    if not RAW_DIR.exists():
        print(f"ERROR: {RAW_DIR} not found. Create it and place your GA4 CSV exports there.")
        print(f"   mkdir -p {RAW_DIR}")
        sys.exit(1)

    sessions_files = sorted(RAW_DIR.glob("sessions_*.csv"))
    conversions_files = sorted(RAW_DIR.glob("conversions_*.csv"))

    if not sessions_files:
        print(f"WARN: no sessions_*.csv found in {RAW_DIR}")
        print(f"  Expected files like: sessions_YYYYMMDD.csv")
        return

    print(f"Found {len(sessions_files)} sessions CSV, {len(conversions_files)} conversions CSV")

    # Use the latest sessions file
    print(f"Importing sessions from: {sessions_files[-1].name}")
    by_month = import_sessions(sessions_files[-1])
    if not by_month:
        sys.exit("Failed to import sessions data")

    months = sorted(by_month.keys())
    print(f"Months covered: {months[0]} → {months[-1]} ({len(months)} months)")

    # Build flow data structure
    site_total = [by_month[m]["site_total"] for m in months]
    organic = [by_month[m]["organic"] for m in months]
    ai_total = [by_month[m]["ai_total"] for m in months]
    ai_ratio = [round(at / st * 100, 2) if st else 0.0 for at, st in zip(ai_total, site_total)]

    # AI brand groups
    flow_groups = []
    all_ais = set()
    for m in months:
        all_ais.update(by_month[m]["by_ai"].keys())

    for ai in sorted(all_ais):
        monthly = [by_month[m]["by_ai"].get(ai, 0) for m in months]
        flow_groups.append({
            "label": f"{ai} 流入",
            "total": sum(monthly),
            "llms": [{"name": ai, "values": monthly}],
        })

    # Load existing data
    data = json.load(DATA_PATH.open(encoding="utf-8"))
    data["flow"]["months"] = months
    data["flow"]["series"] = {
        "site_total": site_total,
        "organic": organic,
        "ai_total": ai_total,
        "ai_ratio": ai_ratio,
    }
    data["flow"]["flow_groups"] = flow_groups

    # Conversions (optional)
    if conversions_files:
        print(f"Importing conversions from: {conversions_files[-1].name}")
        cv_by_month = import_sessions(conversions_files[-1])  # same shape parser works
        if cv_by_month:
            cv_months = sorted(cv_by_month.keys())
            # Align to flow.months
            data["flow"]["cv_total"] = [cv_by_month.get(m, {"site_total":0})["site_total"] for m in months]
            data["flow"]["cv_organic"] = [cv_by_month.get(m, {"organic":0})["organic"] for m in months]
            data["flow"]["cv_ai_total"] = [cv_by_month.get(m, {"ai_total":0})["ai_total"] for m in months]
            data["flow"]["cv_site_total"] = data["flow"]["cv_total"]

    # Save
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nUpdated {DATA_PATH}")
    print(f"  Sessions total: {sum(site_total):,}")
    print(f"  AI流入 total: {sum(ai_total):,} ({sum(ai_total)/max(sum(site_total),1)*100:.1f}%)")
    print(f"\n次のステップ:")
    print(f"  python3 build_html_v3.py --out ../index.html")


if __name__ == "__main__":
    main()
