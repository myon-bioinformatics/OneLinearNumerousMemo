# 🧷 OneLinearNumerousMemo (olnm)

bash/zsh 用の **246 個のシェル関数**と、ローカル GitHub（Gitea / Forgejo）を扱う **43 個の Python API**。
実装は `olnm.py` 1 ファイル、実行時の Python 外部依存はゼロ。
Python 3.11 以降、Linux（Ubuntu / WSL の Ubuntu）の bash/zsh を対象とする。
macOS では GNU コマンドとの差異があり、PowerShell/cmd からシェル関数を使う場合は WSL 内で実行する。
Node / Bun / gh / Docker / fzf などは、それを使う関数を実行するときだけ必要。


利用手順の切り替え・再現記録: [olnm 利用・検証ガイド](https://myon-bioinformatics.github.io/OneLinearNumerousMemo/)

## 目次

- [最初の成功まで](#最初の成功まで)
- [呼び出し方の選び方](#呼び出し方の選び方)
- [bash/zsh に関数を登録する](#bashzsh-に関数を登録する)
- [引用符を省略して計算する](#引用符を省略して計算する)
- [標準ライブラリツールのデフォルトコマンド](#標準ライブラリツールのデフォルトコマンド)
- [yourself：登録なしの環境レポート](#yourself登録なしの環境レポート)
- [Python のワンライナーから使う](#python-のワンライナーから使う)
- [JSON で関数を呼ぶ call](#json-で関数を呼ぶ-call)
- [uv：ファイルを実行する](#uvファイルを実行する)
- [uv：常用ツールとして登録する](#uv常用ツールとして登録する)
- [uv：別プロジェクトに依存として登録する](#uv別プロジェクトに依存として登録する)
- [uv 関数で実際の作業をする](#uv-関数で実際の作業をする)
- [CLI の全入口](#cli-の全入口)
- [ダイヤルと保存先](#ダイヤルと保存先)
- [hub の導入から Issue・PR 作成まで](#hub-の導入から-issuepr-作成まで)
- [Node / Bun から呼ぶ](#node--bun-から呼ぶ)
- [入力支援：Tab・タイポ・引用符なしの計算](#入力支援tabタイポ引用符なしの計算)
- [mise：複数言語の共通入口](#mise複数言語の共通入口)
- [Node・Bun・Rust と作業ディレクトリ](#nodebunrust-と作業ディレクトリ)
- [olnm 自体の更新](#olnm-自体の更新)
- [困ったとき](#困ったとき)
- [検証範囲と再実行](#検証範囲と再実行)
- [Python API 全件](#python-api-全件)
- [シェル関数 全件](#シェル関数-全件)

## 最初の成功まで

以下は **bash / zsh のターミナル**に貼り付ける。`$` や `>>>` の入力記号は不要。
`python3` と `curl` が必要。まず uv・シェル登録・forge 導入なしで `42` を表示する。

```sh
mkdir -p "$HOME/.local/share/olnm"
curl -fL https://raw.githubusercontent.com/myon-bioinformatics/OneLinearNumerousMemo/main/olnm.py -o "$HOME/.local/share/olnm/olnm.py"
python3 "$HOME/.local/share/olnm/olnm.py" calc 6 mul 7
```

期待する出力は `42`。以降、**ファイル方式の例ではこの変数を同じターミナルで設定しておく**。

```sh
export OLNM_PY="$HOME/.local/share/olnm/olnm.py"
python3 "$OLNM_PY" --help
python3 "$OLNM_PY" ls python
python3 "$OLNM_PY" like uvtets
```

最後のコマンドには `uvtest` が候補として出る。clone 方式なら次でも同じように使える。

```sh
git clone https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git
cd OneLinearNumerousMemo
export OLNM_PY="$PWD/olnm.py"
python3 "$OLNM_PY" calc 6 mul 7
```

**1 行だけで取得から実行まで：**

```sh
mkdir -p "$HOME/.local/share/olnm" && curl -fL https://raw.githubusercontent.com/myon-bioinformatics/OneLinearNumerousMemo/main/olnm.py -o "$HOME/.local/share/olnm/olnm.py" && python3 "$HOME/.local/share/olnm/olnm.py" calc 6 mul 7
```

`main` は更新される。版を固定する場合は URL の `/main/` を、確認したコミットの完全な SHA に置き換える。

## 呼び出し方の選び方

| やりたいこと | 入力例 | 前提 | 結果 |
|---|---|---|---|
| ファイルから CLI | `python3 "$OLNM_PY" ls python` | ファイルを保存 | 人向けの一覧 |
| 計算を 1 回実行 | `python3 "$OLNM_PY" calc 6 mul 7` | python3 | 出力と終了コードを引き継ぐ |
| 現在のシェルに関数登録 | `eval "$(python3 "$OLNM_PY" init bash)"` | bash / zsh | 以後 `calc 6 mul 7` と打てる |
| Python API | `python3 -c 'import olnm; olnm.like("uvtets")'` | import 可能な場所／環境 | Python オブジェクト。関数によって表示も行う |
| JSON を取得 | `python3 "$OLNM_PY" call like '["uvtets"]'` | 引数は JSON 配列 | stdout は JSON、説明表示は stderr |
| uv でファイル実行 | `uv run --no-project "$OLNM_PY" calc 6 mul 7` | uv | ファイル方式と同じ |
| 常用コマンドを登録 | `uv tool install .` | clone したルート | PATH 上に `olnm` コマンド |
| 他プロジェクトへ依存登録 | `uv add /絶対パス/OneLinearNumerousMemo` | 利用側の uv プロジェクト | `uv run python -c 'import olnm; ...'` |

**`calc` はCLIサブコマンドとシェル関数、`calculate` はPython API。**
計算は `olnm.py calc 6 mul 7`、Python からは `olnm.calculate("6", "mul", "7")` と呼ぶ。
`uvtest` などのシェル関数は引き続き `olnm.py run uvtest ...` で呼ぶ。

## bash/zsh に関数を登録する

### 今開いているターミナルだけで使う

ファイル方式（`OLNM_PY` 設定済み）の場合：

```sh
eval "$(python3 "$OLNM_PY" init bash)"
olnm python
calc 6 mul 7
olnm_like uvtets
```

zsh なら `eval "$(python3 "$OLNM_PY" init zsh)"`。
`init` は定義を**表示**するだけ。`eval` して初めて現在のシェルへ登録される。
`run` は子 bash 内で登録するので、親ターミナルには関数を残さない。
`cd` / `export` を現在のシェルに反映したい場合も、eval 後に関数を直接呼ぶ。

### 次回のターミナルでも使う

次の 1 行を `~/.bashrc` の末尾に追加する。同じ行を繰り返し追加する必要はない。

```sh
eval "$(python3 "$HOME/.local/share/olnm/olnm.py" init bash)"
```

保存後に `source ~/.bashrc`。zsh は `~/.zshrc` に `init zsh` とした行を追加し、`source ~/.zshrc`。
zsh の補完を使う場合は `autoload -Uz compinit; compinit` の実行後に読み込む。
登録をやめる場合はこの行を削除し、新しいターミナルを開く。

### シェルコードへ書き出す

```sh
python3 "$OLNM_PY" init bash > "$HOME/.local/share/olnm/olnm.sh"
source "$HOME/.local/share/olnm/olnm.sh"
```

一覧・ダイヤル・hub などは引き続き `olnm.py` と python3 を呼ぶ。
`olnm.sh` だけ持ち込めば全機能が Python 不要になるわけではない。

## 引用符を省略して計算する

**新しい共通入口は `calc`。** 名前は呼び出し元に依存せず、シェル、Python、Node、uv から使える。
既定の計算エンジンは Python、`--engine node` で JavaScript に切り替える。
従来の `pycalc` / `ncalc` は削除し、`calc` に統一した。移行例：
`pycalc '6*7'` → `calc 6 mul 7`、`ncalc '2**10'` → `calc --engine node 2 pow 10`。
任意のPython/JavaScript式の実行は受け付けず、数値計算に用途を絞る。

ファイル方式では `OLNM_PY` を設定してから、bash なら次を実行する。
zsh は最初の行を `eval "$(python3 "$OLNM_PY" init zsh)"` に置き換える。

```sh
eval "$(python3 "$OLNM_PY" init bash)"
calc 6 + 7
calc 6 mul 7
calc 6 div 4
calc 2 pow 10
calc -6 mul 7
calc 6 minus -7
calc lpar 6 plus 7 rpar mul 2
calc --engine node 2 pow 10
calc --engine node -6 mul 7
```

順に `13`、`42`、`1.5`、`1024`、`-42`、`13`、`26`、`1024`、`-42`。
単語は**空白で区切る**。`6mul7` は受け付けない。`calc '6 mul 7'` のような1引数の式も使える。

| 入力する単語 | 演算子・用途 | 例 |
|---|---|---|
| `plus` / `minus` | `+` / `-` | `calc 6 minus -7` → `13` |
| `mul` / `div` | `*` / `/` | `calc 6 mul 7` → `42` |
| `pow` | `**`（べき乗） | `calc 2 pow 10` → `1024` |
| `mod` | `%`（剰余） | `calc 7 mod 4` → `3` |
| `floordiv` | `//`（Pythonのみ） | `calc -7 floordiv 2` → `-4` |
| `lpar` / `rpar` | `(` / `)` | `calc lpar 6 plus 7 rpar mul 2` → `26` |

`x` や `^` は乗算・べき乗の別名にしない。特に `^` は従来の Python/JS では XOR のため、
暗黙に意味を変えず `pow` を使う。数値リテラルと四則演算・べき乗・剰余・括弧のみを受け付け、
関数呼び出し、変数、文字列、コメント、属性参照、代入などは評価前に拒否する。
不正な入力は stderr に理由を表示して終了コード `1`。`--engine` は式の前に指定する。
**引数なしの `calc` は式の入力を促す**（端末なら `sqrt(` などを Tab 補完できるプロンプト、パイプなら stdin を1行読む）。
この経路は引用符もシェル展開も通らないので `6*7`・`sqrt(81)`・`round(pi,2)` をそのまま書け、誤りは案内付きで終了コード `2`。

```sh
printf '%s\n' '(6+7)*2' | python3 "$OLNM_PY" calc
```

### シェル登録なし・Python・Node・uv から呼ぶ

```sh
python3 "$OLNM_PY" calc 6 mul 7
python3 "$OLNM_PY" calc --engine node 2 pow 10
```

clone したルートなど、`import olnm` が可能な場所では、Python のコードだけを引用符で囲み、
**数式は外側の引数として渡せる**。終了コードも引き継ぐ。

```sh
python3 -c 'import olnm,sys; sys.exit(olnm.calculate(*sys.argv[1:]))' 6 mul 7
python3 -c 'import olnm,sys; sys.exit(olnm.calculate(*sys.argv[1:], engine="node"))' 2 pow 10
```

Node から Python エンジンを呼ぶ場合も共通 CLI を使う。`execFileSync` の引数配列なら
シェルを通さないため、生の `*` も展開されない（コマンドのコード部分の引用符は必要）。

```sh
node -e 'const {execFileSync}=require("node:child_process"); process.stdout.write(execFileSync("python3",[process.env.OLNM_PY,"calc","6","*","7"],{encoding:"utf8"}))'
```

uv の各導入手順は後の節を参照。clone したルートでは次が使える。

```sh
uv run --no-project "$OLNM_PY" calc 6 mul 7
uvx --from . olnm calc 2 pow 10
```

`uv tool install .` で登録済みなら `command olnm calc 6 mul 7`。
利用側プロジェクトで `uv add /絶対パス/OneLinearNumerousMemo` 済みなら
`uv run olnm calc 6 mul 7` または上記 Python ワンライナーを `uv run python -c ...` で実行する。
`calc` CLI と `calculate()` は bash を起動せず、Python エンジンは実行中の Python を使う。
`olnm.run("calc", "6", "mul", "7")` も互換の `run` 経由で利用できる（こちらは bash が必要）。

### シェルの制約と計算エンジンの違い

- `calc 6 * 7` は bash/zsh が関数やCLIを呼ぶ**前**に `*` をファイル名へ展開する。
  zsh の既定設定では一致しないワイルドカードも `no matches found` になる。
  `**`、`?`、`[]` にも展開の問題がある。`mul` / `pow` なら設定変更なしで回避できる。
- `(` / `)`、`;`、`&`、`|`、`<`、`>` はシェルの構文。括弧には `lpar` / `rpar` を使う。
  `$()`、バッククォート、変数展開も呼び出し前に実行されるので、未信頼の文字列をシェルコードへ貼り付けない。
  必要なら式全体を `'6 * (7 + 1)'` のように引用するか、APIの引数配列で渡す。
- `noglob`（zsh）、`set -f`（bash）はグロブだけを抑える。括弧やコマンド置換は抑えられないため、
  `calc` 自身はグローバルなシェル設定やaliasを変更しない。
- 演算子の優先順位・精度・出力・実行エラーは指定したエンジンに従う。
  Python の `calc -2 pow 2` は `-4`、Node は同じ式を構文エラー（終了 `1`）にする。
  Node では `calc --engine node lpar -2 rpar pow 2` → `4` と明示する。
- Python の `calc -7 mod 4` は `1`、Node は `-3`。
  `calc 1 div 0` は終了 `1`、Node は `Infinity` を表示して終了 `0`。
  Node では `floordiv` / `//` を拒否する（JSではコメントになる）。
  整数精度も Python と JavaScript Number で異なる。Node 未導入時の終了コードは `127`。
- 新 `calc` はコード実行につながる構文を拒否するが、サンドボックスではない。
  入力は4096文字まで。非常に大きなべき乗などのCPU・メモリ使用量は制限しないため、
  公開サービスで未信頼入力を受ける場合は別途プロセスのリソース制限が必要。
  関数呼び出しや文字列の評価は移行対象外。必要な場合は `python3 -c` / `node -p` を直接使う。

## 標準ライブラリツールのデフォルトコマンド

olnm を eval で読み込むと、追加の登録なしで次のコマンドを使える。

```sh
xprobe --help
cli_args --help
ghi --help
printf '# Hello\n' | markdown to-html
ascii_artist --help
yourself --minimal --format json
```

| コマンド | 供給元・実装 | 実行方法 |
|---|---|---|
| yourself | yourself.py の固定スナップショット | olnm.py に同梱。Pythonだけで実行 |
| xprobe | myon-bioinformatics/xprobe | uv の専用ツール環境をキャッシュして再利用 |
| cli_args | myon-bioinformatics/cli_args | 同上 |
| ghi | myon-bioinformatics/gh_identity | 同上。供給元は ghi / gh_identity を提供 |
| markdown | myon-bioinformatics/markdown の md-market | 同上。inventory / to-html / to-markdown / toc |
| ascii_artist | myon-bioinformatics/ascii_artist | 同上 |

追加の単一ファイル群をolnm.pyへ重複コピーせず、各リポジトリの最小限の配布設定を利用する。
供給元の実行時Python依存は空。ビルドバックエンドと開発用依存は実行時依存と区別する。
uvが必要な入口は初回に固定したGitコミットを取得・ビルドするため通信する場合があり、その後はuvのキャッシュを再利用する。
**利用者が uv tool install や名前の登録を先に行う必要はない。** uv不在なら公式導入先を示して終了127となる。

CLI・Python・uv・Node/Bunから同じ入口を呼べる。

```sh
python3 "$OLNM_PY" xprobe --help
python3 "$OLNM_PY" run xprobe --help
uv run --no-project "$OLNM_PY" xprobe --help
```

```python
import olnm
raise SystemExit(olnm.xprobe('--help'))
# olnm.cli_args / olnm.ghi / olnm.markdown / olnm.ascii_artist も同じ argv・終了コードの契約
```

Node/Bun側のargv配列も `[OLNM_PY, 'xprobe', '--help']` のようにするだけ。
stdout / stderr / stdin / cwd / 終了コードは供給元へ引き継ぎ、シェル文字列として再解釈しない。
`call xprobe` 等では実行出力と戻り値JSONが混じるため、直接CLI/APIを使う。

olnm の dial が offline / local のときは uv に `--offline` を付け、取得済みキャッシュだけを使用する。未取得のツールは失敗する。
uvのoffline指定は子ツールの通信を遮断しない。ghiのAPI操作等は供給元の仕様に従う。
採用コミットは `_STDLIB_TOOLS` に完全SHAで固定し、olnm更新時に検証済みの版へ更新する。
供給元6リポジトリのuv配布PRはmainへ統合済み。検証したmainの完全SHAを採用し、更新時にも取得・実行テストを行う。

olnmを介さず常用コマンドとして登録したい場合は、各リポジトリで `uv tool install .`。
別プロジェクトからimportする場合は `uv add /絶対パス/リポジトリ` を使う。
設定は build-system・既存モジュール・console script を中心とした最小限とし、実行時依存は増やさない。

## yourself：登録なしの環境レポート

**olnm を読み込めば `yourself` と打つだけで利用できる。**
標準ライブラリだけで動く [yourself.py](https://github.com/myon-bioinformatics/yourself) を、変更せず olnm.py の中に同梱している。
追加のインストール・登録・ファイル配置・実行時ダウンロードは不要。olnm.py だけを別の場所へ持ち込んでも使える。
Python の組み込み標準モジュールという意味ではなく、外部Python依存が不要なモジュールである。

bash/zsh に定義を eval 済みなら：

```sh
yourself
yourself --minimal --format json
yourself --help
```

引数なしでは元の yourself と同じ、現在の作業ディレクトリを対象とする環境レポートになる。
最小JSONだけなら `--minimal --format json`。出力内容は実行環境によって変わり、最小JSONには schema_version / os / runtime が含まれる。
`--versions` / `--reach` など元のオプションもそのまま受け取る。観測の範囲・通信・実行の有無は元のオプションの仕様に従う。
引数の定義を複製せず、内蔵した `main(argv)` を呼ぶ。`yourself --fo<Tab>` / `yourself --format <Tab>` の補完も内蔵版の引数定義から生成する。

シェルへ読み込まず、保存したファイルを使う場合：

```sh
python3 "$OLNM_PY" yourself --minimal --format json
python3 "$OLNM_PY" run yourself --minimal --format json
uv run --no-project "$OLNM_PY" yourself --minimal --format json
```

uv tool 登録後は `command olnm yourself --minimal --format json`。
eval 後は `olnm yourself --minimal --format json` / `olnm run yourself --minimal --format json` でもよい。
Node/Bunからは既存の subprocess の argv を `[OLNM_PY, "yourself", "--minimal", "--format", "json"]` にすれば同じ入口を使える。
mise / Node / Bun がない環境でも Python 3.11+ だけで利用できる。

Python から直接呼ぶと、JSONなどの出力はそのまま stdout に出て、戻り値は終了コードとなる。

```sh
python3 -c 'import olnm, sys; sys.exit(olnm.yourself("--minimal", "--format", "json"))'
```

`--help` は終了0、不正な引数は終了2。機械処理する場合は上の直接CLI/APIを使い、子の出力と戻り値JSONが混じる `call yourself` は使わない。

### 同梱版の根拠と更新（保守者向け）

実行時は固定した版を使う。取得元・完全コミットSHA・元ファイルのSHA256・MITライセンス本文を olnm.py に保存している。
通常の利用者が更新や登録の手順を行う必要はなく、olnm本体の更新とともに採用版が更新される。

保守者が最新 main を採用する場合は、確認済みのクリーンな yourself clone を用意して以下を実行する。
この更新スクリプトは通信せず、clone の HEAD と yourself.py / LICENSE のバイト一致を検査して取り込む。

```sh
python3 scripts/update_yourself.py /絶対パス/yourself
OLNM_TEST_UV=1 python3 -m unittest discover -s tests -v
```

取り込み前に upstream 側でも `uv run pytest -q` を実行する。採用SHA、ハッシュ、テスト結果と生成差分をレビューする。
未コミットで変更したソースは拒否し、同じ版の再取り込みでは差分を作らない。

## Python のワンライナーから使う

### clone したディレクトリ、またはインストール済みの Python 環境

以下は `olnm.py` のあるディレクトリで実行する。外側をシングルクォート、Python 内の文字列をダブルクォートにすると書きやすい。

```sh
python3 -c 'import olnm; olnm.ls("python")'
python3 -c 'import olnm; olnm.grep("json")'
python3 -c 'import olnm; olnm.like("uvtets")'
python3 -c 'import olnm; print(olnm.names()[:5])'
python3 -c 'import olnm; print(len(olnm.entries()))'
python3 -c 'import olnm; print(olnm.public())'
python3 -c 'import olnm; print(olnm.read_dial())'
python3 -c 'import olnm, sys; sys.exit(olnm.calculate("6", "mul", "7"))'
```

`entries()` / `names()` / `public()` / `read_dial()` は自分では表示しないので `print()` が必要。
`like()` / `ls()` / `grep()` は表示と戻り値の両方がある。
`print(olnm.like("uvtets"))` では候補表示に加えて Python のリストも表示される。

### 別のディレクトリから保存済みファイルを import

ファイル方式の `OLNM_PY` を設定済みなら、作業ディレクトリを変えずに次を実行できる。

```sh
python3 -c 'import os, sys; from pathlib import Path; sys.path.insert(0, str(Path(os.environ["OLNM_PY"]).parent)); import olnm; olnm.like("uvtets")'
```

古い保存名 `~/.olnm.py` など、`import olnm` で見つからないファイル名でも `runpy` なら読める。

```sh
python3 -c 'import os, runpy; m = runpy.run_path(os.environ["OLNM_PY"]); m["like"]("uvtets")'
```

戻り値は module ではなく辞書。CLI を呼ぶ場合は、次の subprocess 方式で終了コードも扱える。

### 出力を文字列として取得／標準入力を渡す

```sh
python3 -c 'import os, subprocess, sys; r = subprocess.run([sys.executable, os.environ["OLNM_PY"], "calc", "6*7"], text=True, capture_output=True, check=True); print(r.stdout.strip())'
python3 -c 'import os, subprocess, sys; r = subprocess.run([sys.executable, os.environ["OLNM_PY"], "run", "pyjson"], input="{\"answer\":42}", text=True, capture_output=True, check=True); print(r.stdout, end="")'
```

引数はリストで渡す。`shell=True` は不要。`run` の引数の空白はそのまま渡る。
`calc` / `calculate()` は数値計算のみを受け付ける。

### 表示なしで一覧データを使う

表示しない `entries()` を絞り込むと、表示ログの捕捉が要らない。

```sh
python3 -c 'import olnm; print([e["name"] for e in olnm.entries() if e["section"] == "python"])'
python3 -c 'import json, olnm; print(json.dumps(olnm.entries(), ensure_ascii=False))'
```

表示を行う API の戻り値だけを JSON で取得する場合は、次の `call` を使う。

## JSON で関数を呼ぶ call

```sh
python3 "$OLNM_PY" call public
python3 "$OLNM_PY" call names
python3 "$OLNM_PY" call entries
python3 "$OLNM_PY" call like '["uvtets"]'
python3 "$OLNM_PY" call like '["uvtets"]' --kwargs '{"n":2}'
python3 "$OLNM_PY" call ls '["python"]' --kwargs '{"offline":true}'
python3 "$OLNM_PY" call grep '["json","pretty"]'
python3 "$OLNM_PY" call read_dial
```

構文は `call 関数名 '[位置引数の配列]' --kwargs '{キーワード引数のオブジェクト}'`。
引数を省略すると `[]` / `{}`。JSON は `true` / `false` / `null`、Python 直呼びは `True` / `False` / `None`。
説明表示は stderr へ移るため、候補がターミナルに見えても stdout は JSON 配列だけとなる。

```sh
python3 "$OLNM_PY" call like '["uvtets"]' > candidates.json
python3 -c 'import json; print(json.load(open("candidates.json"))[0])'
```

期待値は `uvtest`。ログも分離するなら最初の行に `2> candidates.log` を追加する。
`call run` は子プロセスの stdout が混じるため、JSON の受け渡しには使わない。
シェル関数には `run`、機械処理には `call entries` などのデータ API を使う。

## uv：ファイルを実行する

uv がなければ [公式の導入手順](https://docs.astral.sh/uv/getting-started/installation/)に従って導入し、`uv --version` を確認する。
uv へのスクリプト登録は不要。保存したファイルはすぐ実行できる。

```sh
uv run --no-project "$OLNM_PY" ls python
uv run --no-project "$OLNM_PY" calc 6 mul 7
uv run --no-project "$OLNM_PY" call like '["uvtets"]'
uv run --no-project --python 3.11 "$OLNM_PY" calc 6 mul 7
```

`--no-project` は作業中の別プロジェクトの依存解決を避けるため。
`--python` はファイル名より前に置く。未導入の Python は uv が取得する場合がある。
完全オフラインなら Python も事前に用意する。

```sh
uv run --offline --no-project --python 3.11 "$OLNM_PY" calc 6 mul 7
```

`--offline` は **uv の通信**を止める。実行する関数や API の通信まで止めるものではない。
ファイルからのシェル登録もできる。

```sh
eval "$(uv run --no-project "$OLNM_PY" init bash)"
calc 6 mul 7
```

登録されたシェル関数の内部は python3 を呼ぶので、`command -v python3` でも存在を確認する。

## uv：常用ツールとして登録する

### ローカルソースを登録 → 実行

リポジトリルート（`pyproject.toml` がある場所）で実行する。単独の `olnm.py` ファイルは tool install の登録対象ではない。

```sh
uv tool install .
uv tool list
uv tool dir --bin
uv tool update-shell
```

update-shell の案内に従いターミナルを開き直して PATH を反映する。以後は別ディレクトリでも使える。

```sh
olnm --help
olnm ls python
olnm calc 6 mul 7
olnm call like '["uvtets"]'
```

**パッケージ名は `one-linear-numerous-memo`、コマンド名と import 名は `olnm`。**
ツール用 Python 環境と普段の python3 の環境は別。
tool install だけでは `python3 -c 'import olnm'` がどこからでも成功するようにはならない。
import 目的なら次節の uv add を使う。

### GitHub から直接登録

clone なしで導入する場合：

```sh
uv tool install 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@main'
olnm calc 6 mul 7
```

PyPI の同名パッケージを仮定せず、このリポジトリを指定する。
固定版を使う場合は `@main` を完全な SHA に変更する。以下の uvx / uv add でも同様。

### 登録せず 1 回だけ使う（uvx）

ローカルソースはリポジトリルートで：

```sh
uvx --from . olnm calc 6 mul 7
uvx --from . olnm call like '["uvtets"]'
```

GitHub のソースを使う場合：

```sh
uvx --from 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@main' olnm ls python
```

### 登録後にシェル関数も使う

```sh
eval "$(olnm init bash)"
calc 6 mul 7
olnm python
```

ここから `olnm` は**シェル関数**になる。従来の `olnm python` など分類名1語は一覧表示を保ち、`olnm run ...` / `olnm calc` / `olnm tools` などの CLI も呼べる。分類名と衝突する場合を含め、インストール済み CLI を確実に呼ぶには `command olnm`。

```sh
command olnm calc 6 mul 7
command olnm call like '["uvtets"]'
```

永続化する場合は `~/.bashrc` に `eval "$(command olnm init bash)"` を 1 行追加する。
zsh は `~/.zshrc` と `init zsh`。ファイル方式の登録行と併用せず、使う方式の行を 1 つ残す。
ツール環境を消すと、この方式の `OLNM_PY` 参照先も消える。

### 更新・確認・削除

| 導入元 | 更新コマンド | 注意 |
|---|---|---|
| ローカル clone | `git pull --ff-only` → `uv tool install --force .` | ソースのあるディレクトリで実行 |
| GitHub の @main | `uv tool upgrade one-linear-numerous-memo` | 登録元のブランチから更新 |
| SHA 固定 | `uv tool install --force 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@新しい完全SHA'` | SHA を自分で更新 |
| シェル関数定義 | `eval "$(command olnm init bash)"` | 更新後に再登録。zsh なら zsh |

```sh
uv tool list
uv tool uninstall one-linear-numerous-memo
```

削除時は rc ファイルの init 行も削除し、新しいターミナルを開く。
`~/.olnm` のダイヤル・forge データはアンインストールで消えない。
ツール方式の更新には uv を使う。`olnm_update` は手動保存したファイルを URL から上書きする関数。

## uv：別プロジェクトに依存として登録する

### 新規作成 → 依存登録 → import

`OLNM_SOURCE` は clone 済みリポジトリの絶対パスに置き換える。

```sh
export OLNM_SOURCE="$HOME/src/OneLinearNumerousMemo"
uv init --bare --python 3.11 olnm-demo
cd olnm-demo
uv add "$OLNM_SOURCE"
uv run python -c 'import olnm; olnm.like("uvtets")'
uv run python -c 'import olnm, sys; sys.exit(olnm.calculate("6", "mul", "7"))'
uv run olnm call names
```

GitHub から登録するなら uv add の行を次に置き換える。

```sh
uv add 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@main'
```

開発中の変更を直ちに反映するなら `uv add --editable "$OLNM_SOURCE"`。
`uv tool install --editable "$OLNM_SOURCE"` も開発用ツール登録に使える。ソースを移動・削除しない。

### 既存プロジェクトを変えず一時的に import

```sh
uv run --no-project --with "$OLNM_SOURCE" python -c 'import olnm; olnm.like("uvtets")'
```

### 登録後のロック・更新・削除

```sh
uv sync --locked
uv run --locked python -c 'import olnm; print(len(olnm.names()))'
uv lock --upgrade-package one-linear-numerous-memo
uv sync
uv remove one-linear-numerous-memo
```

利用側で `uv.lock` をコミットする。GitHub @main を登録しても通常実行は lock の固定コミットを使う。
最新 main の採用は lock 更新後にテストする。
ローカル通常インストールの再構築には `uv sync --reinstall-package one-linear-numerous-memo`。
uv remove はそのプロジェクトの依存を削除する。別途登録した uv tool は残る。

## uv 関数で実際の作業をする

ここは olnm 自体の登録とは別で、olnm 内の便利関数を使う例。
**シェルへ eval で読み込み済み**として、空の作業用ディレクトリで始める。

```sh
mkdir olnm-work-demo
cd olnm-work-demo
uvinit olnm-work-demo
uvdev ruff
printf 'import unittest\n\n\nclass Smoke(unittest.TestCase):\n    def test_answer(self):\n        self.assertEqual(6*7, 42)\n' > test_smoke.py
uvtest
uvcheck
uvpy -c 'print(6*7)'
```

uvtest は **pytest ではなく `python -m unittest discover`**。期待値は `Ran 1 test` / `OK`、最後は `42`。
uvcheck は ruff が必要なので先に uvdev ruff。uvinit は既存プロジェクトで再実行せず、その場所では uv sync を使う。

| 関数 | 実行例 | 前提・結果 |
|---|---|---|
| uvinit | `uvinit demo` | 空の cwd にプロジェクト作成 + sync |
| uvadd | `uvadd requests` | uv add に委譲し、通常は依存追加後に同期。`--no-sync` も利用可 |
| uvdev | `uvdev ruff` | 開発依存追加。ネットワーク使用 |
| uvtest | `uvtest -v` | lock に従い unittest。先に uv.lock を作成 |
| uvcheck | `uvcheck` | ruff check → uvtest。ruff が必要 |
| uvpy | `uvpy -c 'print(42)'` | lock に従い Python 実行。引数なしなら REPL |
| uvdeps | `uvdeps` | ツリーと環境の整合性確認 |
| uvup | `uvup requests` | 指定依存の lock 更新 + sync |
| uvupall | `uvupall` | 全依存の lock 更新 + sync |
| uvfmt | `uvfmt` | uvx で ruff format / fix。ファイルを書換え |
| uvbuild | `uvbuild` | build-system 設定済みプロジェクトを dist/ にビルド |
| uvpys | `uvpys 3.11 3.12` | 指定した Python を取得。引数なしなら導入済み一覧。失敗時は終了コードを返す |
| uvresync | `uvresync` | lock を削除して再解決。先に差分を保存 |
| uvclean | `uvclean` | cwd の .venv / build / dist / キャッシュを削除 |

未登録で 1 回だけ実行するなら、利用側プロジェクトで `python3 "$OLNM_PY" run uvtest -v`。
run は呼び出し元の cwd を引き継ぐ。

## CLI の全入口

`python3 "$OLNM_PY"` は、ツール方式なら `command olnm`、uv ファイル方式なら `uv run --no-project "$OLNM_PY"` に置換できる。

| 入口 | 実行例・オプション |
|---|---|
| init | `python3 "$OLNM_PY" init bash` / `init zsh`（定義を出力） |
| ls | `python3 "$OLNM_PY" ls` / `ls git` / `ls --offline` / `ls python --offline` |
| grep | `python3 "$OLNM_PY" grep json pretty`（全語一致） |
| like | `python3 "$OLNM_PY" like uvtets` / `like uvtets --hint` |
| sections | `python3 "$OLNM_PY" sections` |
| net | `python3 "$OLNM_PY" net`（🌍 の関数名） |
| doctor | `python3 "$OLNM_PY" doctor`（任意ツールの欠如も表示） |
| calc | `python3 "$OLNM_PY" calc`（式を対話入力）、`calc 6 + 7`、stdin からも入力可 |
| complete | `python3 "$OLNM_PY" complete -- olnm dial ""`（候補を改行区切りで表示） |
| tools | `python3 "$OLNM_PY" tools` / `tools mise` / `tools node` / `tools bun` / `tools go` / `tools rust`（存在確認と導入案内のみ） |
| mise | `python3 "$OLNM_PY" mise exec node@26 -- node -v`（argv を mise へ転送） |
| yourself | `python3 "$OLNM_PY" yourself --minimal --format json`（登録不要の同梱版） |
| dial | `python3 "$OLNM_PY" dial` / `dial offline`（設定変更。local / mirror / github、0〜3 も可） |
| calc | `python3 "$OLNM_PY" calc 2 pow 10` |
| run | `python3 "$OLNM_PY" run pyjson` |
| call | `python3 "$OLNM_PY" call like '["uvtets"]' --kwargs '{"n":2}'` |
| hub | `python3 "$OLNM_PY" hub --help`。`nagoyaction forge` へ転送。次節に全件 |

NagoyAction 導入後は `hub repo add --help` / `hub issue new --help` / `hub pr new --help` まで個別ヘルプがある（`nagoyaction forge …` のヘルプ）。
終了コードは通常成功 0、構文エラー 2、未知の run 関数 127。
候補なしの通常 like は 0、like --hint は候補なしなら 127。
run は子コマンドの終了コードを返す。call の数値の戻り値は JSON データであり、終了コードではない。

### uv へ整理する前の診断

`olnm doctor` は実行中の Python のバージョンとパス、PATH 上の python3、uv 管理下のインストール済み Python、olnm のパス、ツールの有無、uv への登録状況、`OLNM_` と `DIAL_FILE` の環境変数名、bash/zsh の主な起動ファイル内の関連行番号、旧 `~/.olnm.py` や `~/.olnm` の存在を表示する。環境変数の値や設定行の内容は表示せず、ファイルの変更や削除は行わない。行番号は候補であり、間接的に読み込まれるファイルや親シェル内の関数・エイリアスは検査できないため、`type -a olnm` も合わせて確認する。

Node、Bun、Go、Rust、uv、mise は PATH 上の実行ファイルとバージョンを表示する。見つからない場合は `not found on PATH` と表示し、導入や更新は行わない。mise にインストール済みでも PATH に有効化されていないランタイムは、この表示では確認できない。

表示された起動ファイルから不要な olnm の設定を外し、新しいシェルを開く。uv に登録するには `uv tool install --force 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@main'` を実行する。PATH に見つからない場合は `uv tool update-shell` を実行して新しいシェルを開く。診断は任意ツールが見つからなくても成功終了する。


## ダイヤルと保存先

ダイヤルは名前で指定する：`offline` / `local` / `mirror` / `github`。表示は名前が先で、保存値の数字を後ろに付ける（例 `🔁 mirror (2)`）。
`DIAL_FILE` には従来どおり数字 0〜3 を保存するため、既存の読み手はそのまま動く。`dial 2` のような数字指定も使える。
綴りを誤ると `did you mean: mirror?` を表示し、ダイヤルは変えない。

ローカル forge は NagoyAction へ移った。`olnm hub ...` は `nagoyaction forge ...` に引数と終了コードをそのまま引き渡す。
forge の状態（`$OLNM_HOME/forge/state.json`）がある場合、`olnm dial` の変更も `nagoyaction forge dial` に任せる。NagoyAction は origin と forge を動かしてから同じ `DIAL_FILE` を書く。
forge があるのに NagoyAction が見つからない場合、olnm は `dial unchanged` と導入方法を表示して終了コード 127 で止まる。origin だけが古い接続先を指したまま push しないため。
forge がなければ olnm 自身が `DIAL_FILE` を読み書きする。表示は NagoyAction と同じ。

`OLNM_HOME`（既定 `~/.olnm`）、`DIAL_FILE`（既定 `$OLNM_HOME/dial`）は **Python の起動／import 前**に設定する。
ダイヤル未設定時は github（3）。

| 名前（保存値） | 🌍 付きシェル関数 | 🎛️ 関数（ghpr ghprs ghis ghisn ghweb） | origin（gp / gpl） | forge |
|---|---|---|---|---|
| 🔌 offline (0) | 停止するスタブ | forge 登録済みならローカルへ | bare | 停止 |
| 🏠 local (1) | 停止するスタブ | forge 登録済みならローカルへ | ローカル forge | 起動 |
| 🔁 mirror (2) | 実行可能 | forge 登録済みならローカルへ | ローカル forge | 起動・GitHub へ mirror |
| ☁️ github (3) | 実行可能 | gh へ | GitHub | 起動（バックアップ） |

通信を OS レベルで遮断する機能ではない。🌍 なしの関数や Python API の直呼びも遮断しない。
forge 未初期化時は 🎛️ 関数が gh に進む場合もある。
forge がある状態で dial を変えると、登録済み repo の origin と forge 起動状態も変わる。

**普段の状態を変更せず offline を試す：**

```sh
(
  export OLNM_HOME="$(mktemp -d)"
  export DIAL_FILE="$OLNM_HOME/dial"
  python3 "$OLNM_PY" dial offline
  python3 "$OLNM_PY" calc 6 mul 7
  python3 "$OLNM_PY" run myip
)
```

期待値は 42 と `myip: 🌍 needs dial mirror or github (now 🔌 offline)`。最後の終了コードは 1。
読込後にダイヤルを変えるなら `olnm_dial offline` で関数も再登録される。
Python の `olnm.dial("offline")` や CLI の `dial offline` は親シェルを再読込しないので、続けて `olnm_reload` が必要。

forge 関連の保存物は NagoyAction が作り、同じ場所を使い続ける。

| 保存物 | 既定の場所 |
|---|---|
| ダイヤル | `~/.olnm/dial` |
| forge バイナリ | `~/.olnm/forge/bin/forge` |
| 設定・資格情報 | `~/.olnm/forge/app.ini` / `state.json`（トークン等を含む） |
| DB・リポジトリ | `~/.olnm/forge/data/` |
| bare バックアップ | `~/.olnm/forge/bare/` |
| ログ・PID | `~/.olnm/forge/log/` / `forge.pid` |
| forge 向け Git 認証ヘッダー | `~/.gitconfig`（GIT_CONFIG_GLOBAL で分離可能） |

## hub の導入から Issue・PR 作成まで

forge の管理は [NagoyAction](https://github.com/myon-bioinformatics/NagoyAction) の `nagoyaction forge` が担う。olnm の `hub` はそこへ引数と終了コードを転送するだけで、forge のコードは持たない。
先に NagoyAction を uv ツールとして入れる（標準ライブラリのみ、実行時依存なし）：

```bash
git clone https://github.com/myon-bioinformatics/NagoyAction
cd NagoyAction
python3 tools/build_uv_tool.py build/nagoyaction-tool
uv tool install ./build/nagoyaction-tool
nagoyaction forge --help
```

導入せずに clone だけ使う場合は `export NAGOYACTION=/path/to/NagoyAction/nagoyaction.py` を設定する（閉域網へ持ち込んだ `local_forge.py` も指定できる。後述）。どちらもない状態で `olnm hub ...` を実行すると、この導入方法を表示して終了コード 127 で止まる。

Gitea（既定）または Forgejo の Linux バイナリが必要。Go は不要。
**通常ユーザーで実行する。** forge 本体は root 起動できない。
以下はシェル関数未登録でも使える CLI 方式。`python3 "$OLNM_PY" hub ...` は `nagoyaction forge ...` と同じで、`hubdial ...` はその短縮関数。

### 導入 → 起動 → repo 登録

```sh
python3 "$OLNM_PY" hub install
python3 "$OLNM_PY" hub init --port 3000 --user admin
python3 "$OLNM_PY" hub up
python3 "$OLNM_PY" hub status
```

init が表示する初期パスワードで http://localhost:3000 にログインする。
app.ini・DB・管理者・API トークン・Git 認証を作る。dial 未設定時は 1、既存 dial は上書きしない。
設定は 127.0.0.1、SQLite、SSH/メール/新規登録なし。

以下は専用のサンプルリポジトリで行う。

```sh
mkdir olnm-hub-demo
cd olnm-hub-demo
git init -b main
printf 'hello\n' > README.md
git add README.md
git -c user.name=demo -c user.email=demo@localhost commit -m 'initial commit'
python3 "$OLNM_PY" hub repo add .
git remote -v
git push -u local main
python3 "$OLNM_PY" hub labels
python3 "$OLNM_PY" hub issue new 'crash' --body '再現手順を書く' --label bug
python3 "$OLNM_PY" hub issue ls
```

repo add は local / bare / origin を設定する。GitHub にも紐付ける場合だけ `--github owner/name` を付ける。
その値は自分の実在する repo に置換する。mirror / github の sync / mirror は GitHub へ push する。

### ブランチ → PR

```sh
git switch -c fix-demo
printf 'fixed\n' >> README.md
git add README.md
git -c user.name=demo -c user.email=demo@localhost commit -m 'fix demo'
python3 "$OLNM_PY" hub pr new 'fix demo' --base main --body '変更内容を書く'
python3 "$OLNM_PY" hub pr ls
python3 "$OLNM_PY" hub sync
python3 "$OLNM_PY" hub down
```

PR 作成は作業ブランチを local へ先に push する。base の main も先に push しておく。
Issue / PR / labels の対象は cwd の登録済み repo。repo ls は全登録一覧。
読込済みなら `ghisn 'crash' bug` / `ghis` / `ghpr 'fix demo'` も使える。

### Python から hub

導入・起動・repo 登録後、その repo で実行する。forge の関数は olnm ではなく NagoyAction 側にある。
`nagoyaction.forge(...)` は CLI と同じ引数を受け取り、終了コードを返す。NagoyAction の clone を import パスに置くか、その uv ツール環境の Python で実行する。

```bash
python3 -c 'import nagoyaction; raise SystemExit(nagoyaction.forge("issue", "new", "crash", "--body", "再現手順", "--label", "bug"))'
python3 -c 'import nagoyaction; raise SystemExit(nagoyaction.forge("dial", "mirror"))'
python3 -c 'import local_forge; print(local_forge.hub_repo_ls())'
```

olnm 側に残る forge 関連の API は `hub_url()`（状態ファイルの port から URL を返すだけ）と、ダイヤルの `dial` / `dial_level` / `dial_label` / `read_dial`。
`local_forge.hub_init()` の戻り値はトークン・パスワードを含む状態データなので、共有ログに保存しない。

### hub サブコマンド全件

以下は `nagoyaction forge`（または同じものを転送する `python3 "$OLNM_PY" hub`）に続ける。olnm は最初の語だけを確認し、未知の語には候補を出す。それ以降の解釈とタイポ候補は NagoyAction が行う。

| 入口 | 引数・例 | 前提／副作用 |
|---|---|---|
| install | `--version latest --flavor gitea` / `--from ファイル --sha256 SHA` | 取得または持込バイナリを検証・配置 |
| bundle | `./carry --version 1.27.3 --flavor gitea` | オンライン側で持込用ファイル作成 |
| init | `--port 3000 --user admin`（--password も可） | DB・管理者・トークン・Git 設定作成 |
| up / down | 引数なし | 起動／停止 |
| status / doctor | 引数なし | doctor は GitHub 到達性も確認 |
| logs | `-n 80` | ログ末尾 |
| dial | 引数なし／offline / local / mirror / github（0〜3 も可） | 通常の dial と同じ。表示は `🔁 mirror (2)` |
| repo add | `. --github owner/name --public` | --public 省略時 private |
| repo ls / repo rm | `ls` / `rm .` | rm は登録解除のみ。データ・remote は残る |
| api | `GET /user/repos` / `POST /user/repos --data '{"name":"demo"}'` | GET / POST / PATCH / PUT / DELETE。path は /api/v1 より後 |
| issue ls | `--state open`（closed / all も可） | cwd の Issue |
| issue new | `'title' --body 'text' --label bug --label enhancement` | 作成済みのラベル名を指定 |
| pr ls | 引数なし | cwd の open PR |
| pr new | `'title' --head fix-demo --base main --body 'text'` | --head 省略時は現在ブランチ |
| labels | 引数なし | GitHub 既定ラベルを追加 |
| sync | 引数なし | 全登録を bare / local /（mirror / github なら）github へ push |

install / bundle の --flavor は gitea / forgejo。Forgejo は Codeberg、Gitea は GitHub 等から取得する。
install は最新を問い合わせ、問い合わせが塞がれた Gitea 環境ではコード内の VERIFIED（1.27.3）にフォールバック。
固定版なら --version 1.27.3。mirror 用の GitHub トークンは forge DB に保存される。

### 閉域網へ持ち込む

オンライン側：

```sh
python3 "$OLNM_PY" hub bundle ./carry --flavor gitea --version 1.27.3
```

carry/ を閉域側へコピーし、Linux amd64 の通常ユーザーで：

```sh
python3 carry/local_forge.py install --from carry/gitea-1.27.3-linux-amd64
python3 carry/local_forge.py init
python3 carry/local_forge.py up
```

bundle はバイナリ・.sha256・local_forge.py（NagoyAction の forge 単体、標準ライブラリのみ）を含む。olnm.py・Python・git 自体は別途必要。
閉域側で olnm の `hub` / `hubdial` / `ghis` などを使うなら `export NAGOYACTION="$PWD/carry/local_forge.py"` を設定する。olnm はこのファイルにサブコマンドを直接渡す。
amd64 以外は NagoyAction の Python API `local_forge.hub_bundle(..., arch="arm64")` などで明示し、取得元の対応を確認する。
forge なしでも gbundle / gunbundle で Git を持ち運べる。

uvbundle は `uv tool run --from pip pip download` で wheels を取得する。初回は pip 自体の取得にもネットワークが必要。取得失敗時は失敗として終了する。
uv に download がない版では pip が必要。オンライン側で wheels / requirements.txt / 対応 Python を準備する。
uvoffline は wheels があればそこから install、なければ uv sync --offline。wheels からのインストールが失敗した場合はその失敗を返す。
必要なファイルやキャッシュなしで依存を生成する機能ではない。

## Node / Bun から呼ぶ

ファイル方式の OLNM_PY を設定済みとして実行する。node を bun に変えても使える。

```sh
node -e 'const {execFileSync}=require("node:child_process"); process.stdout.write(execFileSync("python3",[process.env.OLNM_PY,"calc","6*7"],{encoding:"utf8"}))'
node -e 'const {execFileSync}=require("node:child_process"); const rows=JSON.parse(execFileSync("python3",[process.env.OLNM_PY,"call","names"],{encoding:"utf8"})); console.log(rows.length)'
```

ツール方式なら `execFileSync("olnm", ["calc", "6*7"], ...)`。
uv 経由なら `execFileSync("uv", ["run", "--no-project", process.env.OLNM_PY, "calc", "6*7"], ...)`。

## 入力支援：Tab・タイポ・引用符なしの計算

bash/zsh へ最新の定義を読み込む。zsh は先に `autoload -Uz compinit; compinit` を実行する。
ファイル方式なら `eval "$(python3 "$OLNM_PY" init bash)"`（zsh は bash を zsh に変更）。
ツール方式なら `eval "$(command olnm init bash)"`。

入力途中で Tab を押す（以下の `<Tab>` は入力文字ではなくキー操作）。

| 入力位置 | 候補 |
|---|---|
| `olnm ru<Tab>` | `run` |
| `olnm run pyc<Tab>` | `pyclean` / `pycsv` |
| `olnm ls py<Tab>` | `python` |
| `hubdial issue <Tab>` | `ls` / `new` |
| `hubdial install --flavor <Tab>` | `forgejo` / `gitea` |
| `olnm hub issue ls --st<Tab>` | `--state` |
| `olnm_dial <Tab>` | `0` / `1` / `2` / `3` |
| `olnm call read_<Tab>` | `read_dial` |
| `olnm tools ru<Tab>` | `rust` / `rustc` / `rustup` |

候補は CLI の引数定義と関数一覧から生成する。補完のためにサービスへ接続したり、コマンドを実行したりしない。
ファイル名など自由入力部分は bash の標準補完へ委ねる。zsh では登録したコマンド／選択値を補完する。
`python3 olnm.py ...` 自体の Python コマンド補完は登録しない。ファイル方式でも eval 後の `olnm ...` を使う。

`olnm rn` / `olnm hub isue` などで近い候補を表示し、実行は失敗で終了する。勝手に別の操作へ補正・実行しない。
分類名一覧に該当しない `olnm rn` もコマンド名と分類名の候補を案内し、終了2になる。分類名の入力ミスも同様。CLI 単独の利用は `command olnm rn` または `python3 "$OLNM_PY" rn`。
既存の未定義シェル関数に対する `uvtets` → `uvtest` の誘導も維持する。
JSON call の構文誤りは、配列／オブジェクトの指定例を表示して終了2となる。

### 式はプロンプトで入力すれば引用符不要

```sh
python3 "$OLNM_PY" calc
```

プロンプトが出たら、次の式だけを入力して Enter（シェルへ直接貼る行ではない）。

```text
(6+7)*2
```

期待値は `26`。`*` や括弧をシェルが解釈しないため、外側の引用符は不要。
eval 後なら `olnm calc` または引数なしの `calc` でも同じ入力モードへ入る。
readline が利用できれば、プロンプト内の `sq<Tab>` が `sqrt(` に補完され、矢印キーで編集できる。
readline は任意の標準ライブラリ機能で、ない場合も通常の入力はできる。

一行で使うときのシェル規則は変わらない。`calc 6 + 7` は `13`、乗算や括弧を含める場合は引用する。
Python から argv 配列や API で呼ぶ場合、式文字列の中にシェル用の引用符を付ける必要はない。

```sh
python3 "$OLNM_PY" calc '(6+7)*2'
printf '%s\n' '(6+7)*2' | python3 "$OLNM_PY" calc
```

入力モード（引数なし）の calc は四則演算・`// % **`、`pi/e/tau`、`sqrt/sin/cos/tan/log/log2/log10/exp/ceil/floor/abs/round/min/max` に限定する。
文・import・属性参照・文字列は受け付けず、式長1000字・構文128ノード・整数4096bit・指数絶対値1000まで。
計算式の誤りは理由と再入力例を stderr に示して終了2。引数ありの `calc` は[前の節](#引用符を省略して計算する)の数値計算（関数・定数は使えない、誤りは終了1）。

## mise：複数言語の共通入口

Python の環境・依存は uv に任せ、Node/Bun/Go などの本体は mise でまとめて管理できる。
olnm は薄い呼び出し口として、mise の引数・設定・ロック形式をそのまま使う。各言語のパッケージ管理は引き続き uv / npm・Bun / Go modules が担当する。
mise のインストール自体は [公式手順](https://mise.jdx.dev/getting-started.html)で一度だけ行う。
`python3 "$OLNM_PY" tools mise` でも PATH の有無と導入先を確認できる。
olnm が mise や Node/Bun/Go を勝手にインストールすることはない。

### シェル関数から使う

最新定義を eval で読み込んでから使う。通常は個人共通のバージョンを一度設定し、プロジェクトごとの差があるときだけ上書きする。
以下の use / global / install は実際に導入・設定変更を行う操作なので、使うものだけを選んで実行する。

| olnm 関数 | mise に渡す操作 | 用途 |
|---|---|---|
| `miseglobal node@26 bun@latest go@latest` | `mise use --global ...` | 個人共通の本体を導入して既定値にする |
| `miseuse node@26` | `mise use ...` | 作業ディレクトリの mise.toml へ記録して導入 |
| `miseinstall` | `mise install` | 既存設定に従って本体を導入 |
| `miseexec -- node --version` | `mise exec -- ...` | 設定を適用した子プロセスを起動 |
| `miseexec node@26 -- node --version` | `mise exec node@26 -- ...` | 設定を書き換えず、その実行だけ版を指定 |
| `miseoffline -- node --version` | 自動導入を無効にした `mise exec` | 導入済み環境で実行 |
| `misels` | `mise ls` | バージョンと設定元を確認 |
| `miselock` | `mise lock` | 正確なバージョン・チェックサム等をロック |
| `misedoctor` | `mise doctor` | mise の設定を診断 |

`miseexec` はシェルを activate しなくても利用でき、親シェルの PATH は変更しない。
`miseglobal` / `miseuse` の後も、実行は `miseexec -- ...` にすれば現在のシェルへ即時に反映されるかどうかを気にせず使える。
`miseuse` の `--pin` など、mise の追加オプションはそのまま渡る。ロックの機能・対応範囲は導入した mise のバージョンにも依存する。
`miseexec` 等のツール指定位置は node@26 / bun@latest / go@latest / uv@latest の候補を Tab で表示する。他のツールもそのまま入力できる。

```sh
miseexec node@26 -- node --version
miseexec bun@latest -- bun --version
miseexec go@latest -- go version
miseexec -- uv run --locked python -c 'print(6*7)'
```

**`mise exec` は設定に従って不足したツールを自動導入する場合がある。**
初回の版情報取得がタイムアウトし、警告後に PATH 上の別バージョンが実行される場合も実測した。
初回は `miseinstall node@26` → `miseexec node@26 -- node --version` の順で、導入成功と表示された実バージョンを確認する。
ラッパーは mise の警告を stderr に保ち、終了0だけを要求バージョンの確認結果にはしない。
`miseoffline` は `MISE_AUTO_INSTALL=false` と `MISE_EXEC_AUTO_INSTALL=false` を子プロセスに設定する。
これは完全なネットワーク遮断ではない。実行したコマンド・設定内の処理・バックエンドの通信まで止めるものではない。
🌍 の付いたラッパーは従来どおり offline / local では停止し、miseoffline / misels / misedoctor は利用できる。
Python API と後述の `olnm mise` は任意の mise コマンドを明示的に呼ぶ入口で、olnm の dial を適用せず mise 自体の設定に従う。

### Python / uv / Node から同じ処理を呼ぶ

ファイルを保存してあれば、シェル関数の登録なしで呼べる。

```sh
python3 "$OLNM_PY" mise exec node@26 -- node --version
uv run --no-project "$OLNM_PY" mise exec node@26 -- node --version
```

uv tool 登録後なら `command olnm mise exec node@26 -- node --version`。
eval 後の `olnm mise` 1語は mise 分類の一覧、`olnm mise exec ...` は mise への呼び出しになる。

`olnm.py` を import 可能な場所へ置くか、利用側へ依存登録した Python 環境では：

```sh
python3 -c 'import olnm, sys; sys.exit(olnm.mise("exec", "node@26", "--", "node", "--version"))'
```

uv プロジェクトなら `uv run python -c ...` として同じ API を呼べる。
`olnm.mise()` は bash を経由せず argv リストで起動し、呼出し元の cwd・stdin・stdout・stderr・終了コードを引き継ぐ。
JSON が必要なデータ API ではないため、子出力が混じる `call mise` は使わず、CLI または Python API を使う。
ファイル方式と uv tool 方式の import 環境の違いは既存の説明と同じ。

Node 側もシェル文字列を組み立てず argv 配列で呼ぶ。以下を `invoke-olnm.cjs` として保存すると、Node/Bun のどちらからも呼べる。

```js
const { spawnSync } = require('node:child_process');
const result = spawnSync('python3', [
  process.env.OLNM_PY, 'mise', 'exec', 'node@26', '--', 'node', '--version'
], { stdio: 'inherit' });
if (result.error) { console.error(result.error.message); process.exit(127); }
process.exit(result.status ?? 1);
```

```sh
node invoke-olnm.cjs
bun invoke-olnm.cjs
```

Node/Bun 自体がまだない場合は、最初の一回を上記の Python/uv の入口から呼ぶ。
`--` 以降は実行するコマンドの引数として保ち、空白・引用符・日本語も argv の要素単位で渡す。
mise 不在時は公式導入先と次の操作を stderr に示し、終了127。勝手なシェル設定の変更はしない。

公式: [exec](https://mise.jdx.dev/cli/exec) / [use](https://mise.jdx.dev/cli/use.html) / [自動導入の設定](https://mise.jdx.dev/configuration/settings.html) / [lock](https://mise.jdx.dev/cli/lock)。

## Node・Bun・Rust と作業ディレクトリ

Ubuntu / WSL にこれらが初めから入っているとは限らない。Windows 側へ入れたものと WSL 側の Linux 版も別に確認する。
olnm の一覧・Python 関数・Python計算には Node/Bun/Rust は不要。それぞれを利用する関数だけで必要になる。

```sh
python3 "$OLNM_PY" tools
python3 "$OLNM_PY" tools node
python3 "$OLNM_PY" tools bun
python3 "$OLNM_PY" tools rust
command -v node npm npx bun rustc cargo rustup
```

`tools` は PATH 上の有無・見つかったパス・公式の導入先・作業フォルダの扱いを表示する。自動インストールや設定変更はしない。
Node/Bun 関数の呼び出し時にも、不足した実行環境を確認して具体的な案内を表示し、終了127となる。
例: `run njson` に Node がなければ Node の案内。`run bi` に Bun がなければ Bun の案内。
呼ぶたびに確認するため、同じターミナルの PATH に追加した後は定義の再読み込みは不要。
`nclean` は npm 不在時に node_modules やロックを消さず停止する。

| 層 | Node | Bun | Rust |
|---|---|---|---|
| ユーザーごとの本体 | nvm 等で Node 26 を導入。npm/npx も確認 | 公式手順で導入。通常 ~/.bun/bin を PATH に追加 | rustup で導入。通常 ~/.cargo/bin を PATH に追加 |
| 作業フォルダの指定 | .nvmrc に26を記録、nvm use | 使用する Bun のバージョンを README / CI に記録 | rust-toolchain.toml で採用ツールチェーンを指定 |
| そのプロジェクトの依存・生成物 | package.json / lock / node_modules | package.json / bun.lock / node_modules | Cargo.toml / Cargo.lock / target |

nvm 導入済みなら、Ubuntu/WSL 内で次を実行する（新しい `.nvmrc` を用意する例。既存の指定は先に確認）。

```sh
nvm install 26
nvm use 26
printf '%s\n' 26 > .nvmrc
```

`npm install` は Node 本体、`bun install` は Bun 本体をインストールするコマンドではない。
uv の Python 環境に Node/Bun/Rust が自動で含まれるわけでもない。配布済みバイナリの uv/Bun を使うだけなら、Rust コンパイラの追加は不要。
必要なものだけ導入し、プロジェクトではバージョンと依存を固定する。

公式: [Node](https://nodejs.org/en/download) / [nvm](https://github.com/nvm-sh/nvm) / [Bun](https://bun.sh/docs/installation) / [Rust](https://rust-lang.org/tools/install)。

## olnm 自体の更新

| 導入方法 | 実行する場所 | 更新と再読み込み |
|---|---|---|
| 手動保存した olnm.py | 保存ファイルへ書ける場所。cwd 不問 | OLNM_URL を確認した raw URL に設定 → olnm_update。新ファイルの help が通った場合のみ置換して reload |
| uv tool + Git の @main | cwd 不問 | uv tool upgrade one-linear-numerous-memo → eval "$(command olnm init bash)" |
| uv tool + ローカル clone | その clone | git pull --ff-only → uv tool install --force . → init を再度 eval |
| SHA 固定の uv tool | cwd 不問 | uv tool install --force 'git+https://github.com/myon-bioinformatics/OneLinearNumerousMemo.git@新SHA' → init を再度 eval |
| uv add の利用側 | 利用側の pyproject.toml / uv.lock のある場所 | uv lock --upgrade-package one-linear-numerous-memo → uv sync → テスト |

`olnm_update` の対象は手動保存ファイル。uv 管理の site-packages や Git checkout をこの関数で書き換えず、導入方法に対応する手段を使う。
`main` 参照でも uv.lock がある通常実行はロック済みコミットを使う。更新後の SHA と挙動を確認し、lock をコミットする。
シェルへ読み込んだ関数は古い定義が残るため、本体更新後に init を再度 eval する。zsh は init zsh。
`olnm_update` の URL 未設定時もファイル方式／uv tool 方式の次の操作を表示する。

## 困ったとき

| 症状 | 確認・対処 |
|---|---|
| python3 がない | Python 3.11+ を用意。uv の取得も使えるが、シェル関数は PATH の python3 が必要 |
| can't open file | `printf '%s\n' "$OLNM_PY"` と `ls -l "$OLNM_PY"`。絶対パスを指定 |
| ModuleNotFoundError: olnm | cwd に olnm.py があるか確認。別 cwd は uv add または sys.path / runpy 方式 |
| uv tool install olnm.py が失敗 | pyproject.toml を含むディレクトリ／Git URL を指定。単一ファイルは uv run |
| olnm が見つからない | ツール方式は uv tool list / uv tool update-shell。シェル方式はそのターミナルで eval |
| olnm run ... で no section | 古いシェル定義なら再度 init を eval。インストール済み CLI は `command olnm run ...` |
| pycalc / ncalc が見つからない | `calc` へ統一。`python3 "$OLNM_PY" calc 6 mul 7` |
| call calc が失敗 | CLIは `calc`、Python APIは `calculate`。`call calculate` も利用可 |
| JSON parse error | 配列／オブジェクトをシングルクォートで囲む。true は小文字。stderr を stdout に結合しない |
| --locked で失敗 | 利用側の cwd と uv.lock を確認。初回 uv sync、変更後 uv lock |
| ruff がない | 利用側で uv add --dev ruff。uvcheck は自動導入しない |
| needs dial mirror or github | ネット使用関数が offline / local で停止。接続先を確認後 olnm_dial mirror 等で変更 |
| dial を変えても定義が古い | olnm_reload または init を再度 eval。run は毎回読み直す |
| the local forge now lives in NagoyAction | NagoyAction が未導入。表示どおり uv ツールとして入れるか NAGOYACTION を設定 |
| dial unchanged | forge があるのに NagoyAction が見つからない。上と同じく導入してから olnm_dial を再実行 |
| forge が起動しない | 通常ユーザー、対応 CPU、空きポートを確認。hub status / logs / doctor |
| not a registered repo | 対象 repo で hub repo add .。Python API は path を明示 |
| PR の base がない | main を local へ先に push。別 base は --base で指定 |

## 検証範囲と再実行

リポジトリルートで：

```sh
python3 -m unittest discover -s tests -v
```

forge 本体のテスト（偽 Forgejo による CLI / REST、実 Gitea 1.27.3 の CI）は NagoyAction 側にある。olnm のテストは、偽の `nagoyaction` で引数・終了コードの転送、forge があるときの dial の委譲と拒否、ダイヤル名を確認する。
実際の forge 取得、外部サービスへの push、全 246 関数の副作用を伴う実行はこのテストでは行わない。
全関数の定義・名前の一意性、全 CLI 階層のヘルプ、代表例の実出力・終了コードを確認する。
Python ワンライナー、Node の引数配列、JSON、stdin、空白を含むパス、uv の導入経路も確認する。
追加の入力支援テストは bash / zsh の補完登録と候補、疑似端末での式入力と Tab、タイポ候補、不正JSON、Node/Bun不在時の案内を確認する。zsh / readline がない環境では該当ケースのみ skip。
計算テストは bash/zsh の双方で実ファイルに一致するグロブ、空白、乗除算、べき乗、負数、
不正コードの拒否、エンジン別の出力と終了コードを確認する。
CIでは Python 3.11 / 3.15、Node 26、uv latest、Ubuntu 24.04、bash/zsh で全テストを実行する。

uv の install / uvx / uv add / 再インストール / uninstall を実際に試す場合：

```sh
OLNM_TEST_UV=1 python3 -m unittest tests.test_invocation.TestUvLifecycle -v
```

uv とビルド時の setuptools が必要。初回はネットワークを使う場合がある。
ツール登録先・bin・利用側プロジェクトを一時ディレクトリに分離する。
実行時依存はゼロで、setuptools はパッケージを作るときだけ使う。
Git URL の導入は当該コミットが GitHub にある必要があり、ローカル導入検証とは別に扱う。

従来 README の実機記録（forge が olnm 内蔵だった時期）：Gitea 1.27.3 / 1.24.6 で install / bundle / init / up / repo add / push / labels / issue / PR / dial 0〜3 / sync / mirror 登録を確認。Forgejo 実機は未確認。
この履歴は今回の代行テスト・uv 検証と区別する。

uv の参照先：[scripts](https://docs.astral.sh/uv/guides/scripts/)・[tools](https://docs.astral.sh/uv/guides/tools/)・[entry points](https://docs.astral.sh/uv/concepts/projects/config/#command-line-interfaces)。

## 追加ルール

olnm.py の SHELL 内で関数の直前に `# <絵文字> 名前: 説明` を 1 行。🌍 を書くと offline / local で停止する。
実装を増減したら全件表と件数も更新する。実行時の最新一覧は ls / call public / call entries。

## Python API 全件

`import olnm` 後の名前。シェル関数とは別の API。call public で同じ一覧を得られる。
Python 欄の中身は `python3 -c 'import olnm; 表の中身'` として使う。call 欄は `python3 "$OLNM_PY" call` に続ける。
Path の戻り値は CLI call で JSON 文字列、戻り値なしは null となる。
forge の操作関数（install / init / repo / issue / pr など）は NagoyAction の `local_forge` / `nagoyaction.forge` にある。「Python から hub」を参照。

<!-- python-api:start -->
| Python 署名 | Python ワンライナーの中身 | call に続ける引数 | 処理 |
|---|---|---|---|
| `calc(expression: str) -> int \| float` | `print(olnm.calc("sqrt(81)*2"))` | `calc '["sqrt(81)*2"]'` | 制限付きの算術評価。対話入力は CLI calc を使う。 |
| `complete(*words: str) -> list[str]` | `olnm.complete("olnm", "run", "pyc")` | `complete '["olnm","run","pyc"]'` | コマンド名と現在語を含む候補。表示と戻り値。 |
| `tools(name: str \| None = None) -> dict` | `olnm.tools("node")` | `tools '["node"]'` | PATH と導入案内。インストールは行わない。 |
| `dial(level: int \| str \| None = None) -> int` | `olnm.dial()` | `dial` | 表示、または offline / local / mirror / github（0〜3 も可）で設定。forge があれば NagoyAction が forge と origin を動かす。 |
| `dial_level(value: int \| str) -> int` | `print(olnm.dial_level("mirror"))` | `dial_level '["mirror"]'` | 名前または 0〜3 を保存値の数字へ。不正な値は ValueError。 |
| `dial_label(level: int) -> str` | `print(olnm.dial_label(2))` | `dial_label '[2]'` | 名前が先、保存値が後の表示（`🔁 mirror (2)`）。 |
| `hub_url() -> str` | `print(olnm.hub_url())` | `hub_url` | NagoyAction の状態ファイルの port から forge の URL。未設定なら 3000。 |
| `doctor() -> dict` | `olnm.doctor()` | `doctor` | Optional tools on PATH, the dial, and the forge if set up. |
| `entries() -> list[dict]` | `print(olnm.entries())` | `entries` | Every help line: section, emoji, name, description, needs-internet flag. |
| `grep(*words: str) -> list[dict]` | `olnm.grep("json", "pretty")` | `grep '["json","pretty"]'` | Search names and descriptions (all words must match, case-insensitive). |
| `init(shell: str \| None = None) -> str` | `olnm.init("bash")` | `init '["bash"]'` | Shell code to eval: functions + dial stubs + typo hook + completion. |
| `like(word: str, hint: bool = False, n: int = 6) -> list[str]` | `olnm.like("uvtets", n=2)` | `like '["uvtets"]' --kwargs '{"n":2}'` | Closest names: substring hits first, then difflib similarity ≥0.5. |
| `ls(section: str \| None = None, offline: bool = False) -> list[dict]` | `olnm.ls("python", offline=True)` | `ls '["python"]' --kwargs '{"offline":true}'` | Print help lines, optionally one section and/or offline-only. |
| `mise(*args: str) -> int` | `raise SystemExit(olnm.mise("exec", "--", "node", "--version"))` | mise サブコマンドを使う | argv・入出力・終了コードを引き継ぐ直接呼び出し。 |
| `names() -> list[str]` | `print(olnm.names())` | `names` | All function names (help lines only, private helpers excluded). |
| `net() -> list[str]` | `olnm.net()` | `net` | Names that need internet (🌍). |
| `public() -> list[str]` | `print(olnm.public())` | `public` | Names callable through `call`. |
| `read_dial(default: int = 3) -> int` | `print(olnm.read_dial())` | `read_dial` | 現在のダイヤルを保存値の数字で（0 offline · 1 local · 2 mirror · 3 github）。未設定は 3。 |
| `calculate(*args: str, engine: str = "python") -> int` | `olnm.calculate("6", "mul", "7")` | `olnm calc 6 mul 7` | 数値計算を表示し、エンジンの終了コードを返す。bash不要。 |
| `run(name: str, *args: str) -> int` | `raise SystemExit(olnm.run("calc", "6", "mul", "7"))` | run サブコマンドを使う | Run one one-liner in a non-interactive bash (for Node / Bun / Python callers). |
| `xprobe(*args: str) -> int` | `raise SystemExit(olnm.xprobe("--help"))` | xprobe サブコマンドを使う | 固定コミットの単一ファイルツールをuvのキャッシュ経由で実行。 |
| `cli_args(*args: str) -> int` | `raise SystemExit(olnm.cli_args("--help"))` | cli_args サブコマンドを使う | 固定コミットの単一ファイルツールをuvのキャッシュ経由で実行。 |
| `ghi(*args: str) -> int` | `raise SystemExit(olnm.ghi("--help"))` | ghi サブコマンドを使う | 固定コミットの単一ファイルツールをuvのキャッシュ経由で実行。 |
| `markdown(*args: str) -> int` | `raise SystemExit(olnm.markdown("--help"))` | markdown サブコマンドを使う | 固定コミットの単一ファイルツールをuvのキャッシュ経由で実行。 |
| `ascii_artist(*args: str) -> int` | `raise SystemExit(olnm.ascii_artist("--help"))` | ascii_artist サブコマンドを使う | 固定コミットの単一ファイルツールをuvのキャッシュ経由で実行。 |
| `yourself(*args: str) -> int` | `raise SystemExit(olnm.yourself("--minimal", "--format", "json"))` | yourself サブコマンドを使う | 登録・ダウンロード不要の同梱版 main(argv)。戻り値は終了コード。 |
| `sections() -> list[str]` | `olnm.sections()` | `sections` | Section names in file order. |
<!-- python-api:end -->

## シェル関数 全件

全件を `python3 "$OLNM_PY" run 関数名 引数...` または eval 後の直接呼出しで使える。
説明はソースのヘルプから列挙。🌍 はネット区分、🎛️ は接続先切替。
🌍 がないことは、削除・書換えがないことや、通信が絶対に起きないことを意味しない。

<!-- shell-catalog:start -->
### meta

| 関数 | 説明 |
|---|---|
| `olnm` | 📖 list one-liners (olnm git = one section) |
| `olnm_grep` | 🔎 search help text (olnm_grep json) |
| `olnm_like` | 🤔 closest names to a typo or fragment (olnm_like uvtets) |
| `olnm_sections` | 🗂️ section names |
| `olnm_offline` | 🔒 only one-liners that work without internet |
| `olnm_net` | 🌍 names that need internet |
| `olnm_dial` | 🎛️ show / set dial offline \| local \| mirror \| github (with a local forge, NagoyAction also moves it and origins) |
| `olnm_doctor` | 🩺 which tools are present |
| `olnm_reload` | 🔄 re-evaluate after edits or dial change |
| `olnm_edit` | 📝 open olnm.py in $EDITOR |
| `olnm_update` | ⬇️ 🌍 re-download olnm.py from $OLNM_URL and reload |
| `olnm_steps` | 🔢 non-blank lines of olnm.py |

### uv

| 関数 | 説明 |
|---|---|
| `uvtest` | 🧪 run unittest discover (locked env) |
| `uvcheck` | ✅ ruff check then unittest |
| `uvdeps` | 🌳 dependency tree + pip check |
| `uvup` | ⬆️ 🌍 upgrade one package in lock and sync (uvup requests) |
| `uvupall` | ⬆️ 🌍 upgrade every locked package and sync |
| `uvinit` | 🆕 new project in current dir (uvinit [name]) |
| `uvadd` | ➕ 🌍 add package(s) and sync |
| `uvdev` | ➕ 🌍 add dev package(s) |
| `uvpy` | 🐍 python REPL inside locked env |
| `uvfmt` | 🎨 🌍(first run) ruff format + ruff fix |
| `uvclean` | 🧹 remove .venv, caches, build dirs |
| `uvbuild` | 📦 build sdist+wheel into dist/ |
| `uvresync` | 🔁 🌍 delete lock and resolve from scratch |
| `uvpys` | 🐍 list / 🌍 install pythons (uvpys 3.13) |

### python

| 関数 | 説明 |
|---|---|
| `pyv` | 🐍 python version + path |
| `pyhttp` | 🌐 serve current dir over http (pyhttp [port=8000]) |
| `pyjson` | 📐 pretty-print json from file or stdin |
| `xprobe` | 📦 single-file xprobe via uv's cached, pinned tool environment |
| `cli_args` | 📦 single-file CLI argument helpers via uv's cached tool environment |
| `ghi` | 📦 single-file gh_identity CLI via uv's cached tool environment |
| `markdown` | 📦 single-file Markdown stdio CLI via uv's cached tool environment |
| `ascii_artist` | 📦 single-file ASCII CLI via uv's cached tool environment |
| `yourself` | 🧾 bundled standard-library environment report; no separate file or registration |
| `calc` | 🧮 共通の数値計算（`calc 6 mul 7`、`calc --engine node 2 pow 10`） |
| `pyimp` | 📥 check if module is importable and where (pyimp numpy) |
| `pymods` | 📦 list top-level importable third-party modules |
| `pytest1` | 🧪 run unittest discover with plain python |
| `pyprof` | 🔬 cProfile a script sorted by cumulative time |
| `pyvenv` | 🧵 create .venv and print activate hint |
| `pycsv` | 📄 show head of csv as aligned table (pycsv file.csv [n=10]) |
| `pyhash` | 🔐 sha256 of a file |
| `pyepoch` | 🕰️ epoch seconds → iso (pyepoch 1700000000) or now |
| `pyclean` | 🧹 remove __pycache__ and .pyc under cwd |

### node

| 関数 | 説明 |
|---|---|
| `nv` | 🟩 node / npm / npx versions |
| `nls` | 📜 top-level installed packages |
| `nout` | 🕰️ 🌍 outdated packages |
| `nup` | ⬆️ 🌍 update deps within semver range |
| `nupall` | ⬆️ 🌍 bump every dep to latest (npm-check-updates) |
| `nr` | 🚀 npm run <script> (nr build) |
| `nscripts` | 📋 list package.json scripts |
| `nclean` | 🧹 remove node_modules + lock and reinstall |
| `naudit` | 🛡️ 🌍 audit and auto-fix |
| `nwhy` | 📦 why is a package installed (nwhy lodash) |
| `ninfo` | 🔢 🌍 show latest versions of a package (ninfo react) |
| `njson` | 📐 pretty-print json via node |
| `nhttp` | 🌐 serve current dir with node stdlib only (nhttp [port=3000]) |
| `nlts` | 🟩 🌍 install/use Node LTS via nvm or fnm if present |

### bun

| 関数 | 説明 |
|---|---|
| `bv` | 🥟 bun version |
| `bi` | 📦 🌍 bun install |
| `ba` | ➕ 🌍 bun add |
| `br` | 🚀 bun run <script\|file> |
| `bt` | 🧪 bun test |
| `bx` | 🚀 🌍 bunx (run package binary) |
| `bup` | ⬆️ 🌍 bun upgrade (self) + bun update (deps) |
| `bjson` | 📐 pretty-print json via bun |
| `bbuild` | 🏗️ bundle entry to dist/ (bbuild src/index.ts) |

### git

| 関数 | 説明 |
|---|---|
| `gs` | 🌿 short status + branch |
| `gl` | 📜 graph log (gl [n=20]) |
| `ga` | ➕ add all |
| `gc` | 💬 commit with message (gc "msg") |
| `gca` | 💬 amend without editing message |
| `gp` | 🚀 push current branch to origin (dial decides where), set upstream |
| `gpf` | 🚀 force-push to origin safely (with-lease) |
| `gpl` | ⬇️ pull from origin with rebase + autostash |
| `gcb` | 🌱 create and switch to branch (gcb feat/x) |
| `gco` | 🔀 switch branch (fzf picker when no arg) |
| `gbr` | 🌳 branches sorted by last commit |
| `gwip` | 📦 quick wip commit of everything |
| `gundo` | ↩️ undo last commit, keep changes |
| `gclean` | 🧹 delete local branches already merged into main/master |
| `gprune` | 🧹 fetch origin + prune + gc |
| `gdiff` | 🔍 diff of staged changes (gdiff) or working (gdiffw) |
| `gdiffw` | 🔍 diff of working tree |
| `gblame` | 🕵️ who touched a line range (gblame file 10,20) |
| `ggrep` | 🔎 grep tracked files (ggrep TODO) |
| `gcl` | 📥 🌍 shallow clone (gcl url [dir]) |
| `gtag` | 🏷️ list tags by date or create (gtag v1.0.0) |
| `gstat` | 📊 commit count per author |
| `groot` | 🔙 cd to repo root |
| `gstash` | 🧳 stash incl. untracked with message (gstash "msg") |
| `gsearch` | 🔍 search commit messages (gsearch fix) |
| `gchanged` | 🧾 files changed in last n commits (gchanged [n=1]) |

### gh

| 関数 | 説明 |
|---|---|
| `ghpr` | 🐙 🎛️ create PR (hubdial at offline..mirror, gh at github) (ghpr "title") |
| `ghprs` | 📋 🎛️ list open PRs (hubdial at offline..mirror) |
| `ghprv` | 👀 🌍 view current PR in browser |
| `ghprm` | ✅ 🌍 squash-merge PR and delete branch (ghprm [num]) |
| `ghco` | 🔀 🌍 checkout PR by number (ghco 42) |
| `ghis` | 🐛 🎛️ list open issues (hubdial at offline..mirror) |
| `ghisn` | 🐛 🎛️ new issue (ghisn "title" [label]) (hubdial at offline..mirror) |
| `ghweb` | 🌐 🎛️ open repo in browser (local forge at offline..mirror) |
| `ghruns` | 🏃 🌍 recent workflow runs |
| `ghwatch` | 👀 🌍 watch latest workflow run |
| `ghclone` | 📥 🌍 clone by owner/repo (ghclone owner/repo) |
| `ghrel` | 📦 🌍 list releases |

### files

| 関数 | 説明 |
|---|---|
| `mkcd` | 📁 mkdir -p and cd |
| `tmpd` | 🗂️ cd into a fresh temp dir |
| `ex` | 📦 extract any archive (ex file.tar.gz) |
| `tgz` | 📦 make dir.tar.gz from dir (tgz dir) |
| `zipd` | 📦 make dir.zip from dir (zipd dir) |
| `sz` | 📏 sizes of entries in cwd, largest first |
| `big` | 📏 largest files under cwd (big [n=20]) |
| `ff` | 🔎 find files by name fragment (ff main.py) |
| `rgg` | 🔎 ripgrep with hidden files, skip .git (rgg TODO) |
| `fzo` | 🔎 fuzzy-pick a file and open in $EDITOR |
| `fzcd` | 🔎 fuzzy-pick a directory and cd |
| `tre` | 🌳 tree view, depth n, no .git/node_modules (tre [2]) |
| `trash` | 🧹 move to ~/.trash instead of rm |
| `bak` | 🔁 copy file to file.bak.YYYYmmdd |
| `swap` | 🔁 swap two files |
| `cnt` | 🔢 count files per extension under cwd |
| `loc` | 📏 non-blank lines of code by extension (loc py js) |
| `watchf` | 👀 re-run a command when files change (watchf 'uvtest') |
| `head2` | 📄 first and last n lines (head2 file [5]) |
| `renx` | 🔁 rename extension in cwd (renx txt md) |
| `lowerf` | 🔡 lowercase filenames in cwd |
| `dos2unix1` | 🔄 strip CRLF in place (dos2unix1 file) |
| `touchp` | 📝 touch with parent dirs (touchp a/b/c.txt) |

### text

| 関数 | 説明 |
|---|---|
| `jsonf` | 📐 pretty-print json (jq → python fallback) |
| `jsonmin` | 📐 minify json |
| `y2j` | 🔁 🌍(first run) yaml → json via uvx pyyaml |
| `j2y` | 🔁 🌍(first run) json → yaml via uvx pyyaml |
| `t2j` | 🔁 toml → json (stdlib tomllib) |
| `wcl` | 🔢 count lines/words/chars |
| `uniqc` | 🔁 frequency table of stdin lines, sorted |
| `trimw` | ✂️ strip trailing whitespace in files (trimw *.py) |
| `lower` | 🔡 stdin → lowercase |
| `upper` | 🔡 stdin → uppercase |
| `b64` | 🔐 base64 encode (b64 text) or decode stdin (b64 -d) |
| `urlenc` | 🌐 url-encode string |
| `urldec` | 🌐 url-decode string |
| `sha` | 🔐 sha256 of files |
| `md5` | 🔐 md5 of files |
| `uuid` | 🆔 random uuid4 |
| `pw` | 🔑 random password (pw [len=24]) |
| `hexrand` | 🔑 random hex (hexrand [bytes=16]) |
| `cb` | 📋 copy stdin to clipboard (wl-copy/xclip/pbcopy) |
| `cbp` | 📋 paste clipboard |
| `col1` | 📊 print nth column (col1 3) |
| `csv2tsv` | 🔁 csv → tsv via python csv module |
| `mdtoc` | 📄 markdown table of contents from headings (mdtoc README.md) |
| `nums` | 🔢 sum / avg / min / max of numeric stdin |
| `datef` | 📅 today as YYYYMMDD (datef) or custom fmt (datef %F) |
| `ts` | ⏱️ current timestamp YYYYmmdd_HHMMSS (for file names) |
| `epoch` | 🕰️ unix epoch now |

### net

| 関数 | 説明 |
|---|---|
| `myip` | 🌐 🌍 public ip |
| `lanip` | 🏠 local ip(s) |
| `ports` | 🔌 listening tcp/udp ports |
| `kp` | 🔫 kill process listening on port (kp 3000) |
| `whoport` | 🔎 show process on port (whoport 8000) |
| `hh` | 📡 http headers only (hh url) |
| `hget` | 📡 GET and pretty json (hget url) |
| `hpost` | 📡 POST json (hpost url '{"a":1}') |
| `htime` | ⏱️ timing breakdown of a request |
| `dl` | ⬇️ 🌍 download keeping remote filename, resume |
| `dlpy` | ⬇️ 🌍 curl a single python file and run (dlpy url -- args) |
| `ping1` | 📶 🌍 ping 4 times |
| `dns` | 🔍 dns lookup (dns example.com) |
| `certinfo` | 🔐 🌍(or intranet) show tls cert dates of a host (certinfo example.com) |
| `waitport` | ⏳ wait until host:port is open (waitport localhost 5432) |

### system

| 関数 | 説明 |
|---|---|
| `up` | ⬆️ 🌍 apt update + upgrade + autoremove |
| `psg` | 🔎 grep processes (psg node) |
| `killall1` | 💀 kill by name pattern (killall1 node) |
| `mem` | 🧠 memory summary |
| `disk` | 💽 disk usage of mounts |
| `top1` | 🔥 top 10 by cpu |
| `topm` | 🔥 top 10 by memory |
| `path` | 🛤️ PATH entries one per line |
| `addpath` | 🛤️ prepend dir to PATH for this shell |
| `which1` | 🔎 resolve a command fully (which1 python3) |
| `envg` | 🧾 grep env vars (envg PATH) |
| `h` | 📜 grep shell history (h git) |
| `rl` | 🔁 reload shell rc |
| `tm` | ⏱️ time a command with wall clock (tm sleep 1) |
| `rep` | 🔁 repeat command n times (rep 3 echo hi) |
| `retry` | 🔁 retry until success, max n (retry 5 curl ...) |
| `notify` | 🔔 beep + message when a command ends (notify make) |
| `sysinfo` | 🧾 os, kernel, cpu, mem, uptime one-shot |
| `ver` | 🧰 versions of the usual toolchain |
| `cleanup` | 🧹 clear apt/npm/uv/pip caches |
| `alias1` | 📋 print a help line + function to paste into olnm.py (alias1 ll "ls -la") |

### airgap

| 関数 | 説明 |
|---|---|
| `uvexport` | 📦 pin lock to requirements.txt (hashes) for hand-off |
| `uvbundle` | 🎒 🌍 build wheels/ from lock for carrying into a closed network (run online side) |
| `uvoffline` | 🔌 sync from cache/wheels without network |
| `pipoffline` | 🔌 pip install from local wheels/ only |
| `nbundle` | 🎒 🌍 fill a portable npm cache dir (.npm-cache) for offline `nci` |
| `nci` | 🔌 npm ci strictly offline from .npm-cache |
| `npack` | 📦 pack current package into a tarball for transfer |
| `gbundle` | 🎒 git bundle of all refs for sneakernet (gbundle out.bundle) |
| `gunbundle` | 📥 clone from bundle (gunbundle repo.bundle dir) |
| `hashdir` | 🧾 write SHA256SUMS manifest of a dir (hashdir [dir=.]) |
| `verifydir` | ✅ verify dir against its SHA256SUMS |
| `dirdiff` | 🔍 which files differ between two trees (dirdiff a b) |
| `secrets` | 🕵️ scan tracked/current files for key-like strings before sharing |
| `redact` | 🫥 mask emails, ipv4, long hex/base64 tokens in stdin (for pasting logs) |
| `redactf` | 🫥 redact a file into file.redacted (redactf app.log) |
| `noenv` | 🧼 run a command with a scrubbed environment (noenv python3 x.py) |
| `sandbox` | 🧪 run python isolated (-I) in a throwaway dir, cwd files copied (sandbox x.py) |
| `proxyon` | 🛰️ export proxy vars from $CORP_PROXY for shell, npm, uv, git |
| `proxyoff` | 🛰️ unset proxy vars |
| `cabundle` | 🏛️ point python/node/curl/git/uv at a corporate CA bundle (cabundle /path/ca.pem) |
| `envreport` | 🧾 snapshot of toolchain + lock hashes → env-report.txt (evidence for reviews) |
| `licenses` | 🧾 list licenses of installed python packages (stdlib metadata only) |
| `pyfreeze` | 📋 pip freeze of current interpreter (uv env if present) |

### hub

| 関数 | 説明 |
|---|---|
| `hubdial` | 🏠 local GitHub-like forge via `nagoyaction forge` (hubdial install \| init \| up \| down \| status \| repo \| issue \| pr \| labels \| sync \| api) |
| `hubadd` | 📚 register cwd in the local forge (hubadd [--github owner/name]) |
| `hubsync` | 🔄 push every registered repo to bare / local / github (github at mirror and up) |
| `hubopen` | 🌐 open the local forge in a browser (or print its URL) |

### docker

| 関数 | 説明 |
|---|---|
| `dps` | 🐳 running containers, compact |
| `dpsa` | 🐳 all containers |
| `dsh` | 🐚 shell into container (dsh name) |
| `dlog` | 📜 follow logs (dlog name) |
| `dclean` | 🧹 prune stopped containers, dangling images, networks |
| `dnuke` | 🧹 prune everything incl. volumes (asks) |
| `dimg` | 📦 images sorted by size |
| `dcu` | 🧩 compose up detached, build |
| `dcd` | 🧩 compose down |
| `dcl` | 🧩 compose logs follow |
| `dstat` | 📊 live resource usage |

### tmux

| 関数 | 説明 |
|---|---|
| `ta` | 🧰 attach or create session (ta [name=main]) |
| `tl` | 📋 list sessions |
| `tk` | 💀 kill session (tk name) |

### memo

| 関数 | 説明 |
|---|---|
| `memo` | 📝 append a line to ~/memo.md with timestamp (memo "text") or show tail |
| `memog` | 🔎 grep ~/memo.md |
| `todo` | ✅ append todo (todo "x") / list open ones |
| `done1` | ✅ mark todo line n done (done1 3) |
| `jnl` | 📓 open today's journal ~/journal/YYYY-MM-DD.md |

### mise

| 関数 | 説明 |
|---|---|
| `miseuse` | ➕ 🌍 install tools and record project versions (miseuse node@26) |
| `miseglobal` | 🌐 🌍 install tools and set personal defaults (miseglobal node@26 bun@latest go@latest) |
| `miseinstall` | 📦 🌍 install configured or specified tools |
| `miseexec` | ▶️ 🌍 run in mise environment, installing missing tools as mise settings allow (miseexec node@26 -- node -v) |
| `miseoffline` | 🔌 run with automatic tool installation disabled; child command may still use network (miseoffline -- node -v) |
| `misels` | 📋 list mise tool versions and configuration sources |
| `miselock` | 🔒 🌍 create or refresh mise.lock versions, checksums and download URLs |
| `misedoctor` | 🩺 diagnose mise installation and configuration |

<!-- shell-catalog:end -->
