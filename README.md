# bookmgr

蔵書管理のためのウェブアプリケーション。REST API とサーバーサイドレンダリング画面を Gin で提供する。詳細は `docs/requirement.md`, `docs/spec.md`, `docs/plan.md` を参照。

## 起動方法

```sh
export API_KEY=your-secret-key   # 必須
export PORT=8080                 # 任意（デフォルト 8080）
export DB_PATH=db/bookmgr.db     # 任意（デフォルト db/bookmgr.db）

go run ./cmd/server
```

起動時に `db/migrations/` 配下のSQLが自動適用される（`CREATE TABLE/INDEX IF NOT EXISTS` のため複数回実行しても安全）。

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)

## ビルド

```sh
go build -o bookmgr ./cmd/server
```

`bookmgr` バイナリが生成される。実行方法は起動方法と同様に環境変数を設定してから起動する。

```sh
API_KEY=your-secret-key ./bookmgr
```

## テスト

```sh
go test ./...
```

