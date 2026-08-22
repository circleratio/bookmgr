# bookmgr

蔵書管理のためのウェブアプリケーション。REST API とサーバーサイドレンダリング画面を Python/FastAPI（`server/`）で提供する。詳細は `docs/requirement.md`, `docs/spec.md`, `docs/plan.md` を参照。

## 起動方法

```sh
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows。macOS/Linuxは `source .venv/bin/activate`
pip install -r requirements.txt

export API_KEY=your-secret-key       # 必須
export HOST=0.0.0.0                  # 任意（デフォルト 0.0.0.0。リバースプロキシ配下では127.0.0.1推奨、後述）
export PORT=8080                     # 任意（デフォルト 8080）
export DB_PATH=db/bookmgr.db         # 任意（デフォルト db/bookmgr.db、リポジトリルート基準）
export GOOGLE_BOOKS_API_KEY=...      # 任意（新規登録画面のISBN取得機能で使用。未設定でも動作する）
export COOKIE_SECURE=false           # 任意（デフォルト false。HTTPS配信時はtrueにする、後述）

python -m app.main
```

起動時に `db/migrations/` 配下のSQLが自動適用される（`CREATE TABLE/INDEX IF NOT EXISTS` のため複数回実行しても安全）。

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)
- 新規登録画面ではISBNを入力して「取得」ボタンを押すと、Google Books API から書名・著者・出版社・出版日を取得してフォームに反映できる。

## HTTPS化（Caddyをリバースプロキシとして使う）

ドメインを持つサーバーで公開する場合、[Caddy](https://caddyserver.com/) を前段に置きTLS終端させる。Let's Encrypt証明書の取得・更新はCaddyが自動で行う。

1. サーバーをローカルポートのみで待ち受けるように起動する（外部から直接`PORT`にアクセスできないようにする）。

   ```sh
   export API_KEY=your-secret-key
   export HOST=127.0.0.1          # Caddyからのみ受け付ける
   export COOKIE_SECURE=true      # HTTPS配信時はセッションCookieにSecure属性を付与する

   python -m app.main
   ```

   `COOKIE_SECURE`未設定（デフォルト`false`）だとローカルの平文HTTP開発用の挙動のまま。HTTPSで配信するのに`COOKIE_SECURE`を`false`のままにすると、ブラウザからはCookieが送られセッションは機能するが、TLSが外れた場合の保護が働かない。逆に平文HTTPのまま`true`にすると、ブラウザがSecure Cookieを保存せずログインループになるため、必ずセットで切り替えること。

2. `deploy/Caddyfile` の `bookmgr.example.com` を実際のドメインに書き換える（事前にDNSのAレコードをこのサーバーの公開IPに向けておく。ポート80/443を外部に開放する必要がある）。

3. Caddyを起動する。

   ```sh
   caddy run --config deploy/Caddyfile
   ```

4. `https://<ドメイン>` でアクセスできる。CLI・Androidアプリは接続先URLを`https://<ドメイン>`に変更するだけでよく（正規CA発行証明書のため）、クライアント側の追加設定は不要。

## CLIクライアント

```sh
cd cli
python -m venv .venv
.venv\Scripts\activate          # Windows。macOS/Linuxは `source .venv/bin/activate`
pip install -r requirements.txt

export BOOKMGR_API_URL=http://localhost:8080   # 任意（デフォルト http://localhost:8080）
export BOOKMGR_API_KEY=your-secret-key         # 必須（サーバーの API_KEY と同じ値）

python -m bookmgr_cli list --q 猫
python -m bookmgr_cli get 1
python -m bookmgr_cli create --title "吾輩は猫である" --author "夏目漱石" --rating 5
python -m bookmgr_cli update 1 --title "坊っちゃん" --author "夏目漱石"
python -m bookmgr_cli delete 1
python -m bookmgr_cli isbn-lookup 9784101010359
```

## Androidクライアント

`android/` 配下に独立したGradle/Kotlin(Jetpack Compose)プロジェクトとして実装している。Android Studioで `android/` を開いて実行する。詳細は `android/README.md` を参照。

## テスト

```sh
cd server
pytest
```

```sh
cd cli
pytest
```

