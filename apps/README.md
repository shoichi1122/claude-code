# 自作アプリ

このリポジトリに追加した自作のアプリ・ツールをまとめたフォルダです(リポジトリ直下のその他のファイルはフォーク元の Claude Code 公式のものです)。

| フォルダ | 内容 | 公開URL |
| --- | --- | --- |
| [`daily-schedule-app/`](daily-schedule-app/) | 📋 今日の予定まとめアプリ(Googleカレンダー連携) | https://shoichi1122.github.io/claude-code/ |
| [`referral-sns-app/`](referral-sns-app/) | 📨 SNSリファラル管理アプリ(Instagram / Threads の誘い文面管理) | https://shoichi1122.github.io/claude-code/referral-sns-app/ |
| [`threads-connector/`](threads-connector/) | 🧵 リファラル管理アプリ用の Threads 中継サーバー(Cloudflare Worker) | — |

GitHub Pages へのデプロイは `.github/workflows/deploy-schedule-app.yml` で行っています(`apps/` 配下の変更を main に push すると自動で公開されます)。
