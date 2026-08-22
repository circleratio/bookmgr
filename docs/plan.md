# 実装計画

`docs/spec.md` の設計に基づく実装手順。フェーズ順に上から実装する。

# 使用ライブラリ

- Webフレームワーク: `github.com/gin-gonic/gin`
- sqlite3ドライバ: `modernc.org/sqlite`（pure Go実装。CGO不要でクロスコンパイル・ビルドが容易なため採用）
- `database/sql` 標準パッケージ経由でドライバを利用する（ORMは使わない）

# フェーズ0: プロジェクト初期化

- [ ] `go.mod` 作成（`go mod init`）
- [ ] `gin-gonic/gin`, `modernc.org/sqlite` を `go get`
- [ ] ディレクトリ雛形作成（`cmd/server`, `internal/{model,repository,service,handler/api,handler/web,middleware}`, `db/migrations`, `templates`, `static`）
- [ ] `.gitignore` 作成（`db/bookmgr.db`, バイナリ等）
- [ ] git初期化・最初のコミット

# フェーズ1: DB層

- [ ] `db/migrations/0001_create_books.sql` を作成（`docs/spec.md` のDDLをそのまま使用）
- [ ] `internal/model/book.go`: `Book` 構造体定義（`rating` は `*int`、`isbn`/`memo`/`publisher`/`published_date` は `*string` でNULL許容を表現）
- [ ] `internal/repository/db.go`: sqlite3接続初期化・起動時マイグレーション適用処理
- [ ] `internal/repository/book_repository.go`: `BookRepository` インターフェースと実装
  - `List(ctx, query string, page, pageSize int) ([]Book, total int, error)`
  - `FindByID(ctx, id int64) (*Book, error)`
  - `Create(ctx, *Book) error`
  - `Update(ctx, *Book) error`
  - `Delete(ctx, id int64) error`
  - ISBN重複は sqlite3 の `UNIQUE` 制約違反エラーを判定して呼び出し元へ返す
- [ ] リポジトリ層の単体テスト（`:memory:` DBを使用）

# フェーズ2: サービス層

- [ ] `internal/service/book_service.go`: バリデーションとリポジトリ呼び出しの仲介
  - `docs/spec.md` のバリデーションルール（title/author必須、rating範囲、isbn桁数、published_date形式）を実装
  - 独自エラー型（`ErrValidation`, `ErrNotFound`, `ErrConflict`）を定義し、ハンドラ層でHTTPステータスに変換できるようにする
- [ ] サービス層の単体テスト（バリデーション境界値、ISBN重複時のエラー等）

# フェーズ3: REST API層

- [ ] `internal/handler/api/book_handler.go`: 5エンドポイント実装
  - `GET /api/books`（`q`, `page`, `page_size` クエリ対応）
  - `GET /api/books/:id`
  - `POST /api/books`
  - `PUT /api/books/:id`
  - `DELETE /api/books/:id`
- `docs/spec.md` の共通レスポンス形式（`data`/`pagination`/`error`）に沿ったヘルパー関数を用意する
- [ ] APIハンドラのテスト（`httptest` + `net/http/httptest` でリクエスト/レスポンス検証）

# フェーズ4: 認証ミドルウェア

- [ ] `internal/middleware/auth.go`
  - API用: `X-API-Key` ヘッダー検証（不一致・未指定は `401`）
  - Web用: `session` Cookie検証、未ログインは `/login` へリダイレクト
- [ ] APIキーは環境変数 `API_KEY` から読み込む（`cmd/server/main.go` で起動時に必須チェック）

# フェーズ5: SSR画面

- [ ] `templates/` にレイアウト・各画面のHTMLテンプレート作成（`layout.html`, `login.html`, `books/list.html`, `books/form.html`）
- [ ] `internal/handler/web/auth_handler.go`: ログイン/ログアウト処理
- [ ] `internal/handler/web/book_handler.go`: 一覧・登録・編集・削除の画面ハンドラ（サービス層を直接呼び出す）
- [ ] `static/` に最低限のCSS配置

# フェーズ6: ルーティング・エントリポイント

- [ ] `cmd/server/main.go`: 環境変数読み込み（`API_KEY`, `PORT`, `DB_PATH`）、DB初期化、ミドルウェア・ルーティング登録、サーバー起動

# フェーズ7: 動作確認・仕上げ

- [ ] `go build` / `go vet` / `go test ./...` が通ることを確認
- [ ] 手動でサーバーを起動し、ブラウザでログイン→一覧→登録→編集→削除の一連の操作を確認
- [ ] `curl` で `/api/books` のCRUD・検索・ページング・認証エラーを確認
- [ ] READMEに起動方法（環境変数、`go run ./cmd/server`）を記載

# 実装順序の理由

DBスキーマ・モデルを最初に固めてから、下位層（repository）→中位層（service）→上位層（handler）の順で積み上げることで、各層を独立してテストしながら進める。認証ミドルウェアはAPI・画面どちらにも影響するため、両ハンドラの実装と並行または直後に組み込む。
