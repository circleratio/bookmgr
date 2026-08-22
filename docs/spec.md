# 設計書

`docs/requirement.md` の要件を踏まえた蔵書管理アプリケーションの設計。

# アーキテクチャ

- Python / FastAPI によるモノリシックなWebアプリケーション（`server/`）。元はGo/Ginで実装していたが移行した。
- REST API（`/api/*`）とサーバーサイドレンダリング画面（それ以外）を同一プロセスで提供する。
- 画面ハンドラ（SSR）はHTTP経由でAPIを呼び出さず、サービス層を直接呼び出す。
- DBはsqlite3。標準ライブラリの`sqlite3`モジュールを生SQLのまま使用する（ORMは使わない）。単一コネクションを`threading.Lock`でシリアライズし、sqlite3が並行書き込みに対応しない点をGo版（`db.SetMaxOpenConns(1)`）と同様に扱う。マイグレーションはSQLファイルを起動時に適用する簡易方式とする。
- CLIクライアント（`cli/`）もPython製。サーバーのHTTP/JSON API（`/api/*`）のみに依存し、サーバー内部実装（`server/app/`）には依存しない。

# ディレクトリ構成

```
server/
  app/
    main.py               # FastAPIアプリの組み立て（create_app）、エントリポイント（main）
    config.py             # 環境変数読み込み（Settings）
    db.py                 # sqlite3接続・起動時マイグレーション適用
    errors.py             # アプリケーションエラー型とFastAPI例外ハンドラ
    auth.py               # APIキー認証（X-API-Key）・セッションCookie認証
    schemas.py            # Pydanticモデル（Book, BookInput, BookInfo）
    template_helpers.py   # Jinja2テンプレート用ヘルパー（stars等）
    repositories/
      book_repository.py  # DBアクセス層
    services/
      book_service.py         # バリデーション・ビジネスロジック
      isbn_lookup_service.py  # Google Books API連携
    routers/
      books.py            # REST APIハンドラ（/api/books系）
      isbn_lookup.py      # REST APIハンドラ（/api/isbn-lookup）
      web_auth.py         # SSR画面: ログイン/ログアウト
      web_books.py        # SSR画面: 一覧・登録・編集・削除・ISBN検索(AJAX)
  templates/               # Jinja2テンプレート（layout.html, login.html, books/*.html）
  static/                  # CSS等の静的ファイル
  tests/                   # pytest
  requirements.txt
cli/
  bookmgr_cli/
    main.py                # エントリポイント、argparseによるサブコマンド定義
    client.py              # REST APIを呼び出すHTTPクライアント（httpx使用）
  tests/                   # pytest
  requirements.txt
db/
  migrations/              # DDL（SQLファイル、Go/Python両実装で共有）
  bookmgr.db               # sqlite3ファイル（実行時生成、.gitignore対象）
android/                    # Androidアプリ（独立したGradle/Kotlinプロジェクト）
docs/
  requirement.md
  spec.md
  plan.md
```

サーバー（`server/`）とCLI（`cli/`）は同じリポジトリ内に同居するが、それぞれ独立したPython環境（venv・`requirements.txt`）を持つ。CLIはサーバーの内部実装には依存せず、HTTP/JSON API（`/api/*`）のみを利用する。Androidも同様にHTTP/JSON APIのみに依存する。旧Go実装（`cmd/server`, `cmd/cli`, `internal/`）は移行完了に伴いすべて削除済み。

# DB設計

## books テーブル

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 書籍ID |
| title | TEXT | NOT NULL | 書名 |
| author | TEXT | NOT NULL | 著者 |
| rating | INTEGER | NULL可、CHECK(rating IS NULL OR rating BETWEEN 1 AND 5) | 評価（☆1〜5、未評価はNULL） |
| memo | TEXT | NULL可 | メモ（自由記入） |
| isbn | TEXT | NULL可、UNIQUE | ISBN（ハイフン込みの文字列として保持） |
| publisher | TEXT | NULL可 | 出版社 |
| published_date | TEXT | NULL可（`YYYY-MM-DD`） | 出版日 |
| created_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 登録日時 |
| updated_at | DATETIME | NOT NULL DEFAULT CURRENT_TIMESTAMP | 更新日時 |

```sql
CREATE TABLE books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    author          TEXT NOT NULL,
    rating          INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    memo            TEXT,
    isbn            TEXT UNIQUE,
    publisher       TEXT,
    published_date  TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_books_title  ON books(title);
CREATE INDEX idx_books_author ON books(author);
```

補足:
- sqlite3の`UNIQUE`制約はNULL同士を重複とみなさないため、ISBN未入力の書籍は`isbn`を`NULL`として保存する（空文字列は保存しない）。これにより「ISBN未入力の本は複数登録可・ISBN入力済みの本は一意」という要件を満たす。

# 認証設計

- 固定のAPIキーを環境変数（`API_KEY`）で設定する運用とする（利用者テーブルは持たない）。
- REST APIエンドポイント（`/api/*`）: リクエストヘッダー `X-API-Key` にAPIキーを必須とする。一致しない場合は `401 Unauthorized` を返す。
- SSR画面（`/`, `/books/*` など）: 未ログイン状態でアクセスすると `/login` にリダイレクトする。
  - `GET /login`: APIキー入力フォームを表示。
  - `POST /login`: 入力されたAPIキーを検証し、一致すればCookie（`session`、`HttpOnly`, `SameSite=Lax`）にAPIキーを保存してトップページへリダイレクト。不一致ならエラーメッセージ付きでログイン画面を再表示。
  - `POST /logout`: Cookieを削除してログイン画面へリダイレクト。
  - 画面用ミドルウェアはCookieの値がAPIキーと一致するかを検証する。

# API仕様

ベースパス: `/api`

共通レスポンス形式:

成功時（単体）
```json
{ "data": { "...": "..." } }
```

成功時（一覧、ページングあり）
```json
{
  "data": [ { "...": "..." } ],
  "pagination": { "page": 1, "page_size": 20, "total": 42 }
}
```

エラー時
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "title is required" } }
```

## エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | /api/books | 蔵書一覧取得（検索・ページング） |
| GET | /api/books/:id | 蔵書詳細取得 |
| POST | /api/books | 蔵書登録 |
| PUT | /api/books/:id | 蔵書更新 |
| DELETE | /api/books/:id | 蔵書削除 |
| GET | /api/isbn-lookup | ISBNから書誌情報を取得（Google Books API連携） |

### GET /api/books

クエリパラメータ:

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| q | string | 任意 | 書名・著者に対するフリーワード検索（部分一致、両カラムをOR検索） |
| page | integer | 任意（デフォルト1） | ページ番号（1始まり） |
| page_size | integer | 任意（デフォルト20、最大100） | 1ページあたりの件数 |

並び順は `id DESC`（新規登録順）固定とする。

### POST /api/books, PUT /api/books/:id

リクエストボディ:

```json
{
  "title": "吾輩は猫である",
  "author": "夏目漱石",
  "rating": 5,
  "memo": "最初の一冊",
  "isbn": "978-4-10-101035-9",
  "publisher": "新潮社",
  "published_date": "2003-05-01"
}
```

バリデーション:

| フィールド | ルール |
|---|---|
| title | 必須、1〜255文字 |
| author | 必須、1〜255文字 |
| rating | 任意、1〜5の整数、未指定は`null` |
| memo | 任意、最大2000文字 |
| isbn | 任意、ハイフンを除いて13桁（ISBN-13、数字のみ）または10桁（ISBN-10、先頭9桁は数字・末尾1桁は数字または`X`/`x`のチェックデジット）、DB上一意（重複時は`409 Conflict`） |
| publisher | 任意、最大255文字 |
| published_date | 任意、`YYYY-MM-DD`形式 |

### GET /api/isbn-lookup

クエリパラメータ:

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| isbn | string | 必須 | 検索対象のISBN（ハイフン有無どちらも可） |

`GET /books/isbn-lookup`（SSR画面用、Cookie認証）と同じ`ISBNLookupService`（`server/app/services/isbn_lookup_service.py`）を呼び出す、`X-API-Key`ヘッダー認証版のエンドポイント。CLI・Androidなどブラウザ以外のAPIクライアントはこちらを使う。レスポンス形式・エラー内容は `# ISBN検索（Google Books API連携）` を参照（成功時は`{"data": {...}}`、`isbn`未指定は`400 VALIDATION_ERROR`、該当なしは`404 NOT_FOUND`、外部API呼び出し失敗は`502`相当）。

### エラーコード

| HTTPステータス | code | 状況 |
|---|---|---|
| 400 | VALIDATION_ERROR | 入力値不正 |
| 401 | UNAUTHORIZED | APIキー不一致・未指定 |
| 404 | NOT_FOUND | 指定IDの蔵書が存在しない |
| 409 | CONFLICT | ISBN重複 |
| 500 | INTERNAL_ERROR | サーバー内部エラー |

# 画面設計（SSR）

| メソッド | パス | 説明 |
|---|---|---|
| GET | /login | ログイン画面 |
| POST | /login | ログイン処理 |
| POST | /logout | ログアウト処理 |
| GET | / | 蔵書一覧画面（検索フォーム・ページネーション付き） |
| GET | /books/new | 新規登録フォーム |
| POST | /books | 新規登録処理 |
| GET | /books/:id/edit | 編集フォーム |
| POST | /books/:id | 更新処理 |
| POST | /books/:id/delete | 削除処理 |
| GET | /books/isbn-lookup | ISBNから書誌情報を取得（JSON、新規登録フォームからのAJAX用） |

- 一覧画面は `GET /api/books` と同じクエリパラメータ（`q`, `page`）をURLクエリとして受け取り、検索状態を維持する。
- HTMLフォームは`PUT`/`DELETE`を送れないため、更新・削除は`POST`で統一する。
- フォームのバリデーションエラーはAPI層と同じルールを再利用し、入力値を保持したまま画面を再表示する。

# ISBN検索（Google Books API連携）

- 新規登録フォームにISBN入力欄と「取得」ボタンを設け、クリック時にブラウザから `GET /books/isbn-lookup?isbn=...` へfetchする（Cookieセッションで認証済みの画面用エンドポイントであり、`/api/*`とは別。`/api/*`はヘッダー認証のためブラウザJSから直接呼べないことによる）。
- サーバー側は `server/app/services/isbn_lookup_service.py` の `ISBNLookupService` が Google Books API（`https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}`）を呼び出す。検索結果には同じ書籍でもメタデータの充実度が異なる複数の候補（`items`）が含まれることがあるため、全候補を走査し各項目（書名・著者・出版社・出版日）で最初に見つかった非空の値を採用する。著者は複数著者を`,`区切りで連結する。ISBNは`ISBN_13`優先、無ければ`ISBN_10`、それも無ければ入力値を使う。
- 取得成功時: `200 { "data": { "title", "author", "publisher", "published_date", "isbn" } }`。フロントエンドJSが該当フォーム項目（書名・著者・出版社・出版日・ISBN）に反映する。評価・メモはGoogle Books側に無いため対象外。
- 該当書籍が見つからない場合: `404 { "error": "..." }`。
- APIキー未指定・不正な場合や外部API呼び出し失敗時: `400`/`502` 相当のエラーJSON。
- Google BooksのAPIキー（`GOOGLE_BOOKS_API_KEY`）は任意。設定時のみクエリパラメータ`key`として付与する（未設定でも動作する）。
- `publishedDate`が年のみ（`YYYY`）や年月のみ（`YYYY-MM`）の場合は、フォームの`date`入力欄に収まるよう`-01-01`/`-01`を補って`YYYY-MM-DD`に正規化する。

# CLIクライアント

- `cli/bookmgr_cli` に実装するPython製CLI（`argparse`でサブコマンドを定義、`client.py` が `/api/*` を `X-API-Key` ヘッダー認証で呼び出す）。
- 接続設定は環境変数で受け取る: `BOOKMGR_API_URL`（例: `http://localhost:8080`）, `BOOKMGR_API_KEY`（必須）。
- サブコマンド:
  | コマンド | 説明 |
  |---|---|
  | `bookmgr-cli list [--q ...] [--page N] [--page-size N]` | 一覧・検索（表形式で出力） |
  | `bookmgr-cli get <id>` | 詳細取得（JSON出力） |
  | `bookmgr-cli create --title ... --author ... [--rating N] [--isbn ...] [--publisher ...] [--published-date ...] [--memo ...]` | 新規登録 |
  | `bookmgr-cli update <id> [同上のフラグ]` | 更新 |
  | `bookmgr-cli delete <id>` | 削除 |
  | `bookmgr-cli isbn-lookup <isbn>` | ISBNから書誌情報取得（`GET /api/isbn-lookup`） |
- APIのエラーレスポンス（`{"error":{"code","message"}}`）はそのままエラーメッセージとして標準エラー出力に表示し、終了コード1で終了する。

# Androidクライアント

- `android/` に独立したGradle/Kotlinプロジェクトとして実装する（`server/`, `cli/`のPythonプロジェクトには含めない）。
- UI: Jetpack Compose + Material3。画面遷移はNavigation Compose。
- 機能はWeb版と同等: 設定（サーバーURL・APIキー入力、端末内に保存）、一覧・検索（ページング）、詳細表示、新規登録・編集・削除、ISBN入力による書誌情報取得（`GET /api/isbn-lookup`）。
- 通信: `/api/*` を `X-API-Key` ヘッダー認証で直接呼び出す（Web版と異なりCookieを使わないため、サーバー側の変更は不要）。
- 設定値の永続化: Jetpack DataStore（Preferences）。
- 初回起動時、サーバーURL・APIキーが未設定であれば設定画面を表示する。

# 非機能

- テスト: `server/tests`・`cli/tests`（いずれもpytest）を中心にユニットテスト・ハンドラテストを整備する。
- マイグレーション: `db/migrations/0001_create_books.sql` を起動時に適用する。
- 設定: `API_KEY`, `PORT`, `DB_PATH`, `GOOGLE_BOOKS_API_KEY`（任意）を環境変数で受け取る。
