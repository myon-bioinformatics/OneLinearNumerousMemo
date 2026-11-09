# 🧷 OneLinearNumerousMemo (olnm)

bash/zsh 用ワンライナー集。1ファイル・外部依存なし（fzf/fd/rg/jq/gh/docker はあれば使う）。
想定: Ubuntu 26.04、Python / Node(LTS) / uv はある前提（Bun ほかは任意）。閉域網・持ち込み運用を意識（🌍 付きはネット必要）。

## 導入
```sh
curl -fsSL <RAW_URL>/olnm.sh -o ~/.olnm.sh && echo 'source ~/.olnm.sh' >> ~/.bashrc   # zsh なら ~/.zshrc
```
閉域網へは `olnm.sh` をそのまま持ち込んで `source` するだけ。

## 使い方
| コマンド | 動作 |
|---|---|
| `olnm` | 📖 全一覧（`olnm git` でセクション絞り込み） |
| `olnm_grep json` | 🔎 説明文を検索 |
| `olnm_offline` | 🔒 ネット不要なものだけ |
| `olnm_doctor` | 🩺 任意ツールの有無 |
| `olnm_edit` / `olnm_reload` | 📝 編集 / 再読込 |
| `olnm_like uvtets` | 🤔 近い名前を提示（打ち間違い時は自動で「did you mean」が出る） |
| `olnm <Tab>` | ⌨️ セクション名を補完 |

## セクション
📖 meta · 🐍 uv · 🐍 python · 🟩 node · 🥟 bun · 🌿 git · 🐙 gh · 📁 files · 🔤 text · 🌐 net · 🖥️ system · 🔒 airgap · 🐳 docker · 🧰 tmux · 📝 memo

## 追加ルール
関数の直前に `# <絵文字> 名前: 説明` を1行書くだけでヘルプに載る。`alias1 名前 "コマンド"` が雛形を出す。

## テスト
```sh
bash tests/test_olnm.sh
```
