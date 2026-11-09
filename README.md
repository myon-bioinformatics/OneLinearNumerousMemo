# 🧷 OneLinearNumerousMemo (olnm)

bash/zsh 用ワンライナー集。**Python 1 ファイル**（`olnm.py`）が中にシェル関数を持ち、`eval` で読み込む形。
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
| `olnm_dial 0..3` | 🎛️ ダイヤル（hubdial と共有） |
| `olnm_doctor` / `olnm_edit` / `olnm_reload` | 🩺 📝 🔄 |

## 🎛️ ダイヤル
`$DIAL_FILE`（既定 `~/.config/dial`）の数字 1 つを hubdial と共有。未設定は 3。

| | 🌍 付き | 🎛️ 付き（ghpr ghprs ghis ghisn） | gp / gpl |
|---|---|---|---|
| 0 🔌 offline | 止める（スタブ） | hubdial へ | origin = bare |
| 1 🏠 local | 止める | hubdial へ | origin = ローカル forge |
| 2 🔁 mirror | 動く | hubdial へ | origin = ローカル forge |
| 3 ☁️ github | 動く | gh へ | origin = GitHub |

## 🔒 閉域網向け（airgap セクション）
`uvbundle` → `uvoffline` / `nbundle` → `nci` / `gbundle` `gunbundle` / `hashdir` `verifydir` / `secrets` / `redact` / `proxyon` `cabundle` / `noenv` `sandbox` / `envreport` `licenses`

## Python / Node / Bun から
```python
import olnm; olnm.like("uvtets")
```
```js
require("child_process").execFileSync("python3", ["olnm.py", "run", "pycalc", "6*7"]).toString()   // "42"
```

## 追加ルール
`olnm.py` の `SHELL` 内で、関数の直前に `# <絵文字> 名前: 説明` を 1 行。🌍 を書けばダイヤル 0/1 で自動停止。

## テスト
```sh
python3 -m unittest discover
```
