# Smart Journal AI

ローカルで動く証憑自動仕訳支援アプリです。証憑のテキスト抽出、ルールベースの仕訳推定、過去履歴の参照、AI補助、承認済みCSV出力を組み合わせて、会計担当者がレビューしやすい仕訳案を提示します。

## 主要機能

- PDF/画像証憑のアップロード
- 文字抽出と金額・取引先の抽出
- ルールベースの仕訳推定
- 類似履歴の参照と修正理由の保存
- AI補助の利用（Ollamaが利用可能な場合）
- 証憑ごとの監査証跡とレビュー要約
- SQLite保存
- 承認済み仕訳のCSV出力

## アーキテクチャ

- UI: Streamlit
- 解析: PyMuPDF / pytesseract
- 数据保存: SQLite
- ルール推定: 独自ルール + 過去履歴の補正
- AI連携: ローカルOllamaのみ
- 監査: journal_history, journal_entries, ocr_extractions

## ローカル実行

```bash
cd "/Users/shimizuaika/Documents/journal entry-app"
./.venv/bin/python -m pytest -q
./.venv/bin/streamlit run app.py --server.headless true --server.port 8505
```

## 必要ソフトウェア

- Python 3.9+
- Tesseract OCR（画像OCRを使う場合）
- Ollama（AI補助を使う場合）

## 推奨LLM

- qwen2.5:7b-instruct
- llama3.1:8b-instruct

## GitHub / デプロイ方針

### GitHub

- ソースコードの管理先としては GitHub を推奨します。
- まずはローカル開発版を GitHub に push し、実運用環境を段階的に構築するのが安全です。

### Vercel について

- Vercel は主に Node.js / Next.js 前提で設計されています。
- このアプリは Python + Streamlit ベースのため、Vercel ではなく Streamlit Community Cloud、Render、Railway、または自社VM/EC2 などのほうが適しています。
- ただし、ローカルファーストで証憑処理を行う用途では、最初は GitHub とローカル実行環境を確立してからクラウド公開を検討するのが現実的です。

## 注意事項

- AI連携はローカル環境の Ollama のみ利用する設計です。
- Ollama が未導入でも、ルールベースの仕訳推定とレビュー表示は動作します。
- 仕訳の最終承認は人間が行う前提です。AIは補助として扱います。
