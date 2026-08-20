# 設計書

`docs/requirement.md` の要件を踏まえた蔵書管理アプリケーションの設計。

# アーキテクチャ

- Go / Gin によるモノリシックなWebアプリケーション。
- REST API（`/api/*`）とサーバーサイドレンダリング画面（それ以外）を同一プロセスで提供する。
- 画面ハンドラはHTTP経由でAPIを呼び出さず、サービス層を直接呼び出す。
- DBはsqlite3。マイグレーションはSQLファイルを起動時に適用する簡易方式とする。

# ディレクトリ構成

```
cmd/
  server/
    main.go            # エントリポイント、ルーティング定義
internal/
  model/                # 構造体定義（Book等）
  repository/           # DBアクセス層（database/sql）
  service/               # ビジネスロジック・バリデーション
  handler/
    api/                 # REST APIハンドラ
    web/                 # SSR画面ハンドラ
  middleware/            # APIキー認証ミドルウェア
db/
  migrations/            # DDL（SQLファイル）
  bookmgr.db             # sqlite3ファイル（実行時生成、.gitignore対象）
templates/                # HTMLテンプレート（html/template）
static/                    # CSS等の静的ファイル
docs/
  requirement.md
  spec.md
```

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
| isbn | 任意、ハイフンを除いた数字10桁または13桁、DB上一意（重複時は`409 Conflict`） |
| publisher | 任意、最大255文字 |
| published_date | 任意、`YYYY-MM-DD`形式 |

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

- 一覧画面は `GET /api/books` と同じクエリパラメータ（`q`, `page`）をURLクエリとして受け取り、検索状態を維持する。
- HTMLフォームは`PUT`/`DELETE`を送れないため、更新・削除は`POST`で統一する。
- フォームのバリデーションエラーはAPI層と同じルールを再利用し、入力値を保持したまま画面を再表示する。

# 非機能

- テスト: `internal/service`, `internal/repository` を中心にユニットテストを整備する。
- マイグレーション: `db/migrations/0001_create_books.sql` を起動時に適用する。
- 設定: `API_KEY`, `PORT`, `DB_PATH` を環境変数で受け取る。
