# WingArc MotionBoard LLMO ダッシュボード

GitHub Pages 公開ダッシュボード（手動更新版・週次cronなし・Chatwork連携なし）。

- 公開 URL: https://hibiki-nabetani-ideatech.github.io/wingarc-llmo-dashboard/v2
- 公開範囲: URL を知っている人のみ（`<meta robots="noindex">` および `robots.txt` で検索エンジン除外）
- 更新: 手動（`bash _pipeline/manual_update.sh`）

## ファイル構成

- `index.html` — ダッシュボード本体（自動生成、コミット）
- `robots.txt` — 検索エンジン除外
- `_pipeline/` — 生成スクリプト一式
  - `build_html_v3.py` — HTML 生成
  - `data_v3.json` — 生データ
  - `manual_update.sh` — 手動再ビルド（snapshot → BR merge → diff → build）
  - `import_ga4_csv.py` — GA4 CSV 取り込み（②タブ用）
  - `seed_wingarc_placeholder.py` — 初期シード（実行済み、再実行不要）
  - `fetch_brand_radar.py` / `merge_brand_radar.py` — Brand Radar 取り込み
  - `fetch_ai_topics.py` — AI ニュース取り込み（要 `ANTHROPIC_API_KEY`）
- `raw/ga4/` — GA4 CSV 配置場所
- `_pipeline/data_v3_prev.json` — 前回更新時のスナップショット（差分計算用、自動生成）

## 各タブのデータソース

| タブ | データ | 更新方法 |
|---|---|---|
| ① 初期診断 | `data.diag` (20項目スコア) | 手動編集 (`data_v3.json` を直接) |
| ② Webトラフィック / CV | `data.flow` | GA4 CSVを `raw/ga4/` に置いて `import_ga4_csv.py` |
| ③ プロンプト | `data.prompts` | `python3 fetch_brand_radar.py && python3 merge_brand_radar.py` |
| ④ サイテーション | `data.citation_main`, `data.citation_competitor` | `manual_update.sh` 経由で BR 取り込み |
| ⑤ 主要AIニュース | `data.ai_topics` | `python3 fetch_ai_topics.py`（要APIキー） |

## 更新フロー

```bash
# 1. データ更新
cd _pipeline
python3 import_ga4_csv.py        # GA4 CSV を反映（必要時）
bash manual_update.sh            # Brand Radar・AI Topics を反映

# 2. push してデプロイ
cd ..
git add -A && git commit -m "data refresh"
git push
```

## カスタマイズ

`data_v3.json` を直接編集 → `python3 _pipeline/build_html_v3.py --out index.html` で再生成。
