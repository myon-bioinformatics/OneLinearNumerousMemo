# 🧷 OneLinearNumerousMemo (olnm)

bash/zsh 用ワンライナー集 + ローカル GitHub（Gitea / Forgejo）。**Python 1 ファイル**（`olnm.py`、標準ライブラリのみ）が中にシェル関数を持ち、`eval` で読み込む形。
想定: Ubuntu 26.04、Python / Node(LTS) / uv はある前提（Bun・fzf・fd・rg・jq・gh・docker は任意）。

## 導入
```sh
curl -fsSL <RAW_URL>/olnm.py -o ~/.olnm.py && echo 'eval "$(python3 ~/.olnm.py init)"' >> ~/.bashrc   # zsh なら ~/.zshrc
```
閉域網へは `olnm.py` をそのまま持ち込むだけ。純シェル版が欲しければ `python3 olnm.py init bash > olnm.sh`。

## 使い方
| コマンド | 動作 |
|---|---|
| `olnm` / `olnm git` | 📖 全一覧 / セクション（`olnm <Tab>` で補完） |
| `olnm_grep json` | 🔎 説明文を検索 |
| `olnm_like uvtets` | 🤔 近い名前。打ち間違えると自動で「did you mean」 |
| `olnm_offline` / `olnm_net` | 🔒 ネット不要なもの / 🌍 ネットが要るもの |
| `olnm_dial 0..3` | 🎛️ ダイヤル（ローカル forge の起動停止・origin の向き先も連動） |
| `olnm_doctor` / `olnm_edit` / `olnm_reload` | 🩺 📝 🔄 |

## 🎛️ ダイヤル
`$DIAL_FILE`（既定 `~/.olnm/dial`）に数字 1 つ。未設定は 3（普通のオンライン端末）。

| | 🌍 付き | 🎛️ 付き（ghpr ghprs ghis ghisn ghweb） | origin（gp / gpl） | forge |
|---|---|---|---|---|
| 0 🔌 offline | 止める（スタブ） | ローカル forge へ | bare | 停止 |
| 1 🏠 local | 止める | ローカル forge へ | ローカル forge | 起動 |
| 2 🔁 mirror | 動く | ローカル forge へ | ローカル forge | 起動・GitHub へ push mirror |
| 3 ☁️ github | 動く | gh へ | GitHub | 起動（バックアップ） |

## 🏠 hub（ローカル GitHub）
中身は [Gitea](https://about.gitea.com)（既定）か [Forgejo](https://forgejo.org)。どちらも単一バイナリで Issue・PR・Actions 互換 CI。設定は sqlite・127.0.0.1 のみ・SSH/メール/新規登録なし。
```sh
hubdial install        # 🌍 バイナリ取得 + sha256 照合（→ ~/.olnm/forge/bin）
hubdial init           # 🏗️ admin・API トークン作成、git 認証を ~/.gitconfig へ、ダイヤルを 1 に
hubdial up             # 🟢 http://localhost:3000（hubopen でブラウザ）
cd myrepo && hubadd --github owner/name   # 📚 remote に local / bare / github、origin はダイヤル次第
ghisn "crash" bug ; ghis ; ghpr "fix"     # 🐛🔀 ダイヤル ≤2 ならローカル forge に行く
olnm_dial 2            # 🔁 GitHub へ push mirror（GITHUB_TOKEN か gh auth が必要）
hubsync                # 🔄 bare / local /（≥2 なら）github へまとめて push
```
閉域網へ持ち込み: オンライン側で `hubdial bundle ./carry`（バイナリ + .sha256 + olnm.py）→ 閉域側で `python3 carry/olnm.py hub install --from carry/gitea-*-linux-amd64`。

- 🧬 `--flavor`（install / bundle）: 既定 `gitea`（2016〜、MIT、GitHub 配布）。`forgejo`（2022 年の Gitea フォーク、GPLv3+、Codeberg 配布）も選べる。CLI も API も同じ形なので olnm からの使い方は変わらない
- 🧯 forge が使えなくてもダイヤル 0（bare repo + `gbundle`）は git だけで動く
- 👤 forge は root では起動しない（Gitea / Forgejo の仕様）。普通のユーザーで使う
- 🐹 Go は不要（配布済みバイナリを使う。ソースからビルドするときだけ要る）
- 🔖 `hubdial install` は最新版を取る。最新版の問い合わせ（GitHub API / リリースページ）だけ塞がれている環境では、実機確認済みの版（`VERIFIED`、いまは Gitea 1.27.3）に切り替わる。版を固定するなら `--version 1.27.3`
- 🔑 ダイヤル 2 の push mirror は GitHub トークンをローカル forge の DB に保存する（forge の SECRET_KEY で暗号化）
- ✅ 実機確認（普通のユーザーで）: Gitea **1.27.3**（2026-08-31）と 1.24.6 — install / bundle / init / up / repo add / push / labels / issue / PR / ダイヤル 0〜3 / ダイヤル 0 でのコミットを sync で forge へ / push mirror 登録。Forgejo は未確認（CLI・API は同じ形）
ほか `hubdial status | doctor | logs | labels（GitHub 既定ラベル）| api GET /user/repos | repo ls | pr ls`。

## 🔒 閉域網向け（airgap セクション）
`uvbundle` → `uvoffline` / `nbundle` → `nci` / `gbundle` `gunbundle` / `hashdir` `verifydir` / `secrets` / `redact` / `proxyon` `cabundle` / `noenv` `sandbox` / `envreport` `licenses`

## Python / Node / Bun から
```python
import olnm; olnm.like("uvtets"); olnm.dial(1); olnm.hub_issue_new("crash", labels=["bug"])
```
```sh
python3 olnm.py call hub_repo_ls     # 任意の関数を名前で → JSON（進捗は stderr）
```
```js
require("child_process").execFileSync("python3", ["olnm.py", "run", "pycalc", "6*7"]).toString()   // "42"
```

## 追加ルール
`olnm.py` の `SHELL` 内で、関数の直前に `# <絵文字> 名前: 説明` を 1 行。🌍 を書けばダイヤル 0/1 で自動停止。

## テスト
```sh
python3 -m unittest discover     # forge 本体は不要（tests/fake_forgejo.py が CLI と REST の一部を代行）
```
