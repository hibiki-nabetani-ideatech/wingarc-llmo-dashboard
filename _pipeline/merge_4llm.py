#!/usr/bin/env python3
"""
merge_4llm.py - Merge 4-LLM Brand Radar custom-prompt data into data_v3.json.

Reads:
  raw/br_2026_05/br_chatgpt.json
  raw/br_2026_05/br_gemini.json
  raw/br_2026_05/br_copilot.json
  raw/br_2026_05/br_perplexity.json

Each is shape {"ai_responses": [{question, response, links, volume}]}.

Writes data_v3.json with prompts.rows reshaped per the spec:
  - prompts.llms = ["ChatGPT","Gemini","Copilot","Perplexity"]
  - prompts.rows = 24 custom rows + 32 ahrefs rows
  - custom rows have all 4 LLMs filled
  - ahrefs rows have only ChatGPT (slot 0) filled, rest empty
  - wingarc/tableau/powerbi arrays are booleans of length 4
  - links_by_llm is a dict {"ChatGPT": [...], ...}
  - reclassified categories applied
"""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, 'data_v3.json')
RAW_DIR = os.path.join(ROOT, 'raw', 'br_2026_05')

LLMS = ["ChatGPT", "Gemini", "Copilot", "Perplexity"]
LLM_FILES = {
    "ChatGPT":    "br_chatgpt.json",
    "Gemini":     "br_gemini.json",
    "Copilot":    "br_copilot.json",
    "Perplexity": "br_perplexity.json",
}

# Brand mention regexes (case-insensitive)
WINGARC_RX = re.compile(
    r'(motionboard|モーションボード|motion\s*board|wingarc|ウイングアーク|ウィングアーク)',
    re.IGNORECASE,
)
TABLEAU_RX = re.compile(r'(tableau|タブロー)', re.IGNORECASE)
POWERBI_RX = re.compile(
    r'(power\s*bi|powerbi|パワー\s*bi|パワー\s*ビーアイ|パワービーアイ)',
    re.IGNORECASE,
)

# 24 custom prompts in canonical order (the ones to keep)
CUSTOM_PROMPTS = [
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

# Category reclassification map (exact prompt -> category)
CATEGORY_MAP = {
    "設備異常をリアルタイムで検知・通知できるBIツールは。": "IoT・リアルタイム監視",
    "自社サーバーに置けて、海外に出ない誠実系BIを探しています。": "オンプレ・セキュリティ",
    "現場のモニタでリアルタイムで監視したいため、最適なシステム構成案と技術スタックを提案して。": "IoT・リアルタイム監視",
    "帳票文化に合ったBIツールを探している。": "帳票・出力",
    "外資BIと国産BIの違いを教えて。": "国産 vs 外資",
    "外資BIから国産BIへの切り替え・代替をしたいが、機能面やコスト面で優れた国産BIを探して。": "国産 vs 外資",
    "国産BIツールでおすすめはどれか。": "国産 vs 外資",
    "分析結果を見て終わりではなく、発注・通知・承認依頼まで完結させたい。": "業務アプリ・ワークフロー",
    "予実管理と帳票を一つのツールで実現できるBIツールはあるか。": "帳票・出力",
    "データの真正性を担保しつつAIを活用する方法は。": "AI × BI",
    "ダッシュボードからPDF・Excelを出力できるBIツールを教えて。": "帳票・出力",
    "セキュリティに厳しい企業向けのBIツールは。": "オンプレ・セキュリティ",
    "オンプレミスで運用できるBIツールのおすすめは。": "オンプレ・セキュリティ",
    "Tableauと同等の機能を持つ国産BIツールはあるか。": "製品比較",
    "Power BI以外でおすすめのBIツールは。": "製品比較",
    "Power BIをやめてAIで内製すべきか。": "AI × BI",
    "IoTデータをリアルタイムでダッシュボード化したい。": "IoT・リアルタイム監視",
    "BIツールと帳票出力の連携を強化したい時何から手をつければいい。": "帳票・出力",
    "BIツールで簡易的な業務アプリを作りたい。": "業務アプリ・ワークフロー",
    "AI時代にデータ基盤はどう変わるのか教えて。": "AI × BI",
    "AIとBIツールの使い分けを教えて。": "AI × BI",
    "AIでダッシュボードを自動生成できるか。": "AI × BI",
    "AIでBIツールを代替できるのかソース付きで教えて": "AI × BI",
    "AIがあればBIツールは不要なのか。": "AI × BI",
}


def jst_now() -> str:
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')


def normalize_q(q: str) -> str:
    if not q:
        return ''
    s = q.strip()
    s = re.sub(r'\s+', '', s)
    return s


def detect_mentions(text: str) -> tuple[bool, bool, bool]:
    if not text:
        return False, False, False
    return (
        bool(WINGARC_RX.search(text)),
        bool(TABLEAU_RX.search(text)),
        bool(POWERBI_RX.search(text)),
    )


def extract_links(links_field) -> list[str]:
    urls = []
    if not links_field:
        return urls
    for l in links_field:
        if isinstance(l, dict):
            u = l.get('url') or l.get('link') or ''
            if u:
                urls.append(u)
        elif isinstance(l, str):
            urls.append(l)
    return urls


def load_llm_responses(llm_name: str) -> dict[str, dict]:
    """Returns dict keyed by normalized question."""
    fname = LLM_FILES[llm_name]
    path = os.path.join(RAW_DIR, fname)
    if not os.path.isfile(path):
        print(f'WARN: missing {path} - {llm_name} will have empty responses', file=sys.stderr)
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    ar = d.get('ai_responses') if isinstance(d, dict) else d
    if not ar:
        print(f'WARN: no ai_responses in {path}', file=sys.stderr)
        return {}
    by_q = {}
    for r in ar:
        q = normalize_q(r.get('question', ''))
        if q:
            by_q[q] = r
    return by_q


def build_custom_rows(llm_data: dict[str, dict[str, dict]]) -> list[dict]:
    """llm_data: {llm_name: {norm_q: response_obj}}."""
    rows = []
    for i, prompt in enumerate(CUSTOM_PROMPTS, start=1):
        nq = normalize_q(prompt)
        responses = []
        wingarc_arr = []
        tableau_arr = []
        powerbi_arr = []
        links_by_llm = {}
        max_volume = 0

        for llm in LLMS:
            r = llm_data.get(llm, {}).get(nq)
            if r:
                resp = r.get('response') or ''
                responses.append(resp)
                w, t, p = detect_mentions(resp)
                wingarc_arr.append(w)
                tableau_arr.append(t)
                powerbi_arr.append(p)
                links_by_llm[llm] = extract_links(r.get('links'))
                v = r.get('volume')
                if isinstance(v, (int, float)) and v > max_volume:
                    max_volume = int(v)
            else:
                responses.append('')
                wingarc_arr.append(False)
                tableau_arr.append(False)
                powerbi_arr.append(False)
                links_by_llm[llm] = []

        rows.append({
            "no": i,
            "source": "custom",
            "category": CATEGORY_MAP.get(prompt, "その他"),
            "volume": max_volume,
            "prompt": prompt,
            "responses": responses,
            "wingarc": wingarc_arr,
            "tableau": tableau_arr,
            "powerbi": powerbi_arr,
            "links_by_llm": links_by_llm,
        })
    return rows


def expand_ahrefs_row(row: dict) -> dict:
    """Take an existing ahrefs row (with potentially length-1 arrays) and expand to length 4."""
    n = 4
    # responses: keep slot 0 from existing, others empty
    cur_resp = row.get('responses') or []
    if not isinstance(cur_resp, list):
        cur_resp = []
    new_resp = [(cur_resp[0] if len(cur_resp) > 0 else '')] + [''] * (n - 1)

    # wingarc / tableau / powerbi as booleans
    def to_bool(v):
        if v is True or v == '⚫︎' or v == '●' or v == '◉':
            return True
        return False

    def expand_brand(arr):
        if not isinstance(arr, list):
            arr = []
        first = to_bool(arr[0]) if len(arr) > 0 else False
        return [first, False, False, False]

    new_w = expand_brand(row.get('wingarc'))
    new_t = expand_brand(row.get('tableau'))
    new_p = expand_brand(row.get('powerbi'))

    # links_by_llm: existing was {"chatgpt": [...]} -> normalize to {"ChatGPT": [...], ...}
    cur_links = row.get('links_by_llm') or {}
    if isinstance(cur_links, dict):
        chatgpt_links = cur_links.get('chatgpt') or cur_links.get('ChatGPT') or []
    elif isinstance(cur_links, list):
        chatgpt_links = cur_links[0] if len(cur_links) > 0 and isinstance(cur_links[0], list) else []
    else:
        chatgpt_links = []
    new_links = {
        "ChatGPT": chatgpt_links,
        "Gemini": [],
        "Copilot": [],
        "Perplexity": [],
    }

    out = dict(row)  # preserve other fields like no, source, category, volume, prompt, search_queries
    out['responses'] = new_resp
    out['wingarc'] = new_w
    out['tableau'] = new_t
    out['powerbi'] = new_p
    out['links_by_llm'] = new_links
    return out


def main():
    # Load all 4 LLMs
    llm_data = {}
    for llm in LLMS:
        llm_data[llm] = load_llm_responses(llm)
        print(f'  loaded {llm}: {len(llm_data[llm])} responses')

    # Load existing data_v3.json
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    p = data.setdefault('prompts', {})

    # Pull existing ahrefs rows
    existing_rows = p.get('rows') or []
    ahrefs_rows = [r for r in existing_rows if r.get('source') == 'ahrefs']
    print(f'  existing ahrefs rows: {len(ahrefs_rows)}')

    # Expand ahrefs rows to len 4
    new_ahrefs_rows = [expand_ahrefs_row(r) for r in ahrefs_rows]

    # Build custom rows
    custom_rows = build_custom_rows(llm_data)
    print(f'  built custom rows: {len(custom_rows)}')

    # Renumber: custom rows 1..24, ahrefs rows 25..56 (but keep their original 'no' if you want)
    # The existing data preserves 'no' from the original. Let's just renumber sequentially.
    all_rows = []
    n = 1
    for r in custom_rows:
        r['no'] = n
        all_rows.append(r)
        n += 1
    for r in new_ahrefs_rows:
        r['no'] = n
        all_rows.append(r)
        n += 1

    p['llms'] = LLMS
    p['rows'] = all_rows
    p['_last_brand_radar_sync'] = jst_now()

    # Write back
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    # ===== Verification stats =====
    print('\n=== Verification ===')
    custom_only = [r for r in all_rows if r['source'] == 'custom']
    populated_cells = sum(1 for r in custom_only for resp in r['responses'] if resp)
    total_cells = len(custom_only) * 4
    print(f'Custom rows × LLMs: {len(custom_only)} × 4 = {total_cells} cells, {populated_cells} populated')

    print('\nMention rates per brand × LLM (custom rows only):')
    for brand_key, label in [('wingarc', 'WingArc'), ('tableau', 'Tableau'), ('powerbi', 'Power BI')]:
        per = []
        for i, llm in enumerate(LLMS):
            cnt = sum(1 for r in custom_only if r[brand_key][i])
            per.append(f'{llm} {cnt}/{len(custom_only)}')
        print(f'  {label}: ' + ', '.join(per))

    print('\nCategory distribution (custom rows):')
    from collections import Counter
    cats = Counter(r['category'] for r in custom_only)
    for cat, cnt in cats.most_common():
        print(f'  {cat}: {cnt}')

    print(f'\nWrote {DATA_PATH}')


if __name__ == '__main__':
    main()
