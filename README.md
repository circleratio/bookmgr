# bookmgr

蔵書管理のためのウェブアプリケーション。REST API とサーバーサイドレンダリング画面を Python/FastAPI（`server/`）で提供する。詳細は `docs/requirement.md`, `docs/spec.md`, `docs/plan.md` を参照。

## 起動方法

```sh
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows。macOS/Linuxは `source .venv/bin/activate`
pip install -r requirements.txt      # テストも実行する場合は requirements-dev.txt

export API_KEY=...                   # 必須（32文字以上。生成例: python -c "import secrets; print(secrets.token_urlsafe(32))"）
export HOST=127.0.0.1                # 任意（デフォルト 127.0.0.1。他のマシンから直接接続させる場合のみ 0.0.0.0 にする）
export PORT=8080                     # 任意（デフォルト 8080）
export DB_PATH=/path/to/bookmgr.db  # 任意（デフォルト <リポジトリルート>/db/bookmgr.db。相対パスは起動時のカレントディレクトリ基準になるため絶対パスで指定する）
export GOOGLE_BOOKS_API_KEY=...      # 任意（新規登録画面のISBN取得機能で使用。未設定でも動作する）
export COOKIE_SECURE=false           # 任意（デフォルト false。HTTPS配信時はtrueにする、後述）
export ACCESS_LOG=true               # 任意（デフォルト true。falseでアクセスログを出力しない、後述）

python -m app.main
```

起動時に `db/migrations/` 配下のSQLが自動適用される（`CREATE TABLE/INDEX IF NOT EXISTS` のため複数回実行しても安全）。

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)
- 新規登録画面ではISBNを入力して「取得」ボタンを押すと、Google Books API から書名・著者・出版社・出版日を取得してフォームに反映できる。
- `API_KEY` が32文字未満の場合は起動に失敗する。APIキーはREST API・画面ログイン共通の唯一の認証情報のため、十分な長さの乱数を使うこと。
- `/docs`・`/redoc`・`/openapi.json`（FastAPIの自動生成ドキュメント）は無効化している。
- セキュリティヘッダー（`Content-Security-Policy`・`X-Frame-Options`・`X-Content-Type-Options`・`Referrer-Policy`）はアプリ自身もすべてのレスポンスに付与するため、Caddyを介さずに起動した場合も有効。HSTSのみHTTPS終端側（Caddy）で付与する。
- アクセスログ（uvicorn）にはURLのクエリ文字列（検索語・ISBN）が記録される。不要なら `ACCESS_LOG=false` で無効化できる。systemdで運用する場合ログはjournaldに残るため、`/etc/systemd/journald.conf` の `MaxRetentionSec=`（例: `30day`）で保存期間を制限するとよい。

## HTTPS化（Caddyをリバースプロキシとして使う）

ドメインを持つサーバーで公開する場合、[Caddy](https://caddyserver.com/) を前段に置きTLS終端させる。Let's Encrypt証明書の取得・更新はCaddyが自動で行う。

1. サーバーをローカルポートのみで待ち受けるように起動する（外部から直接`PORT`にアクセスできないようにする）。

   ```sh
   export API_KEY=...             # 32文字以上
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

   `deploy/Caddyfile` はHSTS・`X-Frame-Options`・`Content-Security-Policy`（スクリプト・スタイル・通信先を自オリジンに限定し、フレーム埋め込みを禁止）・`X-Content-Type-Options`・`Referrer-Policy` のセキュリティヘッダーを付与する。リクエストボディは1MiBまでに制限する（アプリ側でも同じ上限を設けている）。HSTSを有効にするとブラウザは以後1年間そのドメインへ平文HTTPで接続しなくなるため、HTTPS配信が安定してから運用すること。

   画面のPOST（ログイン・登録・更新・削除・ログアウト）はCSRF対策として`Origin`（無ければ`Referer`）ヘッダーが`Host`と一致することを検証する。Caddyの`reverse_proxy`は既定で元の`Host`ヘッダーをそのまま転送するため追加設定は不要だが、`Host`を書き換えるプロキシ設定にすると画面のPOSTがすべて`403`になる。

4. `https://<ドメイン>` でアクセスできる。CLI・Androidアプリは接続先URLを`https://<ドメイン>`に変更するだけでよく（正規CA発行証明書のため）、クライアント側の追加設定は不要。

## systemdでの常駐運用

`deploy/bookmgr.service` は専用の非特権ユーザーでサーバーを起動し、異常終了時に自動再起動するユニットファイル。書き込みはDBディレクトリ（`<PROJECT_ROOT>/db`）のみに制限している。

1. 専用ユーザーを作成する（例: `sudo useradd --system --no-create-home --shell /usr/sbin/nologin bookmgr`）。このユーザーがリポジトリを読めること、`db/` に書き込めることを確認する。
2. リポジトリルートに `bookmgr.env` を作成する（`export` は付けず `KEY=value` 形式。Gitの管理対象外）。

   ```sh
   API_KEY=...
   HOST=127.0.0.1
   PORT=8090
   COOKIE_SECURE=true
   GOOGLE_BOOKS_API_KEY=...
   ```

   APIキーを含むため `sudo chown root:root bookmgr.env && sudo chmod 0600 bookmgr.env` とする（`EnvironmentFile` はsystemd本体がroot権限で読み込むため、サービスユーザーに読み取り権限は不要。アプリが乗っ取られてもこのファイルは読まれない）。
3. `deploy/bookmgr.service` の `<PROJECT_ROOT>` と `<SERVICE_USER>` を書き換えて `/etc/systemd/system/` に配置し、`sudo systemctl daemon-reload && sudo systemctl enable --now bookmgr` で起動する。ログは `journalctl -u bookmgr` で確認できる。

## CLIクライアント

```sh
cd cli
python -m venv .venv
.venv\Scripts\activate          # Windows。macOS/Linuxは `source .venv/bin/activate`
pip install -r requirements.txt      # テストも実行する場合は requirements-dev.txt

export BOOKMGR_API_URL=http://localhost:8080   # 任意（デフォルト http://localhost:8080。リモートのサーバーは https:// 必須。平文 http:// はlocalhost/127.0.0.1/::1のみ許可）
export BOOKMGR_API_KEY=...                     # 必須（サーバーの API_KEY と同じ値）

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

