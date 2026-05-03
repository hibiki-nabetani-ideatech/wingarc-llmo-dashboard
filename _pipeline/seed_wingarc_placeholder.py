#!/usr/bin/env python3
"""
Seed data_v3.json with WingArc placeholder shape.

Keeps:
- ai_topics (copied from IDEA — generic AI news, not company-specific)
- rubric (LLMO evaluation criteria — universal)
- diag structure (groups/items same; clear scores/reasons)

Resets:
- flow: 24 months of zero data
- prompts: 24 WingArc-relevant Brand Radar prompts, empty responses
- citation_main / citation_competitor: empty rows

Run:
    python3 seed_wingarc_placeholder.py
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data_v3.json"
d = json.load(DATA_PATH.open(encoding="utf-8"))

# ---------- 24 prompts from Brand Radar report ----------
WINGARC_PROMPTS = [
    "設備異常をリアルタイムで検知・通知できるBIツールは。",
    "自社サーバーに置けて、海外に出ない誠実系BIを探しています。",
    "現場のモニタでリアルタイムで監視したいため、最適なシステム構成案と技術スタックを提案して。",
    "帳票文化に合ったBIツールを探している。",
    "外資BIと国産BIの違いを教えて。",
    "外資BIから国産BIへの切り替え・代替をしたいが、機能面やコスト面で優れた国産BIを探して。",
    "国産BIツールでおすすめはどれか。",
    "分析結果を見て終わりではなく、発注・通知・承認依頼まで完結させたい。",
    "予実管理と帳票を一つのツールで実現できるBIツールはあるか。",
    "データの真正性を担保しつつAIを活用する方法は。",
    "ダッシュボードからPDF・Excelを出力できるBIツールを教えて。",
    "セキュリティに厳しい企業向けのBIツールは。",
    "オンプレミスで運用できるBIツールのおすすめは。",
    "Tableauと同等の機能を持つ国産BIツールはあるか。",
    "Power BI以外でおすすめのBIツールは。",
    "Power BIをやめてAIで内製すべきか。",
    "IoTデータをリアルタイムでダッシュボード化したい。",
    "BIツールと帳票出力の連携を強化したい時何から手をつければいい。",
    "BIツールで簡易的な業務アプリを作りたい。",
    "AI時代にデータ基盤はどう変わるのか教えて。",
    "AIとBIツールの使い分けを教えて。",
    "AIでダッシュボードを自動生成できるか。",
    "AIでBIツールを代替できるのかソース付きで教えて",
    "AIがあればBIツールは不要なのか。",
]

# ---------- prompts.rows: empty WingArc shape ----------
empty_responses = [""] * 4  # 4 LLMs (chatgpt/copilot/gemini/perplexity)
empty_links = {"chatgpt": [], "copilot": [], "gemini": [], "perplexity": []}

new_rows = []
for i, p in enumerate(WINGARC_PROMPTS, start=1):
    cat = "AI/BI 比較" if "AI" in p else (
        "国産BI" if "国産" in p else (
            "Tableau/Power BI比較" if ("Tableau" in p or "Power BI" in p) else (
                "オンプレ/セキュリティ" if any(k in p for k in ["オンプレ", "セキュリティ", "サーバー"]) else "汎用"
            )
        )
    )
    new_rows.append({
        "no": i,
        "category": cat,
        "volume": None,        # to be filled from Brand Radar / Keywords Explorer
        "prompt": p,
        "responses": empty_responses,
        "prizma": [False] * 4,  # legacy field name, repurposed for "competitor1 mention"
        "links_by_llm": empty_links,
        "wingarc": [False] * 4,
    })

d["prompts"] = {
    "survey_date": datetime.now().strftime("%Y-%m-%d"),
    "llms": ["chatgpt", "copilot", "gemini", "perplexity"],
    "rows": new_rows,
    "footnotes": [
        "Brand Radarレポート 「【モニタリング】MotionBoard / Tableau / Power BI」 由来のプロンプト 24本。",
        "responses / mentions は ahrefs Brand Radar から取り込み予定。",
    ],
    "_last_brand_radar_sync": None,
}

# ---------- diag: clear scores/reasons, keep structure ----------
for item in d["diag"]:
    item["score"] = None
    item["reason"] = "WingArc 初期診断未実施"

# ---------- flow: zero-fill last 24 months ----------
today = datetime.now()
months = []
for i in range(23, -1, -1):
    m = (today.replace(day=1) - timedelta(days=30 * i))
    months.append(f"{m.year:04d}-{m.month:02d}")
months = sorted(set(months))[-24:]

n = len(months)
zero_series = [0] * n

d["flow"] = {
    "months": months,
    "series": {
        "ai_ratio": [0.0] * n,
        "site_total": zero_series.copy(),
        "organic": zero_series.copy(),
        "ai_total": zero_series.copy(),
    },
    "flow_groups": [
        {"label": "ChatGPT 流入", "total": 0, "llms": []},
        {"label": "Claude 流入", "total": 0, "llms": []},
        {"label": "Perplexity 流入", "total": 0, "llms": []},
        {"label": "Gemini 流入", "total": 0, "llms": []},
    ],
    "cv_total": zero_series.copy(),
    "cv_site_total": zero_series.copy(),
    "cv_organic": zero_series.copy(),
    "cv_ai_total": zero_series.copy(),
    "cv_groups": [],
}

# ---------- citations: empty ----------
d["citation_main"] = {
    "summary": {
        "今月言及数": "0件",
        "今年言及数": "0件",
        "総言及数": "0件",
    },
    "rows": [],
}
d["citation_competitor"] = {
    "summary": {
        "今月言及数": "0件",
        "今年言及数": "0件",
        "総言及数": "0件",
    },
    "rows": [],
}

# ---------- diff: clear ----------
d["diff"] = {
    "generated_at": datetime.now().isoformat(),
    "prev_generated_at": None,
    "has_prev": False,
    "flow": {},
    "cv": {},
    "prompts": {},
    "citation_main": {},
    "citation_competitor": {},
}

# ---------- meta ----------
d["source_file"] = "WingArc LLMO PRJ.xlsx"
d["sheets"] = []
d["_generated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

# Write
DATA_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {DATA_PATH} ({DATA_PATH.stat().st_size} bytes)")
print(f"  prompts: {len(d['prompts']['rows'])} rows")
print(f"  diag: {len(d['diag'])} items (all scores cleared)")
print(f"  flow.months: {n} months ({months[0]} → {months[-1]})")
print(f"  ai_topics.entries: {len(d['ai_topics']['entries'])} (preserved)")
