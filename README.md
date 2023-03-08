<h1 align="center">
  <br>
  <a href="https://github.com/staciax/ValorantStoreChecker-discord-bot"></a>
  <br>
  Valorant Discord Bot
  <br>
</h1>

<h4 align="center">Fork of <a href="https://github.com/staciax/Valorant-DiscordBot">staciax/Valorant-DiscordBot</a></h4>

<p align="center">
  <a href="https://github.com/shumm7/Valorant-DiscordBot">
     <img src="https://img.shields.io/github/v/release/shumm7/Valorant-DiscordBot" alt="release">
  </a>
  <a href="https://github.com/Rapptz/discord.py/">
     <img src="https://img.shields.io/badge/discord-py-blue.svg" alt="discord.py">
  </a>
 <a href="https://github.com/shumm7/Valorant-DiscordBot/blob/master/LICENSE">
     <img src="https://img.shields.io/github/license/shumm7/Valorant-DiscordBot" alt="License">
  </a>
</p>

# About
[In-game API](https://github.com/HeyM1ke/ValorantClientAPI)を使用して、VALORANTを開かずに様々な情報を表示することのできるDiscord Botです。
このリポジトリは、[staciax/Valorant-DiscordBot](https://github.com/staciax/Valorant-DiscordBot)のフォークです。

## Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)
- [Youtube Tutorial][Tutorial]

## Installations

* [Python 3.8+](https://www.python.org/downloads/)

* [Git](https://git-scm.com/downloads)

* Install requirements

* [discord bot](https://discord.com/developers/applications)を作成し、[`MESSAGE CONTENT INTENT`](https://i.imgur.com/TiiaYR9.png)を有効化

* Clone/[Download](https://github.com/staciax/ValorantStoreChecker-discord-bot/archive/refs/heads/master.zip)

```
pip install -r requirements.txt
```

* 初期設定では[Noto Sans CJK JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP)のインストールが必要です（config.jsonから変更可能）

```
sudo apt install fonts-noto-cjk
```

* `.env`ファイルにdiscord botのトークンを記載します
```
TOKEN='INPUT DISCORD TOKEN HERE'
```
* botを起動
```
python bot.py
```
* config.jsonの内容を設定する<br>`"owner-id"`には管理者のユーザーIDを、`"emoji-server-id"`には絵文字を追加するサーバーIDを記載してください
```json
"default-language": "en-US",
"command-description-language": "en-US",
"owner-id": USER_ID,
"emoji-server-id": [EMOJI_SERVER_ID],
```
* botを再起動してください
