# 🧵 Threads Connector(中継サーバー)

SNSリファラル管理アプリの「Threadsの反応が来た人を自動取り込み」機能で使う、小さな中継サーバーです。
Cloudflare Worker として無料枠で動きます。

## なぜ必要か

- Metaの**アクセストークン発行にはアプリのシークレット**が必要で、これはブラウザに置くと漏洩します。サーバー側に隠す必要があります。
- MetaのAPIは**ブラウザからの直接呼び出し(CORS)を許可していない**ため、間に中継サーバーが必要です。

このWorkerはシークレットを自分の中だけに保持し、ブラウザには**長期アクセストークン(約60日有効)だけ**を渡します。

## 全体の流れ

```
[アプリ] --「連携する」--> [Worker /auth/start] --> [Threadsログイン画面]
                                                          |
[アプリ] <--#トークン付きで戻る-- [Worker /auth/callback] <-- 認可
[アプリ] --「取り込み」--> [Worker /api/replies] --> [Threads API] --> 返信一覧を返す
```

トークンはブラウザのlocalStorageに保存されます(個人利用向けの割り切り)。

---

## セットアップ手順

### 1. Metaアプリを作る

1. https://developers.facebook.com/ でアプリを作成(ユースケースで **Threads API** を選択)。
2. 「Threads」→「Use cases」で、**`threads_basic`** と **`threads_read_replies`** の権限を有効化。
3. 「Threads → Settings」で以下を控える/設定する:
   - **Threads App ID**(公開情報)
   - **Threads App Secret**(秘密。あとで `wrangler secret put` に使う)
   - **Redirect Callback URLs** に、デプロイ後のWorkerのコールバックURLを**完全一致**で登録:
     `https://<あなたのworker>.workers.dev/auth/callback`
4. アプリが「開発モード」の間は、自分のThreadsアカウントを**テスター**として追加しておく(自分だけで使うならこれでOK)。

> 注: MetaのAPI仕様・エンドポイントは更新されることがあります。権限名やフィールドがエラーになる場合は最新の公式ドキュメント(developers.facebook.com/docs/threads)を確認してください。`worker.js` の `SCOPE` と各エンドポイントを直せば対応できます。

### 2. Worker をデプロイ

[Node.js](https://nodejs.org/) が入っている前提です。このディレクトリで:

```bash
npm install -g wrangler         # 初回のみ
wrangler login                  # ブラウザでCloudflareにログイン

# wrangler.toml の THREADS_APP_ID を、手順1で控えたThreads App IDに書き換える

wrangler secret put THREADS_APP_SECRET   # 手順1のApp Secretを貼り付け(画面には残りません)

wrangler deploy
```

デプロイ後に表示される `https://threads-connector.<あなた>.workers.dev` が中継サーバーのURLです。

3. 手順1のMetaアプリの **Redirect Callback URLs** に、`https://threads-connector.<あなた>.workers.dev/auth/callback` が登録されているか(完全一致で)確認します。

### 3. アプリ側で連携

1. リファラル管理アプリの「🔗 連携」タブを開く。
2. 中継サーバーのURL(`https://threads-connector.<あなた>.workers.dev`)を入力して「URLを保存」。
3. 「Threadsと連携する」→ Threadsにログインして許可 → アプリに戻ると「連携済み」になります。
4. 「反応が来た人を取り込む」を押すと、直近の自分の投稿への返信者が送信リストに追加されます。

---

## エンドポイント一覧

| パス | 用途 |
|------|------|
| `GET /auth/start?redirect=<戻り先URL>` | Threadsログインへリダイレクト |
| `GET /auth/callback` | 認可コードを長期トークンへ交換し、`#threads_token=...` を付けて戻り先へ302 |
| `GET /refresh?access_token=<長期トークン>` | 長期トークンを更新(JSON) |
| `GET /api/replies?access_token=<長期トークン>` | 直近投稿への返信者一覧を返す(JSON, CORS対応) |
| `GET /health` | 動作確認 |

## 取得できるもの・できないもの

- 取得できる: 自分の投稿への**返信**(ユーザー名・本文・時刻・パーマリンク)。
- 取得できない: 「いいね」した人の一覧(Threads APIに一覧取得の手段がありません)、DMの送受信(APIが公開されていません)。

## セキュリティ上の注意

- 長期トークンはブラウザのlocalStorageに保存されます。共有PCでは使わないでください。
- `ALLOWED_ORIGIN` を自分のアプリのオリジンに絞ると、他サイトからのAPI利用を防げます。
- App Secret は必ず `wrangler secret put` で設定し、`wrangler.toml` には書かないでください。
