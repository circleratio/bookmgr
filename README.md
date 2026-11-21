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

起動用のシェルスクリプトを作る場合は、APIキーをスクリプトに直書きせず、リポジトリルートの `bookmgr.env`（書式は後述の「systemdでの常駐運用」と同じ `KEY=value` 形式。Gitの管理対象外）に設定を書いて読み込む。`chmod 0600 bookmgr.env` として本人以外が読めないようにすること。同じファイルを後からsystemdの `EnvironmentFile` としてそのまま使える。

```sh
set -a; . ../bookmgr.env; set +a   # server/ から実行する場合。ファイル内の変数をすべて export する
python -m app.main
```

- 画面: `http://localhost:8080/login` からAPIキーでログイン
- API: `X-API-Key` ヘッダーにAPIキーを付与してアクセス（例: `curl -H "X-API-Key: $API_KEY" http://localhost:8080/api/books`)
- 新規登録画面ではISBNを入力して「取得」ボタンを押すと、Google Books API から書名・著者・出版社・出版日を取得してフォームに反映できる。
- `API_KEY` が32文字未満の場合、短い文字列の繰り返し（例: `password` を4回）の場合、使われている文字の種類が少なすぎる場合（例: `aaaa…`、`abcdabcd…`）は起動に失敗する。この確認は明らかに弱いキーを弾くだけで、辞書の単語をつないだキーは検出できない。APIキーはREST API・画面ログイン共通の唯一の認証情報のため、上記の生成例のように乱数で作ること。
- `/docs`・`/redoc`・`/openapi.json`（FastAPIの自動生成ドキュメント）は無効化している。
- セキュリティヘッダー（`Content-Security-Policy`・`X-Frame-Options`・`X-Content-Type-Options`・`Referrer-Policy`）はアプリ自身もすべてのレスポンスに付与するため、Caddyを介さずに起動した場合も有効。HSTSのみHTTPS終端側（Caddy）で付与する。また、静的ファイル（`/static/`）以外のレスポンスには `Cache-Control: no-store` を付与し、画面やAPIの内容をキャッシュさせない。
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

   `COOKIE_SECURE`未設定（デフォルト`false`）でも、リクエストがHTTPSで届いた場合（Caddy経由。uvicornが信頼するプロキシ＝既定で127.0.0.1からの`X-Forwarded-Proto`で判定し、クライアントは偽装できない）はセッションCookieにSecure属性を付与する。それ以外（平文HTTP）では付与しない。HTTPS配信時は明示的に`COOKIE_SECURE=true`とすることを推奨する。逆に平文HTTPのまま`true`にすると、ブラウザがSecure Cookieを保存せずログインループになるため、必ずHTTPS配信とセットで切り替えること。`HOST`がループバック以外かつ`COOKIE_SECURE`未設定で起動すると、平文HTTPでCookieを配信している可能性がある旨の警告を標準エラーに出力する。

2. `deploy/Caddyfile` の `bookmgr.example.com` を実際のドメインに書き換える（事前にDNSのAレコードをこのサーバーの公開IPに向けておく。ポート80/443を外部に開放する必要がある）。

3. Caddyを起動する。

   ```sh
   caddy run --config deploy/Caddyfile
   ```

   `deploy/Caddyfile` はHSTS・`X-Frame-Options`・`Content-Security-Policy`（スクリプト・スタイル・通信先を自オリジンに限定し、フレーム埋め込みを禁止）・`X-Content-Type-Options`・`Referrer-Policy` のセキュリティヘッダーを付与する。リクエストボディは1MiBまでに制限する（アプリ側でも同じ上限を設けている）。HSTSを有効にするとブラウザは以後1年間そのドメインへ平文HTTPで接続しなくなるため、HTTPS配信が安定してから運用すること。

   画面のPOST（ログイン・登録・更新・削除・ログアウト）はCSRF対策として`Origin`（無ければ`Referer`）ヘッダーが`Host`と一致することを検証する。Caddyの`reverse_proxy`は既定で元の`Host`ヘッダーをそのまま転送するため追加設定は不要だが、`Host`を書き換えるプロキシ設定にすると画面のPOSTがすべて`403`になる。

4. `https://<ドメイン>` でアクセスできる。CLI・Androidアプリは接続先URLを`https://<ドメイン>`に変更するだけでよく（正規CA発行証明書のため）、クライアント側の追加設定は不要。

## systemdでの常駐運用

### 専用ユーザーで動かす場合（推奨）

`deploy/bookmgr.service` は、ログインできない専用のシステムユーザー `bookmgr` でサーバーを起動し、異常終了時に自動再起動するシステムユニット。自分のアカウント（sudoやdockerを使えるユーザー）で動かすと、アプリが乗っ取られたときにその権限まで奪われるため、本番ではこの方式を使う。

配置は次のとおり。

| 用途 | 場所 | 所有者・権限 |
| --- | --- | --- |
| サーバーのコード・venv | `/opt/bookmgr/server` | `root:root`（サービスからは読み取り専用） |
| マイグレーション | `/opt/bookmgr/db/migrations` | `root:root`（読み取り専用） |
| 設定（APIキーを含む） | `/etc/bookmgr/bookmgr.env` | `root:root`、`0600` |
| DB | `/var/lib/bookmgr/bookmgr.db` | `bookmgr:bookmgr`（ディレクトリ `0700`、ファイル `0600`） |

- マイグレーションのディレクトリは `server/app/config.py` からの相対位置（リポジトリルートの `db/migrations`）で決まるため、`server/` と `db/` は同じディレクトリの下に並べて置く。
- `bookmgr.env` は、systemd本体（PID 1）がroot権限で読み込んでから実行ユーザーを切り替える。サービスユーザーには読み取り権限が不要で、アプリが乗っ取られてもこのファイルは読まれない。
- `/var/lib/bookmgr` は、ユニットの `StateDirectory=bookmgr` により、起動のたびに所有者 `bookmgr`・権限 `0700` に保たれる。書き込めるのはこのディレクトリだけ。
- Google Books APIへHTTPSで接続するため、外向きの通信は制限していない（bnoteのような `IPAddressDeny` は付けられない）。

#### 新規インストール

リポジトリのルートで実行する。

```sh
# 1. Create the dedicated user (no login, no home directory)
sudo useradd --system --user-group --no-create-home \
  --home-dir /nonexistent --shell /usr/sbin/nologin bookmgr

# 2. Deploy the server code and migrations as root-owned, read-only files
sudo install -d -o root -g root -m 755 /opt/bookmgr /opt/bookmgr/db
sudo rsync -a --delete --chown=root:root \
  --exclude .venv --exclude db --exclude tests --exclude .pytest_cache \
  --exclude start.sh --exclude '__pycache__' --exclude '*.swp' \
  server/ /opt/bookmgr/server/
sudo rsync -a --delete --chown=root:root db/migrations/ /opt/bookmgr/db/migrations/
sudo python3 -m venv /opt/bookmgr/server/.venv
sudo /opt/bookmgr/server/.venv/bin/pip install -r /opt/bookmgr/server/requirements.txt
sudo /opt/bookmgr/server/.venv/bin/python -m compileall -q /opt/bookmgr/server/app

# 3. Create the settings file (KEY=value lines, no `export`)
sudo install -d -o root -g root -m 700 /etc/bookmgr
sudo install -o root -g root -m 600 /dev/null /etc/bookmgr/bookmgr.env
sudoedit /etc/bookmgr/bookmgr.env

# 4. Install and start the unit
sudo cp deploy/bookmgr.service /etc/systemd/system/bookmgr.service
sudo systemctl daemon-reload
sudo systemctl enable --now bookmgr
```

`/etc/bookmgr/bookmgr.env` の内容（`DB_PATH` は必ず `/var/lib/bookmgr` の下にする）:

```sh
API_KEY=...
HOST=127.0.0.1
PORT=8090
COOKIE_SECURE=true
DB_PATH=/var/lib/bookmgr/bookmgr.db
GOOGLE_BOOKS_API_KEY=...
```

- `/opt/bookmgr` はサービスから書き込めないので、`compileall` で `.pyc`（Pythonのキャッシュ）を事前に作っておく。省略しても動くが、起動のたびにコンパイルされる。
- DBが無ければ初回起動時に作られ、マイグレーションが適用される。

#### ユーザーユニットからの移行

すでに `deploy/bookmgr.user.service` で動かしている場合は、上の手順1・2を行ってから、手順3の代わりに既存の設定とDBを移す。

```sh
# Copy the existing settings and point DB_PATH to the new location
sudo install -d -o root -g root -m 700 /etc/bookmgr
sudo install -o root -g root -m 600 bookmgr.env /etc/bookmgr/bookmgr.env
sudo sed -i 's|^DB_PATH=.*|DB_PATH=/var/lib/bookmgr/bookmgr.db|' /etc/bookmgr/bookmgr.env
sudo grep -E '^(HOST|PORT|DB_PATH|COOKIE_SECURE)=' /etc/bookmgr/bookmgr.env   # check non-secret values

# Stop the old user service (the port must be free)
systemctl --user disable --now bookmgr

# Back up the database and check that no -journal / -wal files are left
cp -p server/db/bookmgr.db ~/bookmgr.db.bak-$(date +%Y%m%d)
ls server/db/

# Move the database to the new location
sudo install -d -o bookmgr -g bookmgr -m 700 /var/lib/bookmgr
sudo install -o bookmgr -g bookmgr -m 600 server/db/bookmgr.db /var/lib/bookmgr/bookmgr.db
```

元の `bookmgr.env` に `DB_PATH` の行が無い場合は、`sed` では追加されないので `sudoedit /etc/bookmgr/bookmgr.env` で書き足す。続けて手順4でユニットを配置して起動し、問題なく動くことを確認したら古いユニットを削除する。

```sh
rm ~/.config/systemd/user/bookmgr.service
systemctl --user daemon-reload
```

- 他にユーザーユニットが無ければ、`sudo loginctl disable-linger $USER` でlinger（ログアウト中もユーザーユニットを動かし続ける設定）を無効にできる。
- `server/db/bookmgr.db` とバックアップは、しばらく運用して問題がないことを確かめてから削除する。リポジトリルートの `bookmgr.env` もAPIキーを含むので、ローカルでの開発に使わないなら削除する。

元に戻す場合は、`sudo systemctl disable --now bookmgr` で止めてから、DBを `server/db/` に戻し（所有者を自分にする）、ユーザーユニットを元に戻して `systemctl --user enable --now bookmgr` を実行する。専用ユーザーで動かしていた間に更新されたデータも戻したいときは、`/var/lib/bookmgr/bookmgr.db` を `sudo cp` でコピーしてから `sudo chown $USER: server/db/bookmgr.db` とする。

#### 動作確認

```sh
systemctl status bookmgr
ps -o user,pid,args -C python        # The process must run as bookmgr
ss -ltn | grep 8090                  # Listening on 127.0.0.1:8090
sudo journalctl -u bookmgr -f        # Follow the log while using the app
systemd-analyze security bookmgr     # Sandbox exposure score (for reference)
```

ブラウザでログイン・一覧表示・登録を試し、新規登録画面でISBNの「取得」（Google Books APIへの接続）も動くことを確認する。

#### コードの更新

リポジトリで変更をコミットしたら、`/opt/bookmgr` に反映してサービスを再起動する。`requirements.txt` を変えた場合は `pip install` もやり直す。

```sh
sudo rsync -a --delete --chown=root:root \
  --exclude .venv --exclude db --exclude tests --exclude .pytest_cache \
  --exclude start.sh --exclude '__pycache__' --exclude '*.swp' \
  server/ /opt/bookmgr/server/
sudo rsync -a --delete --chown=root:root db/migrations/ /opt/bookmgr/db/migrations/
sudo /opt/bookmgr/server/.venv/bin/python -m compileall -q /opt/bookmgr/server/app
sudo systemctl restart bookmgr
```

設定（`/etc/bookmgr/bookmgr.env`）を変えた場合も `sudo systemctl restart bookmgr` で反映する。

#### 起動に失敗する場合

`journalctl -u bookmgr` に `SIGSYS`（禁止されたシステムコールの呼び出し）や `Permission denied` が出る場合は、サンドボックス設定が原因。uvicorn[standard] が使うコンパイル済みのライブラリ（uvloop・pydantic-coreなど）とぶつかることがある。`/etc/systemd/system/bookmgr.service` の該当しそうな行（`MemoryDenyWriteExecute`、`SystemCallFilter` など）を1行ずつコメントアウトし、`sudo systemctl daemon-reload && sudo systemctl restart bookmgr` で原因を絞り込む。

`unable to open database file` が出る場合は、`DB_PATH` が `/var/lib/bookmgr` の下を指しているか確認する。書き込めるのはこのディレクトリだけ。

### ユーザー権限で動かす場合（systemdユーザーユニット）

専用ユーザーを作らず、自分のアカウントのsystemd（`systemctl --user`）でサーバーを常駐させることもできる。root権限が要るのは初回の `enable-linger` だけ。ただしsudoなどの権限を持つアカウントで動かすことになるため、本番では上の「専用ユーザーで動かす場合」を推奨する。ユニットファイルは `deploy/bookmgr.user.service`。リポジトリが `~/services/bookmgr` にある前提で書いてあるので、違う場所に置く場合はパスを書き換える（`%h` はホームディレクトリに置き換わる）。

1. 依存パッケージをvenvに入れる（初回と `requirements.txt` を更新したときだけ。ユニット側ではインストールしない）。

   ```sh
   cd server
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. リポジトリルートに `bookmgr.env` を作る（書式は上と同じ）。ユーザーユニットでは自分の権限で読み込まれるので、所有者は自分のままにして `chmod 0600 bookmgr.env` とする（root所有にすると読めずに起動に失敗する）。システムユニット方式と違って、アプリが乗っ取られた場合にこのファイルを読まれるのは防げない。
3. ユニットの `ReadWritePaths` を、`DB_PATH` で指定したDBファイルのあるディレクトリに合わせる（デフォルトは `server/db`）。
4. ユニットを配置して起動する。

   ```sh
   mkdir -p ~/.config/systemd/user
   cp deploy/bookmgr.user.service ~/.config/systemd/user/bookmgr.service
   systemctl --user daemon-reload
   systemctl --user enable --now bookmgr
   sudo loginctl enable-linger $USER   # ログアウト中やOS起動直後も動かすために必要（初回のみ）
   ```

   状態は `systemctl --user status bookmgr`、ログは `journalctl --user -u bookmgr` で確認できる。設定を変えたら `systemctl --user restart bookmgr` で反映する。

注意点:

- `[Install]` には `WantedBy=default.target` を指定する。`multi-user.target` はユーザー用のsystemdには存在しないので、指定しても自動起動されない。
- `Type=simple` にしてpythonを直接起動する。`start.sh` のようにバックグラウンド（`&`）で起動して終了するスクリプトを `Type=oneshot` で動かすと、サーバーがsystemdの管理から外れてしまい、異常終了しても自動再起動されず、`systemctl --user stop` でも止まらなくなる。
- サンドボックス設定（`ProtectSystem` など）は、unprivileged user namespace（一般ユーザーが使える名前空間機能）が有効でないとユーザーユニットでは動かない。名前空間関係のエラーで起動に失敗する場合は、ユニット内のこのブロックを削除する。
- 1024番未満のポートでは待ち受けできない。外部への公開は前述のCaddy経由で行う。

## バックアップ

`python -m app.backup`（`server/` から実行）は、SQLiteのオンラインバックアップ機能（サーバーを止めずに、書き込み中でも一貫した状態を複製する仕組み）でDBを複製する。複製したファイルに整合性チェック（`PRAGMA integrity_check`）をかけ、問題がなければ `bookmgr-YYYYMMDD-HHMMSS.db` という名前で保存し、新しいものから指定した数だけ残して古いものを削除する。元のDBは読み取り専用で開くので、バックアップ処理がDBを変更することはない。

| 環境変数 | 既定値 | 説明 |
| --- | --- | --- |
| `DB_PATH` | サーバーと同じ（`db/bookmgr.db`） | バックアップ元のDB |
| `BACKUP_DIR` | DBと同じディレクトリの `backups/` | 保存先（無ければ権限 `0700` で作成） |
| `BACKUP_KEEP` | `14` | 残すバックアップの数 |

### systemd timerで毎日取る

専用ユーザー構成では、`deploy/bookmgr-backup.timer` が毎日3:45頃（最大10分のランダムな遅れあり）に `deploy/bookmgr-backup.service` を起動し、`/var/lib/bookmgr/backups` に14世代を残す。処理は `bookmgr` ユーザーで、ネットワークを使えない状態で動く。APIキーは不要なので `bookmgr.env` は読み込まない。その時刻にマシンが止まっていた場合は、次の起動時に実行される（`Persistent=true`）。

`app/backup.py` は「コードの更新」の rsync で `/opt/bookmgr/server` に配置される。配置してから次を実行する。

```sh
sudo cp deploy/bookmgr-backup.service deploy/bookmgr-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bookmgr-backup.timer

# Run a backup right away and check the result
sudo systemctl start bookmgr-backup.service
sudo journalctl -u bookmgr-backup -n 20
sudo ls -l /var/lib/bookmgr/backups
```

次回の実行予定は `systemctl list-timers bookmgr-backup.timer` で確認できる。時刻や残す数を変えるときは `/etc/systemd/system/` のファイルを編集し、`sudo systemctl daemon-reload` を実行する。

### バックアップから戻す

```sh
sudo systemctl stop bookmgr
sudo -u bookmgr cp /var/lib/bookmgr/bookmgr.db /var/lib/bookmgr/bookmgr.db.before-restore
sudo -u bookmgr cp /var/lib/bookmgr/backups/bookmgr-YYYYMMDD-HHMMSS.db /var/lib/bookmgr/bookmgr.db
sudo systemctl start bookmgr
```

### 注意

バックアップはDBと同じディスクに保存されるため、ディスク故障やサーバーそのものを失った場合には役に立たない。重要なデータであれば、`/var/lib/bookmgr/backups` を定期的に別のマシンやストレージへコピーする。

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

