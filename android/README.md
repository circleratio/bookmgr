# bookmgr Android クライアント

`bookmgr` サーバーのREST API（`/api/*`）を操作するAndroidアプリ。Jetpack Compose + Material3。

機能はWeb版と同等: 一覧・検索・ページング、詳細表示、新規登録・編集・削除、ISBN入力によるGoogle Books書誌情報取得に加えて、カメラでバーコード（ISBN）を撮影しての登録状況確認・新規登録画面への自動入力。

## セットアップ

1. Android Studio（Koala以降を推奨）でこの `android/` ディレクトリを開く。
2. Gradle Sync を実行する（初回、`gradle/wrapper/gradle-wrapper.jar` が無い場合はAndroid Studioが生成方法を案内するか、`gradlew`/`gradlew.bat` が無い場合は File > Sync/New Project の指示に従う。手元にGradleがインストールされていれば `gradle wrapper` を実行してラッパーを生成してもよい）。
3. compileSdk/targetSdk 34, minSdk 26 のAndroid SDKコンポーネントがインストールされていることを確認する。
4. エミュレータまたは実機で実行する。

## 初回起動

初回起動時、または設定が未入力の場合は接続設定画面が表示される。

- **サーバーURL**: `bookmgr` サーバーのベースURL。エミュレータからホストマシンのlocalhostへ接続する場合は `http://10.0.2.2:8080` を使う。
- **APIキー**: サーバーの `API_KEY` 環境変数と同じ値。

設定は端末内（Jetpack DataStore）に保存される。APIキーはAndroid Keystoreの鍵（AES-256-GCM、端末外へ取り出せない）で暗号化してから保存する。旧バージョンが平文で保存したAPIキーは、起動時に自動で暗号化形式へ移行する。さらに漏洩を防ぐため、アプリデータはバックアップ（クラウドバックアップ・端末間転送）の対象外にしている。Keystoreの鍵が失われた場合（端末の資格情報を消去したときなど）はAPIキーを復号できないため、設定画面で再入力する。

平文HTTPで接続できるのは開発用ホスト（`10.0.2.2`, `localhost`, `127.0.0.1`）のみ。LAN上のIPアドレスやドメインなど、それ以外のサーバーへは `https://` で接続する必要がある（`http://` を指定すると通信がブロックされる）。公開サーバーはルートの README.md の「HTTPS化」の手順でCaddy経由のHTTPSにする。

### 実機（USB接続）からサーバーへ接続する

実機でUSBデバッグ接続している場合、`127.0.0.1`はエミュレータと違い実機自身を指すため、そのままでは接続できず `failed to connect /127.0.0.1:8080` のようなエラーになる。`adb reverse` で実機の `127.0.0.1:8080` へのアクセスをホストPCの8080番ポートへトンネルすることで、URLを変更せずに接続できる。

1. 実機をUSB接続し、`adb devices` で `device` として認識されていることを確認する。
2. ホストPCで以下を実行してポート転送を設定する。

   ```
   adb reverse tcp:8080 tcp:8080
   ```

3. Android側の接続設定画面でサーバーURLを `http://127.0.0.1:8080` に設定する。
4. ホストPCで `bookmgr` サーバー（`server/`、起動方法はリポジトリルートの `README.md` を参照）が起動していることを確認する。

`adb reverse` の設定はPCの再起動やADBサーバーの再起動で失われるため、その都度実行し直す必要がある。ワイヤレスデバッグ（Wi-Fi経由のADB）でも同様に使える。

## 構成

```
app/src/main/java/com/bookmgr/android/
  MainActivity.kt
  data/
    model/          # API JSONのDTO（Book, BookInput, BookInfo等）
    network/         # Retrofit + Moshi + OkHttp（X-API-Keyヘッダー付与）
    BookRepository.kt   # APIクライアントのラッパー、エラーをApiExceptionに変換
    settings/        # DataStoreによる接続設定の永続化（APIキーはKeystoreで暗号化）
  ui/
    BookmgrApp.kt        # 設定要否の分岐
    BookmgrNavHost.kt    # 画面遷移
    BookListScreen.kt
    BookDetailScreen.kt
    BookFormScreen.kt    # 新規登録・編集（ISBN取得ボタン含む）
    BarcodeScanScreen.kt # カメラでISBNバーコードを撮影して登録状況を確認
    SettingsScreen.kt
    theme/
```

## 既知の制約

- AGP 9.3.1 / Kotlin 2.2.10 / Gradle 9.8.2、Android Studio付属JDK（JBR 25）で `assembleDebug` によるビルド成功を確認済み（2026-11-14）。ソースのターゲットはJava 17。
- コマンドラインからビルドする場合は、`JAVA_HOME` にAndroid Studio付属JDK（例: `C:\Program Files\Android\Android Studio\jbr`）を、`ANDROID_HOME` にAndroid SDK（例: `%LOCALAPPDATA%\Android\Sdk`）を設定してから `gradle assembleDebug` を実行する（`local.properties` があれば `ANDROID_HOME` は不要）。生成物は `app/build/outputs/apk/debug/app-debug.apk`。
- `gradle/wrapper/gradle-wrapper.jar`（バイナリ）は同梱していない。Android Studioで開けば自動的に補われる。
