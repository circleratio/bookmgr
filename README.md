# bookmgr

蔵書管理のためのウェブアプリケーション。REST API とサーバーサイドレンダリング画面を Python/FastAPI（`server/`）で提供する。詳細は `docs/requirement.md`, `docs/spec.md`, `docs/plan.md` を参照（これらはGo実装当時の設計書だが、DB設計・API仕様・画面仕様はPython版でも変更していない）。

> 元はGo/Ginで実装していたが、Python/FastAPIへ移行した。Go実装（`cmd/server`, `internal/`）は動作確認用に一時的に残しており、CLIクライアント（`cmd/cli`）とは無関係に後日削除する予定。

## 起動方法

```sh
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows。macOS/Linuxは `source .venv/bin/activate`
pip install -r requirements.txt

export API_KEY=your-secret-key       # 必須
export PORT=8080                     # 任意（デフォルト 8080）
export DB_PATH=db/bookmgr.db         # 任意（デフォルト db/bookmgr.db、リポジトリルート基準）
export GOOGLE_BOOKS_API_KEY=...      # 任意（新規登録画面のISBN取得機能で使用。未設定でも動作する）

python -m app.main
```

起動時に `db/migrations/` 配下のSQLが自動適用される（`CREATE TABLE/INDEX IF NOT EXISTS` のため複数回実行しても安全）。

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)
- 新規登録画面ではISBNを入力して「取得」ボタンを押すと、Google Books API から書名・著者・出版社・出版日を取得してフォームに反映できる。

## CLIクライアント

```sh
go build -o bookmgr-cli ./cmd/cli

export BOOKMGR_API_URL=http://localhost:8080   # 任意（デフォルト http://localhost:8080）
export BOOKMGR_API_KEY=your-secret-key         # 必須（サーバーの API_KEY と同じ値）

./bookmgr-cli list --q 猫
./bookmgr-cli get 1
./bookmgr-cli create --title "吾輩は猫である" --author "夏目漱石" --rating 5
./bookmgr-cli update 1 --title "坊っちゃん" --author "夏目漱石"
./bookmgr-cli delete 1
./bookmgr-cli isbn-lookup 9784101010359
```

## Androidクライアント

`android/` 配下に独立したGradle/Kotlin(Jetpack Compose)プロジェクトとして実装している。Android Studioで `android/` を開いて実行する。詳細は `android/README.md` を参照。

## テスト

```sh
cd server
pytest
```

CLIクライアント（Go）側のテストは従来通り:

```sh
go test ./internal/apiclient/...
```

