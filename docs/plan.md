# 実装計画

`docs/spec.md` の設計に基づく実装手順。フェーズ順に上から実装する。Androidアプリはサーバーの内部実装に依存しない独立したクライアントのため対象外。

# 使用ライブラリ

- Webフレームワーク: FastAPI
- ASGIサーバー: Uvicorn
- HTTPクライアント: httpx（Google Books API呼び出し、CLIからのAPI呼び出し）
- テンプレートエンジン: Jinja2（`fastapi.templating.Jinja2Templates`）
- sqlite3: 標準ライブラリ`sqlite3`モジュール（ORM不使用、生SQLで実装）
- テスト: pytest

# フェーズ0: プロジェクト初期化

- [x] `server/` ディレクトリ作成、`requirements.txt` 作成
- [x] `server/app/` 以下のパッケージ雛形作成（`repositories`, `services`, `routers`）
- [x] `.gitignore` に `.venv/`, `__pycache__/`, `db/*.db` を追加

# フェーズ1: DB層

- [x] `server/app/db.py`: sqlite3接続初期化・起動時マイグレーション適用。単一コネクションを `threading.Lock` でシリアライズし、sqlite3の並行書き込み非対応に対処
- [x] `server/app/schemas.py`: `Book` / `BookInput` / `BookInfo`（Pydanticモデル）。フィールド名は `docs/spec.md` のAPI契約に一致させる
- [x] `server/app/repositories/book_repository.py`: `BookRepository` 実装（`list` / `find_by_id` / `find_by_isbn` / `create` / `update` / `delete`）。ISBN重複はsqlite3の `IntegrityError` を判定して `ConflictError` に変換
- [x] リポジトリ層のテスト（`:memory:` DB使用、`server/tests/test_book_repository.py`）

# フェーズ2: サービス層

- [x] `server/app/services/book_service.py`: バリデーション（title/author必須、rating範囲、isbn桁数、published_date形式）とリポジトリ呼び出しの仲介
- [x] `server/app/errors.py`: `ValidationError` / `NotFoundError` / `ConflictError` 等のアプリケーションエラー型と、FastAPIの例外ハンドラで `{"error": {"code","message"}}` 形式に変換する仕組み
- [x] サービス層のテスト（`server/tests/test_book_service.py`、ISBN境界値・rating境界値・published_date形式などの境界値を網羅）

# フェーズ3: REST API層

- [x] `server/app/routers/books.py`: 5エンドポイント＋ISBN検索用 `GET /api/books/by-isbn/:isbn` を実装
- [x] `server/app/routers/isbn_lookup.py`: `GET /api/isbn-lookup`（`server/app/services/isbn_lookup_service.py` がGoogle Books APIを呼び出し、複数候補のフィールドマージ・ISBN優先順位・published_date正規化を行う）
- [x] 共通レスポンス形式（`data` / `pagination` / `error`）を例外ハンドラで統一的に生成
- [x] APIハンドラのテスト（`fastapi.testclient.TestClient`、`server/tests/test_books_api.py` / `test_isbn_lookup_api.py`）

# フェーズ4: 認証

- [x] `server/app/auth.py`
  - API用: `X-API-Key` ヘッダー検証（`require_api_key`、不一致・未指定は `401`）
  - Web用: `session` Cookie検証（`require_web_session`、未ログインは `/login` へリダイレクト）
- [x] `API_KEY` は環境変数から読み込み、未設定時は起動失敗（`server/app/config.py` の `Settings.from_env`）

# フェーズ5: SSR画面

- [x] `server/templates/` にJinja2テンプレート作成（`layout.html`, `login.html`, `books/list.html`, `books/form.html`）。`extends` / `block` 継承で共通レイアウトを構成
- [x] `server/app/routers/web_auth.py`: ログイン/ログアウト処理
- [x] `server/app/routers/web_books.py`: 一覧・登録・編集・削除・ISBN検索（AJAX用、Cookie認証）の画面ハンドラ
- [x] `server/static/style.css` を配置

# フェーズ6: ルーティング・エントリポイント

- [x] `server/app/main.py`: `create_app(settings)` でDB初期化・`Jinja2Templates`/`StaticFiles`設定・ルーター登録・ライフスパン（終了時にDBクローズ）を組み立て、`main()` で環境変数読み込み→`uvicorn.run`

# フェーズ7: サーバーの動作確認・仕上げ

- [x] `pytest`（`server/tests/`、61件）が通ることを確認
- [x] 手動でサーバーを起動し、curlでログイン→一覧→登録→編集→削除、ISBN検索（API・Web両方）、認証エラー・バリデーションエラーの表示を確認
- [x] READMEの起動方法を記載（`server/` + venv + `python -m app.main`）
- [x] `docs/requirement.md` / `docs/spec.md` の技術スタック・アーキテクチャ記述を整備

# フェーズ8: CLIクライアント

- [x] `cli/` ディレクトリ作成、`requirements.txt`（httpx, pytest）作成
- [x] `cli/bookmgr_cli/client.py`: `/api/*` を `X-API-Key` ヘッダー認証で呼び出すHTTPクライアント。`{"error":{"code","message"}}` を `APIError` に変換
- [x] `cli/bookmgr_cli/main.py`: `argparse` によるサブコマンド構成（`list`/`get`/`create`/`update`/`delete`/`isbn-lookup`）。テーブル出力・JSON出力（インデント2・非ASCIIエスケープなし）
- [x] Windows環境で標準出力の既定エンコーディングにより日本語が文字化けする問題に対応し、`main()` 内で `sys.stdout`/`sys.stderr` を明示的にUTF-8に固定
- [x] `cli/tests/test_client.py`: `httpx.MockTransport` で疑似サーバーを立て、CRUD・バリデーションエラー・認証エラー・検索/ページングを検証
- [x] 手動でサーバーを起動し、全サブコマンド（list/get/create/update/delete/isbn-lookup）と認証エラー・404エラーの経路をCLI経由で確認
- [x] READMEのCLI起動方法を記載（`cli/` + venv + `python -m bookmgr_cli`）

# 実装順序の理由

DBスキーマ・モデルを最初に固めてから、下位層（repository）→中位層（service）→上位層（handler）の順で積み上げることで、各層を独立してテストしながら進めた。認証はAPI・SSR画面どちらの層にも影響するため、両ハンドラの実装と並行して組み込んだ。SSR画面はテンプレートの書き方自体が独立した関心事のため、先に固めたサービス層をそのまま再利用する形で最後に着手し、画面側の実装量を抑えた。CLIクライアントはサーバーのHTTP/JSON API契約のみに依存する独立したクライアントのため、サーバーの実装が固まった後に着手した。
