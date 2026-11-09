#!/usr/bin/env python3
"""olnm 🧷 OneLinearNumerousMemo — one Python file that hands bash/zsh a few hundred human-sized one-liners.

    curl -fsSL <RAW_URL>/olnm.py -o ~/.olnm.py && echo 'eval "$(python3 ~/.olnm.py init)"' >> ~/.bashrc   # or ~/.zshrc

    olnm            📖 list            olnm git        📖 one section
    olnm_like uvtets 🤔 closest names  olnm_dial 0..3  🎛️ shared dial with hubdial ($DIAL_FILE)

Rules: one function per line in SHELL below, `# <emoji> name: what it does` right above it = the help text.
       🌍 in a description = needs internet (stubbed at dial 0/1).  🎛️ = routed to hubdial at dial ≤2.
Target: Ubuntu 26.04 with Python / Node(LTS) / uv. Bun, fzf, fd, rg, jq, gh, docker optional.

Callable by name from Python (`import olnm; olnm.like("uvtets")`), shell (`python3 olnm.py call like '["uvtets"]'`)
and Node / Bun (`execFileSync("python3", ["olnm.py", "run", "pycalc", "2**10"])`).
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PY = Path(__file__).resolve()
DIAL_FILE = Path(os.environ.get("DIAL_FILE", Path.home() / ".config" / "dial"))
DIALS = {0: "🔌 offline", 1: "🏠 local", 2: "🔁 mirror", 3: "☁️ github"}
TOOLS = ("python3", "uv", "node", "npm", "npx", "bun", "git", "gh", "hubdial", "fzf", "fd", "rg", "jq", "curl", "docker", "tmux", "entr", "tree")
HELP = re.compile(r"^# (\S+) ([A-Za-z_0-9]+): (.*)$")
SECTION = re.compile(r"^# ─+ (\S+) (\S+) ─+$")

# ───────────────────────── 📖 meta (shell shims → this file) ─────────────────────────
META = r"""
# 📖 olnm: list one-liners (olnm git = one section)
olnm() { python3 "$OLNM_PY" ls "$@"; }
# 🔎 olnm_grep: search help text (olnm_grep json)
olnm_grep() { python3 "$OLNM_PY" grep "$@"; }
# 🤔 olnm_like: closest names to a typo or fragment (olnm_like uvtets)
olnm_like() { python3 "$OLNM_PY" like "$@"; }
# 🗂️ olnm_sections: section names
olnm_sections() { python3 "$OLNM_PY" sections; }
# 🔒 olnm_offline: only one-liners that work without internet
olnm_offline() { python3 "$OLNM_PY" ls --offline "$@"; }
# 🌍 olnm_net: names that need internet
olnm_net() { python3 "$OLNM_PY" net; }
# 🎛️ olnm_dial: show / set shared dial 0🔌 1🏠 2🔁 3☁️ (also drives hubdial)
olnm_dial() { python3 "$OLNM_PY" dial "$@" && olnm_reload >/dev/null; }
# 🩺 olnm_doctor: which tools are present
olnm_doctor() { python3 "$OLNM_PY" doctor; }
# 🔄 olnm_reload: re-evaluate after edits or dial change
olnm_reload() { eval "$(python3 "$OLNM_PY" init)" && echo "🔄 $OLNM_PY"; }
# 📝 olnm_edit: open olnm.py in $EDITOR
olnm_edit() { "${EDITOR:-vi}" "$OLNM_PY" && olnm_reload; }
# ⬇️ olnm_update: 🌍 re-download olnm.py from $OLNM_URL and reload
olnm_update() { [ -n "$OLNM_URL" ] || { echo "set OLNM_URL"; return 1; }; curl -fsSL "$OLNM_URL" -o "$OLNM_PY.new" && python3 "$OLNM_PY.new" ls >/dev/null && mv "$OLNM_PY.new" "$OLNM_PY" && olnm_reload; }
# 🔢 olnm_steps: non-blank lines of olnm.py
olnm_steps() { grep -cve '^\s*$' "$OLNM_PY"; }
_olnm_d() { cat "$DIAL_FILE" 2>/dev/null || echo 3; }
_olnm_hub() { [ "$(_olnm_d)" -le 2 ] && command -v hubdial >/dev/null; }
_olnm_cnf() { python3 "$OLNM_PY" like "$1" --hint >&2; return 127; }
"""

SHELL = r"""
# ───────────────────────── 🐍 uv ─────────────────────────
# 🧪 uvtest: run unittest discover (locked env)
uvtest() { uv run --locked python -m unittest discover "$@"; }
# ✅ uvcheck: ruff check then unittest
uvcheck() { uv run --locked ruff check . && uvtest; }
# 🌳 uvdeps: dependency tree + pip check
uvdeps() { uv tree && uv pip check; }
# ⬆️ uvup: 🌍 upgrade one package in lock and sync (uvup requests)
uvup() { uv lock --upgrade-package "$1" && uv sync; }
# ⬆️ uvupall: 🌍 upgrade every locked package and sync
uvupall() { uv lock --upgrade && uv sync; }
# 🆕 uvinit: new project in current dir (uvinit [name])
uvinit() { uv init ${1:+--name "$1"} && uv sync; }
# ➕ uvadd: 🌍 add package(s) and sync
uvadd() { uv add "$@" && uv sync; }
# ➕ uvdev: 🌍 add dev package(s)
uvdev() { uv add --dev "$@"; }
# 🐍 uvpy: python REPL inside locked env
uvpy() { uv run --locked python "$@"; }
# 🎨 uvfmt: 🌍(first run) ruff format + ruff fix
uvfmt() { uvx ruff format . && uvx ruff check --fix .; }
# 🧹 uvclean: remove .venv, caches, build dirs
uvclean() { rm -rf .venv .ruff_cache .pytest_cache .mypy_cache build dist ./*.egg-info; find . -name __pycache__ -type d -prune -exec rm -rf {} +; }
# 📦 uvbuild: build sdist+wheel into dist/
uvbuild() { uv build "$@"; }
# 🔁 uvresync: 🌍 delete lock and resolve from scratch
uvresync() { rm -f uv.lock && uv lock && uv sync; }
# 🐍 uvpys: list / 🌍 install pythons (uvpys 3.13)
uvpys() { [ -n "$1" ] && uv python install "$1" || uv python list --only-installed; }

# ───────────────────────── 🐍 python ─────────────────────────
# 🐍 pyv: python version + path
pyv() { python3 --version && command -v python3; }
# 🌐 pyhttp: serve current dir over http (pyhttp [port=8000])
pyhttp() { python3 -m http.server "${1:-8000}"; }
# 📐 pyjson: pretty-print json from file or stdin
pyjson() { python3 -m json.tool "$@"; }
# 🧮 pycalc: evaluate math expression (pycalc '2**10')
pycalc() { python3 -c "from math import *; print($*)"; }
# 📥 pyimp: check if module is importable and where (pyimp numpy)
pyimp() { python3 -c "import importlib,sys; m=importlib.import_module(sys.argv[1]); print(m.__name__, getattr(m,'__version__','?'), m.__file__)" "$1"; }
# 📦 pymods: list top-level importable third-party modules
pymods() { python3 -c "import pkgutil; print('\n'.join(sorted(m.name for m in pkgutil.iter_modules() if not m.name.startswith('_'))))"; }
# 🧪 pytest1: run unittest discover with plain python
pytest1() { python3 -m unittest discover "$@"; }
# 🔬 pyprof: cProfile a script sorted by cumulative time
pyprof() { python3 -m cProfile -s cumulative "$@" | head -40; }
# 🧵 pyvenv: create .venv and print activate hint
pyvenv() { python3 -m venv .venv && echo 'source .venv/bin/activate'; }
# 📄 pycsv: show head of csv as aligned table (pycsv file.csv [n=10])
pycsv() { python3 -c "import csv,sys; r=csv.reader(open(sys.argv[1])); [print(' | '.join(x)) for _,x in zip(range(int(sys.argv[2])), r)]" "$1" "${2:-10}"; }
# 🔐 pyhash: sha256 of a file
pyhash() { python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }
# 🕰️ pyepoch: epoch seconds → iso (pyepoch 1700000000) or now
pyepoch() { python3 -c "import sys,datetime as d; t=float(sys.argv[1]) if len(sys.argv)>1 else d.datetime.now().timestamp(); print(d.datetime.fromtimestamp(t).isoformat())" "$@"; }
# 🧹 pyclean: remove __pycache__ and .pyc under cwd
pyclean() { find . -name '__pycache__' -type d -prune -exec rm -rf {} + ; find . -name '*.pyc' -delete; }

# ───────────────────────── 🟩 node ─────────────────────────
# 🟩 nv: node / npm / npx versions
nv() { node -v && npm -v && command -v node; }
# 📜 nls: top-level installed packages
nls() { npm ls --depth=0 "$@"; }
# 🕰️ nout: 🌍 outdated packages
nout() { npm outdated "$@"; }
# ⬆️ nup: 🌍 update deps within semver range
nup() { npm update "$@"; }
# ⬆️ nupall: 🌍 bump every dep to latest (npm-check-updates)
nupall() { npx -y npm-check-updates -u && npm install; }
# 🚀 nr: npm run <script> (nr build)
nr() { npm run "$@"; }
# 📋 nscripts: list package.json scripts
nscripts() { node -e 'const s=require("./package.json").scripts||{};for(const k in s)console.log(k.padEnd(16),s[k])'; }
# 🧹 nclean: remove node_modules + lock and reinstall
nclean() { rm -rf node_modules package-lock.json && npm install; }
# 🛡️ naudit: 🌍 audit and auto-fix
naudit() { npm audit fix "$@"; }
# 📦 nwhy: why is a package installed (nwhy lodash)
nwhy() { npm explain "$1"; }
# 🔢 ninfo: 🌍 show latest versions of a package (ninfo react)
ninfo() { npm view "$1" version dist-tags.latest time.modified; }
# 📐 njson: pretty-print json via node
njson() { node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>console.log(JSON.stringify(JSON.parse(d),null,2)))'; }
# 🧮 ncalc: evaluate JS expression (ncalc '2**10')
ncalc() { node -p "$*"; }
# 🌐 nhttp: serve current dir with node stdlib only (nhttp [port=3000])
nhttp() { node -e 'const h=require("http"),f=require("fs"),p=require("path");h.createServer((q,r)=>{const u=decodeURIComponent(q.url.split("?")[0]);let x=p.join(process.cwd(),u);if(f.existsSync(x)&&f.statSync(x).isDirectory())x=p.join(x,"index.html");f.readFile(x,(e,d)=>{r.writeHead(e?404:200);r.end(e?"404":d)})}).listen(+process.argv[1],()=>console.log("http://localhost:"+process.argv[1]))' "${1:-3000}"; }
# 🟩 nlts: 🌍 install/use Node LTS via nvm or fnm if present
nlts() { command -v fnm >/dev/null && fnm install --lts && fnm use lts-latest || { [ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" && nvm install --lts && nvm use --lts; } || echo "need fnm or nvm"; }

# ───────────────────────── 🥟 bun ─────────────────────────
# 🥟 bv: bun version
bv() { bun -v; }
# 📦 bi: 🌍 bun install
bi() { bun install "$@"; }
# ➕ ba: 🌍 bun add
ba() { bun add "$@"; }
# 🚀 br: bun run <script|file>
br() { bun run "$@"; }
# 🧪 bt: bun test
bt() { bun test "$@"; }
# 🚀 bx: 🌍 bunx (run package binary)
bx() { bunx "$@"; }
# ⬆️ bup: 🌍 bun upgrade (self) + bun update (deps)
bup() { bun upgrade && bun update; }
# 📐 bjson: pretty-print json via bun
bjson() { bun -e 'const d=await Bun.stdin.text();console.log(JSON.stringify(JSON.parse(d),null,2))'; }
# 🏗️ bbuild: bundle entry to dist/ (bbuild src/index.ts)
bbuild() { bun build "$@" --outdir dist; }

# ───────────────────────── 🌿 git ─────────────────────────
# 🌿 gs: short status + branch
gs() { git status -sb "$@"; }
# 📜 gl: graph log (gl [n=20])
gl() { git log --graph --oneline --decorate --all -n "${1:-20}"; }
# ➕ ga: add all
ga() { git add -A "$@"; }
# 💬 gc: commit with message (gc "msg")
gc() { git commit -m "$*"; }
# 💬 gca: amend without editing message
gca() { git commit --amend --no-edit; }
# 🚀 gp: push current branch to origin (dial decides where), set upstream
gp() { git push -u origin "$(git branch --show-current)" "$@"; }
# 🚀 gpf: force-push to origin safely (with-lease)
gpf() { git push --force-with-lease "$@"; }
# ⬇️ gpl: pull from origin with rebase + autostash
gpl() { git pull --rebase --autostash "$@"; }
# 🌱 gcb: create and switch to branch (gcb feat/x)
gcb() { git switch -c "$1"; }
# 🔀 gco: switch branch (fzf picker when no arg)
gco() { [ -n "$1" ] && git switch "$1" || git switch "$(git branch --format='%(refname:short)' | fzf)"; }
# 🌳 gbr: branches sorted by last commit
gbr() { git branch --sort=-committerdate --format='%(committerdate:short) %(refname:short) %(subject)' "$@"; }
# 📦 gwip: quick wip commit of everything
gwip() { git add -A && git commit -m "wip: $(date +%F_%T)"; }
# ↩️ gundo: undo last commit, keep changes
gundo() { git reset --soft HEAD~1; }
# 🧹 gclean: delete local branches already merged into main/master
gclean() { git branch --merged | grep -vE '^\*|main|master' | xargs -r git branch -d; }
# 🧹 gprune: fetch origin + prune + gc
gprune() { git fetch -p && git gc --auto; }
# 🔍 gdiff: diff of staged changes (gdiff) or working (gdiffw)
gdiff() { git diff --cached "$@"; }
# 🔍 gdiffw: diff of working tree
gdiffw() { git diff "$@"; }
# 🕵️ gblame: who touched a line range (gblame file 10,20)
gblame() { git blame -L "${2:-1,20}" -- "$1"; }
# 🔎 ggrep: grep tracked files (ggrep TODO)
ggrep() { git grep -n -- "$@"; }
# 📥 gcl: 🌍 shallow clone (gcl url [dir])
gcl() { git clone --depth 1 "$@"; }
# 🏷️ gtag: list tags by date or create (gtag v1.0.0)
gtag() { [ -n "$1" ] && git tag -a "$1" -m "$1" || git tag --sort=-creatordate | head -20; }
# 📊 gstat: commit count per author
gstat() { git shortlog -sn --all "$@"; }
# 🔙 groot: cd to repo root
groot() { cd "$(git rev-parse --show-toplevel)" || return; }
# 🧳 gstash: stash incl. untracked with message (gstash "msg")
gstash() { git stash push -u -m "${*:-stash $(date +%T)}"; }
# 🔍 gsearch: search commit messages (gsearch fix)
gsearch() { git log --oneline --all -i --grep="$*"; }
# 🧾 gchanged: files changed in last n commits (gchanged [n=1])
gchanged() { git diff --name-only "HEAD~${1:-1}" HEAD; }

# ───────────────────────── 🐙 gh ─────────────────────────
# 🐙 ghpr: 🎛️ create PR (hubdial at dial ≤2, gh at 3) (ghpr "title")
ghpr() { _olnm_hub && { hubdial pr new "${*:-$(git log -1 --format=%s)}"; return; }; [ -n "$1" ] && gh pr create --fill --title "$*" || gh pr create --fill; }
# 📋 ghprs: 🎛️ list open PRs (hubdial at dial ≤2)
ghprs() { _olnm_hub && { hubdial pr ls; return; }; gh pr list "$@"; }
# 👀 ghprv: 🌍 view current PR in browser
ghprv() { gh pr view --web "$@"; }
# ✅ ghprm: 🌍 squash-merge PR and delete branch (ghprm [num])
ghprm() { gh pr merge "$@" --squash --delete-branch; }
# 🔀 ghco: 🌍 checkout PR by number (ghco 42)
ghco() { gh pr checkout "$1"; }
# 🐛 ghis: 🎛️ list open issues (hubdial at dial ≤2)
ghis() { _olnm_hub && { hubdial issue ls; return; }; gh issue list "$@"; }
# 🐛 ghisn: 🎛️ new issue (ghisn "title" [label]) (hubdial at dial ≤2)
ghisn() { _olnm_hub && { hubdial issue new "$1" ${2:+--label "$2"}; return; }; gh issue create --title "$1" --body "" ${2:+--label "$2"}; }
# 🌐 ghweb: 🌍 open repo in browser
ghweb() { gh repo view --web; }
# 🏃 ghruns: 🌍 recent workflow runs
ghruns() { gh run list --limit "${1:-10}"; }
# 👀 ghwatch: 🌍 watch latest workflow run
ghwatch() { gh run watch "$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')"; }
# 📥 ghclone: 🌍 clone by owner/repo (ghclone owner/repo)
ghclone() { gh repo clone "$@"; }
# 📦 ghrel: 🌍 list releases
ghrel() { gh release list "$@"; }

# ───────────────────────── 📁 files ─────────────────────────
# 📁 mkcd: mkdir -p and cd
mkcd() { mkdir -p "$1" && cd "$1" || return; }
# 🗂️ tmpd: cd into a fresh temp dir
tmpd() { cd "$(mktemp -d)" || return; }
# 📦 ex: extract any archive (ex file.tar.gz)
ex() { case "$1" in *.tar.gz|*.tgz) tar xzf "$1";; *.tar.bz2|*.tbz2) tar xjf "$1";; *.tar.xz|*.txz) tar xJf "$1";; *.tar) tar xf "$1";; *.zip) unzip -q "$1";; *.gz) gunzip -k "$1";; *.bz2) bunzip2 -k "$1";; *.xz) unxz -k "$1";; *.7z) 7z x "$1";; *.rar) unrar x "$1";; *) echo "❓ $1";; esac; }
# 📦 tgz: make dir.tar.gz from dir (tgz dir)
tgz() { tar czf "${1%/}.tar.gz" "${1%/}"; }
# 📦 zipd: make dir.zip from dir (zipd dir)
zipd() { zip -qr "${1%/}.zip" "${1%/}"; }
# 📏 sz: sizes of entries in cwd, largest first
sz() { du -sh -- "${@:-.}"/* 2>/dev/null | sort -rh | head -${N:-30}; }
# 📏 big: largest files under cwd (big [n=20])
big() { find . -type f -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -"${1:-20}" | awk '{printf "%8.1fM  %s\n",$1/1048576,$2}'; }
# 🔎 ff: find files by name fragment (ff main.py)
ff() { command -v fd >/dev/null && fd -H "$@" || find . -iname "*$1*" -not -path '*/.git/*'; }
# 🔎 rgg: ripgrep with hidden files, skip .git (rgg TODO)
rgg() { rg -n --hidden --glob '!.git' "$@"; }
# 🔎 fzo: fuzzy-pick a file and open in $EDITOR
fzo() { local f; f="$(fzf --preview 'head -100 {}')" && "${EDITOR:-vi}" "$f"; }
# 🔎 fzcd: fuzzy-pick a directory and cd
fzcd() { local d; d="$( (command -v fd >/dev/null && fd -t d -H -E .git || find . -type d -not -path '*/.git/*') | fzf)" && cd "$d" || return; }
# 🌳 tre: tree view, depth n, no .git/node_modules (tre [2])
tre() { command -v tree >/dev/null && tree -a -L "${1:-2}" -I '.git|node_modules|.venv|__pycache__' || find . -maxdepth "${1:-2}" -not -path '*/.git*' -not -path '*/node_modules*' | sort; }
# 🧹 trash: move to ~/.trash instead of rm
trash() { mkdir -p ~/.trash && mv -- "$@" ~/.trash/; }
# 🔁 bak: copy file to file.bak.YYYYmmdd
bak() { cp -a -- "$1" "$1.bak.$(date +%Y%m%d)"; }
# 🔁 swap: swap two files
swap() { local t; t="$(mktemp)" && mv -- "$1" "$t" && mv -- "$2" "$1" && mv -- "$t" "$2"; }
# 🔢 cnt: count files per extension under cwd
cnt() { find . -type f -not -path '*/.git/*' | sed -n 's/.*\.\([a-zA-Z0-9]*\)$/\1/p' | sort | uniq -c | sort -rn | head -"${1:-20}"; }
# 📏 loc: non-blank lines of code by extension (loc py js)
loc() { for e in "${@:-py}"; do printf '%-6s %s\n' "$e" "$(find . -name "*.$e" -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -exec cat {} + | grep -cve '^\s*$')"; done; }
# 👀 watchf: re-run a command when files change (watchf 'uvtest')
watchf() { command -v entr >/dev/null && { find . -type f -not -path '*/.git/*' | entr -c sh -c "$*"; } || { while :; do clear; sh -c "$*"; sleep "${WATCH_SEC:-3}"; done; }; }
# 📄 head2: first and last n lines (head2 file [5])
head2() { head -"${2:-5}" "$1"; echo '…'; tail -"${2:-5}" "$1"; }
# 🔁 renx: rename extension in cwd (renx txt md)
renx() { for f in *."$1"; do [ -e "$f" ] && mv -- "$f" "${f%."$1"}.$2"; done; }
# 🔡 lowerf: lowercase filenames in cwd
lowerf() { for f in *; do l="$(printf '%s' "$f" | tr '[:upper:]' '[:lower:]')"; [ "$f" != "$l" ] && mv -- "$f" "$l"; done; }
# 🔄 dos2unix1: strip CRLF in place (dos2unix1 file)
dos2unix1() { sed -i 's/\r$//' "$@"; }
# 📝 touchp: touch with parent dirs (touchp a/b/c.txt)
touchp() { mkdir -p "$(dirname "$1")" && touch "$1"; }

# ───────────────────────── 🔤 text ─────────────────────────
# 📐 jsonf: pretty-print json (jq → python fallback)
jsonf() { command -v jq >/dev/null && jq . "$@" || python3 -m json.tool "$@"; }
# 📐 jsonmin: minify json
jsonmin() { command -v jq >/dev/null && jq -c . "$@" || python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin),separators=(",",":")))'; }
# 🔁 y2j: 🌍(first run) yaml → json via uvx pyyaml
y2j() { uvx --from pyyaml python -c 'import sys,yaml,json;print(json.dumps(yaml.safe_load(sys.stdin),indent=2,ensure_ascii=False))' < "${1:-/dev/stdin}"; }
# 🔁 j2y: 🌍(first run) json → yaml via uvx pyyaml
j2y() { uvx --from pyyaml python -c 'import sys,yaml,json;print(yaml.safe_dump(json.load(sys.stdin),allow_unicode=True,sort_keys=False))' < "${1:-/dev/stdin}"; }
# 🔁 t2j: toml → json (stdlib tomllib)
t2j() { python3 -c 'import sys,tomllib,json;print(json.dumps(tomllib.loads(sys.stdin.read()),indent=2,ensure_ascii=False))' < "${1:-/dev/stdin}"; }
# 🔢 wcl: count lines/words/chars
wcl() { wc -lwc "$@"; }
# 🔁 uniqc: frequency table of stdin lines, sorted
uniqc() { sort | uniq -c | sort -rn; }
# ✂️ trimw: strip trailing whitespace in files (trimw *.py)
trimw() { sed -i 's/[ \t]*$//' "$@"; }
# 🔡 lower: stdin → lowercase
lower() { tr '[:upper:]' '[:lower:]'; }
# 🔡 upper: stdin → uppercase
upper() { tr '[:lower:]' '[:upper:]'; }
# 🔐 b64: base64 encode (b64 text) or decode stdin (b64 -d)
b64() { [ "$1" = -d ] && base64 -d || printf '%s' "$*" | base64; }
# 🌐 urlenc: url-encode string
urlenc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$*"; }
# 🌐 urldec: url-decode string
urldec() { python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))' "$*"; }
# 🔐 sha: sha256 of files
sha() { sha256sum "$@"; }
# 🔐 md5: md5 of files
md5() { md5sum "$@"; }
# 🆔 uuid: random uuid4
uuid() { python3 -c 'import uuid;print(uuid.uuid4())'; }
# 🔑 pw: random password (pw [len=24])
pw() { python3 -c 'import secrets,string,sys;a=string.ascii_letters+string.digits+"-_";print("".join(secrets.choice(a) for _ in range(int(sys.argv[1]))))' "${1:-24}"; }
# 🔑 hexrand: random hex (hexrand [bytes=16])
hexrand() { python3 -c 'import secrets,sys;print(secrets.token_hex(int(sys.argv[1])))' "${1:-16}"; }
# 📋 cb: copy stdin to clipboard (wl-copy/xclip/pbcopy)
cb() { command -v wl-copy >/dev/null && wl-copy || command -v xclip >/dev/null && xclip -sel clip || command -v pbcopy >/dev/null && pbcopy || cat > /tmp/clip.txt; }
# 📋 cbp: paste clipboard
cbp() { command -v wl-paste >/dev/null && wl-paste || command -v xclip >/dev/null && xclip -sel clip -o || command -v pbpaste >/dev/null && pbpaste || cat /tmp/clip.txt; }
# 📊 col1: print nth column (col1 3)
col1() { awk -v n="${1:-1}" '{print $n}'; }
# 🔁 csv2tsv: csv → tsv via python csv module
csv2tsv() { python3 -c 'import csv,sys;w=csv.writer(sys.stdout,delimiter="\t");[w.writerow(r) for r in csv.reader(sys.stdin)]'; }
# 📄 mdtoc: markdown table of contents from headings (mdtoc README.md)
mdtoc() { grep -E '^#{1,6} ' "$1" | sed -E 's/^(#+) (.*)/\1|\2/' | awk -F'|' '{ind=length($1)-1; t=$2; a=tolower(t); gsub(/[^a-z0-9 -]/,"",a); gsub(/ /,"-",a); printf "%*s- [%s](#%s)\n",ind*2,"",t,a}'; }
# 🔢 nums: sum / avg / min / max of numeric stdin
nums() { awk '{s+=$1; if(NR==1||$1<mn)mn=$1; if(NR==1||$1>mx)mx=$1} END{if(NR)printf "n=%d sum=%g avg=%g min=%g max=%g\n",NR,s,s/NR,mn,mx}'; }
# 📅 datef: today as YYYYMMDD (datef) or custom fmt (datef %F)
datef() { date +"${1:-%Y%m%d}"; }
# ⏱️ ts: current timestamp YYYYmmdd_HHMMSS (for file names)
ts() { date +%Y%m%d_%H%M%S; }
# 🕰️ epoch: unix epoch now
epoch() { date +%s; }

# ───────────────────────── 🌐 net ─────────────────────────
# 🌐 myip: 🌍 public ip
myip() { curl -fsS https://ifconfig.me; echo; }
# 🏠 lanip: local ip(s)
lanip() { hostname -I 2>/dev/null || ip -4 -o addr show | awk '{print $4}'; }
# 🔌 ports: listening tcp/udp ports
ports() { ss -tulpn 2>/dev/null || netstat -tulpn; }
# 🔫 kp: kill process listening on port (kp 3000)
kp() { local p; p="$(ss -ltnp "sport = :$1" 2>/dev/null | awk -F'pid=' 'NR>1{split($2,a,",");print a[1]}' | sort -u)"; [ -n "$p" ] && kill $p && echo "💀 $p" || echo "nothing on :$1"; }
# 🔎 whoport: show process on port (whoport 8000)
whoport() { ss -ltnp "sport = :$1"; }
# 📡 hh: http headers only (hh url)
hh() { curl -fsSI "$@"; }
# 📡 hget: GET and pretty json (hget url)
hget() { curl -fsS "$@" | jsonf; }
# 📡 hpost: POST json (hpost url '{"a":1}')
hpost() { curl -fsS -H 'Content-Type: application/json' -d "$2" "$1" | jsonf; }
# ⏱️ htime: timing breakdown of a request
htime() { curl -fsS -o /dev/null -w 'dns %{time_namelookup}s  connect %{time_connect}s  tls %{time_appconnect}s  ttfb %{time_starttransfer}s  total %{time_total}s  code %{http_code}\n' "$@"; }
# ⬇️ dl: 🌍 download keeping remote filename, resume
dl() { curl -fL -O -C - "$@"; }
# ⬇️ dlpy: 🌍 curl a single python file and run (dlpy url -- args)
dlpy() { local u="$1"; shift; curl -fsSL "$u" | python3 -I - "$@"; }
# 📶 ping1: 🌍 ping 4 times
ping1() { ping -c 4 "${1:-1.1.1.1}"; }
# 🔍 dns: dns lookup (dns example.com)
dns() { command -v dig >/dev/null && dig +short "$@" || getent hosts "$1"; }
# 🔐 certinfo: 🌍(or intranet) show tls cert dates of a host (certinfo example.com)
certinfo() { echo | openssl s_client -servername "$1" -connect "$1:${2:-443}" 2>/dev/null | openssl x509 -noout -dates -subject; }
# ⏳ waitport: wait until host:port is open (waitport localhost 5432)
waitport() { until (echo > "/dev/tcp/$1/$2") 2>/dev/null; do sleep 1; done; echo "✅ $1:$2"; }

# ───────────────────────── 🖥️ system ─────────────────────────
# ⬆️ up: 🌍 apt update + upgrade + autoremove
up() { sudo apt update && sudo apt -y upgrade && sudo apt -y autoremove; }
# 🔎 psg: grep processes (psg node)
psg() { ps aux | grep -i -- "[${1:0:1}]${1:1}"; }
# 💀 killall1: kill by name pattern (killall1 node)
killall1() { pkill -f -- "$1" && echo "💀 $1"; }
# 🧠 mem: memory summary
mem() { free -h; }
# 💽 disk: disk usage of mounts
disk() { df -h -x tmpfs -x devtmpfs -x squashfs; }
# 🔥 top1: top 10 by cpu
top1() { ps -eo pid,pcpu,pmem,comm --sort=-pcpu | head -11; }
# 🔥 topm: top 10 by memory
topm() { ps -eo pid,pcpu,pmem,comm --sort=-pmem | head -11; }
# 🛤️ path: PATH entries one per line
path() { printf '%s\n' "${PATH//:/$'\n'}"; }
# 🛤️ addpath: prepend dir to PATH for this shell
addpath() { export PATH="$(realpath "$1"):$PATH"; }
# 🔎 which1: resolve a command fully (which1 python3)
which1() { type -a "$1" 2>/dev/null; command -v "$1" | xargs -r realpath; }
# 🧾 envg: grep env vars (envg PATH)
envg() { env | grep -i -- "$1" | sort; }
# 📜 h: grep shell history (h git)
h() { history | grep -i -- "$*" | tail -"${N:-30}"; }
# 🔁 rl: reload shell rc
rl() { if [ -n "$ZSH_VERSION" ]; then . ~/.zshrc; else . ~/.bashrc; fi; }
# ⏱️ tm: time a command with wall clock (tm sleep 1)
tm() { local s=$SECONDS; "$@"; echo "⏱️ $((SECONDS-s))s"; }
# 🔁 rep: repeat command n times (rep 3 echo hi)
rep() { local n=$1 i; shift; for i in $(seq "$n"); do "$@"; done; }
# 🔁 retry: retry until success, max n (retry 5 curl ...)
retry() { local n=$1 i=0; shift; until "$@"; do i=$((i+1)); [ "$i" -ge "$n" ] && return 1; sleep "${RETRY_SEC:-2}"; done; }
# 🔔 notify: beep + message when a command ends (notify make)
notify() { "$@"; local r=$?; printf '\a%s %s\n' "$([ $r = 0 ] && echo ✅ || echo ❌)" "$*"; return $r; }
# 🧾 sysinfo: os, kernel, cpu, mem, uptime one-shot
sysinfo() { . /etc/os-release 2>/dev/null; echo "🖥️ ${PRETTY_NAME:-?} | $(uname -r) | $(nproc) cpu | $(free -h | awk '/Mem/{print $2}') | $(uptime -p 2>/dev/null)"; }
# 🧰 ver: versions of the usual toolchain
ver() { for t in python3 uv node npm bun git gh; do command -v "$t" >/dev/null && printf '%-8s %s\n' "$t" "$("$t" --version 2>&1 | head -1)"; done; }
# 🧹 cleanup: clear apt/npm/uv/pip caches
cleanup() { sudo apt clean; npm cache clean --force 2>/dev/null; uv cache clean 2>/dev/null; pip cache purge 2>/dev/null; echo "🧹 done"; }
# 📋 alias1: print a help line + function to paste into olnm.py (alias1 ll "ls -la")
alias1() { printf '# ⭐ %s: %s\n%s() { %s "$@"; }\n' "$1" "$2" "$1" "$2"; }

# ───────────────────────── 🔒 airgap ─────────────────────────
# 📦 uvexport: pin lock to requirements.txt (hashes) for hand-off
uvexport() { uv export --frozen --no-dev --format requirements-txt -o requirements.txt && wc -l requirements.txt; }
# 🎒 uvbundle: 🌍 build wheels/ from lock for carrying into a closed network (run online side)
uvbundle() { uvexport && mkdir -p wheels && uv pip download -r requirements.txt -d wheels 2>/dev/null || python3 -m pip download -r requirements.txt -d wheels; ls wheels | wc -l; }
# 🔌 uvoffline: sync from cache/wheels without network
uvoffline() { [ -d wheels ] && uv pip install --no-index --find-links wheels -r requirements.txt || uv sync --offline; }
# 🔌 pipoffline: pip install from local wheels/ only
pipoffline() { python3 -m pip install --no-index --find-links "${1:-wheels}" -r "${2:-requirements.txt}"; }
# 🎒 nbundle: 🌍 fill a portable npm cache dir (.npm-cache) for offline `nci`
nbundle() { npm ci --cache .npm-cache --prefer-online && du -sh .npm-cache; }
# 🔌 nci: npm ci strictly offline from .npm-cache
nci() { npm ci --offline --cache .npm-cache; }
# 📦 npack: pack current package into a tarball for transfer
npack() { npm pack --pack-destination "${1:-.}"; }
# 🎒 gbundle: git bundle of all refs for sneakernet (gbundle out.bundle)
gbundle() { git bundle create "${1:-repo.bundle}" --all && git bundle verify "${1:-repo.bundle}"; }
# 📥 gunbundle: clone from bundle (gunbundle repo.bundle dir)
gunbundle() { git clone "$1" "${2:-${1%.bundle}}"; }
# 🧾 hashdir: write SHA256SUMS manifest of a dir (hashdir [dir=.])
hashdir() { (cd "${1:-.}" && find . -type f -not -path './.git/*' -not -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS && wc -l SHA256SUMS); }
# ✅ verifydir: verify dir against its SHA256SUMS
verifydir() { (cd "${1:-.}" && sha256sum --quiet -c SHA256SUMS && echo "✅ all match"); }
# 🔍 dirdiff: which files differ between two trees (dirdiff a b)
dirdiff() { diff -rq -x .git -x node_modules -x .venv "$1" "$2"; }
# 🕵️ secrets: scan tracked/current files for key-like strings before sharing
secrets() { grep -rnIE --exclude-dir={.git,node_modules,.venv} -e 'AKIA[0-9A-Z]{16}' -e 'sk-[A-Za-z0-9]{20,}' -e 'ghp_[A-Za-z0-9]{36}' -e '-----BEGIN [A-Z ]*PRIVATE KEY' -e '(password|passwd|secret|token|api[_-]?key)["'"'"']?\s*[:=]\s*["'"'"']?[^\s"'"'"']{6,}' "${@:-.}" || echo "✅ none"; }
# 🫥 redact: mask emails, ipv4, long hex/base64 tokens in stdin (for pasting logs)
redact() { sed -E -e 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/<email>/g' -e 's/\b([0-9]{1,3}\.){3}[0-9]{1,3}\b/<ip>/g' -e 's/\b[A-Fa-f0-9]{32,}\b/<hex>/g' -e 's/\b[A-Za-z0-9+\/_-]{40,}={0,2}/<token>/g'; }
# 🫥 redactf: redact a file into file.redacted (redactf app.log)
redactf() { redact < "$1" > "$1.redacted" && echo "$1.redacted"; }
# 🧼 noenv: run a command with a scrubbed environment (noenv python3 x.py)
noenv() { env -i PATH="$PATH" HOME="$HOME" LANG="${LANG:-C.UTF-8}" TERM="${TERM:-dumb}" "$@"; }
# 🧪 sandbox: run python isolated (-I) in a throwaway dir, cwd files copied (sandbox x.py)
sandbox() { local d; d="$(mktemp -d)" && cp -r . "$d"/ && (cd "$d" && python3 -I "$@"); echo "📁 $d"; }
# 🛰️ proxyon: export proxy vars from $CORP_PROXY for shell, npm, uv, git
proxyon() { [ -n "$CORP_PROXY" ] || { echo "set CORP_PROXY=http://host:port"; return 1; }; export http_proxy="$CORP_PROXY" https_proxy="$CORP_PROXY" HTTP_PROXY="$CORP_PROXY" HTTPS_PROXY="$CORP_PROXY" NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,.local}"; echo "🛰️ $CORP_PROXY"; }
# 🛰️ proxyoff: unset proxy vars
proxyoff() { unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; echo "🛰️ off"; }
# 🏛️ cabundle: point python/node/curl/git/uv at a corporate CA bundle (cabundle /path/ca.pem)
cabundle() { [ -f "$1" ] || { echo "file?"; return 1; }; export SSL_CERT_FILE="$1" REQUESTS_CA_BUNDLE="$1" CURL_CA_BUNDLE="$1" NODE_EXTRA_CA_CERTS="$1" GIT_SSL_CAINFO="$1" UV_NATIVE_TLS=1; echo "🏛️ $1"; }
# 🧾 envreport: snapshot of toolchain + lock hashes → env-report.txt (evidence for reviews)
envreport() { { echo "# $(date -Iseconds) $(hostname)"; sysinfo; ver; for f in uv.lock package-lock.json bun.lock requirements.txt; do [ -f "$f" ] && sha256sum "$f"; done; } | tee env-report.txt; }
# 🧾 licenses: list licenses of installed python packages (stdlib metadata only)
licenses() { python3 -c 'import importlib.metadata as m;[print(f"{d.metadata["Name"]:30} {d.version:12} {(d.metadata.get("License-Expression") or d.metadata.get("License") or "?")[:40]}") for d in sorted(m.distributions(),key=lambda d:d.metadata["Name"].lower())]'; }
# 📋 pyfreeze: pip freeze of current interpreter (uv env if present)
pyfreeze() { uv pip freeze 2>/dev/null || python3 -m pip freeze; }

# ───────────────────────── 🐳 docker ─────────────────────────
# 🐳 dps: running containers, compact
dps() { docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' "$@"; }
# 🐳 dpsa: all containers
dpsa() { dps -a; }
# 🐚 dsh: shell into container (dsh name)
dsh() { docker exec -it "$1" sh -c 'command -v bash >/dev/null && exec bash || exec sh'; }
# 📜 dlog: follow logs (dlog name)
dlog() { docker logs -f --tail "${2:-100}" "$1"; }
# 🧹 dclean: prune stopped containers, dangling images, networks
dclean() { docker system prune -f; }
# 🧹 dnuke: prune everything incl. volumes (asks)
dnuke() { docker system prune -a --volumes; }
# 📦 dimg: images sorted by size
dimg() { docker images --format '{{.Size}}\t{{.Repository}}:{{.Tag}}' | sort -rh; }
# 🧩 dcu: compose up detached, build
dcu() { docker compose up -d --build "$@"; }
# 🧩 dcd: compose down
dcd() { docker compose down "$@"; }
# 🧩 dcl: compose logs follow
dcl() { docker compose logs -f --tail "${1:-100}"; }
# 📊 dstat: live resource usage
dstat() { docker stats --no-stream; }

# ───────────────────────── 🧰 tmux ─────────────────────────
# 🧰 ta: attach or create session (ta [name=main])
ta() { tmux new -A -s "${1:-main}"; }
# 📋 tl: list sessions
tl() { tmux ls; }
# 💀 tk: kill session (tk name)
tk() { tmux kill-session -t "$1"; }

# ───────────────────────── 📝 memo ─────────────────────────
# 📝 memo: append a line to ~/memo.md with timestamp (memo "text") or show tail
memo() { [ -n "$1" ] && printf -- '- %s %s\n' "$(date +'%F %R')" "$*" >> ~/memo.md || tail -"${N:-20}" ~/memo.md; }
# 🔎 memog: grep ~/memo.md
memog() { grep -i -- "$*" ~/memo.md; }
# ✅ todo: append todo (todo "x") / list open ones
todo() { [ -n "$1" ] && printf -- '- [ ] %s\n' "$*" >> ~/todo.md || grep -n '\[ \]' ~/todo.md; }
# ✅ done1: mark todo line n done (done1 3)
done1() { sed -i "${1}s/\[ \]/[x]/" ~/todo.md && grep -n '\[x\]' ~/todo.md | tail -1; }
# 📓 jnl: open today's journal ~/journal/YYYY-MM-DD.md
jnl() { mkdir -p ~/journal && "${EDITOR:-vi}" ~/journal/"$(date +%F)".md; }
"""


# ───────────────────────── 🧰 parsing ─────────────────────────
def entries() -> list[dict]:
    """Every help line: section, emoji, name, description, needs-internet flag."""
    out, sec = [], "meta"
    for line in (META + SHELL).splitlines():
        if m := SECTION.match(line):
            sec = m.group(2)
        elif m := HELP.match(line):
            out.append({"section": sec, "emoji": m.group(1), "name": m.group(2), "desc": m.group(3), "net": "🌍" in m.group(3) and "🎛️" not in m.group(3)})
    return out


def names() -> list[str]:
    """All function names (help lines only, private helpers excluded)."""
    return [e["name"] for e in entries()]


def sections() -> list[str]:
    """Section names in file order."""
    seen = _sections()
    print(" ".join(seen))
    return seen


def net() -> list[str]:
    """Names that need internet (🌍)."""
    out = [e["name"] for e in entries() if e["net"]]
    print(" ".join(out))
    return out


# ───────────────────────── 📖 listing ─────────────────────────
def ls(section: str | None = None, offline: bool = False) -> list[dict]:
    """Print help lines, optionally one section and/or offline-only."""
    rows = [e for e in entries() if (not section or e["section"] == section) and not (offline and e["net"])]
    if section and not rows:
        print(f"🤔 no section {section!r} → {' '.join(_sections())}")
    for e in rows:
        print(f"{e['section']:<8} {e['emoji']} {e['name']:<14} {e['desc']}")
    return rows


def _sections() -> list[str]:
    return ["meta"] + [m.group(2) for m in map(SECTION.match, SHELL.splitlines()) if m]


def grep(*words: str) -> list[dict]:
    """Search names and descriptions (all words must match, case-insensitive)."""
    ws = [w.lower() for w in words]
    rows = [e for e in entries() if all(w in f"{e['name']} {e['desc']}".lower() for w in ws)]
    for e in rows:
        print(f"{e['section']:<8} {e['emoji']} {e['name']:<14} {e['desc']}")
    return rows


def like(word: str, hint: bool = False, n: int = 6) -> list[str]:
    """Closest names: substring hits first, then difflib similarity ≥0.5."""
    pool = names()
    hits = [x for x in pool if word.lower() in x.lower() and x != word]
    hits += [x for x in difflib.get_close_matches(word, pool, n, 0.5) if x not in hits]
    hits = hits[:n]
    if hint:
        if hits:
            print(f"🤔 {word} → did you mean: {' '.join(hits)}")
        else:
            print(f"❓ {word}: command not found")
    else:
        print("\n".join(hits))
    return hits


# ───────────────────────── 🎛️ dial ─────────────────────────
def read_dial(default: int = 3) -> int:
    try:
        return int(DIAL_FILE.read_text().strip())
    except (OSError, ValueError):
        return default


def dial(level: int | None = None) -> int:
    """Show or set the shared dial. Also tells hubdial (if installed) so remotes follow."""
    if level is None:
        lv = read_dial()
        print(f"🎛️  {lv} {DIALS[lv]}  ({DIAL_FILE})")
        return lv
    if level not in DIALS:
        raise SystemExit("❌ dial must be 0..3")
    DIAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    DIAL_FILE.write_text(f"{level}\n")
    if shutil.which("hubdial"):
        subprocess.run(["hubdial", "dial", str(level)], check=False)
    print(f"🎛️  → {level} {DIALS[level]}" + ("  🌍 one-liners stubbed" if level <= 1 else ""))
    return level


# ───────────────────────── 🐚 shell ─────────────────────────
def init(shell: str | None = None) -> str:
    """Shell code to eval: functions + dial stubs + typo hook + completion."""
    shell = shell or ("zsh" if "zsh" in os.environ.get("SHELL", "") else "bash")
    parts = [f'OLNM_PY="{PY}"', f'DIAL_FILE="${{DIAL_FILE:-{DIAL_FILE}}}"', META, SHELL]
    if read_dial() <= 1:
        for e in entries():
            if e["net"]:
                parts.append(f'{e["name"]}() {{ echo "🔌 {e["name"]}: 🌍 needs dial ≥2 (now $(_olnm_d)) → olnm_dial 2" >&2; return 1; }}')
    secs = " ".join(_sections())
    if shell == "zsh":
        parts.append("command_not_found_handler() { _olnm_cnf \"$@\"; }")
        parts.append(f'(( $+functions[compdef] )) && compdef "_arguments \\"1:section:({secs})\\"" olnm olnm_offline')
    else:
        parts.append("command_not_found_handle() { _olnm_cnf \"$@\"; }")
        parts.append(f'complete -W "{secs}" olnm olnm_offline')
        parts.append('complete -W "0 1 2 3" olnm_dial')
    code = "\n".join(parts) + "\n"
    print(code, end="")
    return code


def run(name: str, *args: str) -> int:
    """Run one one-liner in a non-interactive bash (for Node / Bun / Python callers)."""
    if name not in names():
        like(name, hint=True)
        return 127
    script = f'eval "$(python3 "{PY}" init bash)"; {name} "$@"'
    return subprocess.run(["bash", "-c", script, name, *args]).returncode


def doctor() -> dict:
    """Which optional tools are on PATH, and the current dial."""
    res = {t: bool(shutil.which(t)) for t in TOOLS}
    print(" ".join(("✅ " if v else "❌ ") + k for k, v in res.items()))
    dial()
    return res


def call(fn: str, args: list | None = None, kwargs: dict | None = None):
    """Call a public function by name; result printed as JSON by the CLI."""
    f = globals().get(fn)
    if fn.startswith("_") or not callable(f) or fn in {"main", "call", "build_parser"}:
        raise SystemExit(f"❌ no function {fn!r}")
    return f(*(args or []), **(kwargs or {}))


# ───────────────────────── 🧭 cli ─────────────────────────
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="olnm", description="🧷 OneLinearNumerousMemo")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("init", help="🐚 print shell code to eval"); s.add_argument("shell", nargs="?", choices=["bash", "zsh"])
    s = sp.add_parser("ls", help="📖 list"); s.add_argument("section", nargs="?"); s.add_argument("--offline", action="store_true")
    s = sp.add_parser("grep", help="🔎 search"); s.add_argument("words", nargs="+")
    s = sp.add_parser("like", help="🤔 closest names"); s.add_argument("word"); s.add_argument("--hint", action="store_true")
    sp.add_parser("sections", help="🗂️ sections"); sp.add_parser("net", help="🌍 internet-needing names"); sp.add_parser("doctor", help="🩺 tools")
    s = sp.add_parser("dial", help="🎛️ show/set dial"); s.add_argument("level", nargs="?", type=int, choices=sorted(DIALS))
    s = sp.add_parser("run", help="▶️ run one one-liner in bash"); s.add_argument("name"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sp.add_parser("call", help="🔌 call a function by name → JSON"); s.add_argument("fn"); s.add_argument("args", nargs="?", default="[]"); s.add_argument("--kwargs", default="{}")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    match a.cmd:
        case "init": init(a.shell)
        case "ls": ls(a.section, a.offline)
        case "grep": grep(*a.words)
        case "like": return 0 if like(a.word, a.hint) or not a.hint else 127
        case "sections": sections()
        case "net": net()
        case "doctor": doctor()
        case "dial": dial(a.level)
        case "run": return run(a.name, *a.args)
        case "call":
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                out = call(a.fn, json.loads(a.args), json.loads(a.kwargs))
            print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
