# BREAK THE NORMS ダンサー登場動画 — Higgsfield プロンプト集

BTNは「ダンサーファースト」のイベント。AI映像は **ダンサーが主役になる舞台の空気** を作る背景素材として使い、
タイトル・ダンサー名・ビートは `make_video.py` で上から重ねる。

## 使い方
1. Higgsfield で下のプロンプトを貼って生成（16:9、音声オフ推奨 → BGMはスクリプト側で付ける）
2. 生成できたら Claude に「生成した」と伝える → 履歴から取得して合成
3. 手元で合成する場合: `python3 make_video.py --name "ダンサー名" --sub "ジャンル" --bg clip.mp4`

## おすすめモデル（無料プラン 10クレジット想定）
- **Seedance 2.0 Mini**（480p/720p, 4〜15秒）… 安くて動きが安定。まず1本試すならこれ
- **Grok Imagine Video 1.5 Lite**（〜15秒）… 速い。背景ループ向き
- 余裕が出たら **Cinema Studio Video 3.0**（genre: action）で本番クオリティ

文字は背景映像の上に重ねるので、**映像の中に文字を入れない**プロンプトにしている（AIの文字は崩れやすいため）。

---

## A. ステージ待機（全ダンサー共通・おすすめ）
暗いステージに照明とスモーク。誰もいない「これから誰かが出てくる」空間。

```
Empty underground dance battle stage at night, thick haze drifting slowly, a single red spotlight cutting through the smoke onto a black floor, strobe flashes in rhythm, crowd silhouettes at the edges raising hands, slow dolly push-in toward the center of the stage, high contrast, cinematic, black and deep red color palette, gritty film grain, no text, no logos
```

## B. シルエット登場
逆光の中からダンサーのシルエットが歩いてくる。顔は出さないので誰にでも使える。

```
Backlit silhouette of a street dancer walking slowly toward the camera through dense stage smoke, powerful red and white backlight, light beams sweeping, the dancer stops center frame and strikes a sharp pose on the beat, low angle, slow motion, cinematic, black and crimson palette, film grain, no text, no logos
```

## C. 壁が割れる（BREAK THE NORMS の世界観）
白い無機質な壁＝「常識」が割れて、奥から赤い光とダンサーの気配。

```
A sterile white concrete wall in a dark void cracks open with an explosive shockwave, shards flying in slow motion, intense red light and smoke bursting through the crack, a dancer's silhouette visible beyond the opening, dramatic camera shake, cinematic, black white and red only, no text, no logos
```

## D. ダンサー本人の写真から（画像→動画）
本人の写真を start_image に入れる。※本人の許可を取ってから。

```
The dancer in the image stands still on a dark smoky stage, then explodes into a powerful freestyle move on the beat, red spotlight from above, strobe flashes, haze, slow camera orbit, cinematic, high contrast, black and red palette, no text
```

---

## 合成の流れ（15秒・BPM120）
| 秒 | 背景（Higgsfield） | 重ねるもの（スクリプト） |
|---|---|---|
| 0–2 | 暗く沈めて気配だけ | ノイズ・ちらつく文字 |
| 2–4 | 〃 | BREAK / THE / NORMS がビートで着弾 |
| 4–8 | 少し明るく | タイトル＋赤スラッシュ |
| 8–11 | 〃 | DANCER FIRST / ダンサーファースト |
| 11–13 | 〃 | NEXT DANCER ＋ ダンサー名 |
| 13–15 | 暗転へ | タイトルロゴ → フェードアウト |
