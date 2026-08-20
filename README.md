# bookmgr

蔵書管理のためのウェブアプリケーション。REST API とサーバーサイドレンダリング画面を Gin で提供する。詳細は `docs/requirement.md`, `docs/spec.md`, `docs/plan.md` を参照。

## 起動方法

```sh
export API_KEY=your-secret-key       # 必須
export PORT=8080                     # 任意（デフォルト 8080）
export DB_PATH=db/bookmgr.db         # 任意（デフォルト db/bookmgr.db）
export GOOGLE_BOOKS_API_KEY=...      # 任意（新規登録画面のISBN取得機能で使用。未設定でも動作する）

go run ./cmd/server
```

起動時に `db/migrations/` 配下のSQLが自動適用される（`CREATE TABLE/INDEX IF NOT EXISTS` のため複数回実行しても安全）。

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)
- 新規登録画面ではISBNを入力して「取得」ボタンを押すと、Google Books API から書名・著者・出版社・出版日を取得してフォームに反映できる。

## ビルド

```sh
go build -o bookmgr ./cmd/server
```

`bookmgr` バイナリが生成される。実行方法は起動方法と同様に環境変数を設定してから起動する。

```sh
API_KEY=your-secret-key ./bookmgr
```

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
go test ./...
```

