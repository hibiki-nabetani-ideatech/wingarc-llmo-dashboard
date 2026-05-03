# WingArc MotionBoard LLMO ダッシュボード

GitHub Pages 公開ダッシュボード（静的・手動更新フォーク）。

- 公開 URL: https://hibiki-nabetani-ideatech.github.io/wingarc-llmo-dashboard/
- 公開範囲: URL を知っている人のみ（`<meta robots="noindex">` および `robots.txt` で検索エンジン除外）
- 更新方式: 手動。新しい CSV / Brand Radar JSON を `raw/` 配下に配置した後、`bash _pipeline/manual_update.sh` を実行して `index.html` を再生成する。
- 自動更新（週次 cron）や ChatWork 通知は無効化済み。

## 手動更新フロー

1. 新しい CSV を `raw/` 配下に配置（または ahrefs Brand Radar JSON を `${BR_DIR:-/tmp/br}` に配置）
2. リポジトリのルートで以下を実行:
   ```bash
   bash _pipeline/manual_update.sh
   ```
3. `git status` / `git diff` で変更内容を確認した上で commit & push。

`manual_update.sh` は以下を順に実行する:

1. `data_v3.json` → `data_v3_prev.json` のスナップショット
2. Brand Radar JSON のマージ（存在する場合）
3. ⑤ AI Topics の取得（`ANTHROPIC_API_KEY` 未設定時はスキップ）
4. 前回更新比 差分の計算（`compute_diff.py`）
5. ダッシュボード HTML の再生成（`build_html_v3.py` → `../index.html`）

## ファイル構成

- `index.html` — ダッシュボード本体（自動生成）
- `robots.txt` — 検索エンジン除外
- `_pipeline/` — 更新パイプライン一式
  - `manual_update.sh` — 手動更新エントリポイント
  - `build_html_v3.py` — HTML ビルダ
  - `compute_diff.py` — 前回更新比 差分計算
  - `fetch_ai_topics.py` — ⑤ AI Topics 自動収集
  - `fetch_brand_radar.py` / `merge_brand_radar.py` — ahrefs Brand Radar 連携
  - `data_v3.json` — ダッシュボードに埋め込まれる元データ
- `README.md` — このファイル
