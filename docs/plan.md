# 実装計画（Python/FastAPI移行）

`docs/spec.md` の設計に基づく、サーバー実装のGo/GinからPython/FastAPIへの移行手順。CLIクライアント（`cmd/cli`, `internal/apiclient`）とAndroidアプリはHTTP/JSON APIのみに依存するため対象外（無改修）。

# 使用ライブラリ

- Webフレームワーク: FastAPI
- ASGIサーバー: Uvicorn
- HTTPクライアント: httpx（Google Books API呼び出し）
- テンプレートエンジン: Jinja2（`fastapi.templating.Jinja2Templates`）
- sqlite3: 標準ライブラリ`sqlite3`モジュール（ORM不使用。Go版の`database/sql`＋生SQLの構成をそのまま踏襲）
- テスト: pytest

# フェーズ0: プロジェクト初期化

- [x] `server/` ディレクトリ作成、`requirements.txt` 作成
- [x] `server/app/` 以下のパッケージ雛形作成（`repositories`, `services`, `routers`）
- [x] `.gitignore` に `.venv/`, `__pycache__/`, `db/*.db` を追加

# フェーズ1: DB層

- [x] `server/app/db.py`: sqlite3接続初期化・起動時マイグレーション適用。Go版と同じ `db/migrations/` を共有し、単一コネクションを `threading.Lock` でシリアライズすることでsqlite3の並行書き込み非対応に対処（Go版の `db.SetMaxOpenConns(1)` と同じ狙い）
- [x] `server/app/schemas.py`: `Book` / `BookInput` / `BookInfo`（Pydanticモデル）。JSONフィールド名はGo版の `json` タグとそのまま一致させ、クライアント側の契約を変えない
- [x] `server/app/repositories/book_repository.py`: `BookRepository` 実装（`list` / `find_by_id` / `find_by_isbn` / `create` / `update` / `delete`）。ISBN重複はsqlite3の `IntegrityError` を判定して `ConflictError` に変換
- [x] リポジトリ層のテスト（`:memory:` DB使用、`server/tests/test_book_repository.py`）。Go版 `book_repository_test.go` の全ケースを移植

# フェーズ2: サービス層

- [x] `server/app/services/book_service.py`: バリデーション（title/author必須、rating範囲、isbn桁数、published_date形式）とリポジトリ呼び出しの仲介。Go版 `internal/service/book_service.go` のロジックを1対1で移植
- [x] `server/app/errors.py`: `ValidationError` / `NotFoundError` / `ConflictError` 等のアプリケーションエラー型と、FastAPIの例外ハンドラで `{"error": {"code","message"}}` 形式に変換する仕組み
- [x] サービス層のテスト（`server/tests/test_book_service.py`）。Go版 `book_service_test.go` の全ケース（ISBN境界値、rating境界値、published_date形式など）を移植

# フェーズ3: REST API層

- [x] `server/app/routers/books.py`: 5エンドポイント＋ISBN検索用 `GET /api/books/by-isbn/:isbn` を実装
- [x] `server/app/routers/isbn_lookup.py`: `GET /api/isbn-lookup`（`server/app/services/isbn_lookup_service.py` がGoogle Books APIを呼び出し、複数候補のフィールドマージ・ISBN優先順位・published_date正規化のロジックをGo版から移植）
- [x] Go版と同じ共通レスポンス形式（`data` / `pagination` / `error`）を例外ハンドラで統一的に生成し、パスやクエリパラメータの緩いパース（数値変換に失敗しても既定値にフォールバック等）もGo版の挙動に合わせる
- [x] APIハンドラのテスト（`fastapi.testclient.TestClient`、`server/tests/test_books_api.py` / `test_isbn_lookup_api.py`）。Go版 `book_handler_test.go` / `isbn_lookup_test.go` の全ケースを移植

# フェーズ4: 認証

- [x] `server/app/auth.py`
  - API用: `X-API-Key` ヘッダー検証（`require_api_key`、不一致・未指定は `401`）
  - Web用: `session` Cookie検証（`require_web_session`、未ログインは `/login` へリダイレクト）
- [x] `API_KEY` は環境変数から読み込み、未設定時は起動失敗（`server/app/config.py` の `Settings.from_env`）

# フェーズ5: SSR画面

- [x] `server/templates/` にJinja2テンプレート作成（`layout.html`, `login.html`, `books/list.html`, `books/form.html`）。Go版の名前付きテンプレート合成（`{{define}}`/`{{template}}`）からJinja2の `extends` / `block` 継承方式に置き換え、`strVal`/`intVal`/`orDash` ヘルパーは `or ''` 相当の式で代替
- [x] `server/app/routers/web_auth.py`: ログイン/ログアウト処理
- [x] `server/app/routers/web_books.py`: 一覧・登録・編集・削除・ISBN検索（AJAX用、Cookie認証）の画面ハンドラ
- [x] `server/static/style.css` をGo版からそのまま流用

# フェーズ6: ルーティング・エントリポイント

- [x] `server/app/main.py`: `create_app(settings)` でDB初期化・`Jinja2Templates`/`StaticFiles`設定・ルーター登録・ライフスパン（終了時にDBクローズ）を組み立て、`main()` で環境変数読み込み→`uvicorn.run`

# フェーズ7: 動作確認・仕上げ

- [x] `pytest`（`server/tests/`、Go版の全テストケースを移植、61件）が通ることを確認
- [x] 手動でサーバーを起動し、curlでログイン→一覧→登録→編集→削除、ISBN検索（API・Web両方）、認証エラー・バリデーションエラーの表示を確認
- [x] READMEの起動方法をPython版（`server/` + venv + `python -m app.main`）に更新
- [x] `docs/requirement.md` / `docs/spec.md` の技術スタック・アーキテクチャ記述をPython/FastAPIに更新
- [ ] 動作確認完了後、旧Go実装（`cmd/server`, `internal/{model,repository,service,handler,middleware}`）を削除する（CLIが使う `internal/apiclient`, `cmd/cli` は対象外）

# 実装順序の理由

Go版のレイヤー構成（repository → service → handler）をそのまま踏襲し、同じ順序でPythonに移植した。ルーティング・JSON形状・エラーコードといった外部契約を一切変えないことを最優先し、各層でGo版の既存テストケースをpytestに1対1で移植することで、移行によるデグレードがないことを機械的に検証できるようにした。認証は API/Web どちらの層にも影響するため、両ハンドラの実装と並行して組み込んだ。SSR画面はテンプレートエンジンの書き方自体が変わる（Goのテンプレート合成 → Jinja2の継承）ため最後に着手し、先に固めたサービス層をそのまま再利用することで画面側の実装量を抑えた。
