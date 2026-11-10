#!/usr/bin/env python3
"""olnm 🧷 OneLinearNumerousMemo — one Python file: a few hundred bash/zsh one-liners + a local GitHub-like forge.

    curl -fsSL <RAW_URL>/olnm.py -o ~/.olnm.py && echo 'eval "$(python3 ~/.olnm.py init)"' >> ~/.bashrc   # or ~/.zshrc

    olnm            📖 list            olnm git        📖 one section
    olnm_like uvtets 🤔 closest names  olnm_dial 0..3  🎛️ 0🔌 offline · 1🏠 local · 2🔁 mirror · 3☁️ github
    hubdial install / init / up      🏠 local forge (Gitea / Forgejo) · hubadd · ghpr/ghis go there at dial ≤2

Rules: one function per line in SHELL below, `# <emoji> name: what it does` right above it = the help text.
       🌍 in a description = needs internet (stubbed at dial 0/1).  🎛️ = routed to hubdial at dial ≤2.
Target: Ubuntu 26.04 with Python / Node(LTS) / uv. Bun, fzf, fd, rg, jq, gh, docker optional.

Callable by name from Python (`import olnm; olnm.like("uvtets")`), shell (`python3 olnm.py call like '["uvtets"]'`)
and Node / Bun (`execFileSync("python3", ["olnm.py", "calc", "2**10"])`).
"""
from __future__ import annotations

import argparse
import ast
import base64
import contextlib
import difflib
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PY = Path(__file__).resolve()
OLNM_HOME = Path(os.environ.get("OLNM_HOME", Path.home() / ".olnm"))
DIAL_FILE = Path(os.environ.get("DIAL_FILE", OLNM_HOME / "dial"))
DIALS = {0: "🔌 offline", 1: "🏠 local", 2: "🔁 mirror", 3: "☁️ github"}
TOOLS = ("python3", "uv", "mise", "node", "npm", "npx", "bun", "go", "rustc", "cargo", "rustup", "git", "gh", "fzf", "fd", "rg", "jq", "curl", "docker", "tmux", "entr", "tree")
HELP = re.compile(r"^# (\S+) ([A-Za-z_0-9]+): (.*)$")
SECTION = re.compile(r"^# ─+ (\S+) (\S+) ─+$")

# ───────────────────────── 📖 meta (shell shims → this file) ─────────────────────────
META = r"""
# 📖 olnm: list one-liners (olnm git = one section)
olnm() { if [ "$#" -eq 1 ]; then case " $_OLNM_SECTIONS " in *" $1 "*) python3 "$OLNM_PY" ls "$@"; return $?;; esac; fi; case "${1-}" in -h|--help|init|ls|grep|like|sections|net|doctor|dial|run|call|hub|complete|calc|tools|mise|yourself|xprobe|cli_args|ghi|markdown|ascii_artist) python3 "$OLNM_PY" "$@";; *) python3 "$OLNM_PY" ls "$@";; esac; }
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
# 🎛️ olnm_dial: show / set dial 0🔌 1🏠 2🔁 3☁️ (also starts/stops the forge, re-points origins)
olnm_dial() { python3 "$OLNM_PY" dial "$@" && olnm_reload >/dev/null; }
# 🩺 olnm_doctor: which tools are present
olnm_doctor() { python3 "$OLNM_PY" doctor; }
# 🔄 olnm_reload: re-evaluate after edits or dial change
olnm_reload() { eval "$(python3 "$OLNM_PY" init)" && echo "🔄 $OLNM_PY"; }
# 📝 olnm_edit: open olnm.py in $EDITOR
olnm_edit() { "${EDITOR:-vi}" "$OLNM_PY" && olnm_reload; }
# ⬇️ olnm_update: 🌍 re-download olnm.py from $OLNM_URL and reload
olnm_update() { [ -n "${OLNM_URL:-}" ] || { printf '%s\n' 'File install: set OLNM_URL to the reviewed raw olnm.py URL, then olnm_update.' 'uv tool install: use uv tool upgrade one-linear-numerous-memo; then eval "$(command olnm init)".' >&2; return 1; }; curl -fsSL "$OLNM_URL" -o "$OLNM_PY.new" && python3 "$OLNM_PY.new" --help >/dev/null && mv "$OLNM_PY.new" "$OLNM_PY" && olnm_reload; }
# 🔢 olnm_steps: non-blank lines of olnm.py
olnm_steps() { grep -cve '^\s*$' "$OLNM_PY"; }
_olnm_d() { cat "$DIAL_FILE" 2>/dev/null || echo 3; }
_olnm_hub() { [ "$(_olnm_d)" -le 2 ] && [ -f "$OLNM_HOME/forge/state.json" ]; }
_olnm_cnf() { python3 "$OLNM_PY" like "$1" --hint >&2; return 127; }
_olnm_require() { local tool; for tool in "$@"; do command -v "$tool" >/dev/null 2>&1 || { python3 "$OLNM_PY" tools "$tool" >&2; return 127; }; done; }
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
# 🧮 calc: quote-free numeric arithmetic (calc 6 mul 7; calc --engine node 2 pow 10)
calc() { python3 "$OLNM_PY" calc "$@"; }
# 🧾 yourself: bundled standard-library environment report; no separate file or registration
yourself() { python3 "$OLNM_PY" yourself "$@"; }
# 📦 xprobe: single-file xprobe via uv's cached, pinned tool environment
xprobe() { python3 "$OLNM_PY" xprobe "$@"; }
# 📦 cli_args: single-file CLI argument helpers via uv's cached tool environment
cli_args() { python3 "$OLNM_PY" cli_args "$@"; }
# 📦 ghi: single-file gh_identity CLI via uv's cached tool environment
ghi() { python3 "$OLNM_PY" ghi "$@"; }
# 📦 markdown: single-file Markdown stdio CLI via uv's cached tool environment
markdown() { python3 "$OLNM_PY" markdown "$@"; }
# 📦 ascii_artist: single-file ASCII CLI via uv's cached tool environment
ascii_artist() { python3 "$OLNM_PY" ascii_artist "$@"; }
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
# 🌐 ghweb: 🎛️ open repo in browser (local forge at dial ≤2)
ghweb() { _olnm_hub && { hubopen; return; }; gh repo view --web; }
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
cabundle() { [ -f "$1" ] || { echo "file?"; return 1; }; export SSL_CERT_FILE="$1" REQUESTS_CA_BUNDLE="$1" CURL_CA_BUNDLE="$1" NODE_EXTRA_CA_CERTS="$1" GIT_SSL_CAINFO="$1" UV_SYSTEM_CERTS=1; unset UV_NATIVE_TLS; echo "🏛️ $1"; }
# 🧾 envreport: snapshot of toolchain + lock hashes → env-report.txt (evidence for reviews)
envreport() { { echo "# $(date -Iseconds) $(hostname)"; sysinfo; ver; for f in uv.lock package-lock.json bun.lock requirements.txt; do [ -f "$f" ] && sha256sum "$f"; done; } | tee env-report.txt; }
# 🧾 licenses: list licenses of installed python packages (stdlib metadata only)
licenses() { python3 -c 'import importlib.metadata as m;[print(f"{d.metadata["Name"]:30} {d.version:12} {(d.metadata.get("License-Expression") or d.metadata.get("License") or "?")[:40]}") for d in sorted(m.distributions(),key=lambda d:d.metadata["Name"].lower())]'; }
# 📋 pyfreeze: pip freeze of current interpreter (uv env if present)
pyfreeze() { uv pip freeze 2>/dev/null || python3 -m pip freeze; }

# ───────────────────────── 🏠 hub ─────────────────────────
# 🏠 hubdial: local GitHub-like forge (hubdial install | init | up | down | status | repo | issue | pr | labels | sync | api)
hubdial() { python3 "$OLNM_PY" hub "$@"; }
# 📚 hubadd: register cwd in the local forge (hubadd [--github owner/name])
hubadd() { hubdial repo add . "$@"; }
# 🔄 hubsync: push every registered repo to bare / local / github(dial ≥2)
hubsync() { hubdial sync; }
# 🌐 hubopen: open the local forge in a browser (or print its URL)
hubopen() { local u; u="http://localhost:$(python3 "$OLNM_PY" call hub_port 2>/dev/null)/"; command -v xdg-open >/dev/null && xdg-open "$u" >/dev/null 2>&1 || echo "$u"; }

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
# ───────────────────────── 🧰 mise ─────────────────────────
# ➕ miseuse: 🌍 install tools and record project versions (miseuse node@26)
miseuse() { _olnm_require mise || return $?; command mise use "$@"; }
# 🌐 miseglobal: 🌍 install tools and set personal defaults (miseglobal node@26 bun@latest go@latest)
miseglobal() { _olnm_require mise || return $?; command mise use --global "$@"; }
# 📦 miseinstall: 🌍 install configured or specified tools
miseinstall() { _olnm_require mise || return $?; command mise install "$@"; }
# ▶️ miseexec: 🌍 run in mise environment, installing missing tools as mise settings allow (miseexec node@26 -- node -v)
miseexec() { _olnm_require mise || return $?; command mise exec "$@"; }
# 🔌 miseoffline: run with automatic tool installation disabled; child command may still use network (miseoffline -- node -v)
miseoffline() { _olnm_require mise || return $?; MISE_AUTO_INSTALL=false MISE_EXEC_AUTO_INSTALL=false command mise exec "$@"; }
# 📋 misels: list mise tool versions and configuration sources
misels() { _olnm_require mise || return $?; command mise ls "$@"; }
# 🔒 miselock: 🌍 create or refresh mise.lock versions, checksums and download URLs
miselock() { _olnm_require mise || return $?; command mise lock "$@"; }
# 🩺 misedoctor: diagnose mise installation and configuration
misedoctor() { _olnm_require mise || return $?; command mise doctor "$@"; }


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


def _sections() -> list[str]:
    return ["meta"] + [m.group(2) for m in map(SECTION.match, SHELL.splitlines()) if m]


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
        if section not in _sections():
            commands = next(a.choices for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
            candidates = difflib.get_close_matches(section, [*_sections(), *commands], n=3, cutoff=0.5)
            if candidates:
                print("did you mean: " + ", ".join(candidates) + "? Use olnm ls SECTION or olnm COMMAND --help", file=sys.stderr)
    for e in rows:
        print(f"{e['section']:<8} {e['emoji']} {e['name']:<14} {e['desc']}")
    return rows


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
        print(f"🤔 {word} → did you mean: {' '.join(hits)}" if hits else f"❓ {word}: command not found")
    else:
        print("\n".join(hits))
    return hits


# ───────────────────────── 🎛️ dial ─────────────────────────
def read_dial(default: int = 3) -> int:
    """Current dial (0..3); unset = 3 (plain online box)."""
    try:
        return int(DIAL_FILE.read_text().strip())
    except (OSError, ValueError):
        return default


def _write_dial(level: int) -> None:
    DIAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    DIAL_FILE.write_text(f"{level}\n")


def dial(level: int | None = None) -> int:
    """Show or set the dial. When the local forge exists, also start/stop it and re-point every repo's origin."""
    if level is None:
        lv = read_dial()
        print(f"🎛️  {lv} {DIALS[lv]}  ({DIAL_FILE})")
        return lv
    if level not in DIALS:
        raise SystemExit("❌ dial must be 0..3")
    _write_dial(level)
    print(f"🎛️  → {level} {DIALS[level]}" + ("  🌍 one-liners stubbed" if level <= 1 else ""))
    if FSTATE.exists():
        _hub_apply(level)
    return level


# ───────────────────────── 🏠 hub: local GitHub-like forge (Gitea / Forgejo) ─────────────────────────
FORGE = OLNM_HOME / "forge"
BIN, DATA, BARE, LOG = FORGE / "bin" / "forge", FORGE / "data", FORGE / "bare", FORGE / "log"
INI, PID, FSTATE = FORGE / "app.ini", FORGE / "forge.pid", FORGE / "state.json"
# 🧬 flavors: Gitea (default: since 2016, MIT, released on GitHub) or Forgejo (its 2022 fork, GPLv3+, released on Codeberg). Same CLI + API.
FLAVORS = {
    "forgejo": {"urls": ("https://codeberg.org/forgejo/forgejo/releases/download/v{v}/forgejo-{v}-linux-{arch}", "https://code.forgejo.org/forgejo/forgejo/releases/download/v{v}/forgejo-{v}-linux-{arch}"),
                "latest": ("https://codeberg.org/api/v1/repos/forgejo/forgejo/releases/latest", "https://code.forgejo.org/api/v1/repos/forgejo/forgejo/releases/latest")},
    "gitea": {"urls": ("https://github.com/go-gitea/gitea/releases/download/v{v}/gitea-{v}-linux-{arch}", "https://dl.gitea.com/gitea/{v}/gitea-{v}-linux-{arch}"),
              "latest": ("https://api.github.com/repos/go-gitea/gitea/releases/latest", "https://github.com/go-gitea/gitea/releases/latest")},
}
VERIFIED = {"gitea": "1.27.3"}  # ✅ end-to-end checked with olnm; used when the "latest" lookup is blocked but downloads are not
GH_LABELS = {"bug": "d73a4a", "enhancement": "a2eeef", "documentation": "0075ca", "question": "d876e3", "help wanted": "008672", "good first issue": "7057ff", "wontfix": "ffffff", "duplicate": "cfd3d7"}
APP_INI = """\
APP_NAME = olnm hub
RUN_MODE = prod
WORK_PATH = {home}
[server]
PROTOCOL = http
HTTP_ADDR = 127.0.0.1
HTTP_PORT = {port}
ROOT_URL = http://localhost:{port}/
PUBLIC_URL_DETECTION = legacy
DISABLE_SSH = true
OFFLINE_MODE = true
[database]
DB_TYPE = sqlite3
PATH = {data}/forge.db
[repository]
ROOT = {data}/repos
DEFAULT_BRANCH = main
[security]
INSTALL_LOCK = true
SECRET_KEY = {secret}
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = false
[mailer]
ENABLED = false
[log]
MODE = file
ROOT_PATH = {log}
[actions]
ENABLED = true
[mirror]
ENABLED = true
DEFAULT_INTERVAL = 1h
"""
_NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _sh(*cmd: str, cwd: Path | None = None, check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode:
        raise SystemExit(f"❌ {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def _open(req: urllib.request.Request | str, timeout: int):
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    opener = _NOPROXY if url.startswith(("http://127.0.0.1", "http://localhost")) else urllib.request.build_opener()
    return opener.open(req, timeout=timeout)


def _fetch(url: str, dest: Path | None = None, timeout: int = 120) -> bytes:
    with _open(urllib.request.Request(url, headers={"User-Agent": "olnm"}), timeout) as r:
        data = r.read()
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fstate() -> dict:
    return json.loads(FSTATE.read_text()) if FSTATE.exists() else {"port": 3000, "user": "admin", "repos": {}}


def _fsave(st: dict) -> None:
    FORGE.mkdir(parents=True, exist_ok=True)
    FSTATE.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
    FSTATE.chmod(0o600)


def _forge(*args: str, check: bool = True) -> str:
    if not BIN.exists():
        raise SystemExit("❌ forge binary missing → hubdial install")
    return _sh(str(BIN), "--config", str(INI), *args, check=check)


def _running() -> int:
    if PID.exists():
        try:
            pid = int(PID.read_text() or 0)
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            PID.unlink(missing_ok=True)
    return 0


def hub_port() -> int:
    """Port of the local forge."""
    return _fstate()["port"]


def _latest_version(flavor: str = "gitea") -> str:
    for url in FLAVORS[flavor]["latest"]:
        try:
            if url.startswith("https://github.com/"):  # release page redirects to /tag/vX.Y.Z
                with _open(urllib.request.Request(url, headers={"User-Agent": "olnm"}), 20) as r:
                    return r.geturl().rsplit("/v", 1)[1]
            return json.loads(_fetch(url, timeout=20))["tag_name"].lstrip("v")
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError):
            continue
    if v := VERIFIED.get(flavor):
        print(f"↪️  latest {flavor} unknown (lookup blocked) → verified {v}")
        return v
    other = "gitea" if flavor == "forgejo" else "forgejo"
    raise SystemExit(f"❌ cannot reach {flavor} releases → try --flavor {other}, or install --from FILE")


def hub_bundle(dest: str = "carry", version: str = "latest", arch: str = "amd64", flavor: str = "gitea") -> Path:
    """🌍 Download the forge binary + .sha256 into DEST and copy olnm.py beside it — carry DEST into a closed network."""
    if flavor not in FLAVORS:
        raise SystemExit(f"❌ flavor must be one of {', '.join(FLAVORS)}")
    v = _latest_version(flavor) if version == "latest" else version
    out = Path(dest)
    name = f"{flavor}-{v}-linux-{arch}"
    for tmpl in FLAVORS[flavor]["urls"]:
        url = tmpl.format(v=v, arch=arch)
        try:
            print(f"⬇️  {url}")
            binary = _fetch(url, out / name, timeout=900)
            want = _fetch(url + ".sha256", out / f"{name}.sha256", timeout=60).split()[0].decode()
            break
        except urllib.error.URLError as e:
            print(f"⚠️  {url.split('/')[2]}: {e}")
    else:
        raise SystemExit(f"❌ download failed on all hosts → try --flavor {'gitea' if flavor == 'forgejo' else 'forgejo'}")
    if hashlib.sha256(binary).hexdigest() != want:
        raise SystemExit("❌ sha256 mismatch")
    shutil.copy2(PY, out / "olnm.py")
    print(f"✅ sha256 ok → 🎒 {out}/  (offline: python3 olnm.py hub install --from {out}/{name})")
    return out / name


def hub_install(version: str = "latest", src: str | None = None, sha: str | None = None, flavor: str = "gitea") -> Path:
    """Place the forge binary at ~/.olnm/forge/bin/forge. Online: download+verify. Offline: --from carried file (checked against sha or sidecar .sha256)."""
    if src:
        path = Path(src)
        if not path.is_file():
            raise SystemExit(f"❌ no such file: {src}")
        side = path.with_name(path.name + ".sha256")
        want = sha or (side.read_text().split()[0] if side.exists() else None)
        if want and _sha256(path) != want:
            raise SystemExit("❌ sha256 mismatch for carried binary")
    else:
        path = hub_bundle(str(FORGE / "bundle"), version, flavor=flavor)
    BIN.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, BIN)
    BIN.chmod(0o755)
    print(f"📦 {BIN} ← {path.name}")
    try:
        print(f"🔖 {_forge('--version', check=False) or 'installed'}")
    except OSError as e:
        print(f"⚠️  binary not runnable here: {e}")
    return BIN


def hub_init(port: int = 3000, user: str = "admin", password: str | None = None, email: str = "admin@localhost") -> dict:
    """Write app.ini (sqlite, 127.0.0.1 only, no SSH/mail/sign-up), migrate, create admin + API token, set git auth."""
    for d in (DATA, BARE, LOG):
        d.mkdir(parents=True, exist_ok=True)
    st = _fstate()
    if not INI.exists():
        INI.write_text(APP_INI.format(home=FORGE, port=port, data=DATA, log=LOG, secret=secrets.token_urlsafe(48)))
        INI.chmod(0o600)
    _forge("migrate")
    pw = password or secrets.token_urlsafe(16)
    out = _forge("admin", "user", "create", "--admin", "--username", user, "--password", pw, "--email", email, "--must-change-password=false", check=False)
    created = "already exists" not in out.lower()
    tok = _forge("admin", "user", "generate-access-token", "--username", user, "--token-name", f"olnm-{int(time.time())}", "--scopes", "all", "--raw")
    st.update(port=port, user=user, token=tok.strip().splitlines()[-1])
    if created:
        st["password"] = pw
    _fsave(st)
    if not DIAL_FILE.exists():
        _write_dial(1)
    basic = base64.b64encode(f"{user}:{st['token']}".encode()).decode()
    _sh("git", "config", "--global", "--replace-all", f"http.http://localhost:{port}/.extraHeader", f"Authorization: Basic {basic}")
    print(f"🏗️  http://localhost:{port}  user={user}" + (f"  password={pw}" if created else "  (user existed)"))
    print(f"🔑 token → {FSTATE}   🔐 git auth → ~/.gitconfig")
    return st


def hub_up() -> int:
    """Start the forge in the background."""
    if pid := _running():
        print(f"🏠 already up pid={pid}")
        return pid
    if os.geteuid() == 0:
        print("⚠️  running as root: Gitea / Forgejo refuse to serve as root → run olnm as a normal user")
    LOG.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([str(BIN), "--config", str(INI), "web"], stdout=(LOG / "web.out").open("a"), stderr=subprocess.STDOUT, start_new_session=True)
    PID.write_text(str(p.pid))
    port = hub_port()
    for _ in range(60):
        try:
            _fetch(f"http://127.0.0.1:{port}/api/healthz", timeout=2)
            print(f"🏠 up pid={p.pid} → http://localhost:{port}")
            return p.pid
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.5)
    print(f"⚠️  started but health check timed out → {LOG / 'web.out'}")
    return p.pid


def hub_down() -> None:
    """Stop the forge."""
    if pid := _running():
        os.kill(pid, signal.SIGTERM)
        PID.unlink(missing_ok=True)
        print(f"🛑 stopped pid={pid}")


def hub_status() -> dict:
    """Dial, forge state, repo count."""
    st, pid, lv = _fstate(), _running(), read_dial()
    print(f"🎛️  {lv} {DIALS[lv]} | {'🟢 pid=' + str(pid) if pid else '⚪ down'} | 📚 {len(st['repos'])} | http://localhost:{st['port']}")
    return {"dial": lv, "pid": pid, "repos": st["repos"]}


def hub_logs(n: int = 40) -> str:
    """Tail the forge web log."""
    f = LOG / "web.out"
    out = "\n".join(f.read_text(errors="replace").splitlines()[-n:]) if f.exists() else "(no log yet)"
    print(out)
    return out


def hub_api(method: str, path: str, data: dict | None = None, token: str | None = None, base: str | None = None):
    """Gitea / Forgejo REST v1 (GitHub-shaped): hub_api('GET', '/user/repos')."""
    st = _fstate()
    url = (base or f"http://127.0.0.1:{st['port']}/api/v1") + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method.upper(), headers={"Authorization": f"token {token or st.get('token', '')}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with _open(req, 30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"❌ {method} {path} → {e.code} {e.read().decode(errors='replace')[:300]}")


def _github_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok and shutil.which("gh"):
        tok = _sh("gh", "auth", "token", check=False)
    if not tok:
        raise SystemExit("❌ dial 2 mirroring needs GITHUB_TOKEN or `gh auth login`")
    return tok


def _ensure_forge_repo(name: str, private: bool = True) -> None:
    if name not in {r["name"] for r in (hub_api("GET", "/user/repos?limit=200") or [])}:
        hub_api("POST", "/user/repos", {"name": name, "private": private, "default_branch": "main", "auto_init": False})
        print(f"  🆕 forge repo {name}")


def _point_origin(p: Path, level: int, st: dict) -> str:
    r = st["repos"][str(p)]
    target = "bare" if level == 0 else ("github" if level == 3 and r.get("github") else "local")
    url = _sh("git", "remote", "get-url", target, cwd=p, check=False) or _sh("git", "remote", "get-url", "bare", cwd=p)
    _sh("git", "remote", "remove", "origin", cwd=p, check=False)
    _sh("git", "remote", "add", "origin", url, cwd=p)
    print(f"  🎯 {r['name']}: origin → {target}")
    return target


def _ensure_push_mirror(r: dict, st: dict) -> None:
    if not r.get("github"):
        return
    orp, gh_url = f"{st['user']}/{r['name']}", f"https://github.com/{r['github']}.git"
    if any(m.get("remote_address", "").rstrip("/") == gh_url for m in hub_api("GET", f"/repos/{orp}/push_mirrors") or []):
        return
    hub_api("POST", f"/repos/{orp}/push_mirrors", {"remote_address": gh_url, "remote_username": r["github"].split("/")[0], "remote_password": _github_token(), "interval": "1h", "sync_on_commit": True})
    print(f"  🔁 push-mirror → {r['github']}")


def _hub_apply(level: int) -> None:
    st = _fstate()
    if level == 0:
        hub_down()
    elif BIN.exists() and INI.exists():
        hub_up()
    for path, r in st["repos"].items():
        p = Path(path)
        if not p.exists():
            continue
        _point_origin(p, level, st)
        if level >= 1 and _running():
            _ensure_forge_repo(r["name"], r.get("private", True))
            if level == 2:
                _ensure_push_mirror(r, st)


def hub_repo_add(path: str = ".", github: str | None = None, private: bool = True) -> dict:
    """Register a working tree: forge repo + bare backup, remotes `local` `bare` (`github`), origin by dial."""
    p = Path(path).resolve()
    if not (p / ".git").exists():
        _sh("git", "init", "-q", "-b", "main", cwd=p)
    st, name = _fstate(), p.name
    bare = BARE / f"{name}.git"
    if not bare.exists():
        bare.parent.mkdir(parents=True, exist_ok=True)
        _sh("git", "init", "-q", "--bare", "-b", "main", str(bare))
    if _running():
        _ensure_forge_repo(name, private)
    else:
        print("⚠️  forge down; repo is created on next `olnm_dial 1` / `hubdial up`")
    remotes = {"local": f"http://localhost:{st['port']}/{st['user']}/{name}.git", "bare": str(bare)}
    if github:
        remotes["github"] = f"https://github.com/{github}.git"
    for rname, url in remotes.items():
        _sh("git", "remote", "remove", rname, cwd=p, check=False)
        _sh("git", "remote", "add", rname, url, cwd=p)
    st["repos"][str(p)] = {"name": name, "github": github, "private": private}
    _fsave(st)
    print(f"📚 {name}  " + "  ".join(f"{k}={v}" for k, v in remotes.items()))
    _point_origin(p, read_dial(), st)
    return st["repos"][str(p)]


def hub_repo_ls() -> dict:
    """Registered repos."""
    repos = _fstate()["repos"]
    for path, r in repos.items():
        print(f"📚 {r['name']:24} {path}  {('☁️ ' + r['github']) if r.get('github') else ''}")
    return repos


def hub_repo_rm(path: str = ".") -> None:
    """Unregister a working tree (nothing deleted)."""
    st = _fstate()
    st["repos"].pop(str(Path(path).resolve()), None)
    _fsave(st)
    print("🗑️  unregistered")


def hub_sync() -> dict:
    """Push every registered repo to bare / local / github (github only at dial ≥2)."""
    st, lv, res = _fstate(), read_dial(), {}
    for path, r in st["repos"].items():
        p = Path(path)
        if not p.exists():
            continue
        for rem in ("bare", "local", "github"):
            if (rem == "local" and not _running()) or (rem == "github" and lv < 2):
                continue
            if _sh("git", "remote", "get-url", rem, cwd=p, check=False):
                ok = subprocess.run(["git", "push", "-q", "--all", rem], cwd=p, capture_output=True).returncode == 0
                res[f"{r['name']}:{rem}"] = ok
                print(f"  {'✅' if ok else '⚠️ '} {r['name']} → {rem}")
    return res


def _owner_repo(path: str = ".") -> str:
    st = _fstate()
    r = st["repos"].get(str(Path(path).resolve()))
    if not r:
        raise SystemExit("❌ not a registered repo → hubadd")
    return f"{st['user']}/{r['name']}"


def hub_issue_ls(path: str = ".", state: str = "open") -> list:
    """Issues of the current repo."""
    items = hub_api("GET", f"/repos/{_owner_repo(path)}/issues?state={state}&type=issues") or []
    for i in items:
        print(f"🐛 #{i['number']:<4} {i['title']}  {' '.join('🏷️' + l['name'] for l in i.get('labels', []))}")
    return items


def hub_issue_new(title: str, body: str = "", labels: list[str] | None = None, path: str = ".") -> dict:
    """New issue; labels by name (unknown names are skipped)."""
    orp = _owner_repo(path)
    have = {l["name"]: l["id"] for l in hub_api("GET", f"/repos/{orp}/labels") or []} if labels else {}
    it = hub_api("POST", f"/repos/{orp}/issues", {"title": title, "body": body, "labels": [have[n] for n in labels or [] if n in have]})
    print(f"🐛 #{it['number']} {it['html_url']}")
    return it


def hub_pr_ls(path: str = ".") -> list:
    """Open pull requests."""
    items = hub_api("GET", f"/repos/{_owner_repo(path)}/pulls?state=open") or []
    for p in items:
        print(f"🔀 #{p['number']:<4} {p['head']['ref']} → {p['base']['ref']}  {p['title']}")
    return items


def hub_pr_new(title: str, head: str | None = None, base: str = "main", body: str = "", path: str = ".") -> dict:
    """PR from the current branch (pushed to `local` first)."""
    p = Path(path).resolve()
    head = head or _sh("git", "branch", "--show-current", cwd=p)
    _sh("git", "push", "-q", "-u", "local", head, cwd=p)
    orp = _owner_repo(path)
    for _ in range(30):  # the forge indexes pushed branches asynchronously
        with contextlib.suppress(SystemExit):
            hub_api("GET", f"/repos/{orp}/branches/{head}")
            break
        time.sleep(0.5)
    pr = hub_api("POST", f"/repos/{orp}/pulls", {"title": title, "head": head, "base": base, "body": body})
    print(f"🔀 #{pr['number']} {pr['html_url']}")
    return pr


def hub_labels(path: str = ".") -> None:
    """GitHub's default labels (bug, enhancement, …) in the current repo."""
    orp = _owner_repo(path)
    have = {l["name"] for l in hub_api("GET", f"/repos/{orp}/labels") or []}
    for name, color in GH_LABELS.items():
        if name not in have:
            hub_api("POST", f"/repos/{orp}/labels", {"name": name, "color": "#" + color})
    print(f"🏷️  labels ready in {orp}")


def hub_doctor() -> dict:
    """Binary, config, token, forge, git, gh, GitHub reachability."""
    st = _fstate()
    checks = {"binary": BIN.exists(), "app.ini": INI.exists(), "token": bool(st.get("token")), "forge up": bool(_running()), "git": bool(shutil.which("git")), "gh": bool(shutil.which("gh"))}
    try:
        _fetch("https://api.github.com", timeout=5)
        checks["github 🌍"] = True
    except Exception:
        checks["github 🌍"] = False
    print(" ".join(("✅ " if v else "❌ ") + k for k, v in checks.items()))
    return checks


# ───────────────────────── 🐚 shell ─────────────────────────
HUB_SUBS = "install bundle init up down status doctor logs dial repo api issue pr labels sync"


_RUNTIME_GUIDES = {
    "uv": ("https://docs.astral.sh/uv/getting-started/installation/", "Install uv once for this WSL/Linux user; then check uv --version.",
           "olnm's single-file tool commands use uv tool run; no manual registration is required."),
    "mise": ("https://mise.jdx.dev/getting-started.html", "Install mise for this WSL/Linux user using the official guide; then check mise --version.",
             "Set personal defaults: mise use --global node@26 bun@latest go@latest. Python projects can keep using uv."),
    "node": ("https://nodejs.org/en/download", "With mise installed: mise use --global node@26 (or use your existing nvm installation).",
             "Override only when needed: mise use node@26 in the project. npm install installs project dependencies, not Node."),
    "bun": ("https://bun.sh/docs/installation", "Install Bun for this WSL/Linux user using the official guide; then check bun --version.",
            "Check ~/.bun/bin is on PATH. bun install installs project dependencies, not Bun."),
    "rust": ("https://rust-lang.org/tools/install", "Install the Rust toolchain with rustup; then check rustc --version and cargo --version.",
             "Check ~/.cargo/bin is on PATH. Pin the project toolchain in rust-toolchain.toml; build output goes to target/."),
    "go": ("https://go.dev/doc/install", "With mise installed: mise use --global go@latest; then check mise exec -- go version.",
           "Use mise.toml for a project-specific runtime; go.mod/go.sum still manage Go dependencies."),
}


def tools(name: str | None = None) -> dict:
    """Explain optional runtime setup without installing anything or changing the project."""
    aliases = {"npm": "node", "npx": "node", "bunx": "bun", "rustc": "rust", "cargo": "rust", "rustup": "rust"}
    key = aliases.get(name, name)
    if key is not None and key not in _RUNTIME_GUIDES:
        raise ValueError("choose uv, mise, node, bun, go or rust")
    result = {}
    for runtime in ([key] if key else _RUNTIME_GUIDES):
        executables = {"uv": ("uv",), "mise": ("mise",), "node": ("node", "npm", "npx"), "bun": ("bun", "bunx"), "go": ("go",), "rust": ("rustc", "cargo", "rustup")}[runtime]
        found = {exe: shutil.which(exe) for exe in executables}
        url, setup, project = _RUNTIME_GUIDES[runtime]
        result[runtime] = found
        print(f"{runtime}: " + ", ".join(f"{exe}={path or 'not found on PATH'}" for exe, path in found.items()))
        print(f"  {setup}\n  {project}\n  {url}")
    print("Ubuntu/WSL does not guarantee these runtimes are installed. Install per user; project dependencies stay in the work directory. olnm itself needs no Node/Bun/Rust.")
    return result


def mise(*args: str) -> int:
    """Forward argv to mise without a shell, inheriting cwd, stdin/stdout/stderr and exit code."""
    executable = shutil.which("mise")
    if executable is None:
        with contextlib.redirect_stdout(sys.stderr):
            tools("mise")
        return 127
    return subprocess.run([executable, *args]).returncode


# BEGIN STDLIB TOOL SOURCES (reviewed commits, no registry or setup step for users)
_STDLIB_TOOLS = {'xprobe': {'repo': 'xprobe', 'command': 'xprobe', 'commit': 'e077895583fb20113a38c75b57dd132e66ea2558'}, 'cli_args': {'repo': 'cli_args', 'command': 'cli_args', 'commit': 'a81a8b4adec0f5951eda0ed1c708f7497653812f'}, 'ghi': {'repo': 'gh_identity', 'command': 'ghi', 'commit': '2d66af6477a8e86abae557279e84c6407aad4efb'}, 'markdown': {'repo': 'markdown', 'command': 'md-market', 'commit': '8d46ef36126e4437be4ac18926e1f67f033815bb'}, 'ascii_artist': {'repo': 'ascii_artist', 'command': 'ascii_artist', 'commit': 'c728a4c541008c9ff1659398e27a9dce1f2f6f31'}}
# END STDLIB TOOL SOURCES


def _stdlib_tool(name: str, *args: str) -> int:
    executable = shutil.which("uv")
    if executable is None:
        with contextlib.redirect_stdout(sys.stderr):
            tools("uv")
        return 127
    tool = _STDLIB_TOOLS[name]
    source = f"git+https://github.com/myon-bioinformatics/{tool['repo']}.git@{tool['commit']}"
    offline = ["--offline"] if read_dial() <= 1 else []
    return subprocess.run([executable, *offline, "tool", "run", "--from", source, tool["command"], *args]).returncode


def xprobe(*args: str) -> int:
    """Run the default xprobe command through uv's pinned tool cache."""
    return _stdlib_tool("xprobe", *args)


def cli_args(*args: str) -> int:
    """Run the default cli_args command through uv's pinned tool cache."""
    return _stdlib_tool("cli_args", *args)


def ghi(*args: str) -> int:
    """Run the default gh_identity command through uv's pinned tool cache."""
    return _stdlib_tool("ghi", *args)


def markdown(*args: str) -> int:
    """Run the default md-market stdio command through uv's pinned tool cache."""
    return _stdlib_tool("markdown", *args)


def ascii_artist(*args: str) -> int:
    """Run the default ascii_artist command through uv's pinned tool cache."""
    return _stdlib_tool("ascii_artist", *args)


def _yourself_namespace() -> dict:
    namespace = {"__name__": "_olnm_bundled_yourself"}
    exec(compile(_YOURSELF_SOURCE, f"<olnm:yourself@{_YOURSELF_COMMIT}>", "exec"), namespace)
    return namespace


def yourself(*args: str) -> int:
    """Run the bundled yourself main(argv); standard library only, no registration or download."""
    try:
        return _yourself_namespace()["main"](list(args))
    except SystemExit as error:
        # argparse --help / argument errors remain return codes for Python callers.
        if error.code is None or isinstance(error.code, int):
            return error.code or 0
        print(error.code, file=sys.stderr)
        return 1


def _yourself_completion(tokens: list[str]) -> list[str]:
    # Reuse the pinned upstream declarations without running any observation.
    main = next(n for n in ast.parse(_YOURSELF_SOURCE).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    options = {"--help": [], "-h": []}
    for node in ast.walk(main):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            choices = next((ast.literal_eval(k.value) for k in node.keywords if k.arg == "choices"), ())
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                    options[arg.value] = list(choices)
    prefix = tokens[-1] if tokens else ""
    pool = options.get(tokens[-2], []) if len(tokens) > 1 and tokens[-2] in options and not prefix.startswith("-") else options
    return sorted(str(p) for p in pool if str(p).startswith(prefix))


def calc(expression: str) -> int | float:
    """Evaluate bounded arithmetic only; no Python statements, attributes, imports or shell execution."""
    if len(expression) > 1000:
        raise ValueError("expression must be at most 1000 characters")
    tree = ast.parse(expression.strip(), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("expression is too complex (maximum 128 syntax nodes)")
    functions = {n: getattr(math, n) for n in ("sqrt", "sin", "cos", "tan", "log", "log2", "log10", "exp", "ceil", "floor")}
    functions.update(abs=abs, round=round, min=min, max=max)
    constants = {n: getattr(math, n) for n in ("pi", "e", "tau")}

    def bounded(value):
        if type(value) not in (int, float):
            raise ValueError("only real numbers are supported")
        if isinstance(value, int) and value.bit_length() > 4096:
            raise ValueError("integer exceeds 4096 bits")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("result must be finite")
        return value

    def visit(node):
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, ast.Name) and node.id in constants:
            return constants[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = visit(node.operand)
            return bounded(v if isinstance(node.op, ast.UAdd) else -v)
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            match node.op:
                case ast.Add(): value = a + b
                case ast.Sub(): value = a - b
                case ast.Mult(): value = a * b
                case ast.Div(): value = a / b
                case ast.FloorDiv(): value = a // b
                case ast.Mod(): value = a % b
                case ast.Pow():
                    if abs(b) > 1000:
                        raise ValueError("absolute exponent must be <= 1000")
                    if isinstance(a, int) and isinstance(b, int) and b > 0 and a.bit_length() * b > 4096:
                        raise ValueError("power may exceed 4096 bits")
                    value = a ** b
                case _: raise ValueError("unsupported operator")
            return bounded(value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and not node.keywords:
            return bounded(functions[node.func.id](*(visit(a) for a in node.args)))
        raise ValueError("use numbers, + - * / // % **, pi/e/tau or supported math functions")

    return visit(tree.body)


def _completion(words: list[str]) -> list[str]:
    """Pure completion: no filesystem scans, service calls or execution."""
    command, *tokens = words or ["olnm", ""]
    if not tokens:
        tokens = [""]
    prefix = tokens[-1]
    if command == "yourself":
        return _yourself_completion(tokens)
    if command == "olnm" and tokens[0] == "yourself" and len(tokens) > 1:
        return _yourself_completion(tokens[1:])
    if command == "olnm" and tokens[:2] == ["run", "yourself"] and len(tokens) > 2:
        return _yourself_completion(tokens[2:])
    if command in {"miseuse", "miseglobal", "miseinstall", "miseexec", "miseoffline"}:
        return [n for n in ("bun@latest", "go@latest", "node@26", "uv@latest") if n.startswith(prefix)] if "--" not in tokens[:-1] and not prefix.startswith("-") else []
    if command == "olnm" and tokens[0] == "mise":
        return [n for n in ("doctor", "exec", "install", "lock", "ls", "use") if n.startswith(prefix)] if len(tokens) == 2 else []
    if command in {"olnm_offline", "olnm_like"}:
        pool = _sections() if command == "olnm_offline" else names()
        return sorted(n for n in pool if n.startswith(prefix))
    tokens = ({"hubdial": ["hub"], "olnm_dial": ["dial"]}.get(command, []) + tokens)
    parser, path, index, pending = build_parser(), [], 0, None
    for token in tokens[:-1]:
        if pending is not None:
            pending = None
            continue
        options = {opt: action for action in parser._actions for opt in action.option_strings}
        if token in options:
            if options[token].nargs != 0:
                pending = options[token]
            continue
        positional = [a for a in parser._actions if not a.option_strings]
        if index >= len(positional):
            return []
        action = positional[index]
        if isinstance(action, argparse._SubParsersAction):
            if token not in action.choices:
                return []
            parser = action.choices[token]
            path.append(token)
            index = 0
        elif action.nargs not in (argparse.REMAINDER, "+", "*"):
            index += 1
    positional = [a for a in parser._actions if not a.option_strings]
    action = pending or (positional[index] if index < len(positional) else None)
    if pending:
        pool = [str(c) for c in pending.choices or []]
    elif prefix.startswith("-"):
        pool = [opt for a in parser._actions for opt in a.option_strings]
    elif action is not None and action.choices is not None:
        pool = [str(c) for c in action.choices]
        if not path:
            pool += _sections()
    elif action is not None and (path, action.dest) == (["ls"], "section"):
        pool = _sections()
    elif action is not None and (path, action.dest) == (["run"], "name"):
        pool = names()
    elif action is not None and (path, action.dest) == (["call"], "fn"):
        pool = public()
    else:
        pool = []
    return sorted({p for p in pool if p.startswith(prefix)})


def complete(*words: str) -> list[str]:
    """Print candidates for shell words including command name and current (possibly empty) word."""
    candidates = _completion(list(words))
    if candidates:
        print("\n".join(candidates))
    return candidates


def init(shell: str | None = None) -> str:
    """Shell code to eval: functions + dial stubs + typo hook + completion."""
    shell = shell or ("zsh" if "zsh" in os.environ.get("SHELL", "") else "bash")
    # Quote literal paths; preserve only the intended environment overrides.
    parts = [f'OLNM_PY={shlex.quote(str(PY))}', f'OLNM_HOME=${{OLNM_HOME:-{shlex.quote(str(OLNM_HOME))}}}', f'DIAL_FILE=${{DIAL_FILE:-{shlex.quote(str(DIAL_FILE))}}}', f'_OLNM_SECTIONS={shlex.quote(" ".join(_sections()))}', META]
    guarded = SHELL
    for entry in entries():
        if entry["section"] in {"node", "bun"}:
            # Guard the executable actually used, not every optional tool in the section.
            body = re.search(r"^" + re.escape(entry["name"]) + r"\(\) \{ (.*)$", SHELL, re.M).group(1)
            executable = body.split()[0]
            required = {"nv": "node npm npx", "nclean": "npm", "nupall": "npx npm"}.get(entry["name"], executable)
            if required.split()[0] in {"node", "npm", "npx", "bun", "bunx"}:
                head = f'{entry["name"]}() {{ '
                guarded = guarded.replace(head, head + f'_olnm_require {required} || return $?; ', 1)
    parts.append(guarded)
    if read_dial() <= 1:
        for e in entries():
            if e["net"]:
                parts.append(f'{e["name"]}() {{ echo "🔌 {e["name"]}: 🌍 needs dial ≥2 (now $(_olnm_d)) → olnm_dial 2" >&2; return 1; }}')
    if shell == "zsh":
        parts.append('command_not_found_handler() { _olnm_cnf "$@"; }')
        parts.append(r'''_olnm_complete_zsh() {
  local -a candidates
  candidates=("${(@f)$(python3 "$OLNM_PY" complete -- "${words[@]:0:$CURRENT}")}")
  (( ${#candidates} )) && compadd -- "${candidates[@]}"
}
(( $+functions[compdef] )) && compdef _olnm_complete_zsh olnm olnm_offline olnm_like olnm_dial hubdial miseuse miseglobal miseinstall miseexec miseoffline yourself
''')
    else:
        parts.append('command_not_found_handle() { _olnm_cnf "$@"; }')
        parts.append(r'''_olnm_complete_bash() {
  local candidate
  COMPREPLY=()
  while IFS= read -r candidate; do COMPREPLY+=("$candidate"); done < <(python3 "$OLNM_PY" complete -- "${COMP_WORDS[@]:0:COMP_CWORD+1}")
}
complete -o default -F _olnm_complete_bash olnm olnm_offline olnm_like olnm_dial hubdial miseuse miseglobal miseinstall miseexec miseoffline yourself
''')
    code = "\n".join(parts) + "\n"
    print(code, end="")
    return code


_CALC_WORDS = {"plus": "+", "minus": "-", "mul": "*", "div": "/",
               "pow": "**", "mod": "%", "floordiv": "//", "lpar": "(", "rpar": ")"}


def calculate(*args: str, engine: str = "python") -> int:
    """Validate numeric arithmetic, then use the original runtime's semantics."""
    if engine not in {"python", "node"}:
        print(f"calc: unknown engine {engine!r}", file=sys.stderr)
        return 1
    expression = " ".join(_CALC_WORDS.get(word, word) for arg in args for word in arg.split())
    try:
        if not expression or len(expression) > 4096:
            raise ValueError("expected 1..4096 characters of numeric arithmetic")
        # Python's parser would silently ignore a trailing comment. Reject it
        # before passing the expression to either runtime (JS // is a comment).
        if "#" in expression or (engine == "node" and "//" in expression):
            raise ValueError("comments and Node floor division are not supported")
        tree = ast.parse(expression, mode="eval")
        allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                   ast.Pow, ast.Mod, ast.UAdd, ast.USub)
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise ValueError("only numeric arithmetic is allowed; use mul/div/pow/lpar/rpar")
            if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
                raise ValueError("only real numeric literals are allowed")
    except (SyntaxError, ValueError, RecursionError) as exc:
        print(f"calc: {exc}", file=sys.stderr)
        return 1
    if engine == "python":
        return subprocess.run([sys.executable, "-c", f"from math import *; print({expression})"]).returncode
    try:
        # Parenthesize the validated expression so a leading minus is not a Node option.
        return subprocess.run(["node", "-p", "(" + expression + ")"]).returncode
    except FileNotFoundError:
        print("calc: node: command not found", file=sys.stderr)
        return 127


def run(name: str, *args: str) -> int:
    """Run one one-liner in a non-interactive bash (for Node / Bun / Python callers)."""
    if name not in names():
        with contextlib.redirect_stdout(sys.stderr):
            like(name, hint=True)
        return 127
    return subprocess.run(["bash", "-c", f'eval "$(python3 {shlex.quote(str(PY))} init bash)"; {name} "$@"', name, *args]).returncode


def doctor() -> dict:
    """Optional tools on PATH, the dial, and the forge if set up."""
    res = {t: bool(shutil.which(t)) for t in TOOLS}
    print(" ".join(("✅ " if v else "❌ ") + k for k, v in res.items()))
    dial()
    if FSTATE.exists():
        hub_status()
    return res


def public() -> list[str]:
    """Names callable through `call`."""
    return sorted(n for n, v in globals().items() if callable(v) and getattr(v, "__module__", "") == __name__ and n[0].islower() and n not in {"main", "call", "build_parser"})


def call(fn: str, args: list | None = None, kwargs: dict | None = None):
    """Call a public function by name; the CLI prints the result as JSON (progress goes to stderr)."""
    f = globals().get(fn)
    if fn.startswith("_") or not callable(f) or fn in {"main", "call", "build_parser"}:
        candidates = difflib.get_close_matches(fn, public(), n=3, cutoff=0.5)
        hint = " → did you mean: " + ", ".join(candidates) if candidates else ""
        raise SystemExit(f"❌ no function {fn!r}{hint}. See olnm call public")
    return f(*(args or []), **(kwargs or {}))


# ───────────────────────── 🧭 cli ─────────────────────────
class _Parser(argparse.ArgumentParser):
    """Suggest corrections on Python 3.11+ without changing or executing the input."""

    def error(self, message):
        match = re.search(r"invalid choice: '([^']+)'", message)
        pool = [str(c) for a in self._actions if a.choices is not None for c in a.choices]
        if match:
            word = match.group(1)
        elif message.startswith("unrecognized arguments: "):
            word = message.split(": ", 1)[1].split()[0]
            def options(parser):
                for action in parser._actions:
                    yield from action.option_strings
                    if isinstance(action, argparse._SubParsersAction):
                        for child in action.choices.values():
                            yield from options(child)
            pool = sorted(set(options(self)))
        else:
            word = ""
        candidates = difflib.get_close_matches(word, pool, n=3, cutoff=0.5) if word else []
        if candidates:
            message += "\n  did you mean: " + ", ".join(candidates) + "? See " + self.prog + " --help"
        super().error(message)


def build_parser() -> argparse.ArgumentParser:
    ap = _Parser(prog="olnm", description="🧷 OneLinearNumerousMemo")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("init", help="🐚 print shell code to eval"); s.add_argument("shell", nargs="?", choices=["bash", "zsh"])
    s = sp.add_parser("ls", help="📖 list"); s.add_argument("section", nargs="?"); s.add_argument("--offline", action="store_true")
    s = sp.add_parser("grep", help="🔎 search"); s.add_argument("words", nargs="+")
    s = sp.add_parser("like", help="🤔 closest names"); s.add_argument("word"); s.add_argument("--hint", action="store_true")
    sp.add_parser("sections", help="🗂️ sections"); sp.add_parser("net", help="🌍 internet-needing names"); sp.add_parser("doctor", help="🩺 tools")
    s = sp.add_parser("complete", help="Tab candidates (shell command and words, ending with current word)"); s.add_argument("words", nargs=argparse.REMAINDER)
    s = sp.add_parser("calc", help="🧮 arithmetic: words (6 mul 7) or symbols; no arguments prompts for an expression without shell quoting")
    s.add_argument("--engine", choices=["python", "node"], default="python"); s.add_argument("expression", nargs=argparse.REMAINDER)
    s = sp.add_parser("tools", help="optional uv/mise/Node/Bun/Go/Rust setup and project-local usage (no installation)"); s.add_argument("name", nargs="?", choices=["uv", "mise", "node", "npm", "npx", "bun", "bunx", "go", "rust", "rustc", "cargo", "rustup"])
    s = sp.add_parser("mise", help="forward arguments to mise (exec can auto-install; use --help for olnm wrapper help)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sp.add_parser("yourself", help="bundled environment report; accepts upstream yourself options directly"); s.add_argument("args", nargs=argparse.REMAINDER)
    for name in _STDLIB_TOOLS:
        s = sp.add_parser(name, help="default stdlib-only command via uv's pinned tool cache"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sp.add_parser("dial", help="🎛️ show/set dial"); s.add_argument("level", nargs="?", type=int, choices=sorted(DIALS))
    s = sp.add_parser("run", help="▶️ run one one-liner in bash"); s.add_argument("name"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sp.add_parser("call", help="🔌 call a function by name → JSON"); s.add_argument("fn"); s.add_argument("args", nargs="?", default="[]"); s.add_argument("--kwargs", default="{}")
    s = sp.add_parser("hub", help="🏠 local GitHub-like forge"); h = s.add_subparsers(dest="sub", required=True)
    x = h.add_parser("install", help="📦 🌍 download or --from carried binary"); x.add_argument("--version", default="latest"); x.add_argument("--from", dest="src"); x.add_argument("--sha256", dest="sha"); x.add_argument("--flavor", choices=sorted(FLAVORS), default="gitea")
    x = h.add_parser("bundle", help="🎒 🌍 binary + .sha256 + olnm.py into DIR"); x.add_argument("dir"); x.add_argument("--version", default="latest"); x.add_argument("--flavor", choices=sorted(FLAVORS), default="gitea")
    x = h.add_parser("init", help="🏗️ config, db, admin, token"); x.add_argument("--port", type=int, default=3000); x.add_argument("--user", default="admin"); x.add_argument("--password")
    for name, hp in (("up", "🟢 start"), ("down", "🛑 stop"), ("status", "📊 status"), ("doctor", "🩺 checks"), ("sync", "🔄 push to all remotes"), ("labels", "🏷️ GitHub default labels")):
        h.add_parser(name, help=hp)
    x = h.add_parser("logs", help="📜 tail log"); x.add_argument("-n", type=int, default=40)
    x = h.add_parser("dial", help="🎛️ same as olnm dial"); x.add_argument("level", nargs="?", type=int, choices=sorted(DIALS))
    x = h.add_parser("repo", help="📚 register working trees"); r = x.add_subparsers(dest="repo_cmd", required=True)
    y = r.add_parser("add"); y.add_argument("path", nargs="?", default="."); y.add_argument("--github", help="owner/name"); y.add_argument("--public", action="store_true")
    r.add_parser("ls"); y = r.add_parser("rm"); y.add_argument("path", nargs="?", default=".")
    x = h.add_parser("api", help="🌐 raw REST"); x.add_argument("method", choices=["GET", "POST", "PATCH", "PUT", "DELETE"]); x.add_argument("path"); x.add_argument("--data", help="JSON body")
    x = h.add_parser("issue", help="🐛 issues"); i = x.add_subparsers(dest="issue_cmd", required=True)
    y = i.add_parser("ls"); y.add_argument("--state", default="open", choices=["open", "closed", "all"])
    y = i.add_parser("new"); y.add_argument("title"); y.add_argument("--body", default=""); y.add_argument("--label", action="append", default=[])
    x = h.add_parser("pr", help="🔀 pull requests"); p = x.add_subparsers(dest="pr_cmd", required=True)
    p.add_parser("ls"); y = p.add_parser("new"); y.add_argument("title"); y.add_argument("--head"); y.add_argument("--base", default="main"); y.add_argument("--body", default="")
    return ap


def _hub_main(a: argparse.Namespace) -> None:
    match a.sub:
        case "install": hub_install(a.version, a.src, a.sha, a.flavor)
        case "bundle": hub_bundle(a.dir, a.version, flavor=a.flavor)
        case "init": hub_init(a.port, a.user, a.password)
        case "up": hub_up()
        case "down": hub_down()
        case "status": hub_status()
        case "doctor": hub_doctor()
        case "sync": hub_sync()
        case "labels": hub_labels()
        case "logs": hub_logs(a.n)
        case "dial": dial(a.level)
        case "repo": {"add": lambda: hub_repo_add(a.path, a.github, not a.public), "ls": hub_repo_ls, "rm": lambda: hub_repo_rm(a.path)}[a.repo_cmd]()
        case "api": print(json.dumps(hub_api(a.method, a.path, json.loads(a.data) if a.data else None), indent=2, ensure_ascii=False))
        case "issue": hub_issue_ls(state=a.state) if a.issue_cmd == "ls" else hub_issue_new(a.title, a.body, a.label)
        case "pr": hub_pr_ls() if a.pr_cmd == "ls" else hub_pr_new(a.title, a.head, a.base, a.body)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in _STDLIB_TOOLS:
        args = argv[1:]
        return _stdlib_tool(argv[0], *(args[1:] if args[:1] == ["--"] else args))
    if argv[:1] == ["yourself"]:
        args = argv[1:]
        return yourself(*(args[1:] if args[:1] == ["--"] else args))
    if argv[:1] == ["calc"]:
        # Only the leading --engine option belongs to the CLI; the rest is math.
        offset = 1
        if argv[1:2] == ["--engine"]:
            offset = 3
        elif len(argv) > 1 and argv[1].startswith("--engine="):
            offset = 2
        if len(argv) > offset and argv[offset] not in {"--", "--help", "-h"}:
            argv.insert(offset, "--")
    a = build_parser().parse_args(argv)
    match a.cmd:
        case "init": init(a.shell)
        case "ls":
            ls(a.section, a.offline)
            return 2 if a.section and a.section not in _sections() else 0
        case "grep": grep(*a.words)
        case "like": return 0 if like(a.word, a.hint) or not a.hint else 127
        case "sections": sections()
        case "net": net()
        case "doctor": doctor()
        case "complete": complete(*(a.words[1:] if a.words[:1] == ["--"] else a.words))
        case "tools": tools(a.name)
        case "mise": return mise(*(a.args[1:] if a.args[:1] == ["--"] else a.args))
        case "calc":
            tokens = a.expression[1:] if a.expression[:1] == ["--"] else a.expression
            if tokens:  # words or symbols on the command line: quote-free, same result as python -c / node -p
                return calculate(*tokens, engine=a.engine)
            try:
                if sys.stdin.isatty():
                    print("Expression (e.g. 6*7 or sqrt(81); no surrounding quotes): ", end="", file=sys.stderr, flush=True)
                    try:
                        import readline
                    except ImportError:
                        pass
                    else:
                        symbols = sorted(["pi", "e", "tau", "abs(", "round(", "min(", "max("] +
                                         [n + "(" for n in ("sqrt", "sin", "cos", "tan", "log", "log2", "log10", "exp", "ceil", "floor")])
                        readline.set_completer(lambda text, state: ([n for n in symbols if n.startswith(text)] + [None])[state])
                        readline.parse_and_bind("bind ^I rl_complete" if "libedit" in (readline.__doc__ or "") else "tab: complete")
                    expression = input()
                else:
                    expression = sys.stdin.read(1002)
                print(calc(expression))
            except (ValueError, SyntaxError, ArithmeticError, TypeError, RecursionError, EOFError) as error:
                print(f"calc: {error}\nTry: olnm calc, then type 6*7 at the prompt; or printf '%s\\n' '6*7' | olnm calc", file=sys.stderr)
                return 2
        case "dial": dial(a.level)
        case "run": return run(a.name, *a.args)
        case "hub": _hub_main(a)
        case "call":
            try:
                args, kwargs = json.loads(a.args), json.loads(a.kwargs)
            except json.JSONDecodeError as error:
                print(f"call: invalid JSON ({error.msg}). Use an array for args and an object for --kwargs.\nExample: olnm call like '[\"uvtets\"]' --kwargs '{{\"n\":2}}'", file=sys.stderr)
                return 2
            if not isinstance(args, list) or not isinstance(kwargs, dict):
                print("call: args must be a JSON array; --kwargs must be a JSON object. See olnm call --help", file=sys.stderr)
                return 2
            with contextlib.redirect_stdout(sys.stderr):
                out = call(a.fn, args, kwargs)
            print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


# BEGIN BUNDLED YOURSELF (generated by scripts/update_yourself.py)
# Upstream: https://github.com/myon-bioinformatics/yourself
_YOURSELF_COMMIT = '93a5d2f3ac3ce25f5c1f25ab8378a66afbfa76d1'
_YOURSELF_SHA256 = 'c3915551d3723e45c2b3563dc9c7063e168b0cdd9a71a27830f836afd70d1ad5'
_YOURSELF_LICENSE = r'''MIT License

Copyright (c) 2026 myon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
_YOURSELF_SOURCE = r'''"""Read-only environment facts, using the standard library only.

No network requests (except the opt-in ``reach`` / ``--reach`` TLS handshake),
package installation or project-file content reads.
Fixed version commands are available only through explicit opt-in diagnostics.
Import is inert. Directory observations are shallow and explicitly requested.
"""

import hashlib, json, os, platform, re, shutil, stat, subprocess, sys
from bisect import insort; from pathlib import Path

__version__ = "0.6.0"
__all__ = ["collect", "directory_summary", "to_json", "to_markdown", "to_text",
           "command_inventory", "workspace_facts", "listener_ports", "diagnose",
           "network_facts", "container_facts", "probe", "probe_all", "hosts_facts", "no_proxy_covers",
           "resource_facts", "session_facts", "runner_fingerprint", "runner_fingerprint_summary",
           "reach", "runtime_facts", "python_packages",
           "main"]


def directory_summary(path, *, sample_size=10):
    """Count immediate entry types and return a sorted, bounded name sample.

    No recursion or file-content reads. Symlinks are counted without following
    them. Invalid roots raise; individual entry errors are reported. Paths and
    names can be sensitive; callers choose whether to include this observation.
    """
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
        raise ValueError("sample_size must be a non-negative integer")
    path = Path(path)
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError("path must be a directory, not a symlink")
    counts = {"files": 0, "directories": 0, "symlinks": 0, "other": 0}
    names = []
    errors = []
    with os.scandir(path) as entries:
        for entry in entries:
            # Keep only the lexicographically smallest sample, not all names.
            if sample_size and (len(names) < sample_size or entry.name < names[-1]):
                insort(names, entry.name)
                if len(names) > sample_size:
                    names.pop()
            try:
                if entry.is_symlink():
                    kind = "symlinks"
                elif entry.is_dir(follow_symlinks=False):
                    kind = "directories"
                elif entry.is_file(follow_symlinks=False):
                    kind = "files"
                else:
                    kind = "other"
                counts[kind] += 1
            except OSError as error:
                errors.append({"name": entry.name, "reason": type(error).__name__})
    return {"path": str(path.absolute()), "counts": counts, "sample": names,
            "errors": sorted(errors, key=lambda item: item["name"])}


def collect(*, directory=None, sample_size=10, include_host=False):
    """Observe OS/runtime facts; optional host name and shallow directory data.

    No environment variable dump, username, IP, Git identity or inferred project
    facts. Host name is opt-in to keep the default report easy to share.
    Stable key order; values reflect the current environment, not a fixed fixture.
    """
    facts = {"schema_version": 1,
             "os": {"system": platform.system(), "release": platform.release(),
                    "machine": platform.machine()},
             "runtime": {"implementation": platform.python_implementation(),
                         "version": platform.python_version(),
                         "bits": 64 if sys.maxsize > 2 ** 32 else 32},
             "host": {"name": platform.node()} if include_host else None,
             "directory": None}
    if directory is not None:
        facts["directory"] = directory_summary(directory, sample_size=sample_size)
    return facts


def to_json(facts):
    """Serialize facts as deterministic Unicode JSON; reject non-finite numbers."""
    return json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + "\n"


def _cell(value):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "".join("\\u%04x" % ord(c) if ord(c) < 32 or ord(c) == 127 else c
                   for c in text).replace("|", "&#124;").replace("`", "&#96;")


def to_markdown(facts):
    """Render collect() facts as a concise Markdown report without raw controls."""
    rows = ["# Environment", "", "| Fact | Observed value |", "| --- | --- |"]
    for section in ("os", "runtime", "host"):
        for key, value in (facts.get(section) or {}).items():
            rows.append("| " + _cell(section + "." + key) + " | " + _cell(value) + " |")
    directory = facts.get("directory")
    if directory is not None:
        rows.extend(["", "## Directory (immediate entries only)", "",
                     "Path: " + _cell(directory["path"]), "",
                     "Counts: " + _cell(directory["counts"]), "",
                     "Sample: " + _cell(directory["sample"]), "",
                     "Errors: " + _cell(directory["errors"])])
    if "commands" in facts:
        rows.extend(["", "## Tools", "", "| Tool | Observation |", "| --- | --- |"])
        for tool in facts["commands"]:
            observed = tool["version"] or ("available; " + tool["status"] if tool["available"] else "not found")
            rows.append("| " + _cell(tool["name"]) + " | " + _cell(observed) + " |")
    for key in ("os_release", "workspace", "listeners"):
        if facts.get(key) is not None:
            rows.extend(["", key + ": " + _cell(facts[key])])
    packages = facts.get("python_packages")
    if packages is not None:
        rows.extend(["", "## Python packages", "", "| Fact | Observed value |", "| --- | --- |"])
        for key in ("count", "installers", "complete", "errors"):
            rows.append("| " + key + " | " + _cell(packages[key]) + " |")
    return "\n".join(rows) + "\n"


# Fixed observation-only commands: no shell, arbitrary argv, service startup,
# builds, package installation, Docker daemon access, or compiler invocation.
_COMMANDS = {
    'python': ('--version',), 'git': ('--version',), 'docker': ('--version',),
    'node': ('--version',), 'cmake': ('--version',), 'ninja': ('--version',),
    'gcc': ('--version',), 'g++': ('--version',), 'clang': ('--version',), 'rg': ('--version',),
    'flutter': None, 'dart': None, 'npm': None, 'pytest': None, 'goma': None, 'gomacc': None,
    'gh': None, 'uv': None, 'pip': None, 'pipx': None, 'npx': None, 'pnpm': None, 'yarn': None,
    'playwright': None, 'actionlint': None, 'jq': None, 'curl': None, 'ffmpeg': None,
    'magick': None, 'tsc': None, 'nvidia-smi': None, 'make': None, 'java': None, 'go': None,
    'rustc': None, 'cargo': None, 'deno': None, 'bun': None, 'chromium': None,
    'google-chrome': None, 'firefox': None, 'xclip': None, 'xsel': None, 'wl-copy': None,
    'pbcopy': None, 'sqlite3': None, 'psql': None, 'kubectl': None, 'terraform': None,
    'aws': None, 'gcloud': None, 'podman': None, 'nerdctl': None, 'helm': None, 'kind': None,
    'minikube': None, 'mise': None, 'asdf': None, 'just': None, 'ssh': None, 'wget': None,
    'zip': None, 'unzip': None, 'tar': None, 'ruff': ('--version',), 'poetry': None,
    'pdm': None, 'pixi': None, 'task': None, 'brew': None, 'bash': None, 'zsh': None,
    'fish': None, 'git-lfs': None, 'mvn': None, 'gradle': None, 'ruby': None, 'bundle': None,
    'mix': None, 'nix': None, 'rye': None, 'conda': None, 'winget': None, 'apt': None,
    'dnf': None, 'yum': None, 'pacman': None, 'scoop': None, 'choco': None, 'gem': None,
    'swift': None, 'bazel': None, 'meson': None, 'mypy': None, 'grep': None, 'sed': None,
    'awk': None, 'find': None, 'fd': None, 'ag': None, 'ack': None, 'tree': None, 'fzf': None,
    'pipenv': None, 'mamba': None, 'virtualenv': None, 'black': None, 'corepack': None,
    'javac': None, 'php': None, 'composer': None, 'elixir': None, 'gzip': None, 'bzip2': None,
    'xz': None, 'zstd': None, '7z': None, 'patch': None, 'diff': None, 'rsync': None,
    'docker-compose': None, 'podman-compose': None, 'yq': None,
}
_MARKERS = (
    'pyproject.toml', 'requirements.txt', 'package.json', 'pubspec.yaml', 'Dockerfile',
    'compose.yaml', 'docker-compose.yml', 'CMakeLists.txt', 'BUILD.gn', 'WORKSPACE', '.goma',
    'Makefile', 'Cargo.toml', 'go.mod', 'tsconfig.json', 'pnpm-workspace.yaml', 'deno.json',
    'tox.ini', 'noxfile.py', 'justfile', 'Taskfile.yml', 'flake.nix', 'pixi.toml', 'Brewfile',
    '.python-version', '.node-version', '.tool-versions', '.mise.toml', 'poetry.lock',
    'pdm.lock', 'uv.lock', 'Pipfile', '.venv', 'pom.xml', 'build.gradle', 'build.gradle.kts',
    'Gemfile', 'mix.exs', 'default.nix', 'Taskfile.yaml', 'bun.lockb', 'bunfig.toml',
    'Rakefile', 'build.sbt', '.pre-commit-config.yaml', 'mise.toml', 'ruff.toml', '.ruff.toml',
)
_MARKER_ALIASES = {'justfile': ('justfile', 'Justfile')}
_DIRECTORY_MARKERS = frozenset(('.goma', '.venv'))


def command_inventory(names=None, *, versions=False, timeout=2):
    """Find fixed tool names; version execution is explicit opt-in.

    Runs only fixed version argv with shell=False, stdin disabled, no cwd
    override and a timeout. Reports numeric versions, never command output,
    paths, environment values, stdout or stderr. PATH executables must be trusted;
    a malicious/replaced binary cannot be made read-only by its argv.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError('timeout must be a finite number in (0, 30]')
    if isinstance(names, str):
        raise TypeError('names must be a sequence, not a string')
    names = tuple(_COMMANDS) if names is None else tuple(names)
    if any(not isinstance(n, str) or n not in _COMMANDS for n in names):
        raise ValueError('unsupported command name')
    rows = []
    for name in sorted(set(names)):
        executable = sys.executable if name == 'python' else shutil.which(name)
        item = {'name': name, 'available': bool(executable), 'version': None,
                'status': 'not_found' if not executable else 'not_requested'}
        args = _COMMANDS[name]
        if executable and versions:
            if args is None:
                item['status'] = 'presence_only'
            else:
                try:
                    observed = subprocess.run([executable, *args], shell=False,
                                              stdin=subprocess.DEVNULL,
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                              timeout=timeout, check=False)
                    # Only a numeric version escapes the observation boundary.
                    output = (observed.stdout + b'\n' + observed.stderr)[:8192]
                    version = re.search(rb'(?<![\w.])v?(\d+(?:\.\d+){1,3})(?![\w.])', output)
                    if observed.returncode:
                        item['status'] = 'nonzero_exit'
                    elif version:
                        item['version'] = version.group(1).decode('ascii')
                        item['status'] = 'measured'
                    else:
                        item['status'] = 'unrecognized_version'
                except subprocess.TimeoutExpired:
                    item['status'] = 'timeout'
                except OSError:
                    item['status'] = 'execution_error'
        rows.append(item)
    return rows


def workspace_facts(path):
    """Observe project marker presence and disk capacity without content reads.

    No Git identity, dependency parsing or recursive inventory. Marker files are
    lstat-ed only; symlinks do not count as files. Disk facts are byte counts.
    Match actual directory-entry spellings on every filesystem. Only registered
    aliases are accepted; justfile/Justfile yield one canonical 'justfile'.
    """
    root = Path(path)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('workspace must be a directory, not a symlink')
    markers, errors = [], []
    try:
        entries = {entry.name for entry in root.iterdir()}
    except OSError as error:
        entries = set()
        errors.append({'marker': 'workspace', 'reason': type(error).__name__})
    for name in _MARKERS:
        for spelling in _MARKER_ALIASES.get(name, (name,)):
            if spelling not in entries:
                continue
            try:
                mode = (root / spelling).lstat().st_mode
                if stat.S_ISREG(mode) or (name in _DIRECTORY_MARKERS and stat.S_ISDIR(mode)):
                    markers.append(name)
                    break
            except FileNotFoundError:
                continue  # Entry disappeared after listing.
            except OSError as error:
                errors.append({'marker': spelling, 'reason': type(error).__name__})
    try:
        disk = shutil.disk_usage(root)
        storage = {'total_bytes': disk.total, 'used_bytes': disk.used,
                   'free_bytes': disk.free}
    except OSError as error:
        storage = None
        errors.append({'marker': 'storage', 'reason': type(error).__name__})
    return {'markers': markers, 'storage': storage, 'errors': errors}


def _proc_address(text, family):
    """Decode a /proc/net/tcp{,6} local address (host byte order per 32-bit word)."""
    import ipaddress
    raw = bytes.fromhex(text)
    if family == 'tcp':
        return str(ipaddress.IPv4Address(raw[::-1]))
    words = b''.join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
    if words[:12] == b'\x00' * 10 + b'\xff\xff':
        return '::ffff:' + str(ipaddress.IPv4Address(words[12:]))
    return str(ipaddress.IPv6Address(words))


def listener_ports(*, proc_root='/proc', addresses=False):
    """Read Linux proc TCP LISTEN ports; never connect, scan or name processes.

    With addresses=True also return each local bind address, so "listens on
    127.0.0.1 only" versus "all interfaces" is visible (a frequent localhost /
    container port-mapping problem). Bind addresses are local facts.

    Unsupported platforms return measured=False. No port scan, PID ownership,
    UDP inference, remote connections or network commands. Restricted proc data
    is represented as an error; an empty observed table is distinct.
    """
    if platform.system() != 'Linux':
        result = {'measured': False, 'tcp_ports': [], 'errors': ['unsupported_platform']}
        if addresses:
            result['bindings'] = []
        return result
    ports, errors, observed, bindings = set(), [], 0, set()
    for name in ('tcp', 'tcp6'):
        try:
            with (Path(proc_root) / 'net' / name).open('r', encoding='ascii') as stream:
                next(stream, None)
                for line in stream:
                    fields = line.split()
                    if len(fields) < 4 or fields[3] != '0A':
                        continue
                    try:
                        port = int(fields[1].rsplit(':', 1)[1], 16)
                    except (ValueError, IndexError):
                        errors.append('malformed_' + name)
                        continue
                    if 0 <= port <= 65535:
                        ports.add(port)
                        if addresses:
                            try:
                                bindings.add((port, _proc_address(fields[1].rsplit(':', 1)[0], name)))
                            except ValueError:
                                errors.append('malformed_' + name)
                    else:
                        errors.append('malformed_' + name)
            observed += 1
        except (OSError, UnicodeError) as error:
            errors.append(name + ':' + type(error).__name__)
    result = {'measured': observed > 0, 'tcp_ports': sorted(ports),
              'errors': sorted(set(errors))}
    if addresses:
        result['bindings'] = [{'port': port, 'address': address} for port, address in sorted(bindings)]
    return result


def diagnose(*, directory=None, include_host=False, versions=False,
             ports=False, commands=None, timeout=2):
    """Compact AI environment context; no environment changes or repairs.

    Defaults to tool presence only. Version commands and proc listener reads
    each require their own opt-in. Workspace inspection requires a directory.
    Does not import project code, read configs, inspect Git or contact a daemon.
    """
    facts = collect(include_host=include_host)
    facts['commands'] = command_inventory(commands, versions=versions, timeout=timeout)
    facts['workspace'] = workspace_facts(directory) if directory is not None else None
    facts['listeners'] = listener_ports() if ports else None
    facts['os_release'] = None
    if platform.system() == 'Linux':
        try:
            release = platform.freedesktop_os_release()
            facts['os_release'] = {k: release[k] for k in ('ID', 'VERSION_ID') if k in release}
        except OSError:
            pass
    return facts


def _hex_ipv4(value):
    """/proc/net/route stores IPv4 little-endian hex."""
    raw = int(value, 16)
    return ".".join(str((raw >> shift) & 255) for shift in (0, 8, 16, 24))


_LOOPBACK_NAMES = ("localhost", "127.0.0.1", "::1")


def no_proxy_covers(value=None):
    """Whether NO_PROXY exempts each loopback name (the value itself is never returned).

    With HTTPS_PROXY set and localhost missing from NO_PROXY, a local dev
    server is reached through the proxy and fails. Accepts "*", exact names,
    leading-dot/wildcard forms of localhost and CIDR ranges such as 127.0.0.0/8.
    """
    import ipaddress
    if value is None:
        value = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    tokens = {t.strip().lower().strip("[]") for t in value.replace(" ", ",").split(",") if t.strip()}
    covers = {}
    for name in _LOOPBACK_NAMES:
        hit = "*" in tokens or name in tokens
        if not hit and name == "localhost":
            hit = bool(tokens & {".localhost", "*.localhost"})
        if not hit and name != "localhost":
            for token in tokens:
                try:
                    hit = ipaddress.ip_address(name) in ipaddress.ip_network(token, strict=False)
                except ValueError:
                    continue
                if hit:
                    break
        covers[name] = hit
    return covers


def network_facts(*, proc_root="/proc", sys_root="/sys", etc_root="/etc"):
    """Local network configuration from files only: no packets, DNS or commands.

    Host name, interfaces with state, IPv4/IPv6 addresses, default route and
    DNS servers. Proxy settings are reported as set/unset only, because their
    values can carry credentials. Unreadable sources are listed in errors.
    """
    proc, sysfs, etc = Path(proc_root), Path(sys_root), Path(etc_root)
    facts = {"hostname": platform.node(), "interfaces": [], "ipv4": [], "ipv6": [],
             "default_route": None, "dns": {"nameservers": [], "search": []},
             "proxy_set": {name: bool(os.environ.get(name) or os.environ.get(name.lower()))
                           for name in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY")},
             "no_proxy_covers": no_proxy_covers(), "errors": []}
    try:
        for entry in sorted((sysfs / "class" / "net").iterdir()):
            try:
                state = (entry / "operstate").read_text(encoding="ascii").strip()
            except OSError:
                state = "unknown"
            facts["interfaces"].append({"name": entry.name, "state": state})
    except OSError as error:
        facts["errors"].append("interfaces:" + type(error).__name__)
    try:
        # fib_trie lists every address; "/32 host LOCAL" marks one of ours.
        previous = None
        for line in (proc / "net" / "fib_trie").read_text(encoding="ascii").splitlines():
            match = re.search(r"\|-- (\d+\.\d+\.\d+\.\d+)$", line)
            if match:
                previous = match.group(1)
            elif "/32 host LOCAL" in line and previous and previous not in facts["ipv4"]:
                facts["ipv4"].append(previous)
    except OSError as error:
        facts["errors"].append("ipv4:" + type(error).__name__)
    try:
        for line in (proc / "net" / "if_inet6").read_text(encoding="ascii").splitlines():
            fields = line.split()
            if len(fields) == 6 and len(fields[0]) == 32:
                address = ":".join(fields[0][i:i + 4] for i in range(0, 32, 4))
                facts["ipv6"].append({"address": address, "interface": fields[5]})
    except FileNotFoundError:
        pass  # IPv6 disabled is an observation, not an error
    except OSError as error:
        facts["errors"].append("ipv6:" + type(error).__name__)
    try:
        for line in (proc / "net" / "route").read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 3 and fields[1] == "00000000":
                facts["default_route"] = {"interface": fields[0], "gateway": _hex_ipv4(fields[2])}
                break
    except (OSError, ValueError) as error:
        facts["errors"].append("route:" + type(error).__name__)
    try:
        for line in (etc / "resolv.conf").read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "nameserver":
                facts["dns"]["nameservers"].append(fields[1])
            elif fields and fields[0] in ("search", "domain"):
                facts["dns"]["search"].extend(fields[1:])
    except OSError as error:
        facts["errors"].append("dns:" + type(error).__name__)
    return facts


def container_facts(*, proc_root="/proc", root="/"):
    """Container / VM hints from marker files, cgroups and CPU flags only."""
    proc, base = Path(proc_root), Path(root)
    kinds = []
    if (base / ".dockerenv").exists():
        kinds.append("docker")
    if (base / "run" / ".containerenv").exists():
        kinds.append("podman")
    try:
        cgroup = (proc / "1" / "cgroup").read_text(encoding="utf-8", errors="replace")
        for marker, kind in (("docker", "docker"), ("kubepods", "kubernetes"),
                             ("containerd", "containerd"), ("lxc", "lxc")):
            if marker in cgroup and kind not in kinds:
                kinds.append(kind)
    except OSError:
        pass
    declared = os.environ.get("container")  # systemd convention (podman, lxc, ...)
    if declared and re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", declared) and declared not in kinds:
        kinds.append(declared)
    if os.environ.get("KUBERNETES_SERVICE_HOST") and "kubernetes" not in kinds:
        kinds.append("kubernetes")
    try:
        virtualized = " hypervisor" in (proc / "cpuinfo").read_text(encoding="ascii", errors="replace")
    except OSError:
        virtualized = None
    return {"in_container": bool(kinds), "kinds": kinds, "virtualized": virtualized, "wsl": _wsl_kind(proc)}


def _wsl_kind(proc):
    """'wsl2' / 'wsl1' from the kernel release, else None. WSL is a VM or a
    compatibility layer, not a container, so it never sets in_container."""
    for path in (proc / "sys" / "kernel" / "osrelease", proc / "version"):
        try:
            text = path.read_text(encoding="ascii", errors="replace").lower()
        except OSError:
            continue
        if "wsl2" in text or "microsoft-standard" in text:
            return "wsl2"
        if "microsoft" in text or "wsl" in text:
            return "wsl1"
        return None
    return None


# Fixed probes run by default (shell=False, bounded time and output). Their
# point is "does this work here?", so a failure is a result, not an error.
_PROBES = {
    "docker.context": ("docker", "context", "show"),
    "docker.server": ("docker", "version", "--format", "{{.Server.Version}}"),
    "docker.networks": ("docker", "network", "ls", "--format", "{{.Name}} {{.Driver}} {{.Scope}}"),
    "docker.bridge": ("docker", "network", "inspect", "bridge", "--format",
                      "{{range .IPAM.Config}}{{.Subnet}} gw={{.Gateway}} {{end}}"),
    "docker.containers": ("docker", "ps", "-a", "--format", "{{.Names}} {{.Image}} {{.State}} {{.Ports}}"),
    "docker.images": ("docker", "images", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}"),
    # The address the system resolver (nsswitch, not only /etc/hosts) gives first.
    "localhost.resolves_to": ("getent", "hosts", "localhost"),
    "gpu": ("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"),
}


def probe(argv, *, timeout=3, max_lines=20):
    """Run one fixed argv; ok is True only for exit 0. Output is bounded."""
    if not shutil.which(argv[0]):
        return {"ok": False, "lines": [], "error": "not_installed"}
    try:
        done = subprocess.run(list(argv), shell=False, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "lines": [], "error": "timeout"}
    except OSError as error:
        return {"ok": False, "lines": [], "error": type(error).__name__}
    text = done.stdout[:65536].decode("utf-8", "replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {"ok": done.returncode == 0, "lines": lines[:max_lines], "truncated": len(lines) > max_lines}
    if done.returncode:
        first = next((l.strip() for l in done.stderr[:4096].decode("utf-8", "replace").splitlines() if l.strip()), "")
        result["error"] = first[:200] or "exit %d" % done.returncode
    return result


def probe_all(names=None, *, timeout=3):
    names = tuple(_PROBES) if names is None else tuple(names)
    if any(n not in _PROBES for n in names):
        raise ValueError("unsupported probe name")
    return {name: probe(_PROBES[name], timeout=timeout) for name in names}


def hosts_facts(*, etc_root="/etc", proc_root="/proc"):
    """What /etc/hosts maps localhost-like names to (no DNS lookup).

    'localhost' can mean 127.0.0.1 or ::1; a server bound to only one of them
    is unreachable through the other, so both mappings are shown.
    """
    wanted = ("localhost", "host.docker.internal", "gateway.docker.internal")
    found = {name: [] for name in wanted}
    is_default_etc = (Path(etc_root) == Path("/etc"))
    hosts_path = Path(etc_root) / "hosts"
    if is_default_etc and not hosts_path.exists() and platform.system() == "Windows":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        win_path = Path(system_root) / "System32" / "drivers" / "etc" / "hosts"
        if win_path.exists():
            hosts_path = win_path
    try:
        for line in hosts_path.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split("#", 1)[0].split()
            for name in fields[1:]:
                if name in found and fields[0] not in found[name]:
                    found[name].append(fields[0])
    except OSError as error:
        return {"measured": False, "error": type(error).__name__, "names": found,
                "ipv6_loopback": _ipv6_loopback(proc_root)}
    return {"measured": True, "names": found, "ipv6_loopback": _ipv6_loopback(proc_root)}


def _ipv6_loopback(proc_root):
    """True when ::1 is configured on Linux (/proc/net/if_inet6); None off Linux.

    A missing if_inet6 on Linux means IPv6 is disabled, so ::1 cannot answer.
    """
    if platform.system() != "Linux":
        return None
    text = _read(Path(proc_root) / "net" / "if_inet6")
    if text is None:
        return False
    return any(line.split()[:1] == ["00000000000000000000000000000001"] for line in text.splitlines())


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return None


def resource_facts(*, proc_root="/proc", cgroup_root="/sys/fs/cgroup"):
    """CPU, memory, load, uptime, container (cgroup v1/v2) limits, open-file limit."""
    proc, cg = Path(proc_root), Path(cgroup_root)
    facts = {"cpus": os.cpu_count(), "usable_cpus": None, "cpu_limit": None,
             "memory_total_bytes": None, "memory_available_bytes": None, "swap_total_bytes": None,
             "memory_limit_bytes": None, "load": None, "uptime_seconds": None, "open_files_limit": None}
    if hasattr(os, "sched_getaffinity"):
        try:
            facts["usable_cpus"] = len(os.sched_getaffinity(0))
        except OSError:
            pass
    for line in (_read(proc / "meminfo") or "").splitlines():
        key, _, rest = line.partition(":")
        value = rest.split()
        if value and value[0].isdigit():
            target = {"MemTotal": "memory_total_bytes", "MemAvailable": "memory_available_bytes",
                      "SwapTotal": "swap_total_bytes"}.get(key)
            if target:
                facts[target] = int(value[0]) * 1024
    loadavg = (_read(proc / "loadavg") or "").split()
    if len(loadavg) >= 3:
        facts["load"] = loadavg[:3]
    uptime = (_read(proc / "uptime") or "").split()
    if uptime:
        try:
            facts["uptime_seconds"] = int(float(uptime[0]))
        except ValueError:
            pass
    # cgroup v2 then v1; "max" or a huge v1 sentinel means unlimited (None).
    memory = _read(cg / "memory.max") or _read(cg / "memory" / "memory.limit_in_bytes")
    if memory and memory.isdigit() and int(memory) < 2 ** 60:
        facts["memory_limit_bytes"] = int(memory)
    cpu = (_read(cg / "cpu.max") or "").split()
    quota, period = (cpu + [None, None])[:2] if cpu else (_read(cg / "cpu" / "cpu.cfs_quota_us"),
                                                         _read(cg / "cpu" / "cpu.cfs_period_us"))
    if quota and period and quota.lstrip("-").isdigit() and period.isdigit() and int(quota) > 0 and int(period) > 0:
        facts["cpu_limit"] = round(int(quota) / int(period), 2)
    try:
        import resource
        soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        facts["open_files_limit"] = None if soft == resource.RLIM_INFINITY else soft
    except (ImportError, OSError, ValueError):
        pass
    return facts


def session_facts():
    """Who/where/when this process runs: user, shell, locale, time zone,
    display (headless?), Python executable and virtualenv, CA bundle and CI
    variables (set/unset only)."""
    import getpass
    from datetime import datetime
    try:
        user = getpass.getuser()
    except Exception:  # no passwd entry in some containers
        user = None
    uid = os.getuid() if hasattr(os, "getuid") else None
    zone = os.environ.get("TZ") or _read("/etc/timezone")
    if not zone:
        try:
            zone = os.readlink("/etc/localtime").split("zoneinfo/", 1)[-1]
        except OSError:
            zone = None
    flags = lambda names: {name: bool(os.environ.get(name)) for name in names}
    is_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    return {"user": user, "uid": uid, "root": uid == 0 if uid is not None else None,
            "home": str(Path.home()) if os.environ.get("HOME") else None,
            "shell": Path(os.environ.get("SHELL", "")).name or None,
            "lang": os.environ.get("LC_ALL") or os.environ.get("LANG"),
            "timezone": zone, "local_time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "display": flags(("DISPLAY", "WAYLAND_DISPLAY")),
            "python_executable": sys.executable, "virtualenv": is_venv,
            "virtualenv_name": Path(sys.prefix).name if is_venv else None,
            "ca_env": flags(("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "CURL_CA_BUNDLE")),
            "ci": flags(("CI", "GITHUB_ACTIONS")), "writable_cwd": os.access(".", os.W_OK)}


def _duration(seconds):
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    return ("%dd " % days if days else "") + "%dh%02dm" % (hours, rest // 60)


def _gib(value):
    return "%.1f GiB" % (value / 2 ** 30)


_RUNNER_ENV_KEYS = ("RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "ImageOS", "ImageVersion",
                    "RUNNER_TOOL_CACHE", "AGENT_TOOLSDIRECTORY")
_DMI_FILES = ("sys_vendor", "product_name", "chassis_asset_tag")


def _soft_ok(value):
    return {"ok": True, "value": value}


def _soft_err(reason, **extra):
    item = {"ok": False, "reason": reason}
    item.update(extra)
    return item


def _read_soft(path):
    try:
        return _soft_ok(Path(path).read_text(encoding="utf-8", errors="replace").strip())
    except FileNotFoundError:
        return _soft_err("not_found")
    except OSError as error:
        return _soft_err(type(error).__name__)


def _env_soft(name, environ=None):
    environ = environ if environ is not None else os.environ
    if name not in environ:
        return _soft_err("unset")
    return _soft_ok(environ[name])


_IMAGEDATA_MAX_BYTES = 2 * 1024 * 1024


def _imagedata_paths(root="/"):
    base = Path(root)
    if platform.system() == "Windows":
        return [Path("C:/imagedata.json")]
    return [base / "imagegeneration" / "imagedata.json"]


def _json_load_soft(text):
    try:
        return _soft_ok(json.loads(text))
    except RecursionError:
        return _soft_err("recursion_depth")
    except json.JSONDecodeError as error:
        return _soft_err("invalid_json", detail=str(error))


def _normalize_imagedata_value(data, path):
    if isinstance(data, dict):
        safe = {key: data[key] for key in ("image", "ImageOS", "ImageVersion")
                if key in data and isinstance(data[key], str)}
        return _soft_ok({"path": str(path), "kind": "object", "keys": sorted(safe), "object": safe})
    if isinstance(data, list):
        entries = []
        for item in data:
            if isinstance(item, dict):
                entries.append({key: item[key] for key in ("group", "detail") if key in item})
            else:
                entries.append({"value_type": type(item).__name__})
        return _soft_ok({"path": str(path), "kind": "array", "length": len(data), "entries": entries})
    return _soft_err("unsupported_type", path=str(path))


def _parse_imagedata(paths):
    for path in paths:
        try:
            with Path(path).open("rb") as stream:
                raw = stream.read(_IMAGEDATA_MAX_BYTES + 1)
        except FileNotFoundError:
            continue
        except OSError as error:
            return _soft_err(type(error).__name__, path=str(path))
        if len(raw) > _IMAGEDATA_MAX_BYTES:
            return _soft_err("too_large", path=str(path), bytes=len(raw))
        loaded = _json_load_soft(raw.decode("utf-8", errors="replace"))
        if not loaded["ok"]:
            return {**loaded, "path": str(path)}
        return _normalize_imagedata_value(loaded["value"], path)
    return _soft_err("not_found", paths=[str(p) for p in paths])


def _os_identity(*, etc_root="/etc"):
    system = platform.system()
    if system == "Linux":
        release = _read_soft(Path(etc_root) / "os-release")
        if release["ok"]:
            parsed = {}
            for line in release["value"].splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, raw = line.partition("=")
                    parsed[key] = raw.strip().strip('"')
            release["value"] = parsed
        return {"platform": system, "os_release": release}
    if system == "Darwin":
        return {"platform": system, "mac_ver": _soft_ok(platform.mac_ver())}
    if system == "Windows":
        return {"platform": system, "win32_ver": _soft_ok(platform.win32_ver())}
    return {"platform": system, "detail": _soft_err("unsupported_platform")}


def _kernel_facts():
    return {"release": platform.release(), "version": platform.version()}


def _dmi_facts(*, sys_root="/sys", root="/"):
    base = Path(sys_root) / "class" / "dmi" / "id"
    fields = {name: _read_soft(base / name) for name in _DMI_FILES}
    waagent = Path(root) / "var/lib/waagent"
    try:
        waagent_present = waagent.exists()
    except OSError as error:
        waagent_present = None
        waagent_err = type(error).__name__
    else:
        waagent_err = None
    evidence = []
    for name, item in fields.items():
        if item.get("ok") and item.get("value"):
            value = item["value"].lower()
            matches = [provider for provider, tokens in (
                ("azure", ("microsoft", "azure")), ("aws", ("amazon", "ec2")),
                ("gcp", ("google",))) if any(token in value for token in tokens)]
            evidence.extend("dmi:" + name + ":" + provider for provider in matches)
    if waagent_present:
        evidence.append("path:/var/lib/waagent")
    guess = None
    blob = " ".join(item.get("value", "") for item in fields.values() if item.get("ok")).lower()
    if "microsoft" in blob or "azure" in blob or waagent_present:
        guess = "azure"
    elif "amazon" in blob or "ec2" in blob:
        guess = "aws"
    elif "google" in blob:
        guess = "gcp"
    safe_fields = {name: (_soft_ok([provider for provider in ("azure", "aws", "gcp")
                                  if "dmi:" + name + ":" + provider in evidence])
                          if item.get("ok") else item) for name, item in fields.items()}
    return {"dmi": safe_fields, "waagent": _soft_ok(waagent_present) if waagent_err is None
            else _soft_err(waagent_err), "guess": guess, "evidence": evidence}


def _dpkg_inventory(*, list_path=None, timeout=30):
    executable = shutil.which("dpkg-query")
    if not executable:
        return _soft_err("not_available")
    if platform.system() != "Linux":
        return _soft_err("unsupported_platform")
    try:
        done = subprocess.run([executable, "-W", "-f=${Package}\t${Version}\n"],
                              shell=False, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return _soft_err("timeout")
    except OSError as error:
        return _soft_err(type(error).__name__)
    if done.returncode:
        detail = done.stderr[:500].decode("utf-8", "replace").strip()
        return _soft_err("nonzero_exit", detail=detail or ("exit %d" % done.returncode))
    text = done.stdout.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    written = None
    if list_path is not None:
        try:
            Path(list_path).write_text(text, encoding="utf-8")
            written = str(list_path)
        except OSError as error:
            return {"ok": True, "value": {"count": len(lines), "sha256": digest,
                                          "list_path": _soft_err(type(error).__name__)}}
    value = {"count": len(lines), "sha256": digest}
    if written is not None:
        value["list_path"] = _soft_ok(written)
    return _soft_ok(value)


def _tool_cache_inventory(path):
    root = Path(path)
    try:
        if not root.is_dir():
            return _soft_err("not_a_directory")
    except OSError as error:
        return _soft_err(type(error).__name__)
    tools = {}
    errors = []
    try:
        names = sorted(entry.name for entry in root.iterdir())
    except OSError as error:
        return _soft_err(type(error).__name__)
    for name in names:
        tool_dir = root / name
        try:
            if not tool_dir.is_dir():
                continue
            versions = sorted(child.name for child in tool_dir.iterdir() if child.is_dir())
            tools[name] = versions
        except OSError as error:
            errors.append({"tool": name, "reason": type(error).__name__})
    result = _soft_ok({"path": str(root.absolute()), "tools": tools})
    if errors:
        result["entry_errors"] = errors
    return result


_IMDS_COMPUTE_ALLOW = ("osType", "location", "vmSize", "sku", "offer", "version")
_IMDS_READ_BYTES = 65536
_IMDS_INSTANCE_URL = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"


def _sanitize_imds_payload(data):
    if not isinstance(data, dict):
        return {"type": type(data).__name__}
    compute = data.get("compute")
    if not isinstance(compute, dict):
        return {}
    return {"compute": {key: compute[key] for key in _IMDS_COMPUTE_ALLOW if key in compute}}


def _build_imds_opener():
    """IMDS fetcher: no HTTP proxy, no redirects."""
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def _imds_facts(*, timeout=1.0):
    """Optional cloud metadata; only when caller opts in (stdlib urllib, no proxy)."""
    import urllib.error
    import urllib.request
    request = urllib.request.Request(_IMDS_INSTANCE_URL, headers={"Metadata": "true"})
    opener = _build_imds_opener()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(_IMDS_READ_BYTES)
    except urllib.error.HTTPError as error:
        return _soft_err("http_error", status=error.code)
    except urllib.error.URLError as error:
        reason = error.reason
        name = type(reason).__name__ if reason is not None else "URLError"
        return _soft_err("url_error", detail=name)
    except TimeoutError:
        return _soft_err("timeout")
    except OSError as error:
        return _soft_err(type(error).__name__)
    loaded = _json_load_soft(raw.decode("utf-8", errors="replace"))
    if not loaded["ok"]:
        return loaded
    return _soft_ok(_sanitize_imds_payload(loaded["value"]))


def runner_fingerprint(*, environ=None, root="/", etc_root="/etc", sys_root="/sys",
                       dpkg_list_path=None, imds=False, imds_timeout=1.0):
    """CI runner image fingerprint; every probe fails soft. No IMDS unless imds=True."""
    environ = environ if environ is not None else os.environ
    tool_cache = _env_soft("RUNNER_TOOL_CACHE", environ)
    if not tool_cache["ok"]:
        tool_cache = _env_soft("AGENT_TOOLSDIRECTORY", environ)
    caches = []
    if tool_cache.get("ok"):
        caches.append(_tool_cache_inventory(tool_cache["value"]))
    fingerprint = {"schema": "runner-fingerprint/1",
                   "github_actions_env": {key: _env_soft(key, environ) for key in _RUNNER_ENV_KEYS},
                   "imagedata": _parse_imagedata(_imagedata_paths(root)),
                   "os_identity": _os_identity(etc_root=etc_root),
                   "kernel": _kernel_facts(),
                   "python": {"implementation": platform.python_implementation(),
                              "version": platform.python_version(),
                              "bits": 64 if sys.maxsize > 2 ** 32 else 32},
                   "cloud": _dmi_facts(sys_root=sys_root, root=root),
                   "dpkg": _dpkg_inventory(list_path=dpkg_list_path),
                   "tool_cache": tool_cache,
                   "tool_cache_contents": caches,
                   "imds": None}
    if imds:
        fingerprint["imds"] = _imds_facts(timeout=imds_timeout)
    return fingerprint


def runner_fingerprint_summary(fingerprint):
    """Short human-readable summary for logs and GITHUB_STEP_SUMMARY."""
    lines = ["Runner fingerprint (schema runner-fingerprint/1)"]
    env = fingerprint.get("github_actions_env") or {}
    for key in ("RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "ImageOS", "ImageVersion"):
        item = env.get(key) or {}
        value = item.get("value") if item.get("ok") else ("(" + item.get("reason", "missing") + ")")
        lines.append("%s: %s" % (key, value))
    os_id = fingerprint.get("os_identity") or {}
    if os_id.get("platform") == "Linux":
        rel = (os_id.get("os_release") or {})
        if rel.get("ok"):
            parsed = rel["value"]
            pretty = parsed.get("PRETTY_NAME") or "%s %s" % (parsed.get("ID", "?"), parsed.get("VERSION_ID", "?"))
            lines.append("os: %s" % pretty)
    cloud = fingerprint.get("cloud") or {}
    if cloud.get("guess"):
        lines.append("cloud_guess: %s (%s)" % (cloud["guess"], ", ".join(cloud.get("evidence") or []) or "no evidence"))
    else:
        lines.append("cloud_guess: (none)")
    dpkg = fingerprint.get("dpkg") or {}
    if dpkg.get("ok"):
        lines.append("dpkg_packages: %s sha256=%s" % (dpkg["value"]["count"], dpkg["value"]["sha256"][:16] + "..."))
    elif dpkg.get("reason"):
        lines.append("dpkg_packages: (%s)" % dpkg["reason"])
    cache = fingerprint.get("tool_cache_contents") or []
    if cache and cache[0].get("ok"):
        tools = cache[0]["value"]["tools"]
        lines.append("tool_cache_tools: %s" % (", ".join(sorted(tools)) if tools else "(empty)"))
    imds = fingerprint.get("imds")
    if imds is not None:
        if imds.get("ok"):
            compute = (imds.get("value") or {}).get("compute") or {}
            bits = ["%s=%s" % (key, compute[key]) for key in _IMDS_COMPUTE_ALLOW if key in compute]
            lines.append("imds: ok" + (" (" + ", ".join(bits) + ")" if bits else ""))
        else:
            lines.append("imds: (%s)" % imds.get("reason", "failed"))
    return "\n".join(lines) + "\n"


_HOST = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?)(?::(\d{1,5}))?$")


def _proxy_for(host, environ):
    """Proxy endpoint for an HTTPS request to host, or None when direct (no proxy or NO_PROXY)."""
    import urllib.parse
    import urllib.request
    value = environ.get("HTTPS_PROXY") or environ.get("https_proxy")
    no_proxy = environ.get("NO_PROXY") or environ.get("no_proxy") or ""
    if not value or (no_proxy and urllib.request.proxy_bypass_environment(host, {"no": no_proxy})):
        return None
    parts = urllib.parse.urlsplit(value if "://" in value else "http://" + value)
    if parts.scheme != "http" or not parts.hostname:
        return {"error": "unsupported_proxy"}
    unquote = urllib.parse.unquote
    return {"host": parts.hostname, "port": parts.port or 80,
            "user": None if parts.username is None else unquote(parts.username),
            "password": None if parts.password is None else unquote(parts.password)}


def _connect_via(sock, host, port, proxy):
    """Send CONNECT; return None when established, else the proxy's status and short reason."""
    import base64
    lines = ["CONNECT %s:%d HTTP/1.1" % (host, port), "Host: %s:%d" % (host, port)]
    if proxy["user"] is not None:
        token = base64.b64encode(("%s:%s" % (proxy["user"], proxy["password"] or "")).encode("utf-8")).decode("ascii")
        lines.append("Proxy-Authorization: Basic " + token)
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 16384:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    status = re.match(rb"HTTP/1\.[01] (\d{3})", head)
    if not status:
        return "bad_proxy_reply"
    if status.group(1) == b"200":
        return None
    reason = " ".join(rest[:200].decode("utf-8", "replace").split())[:120]
    return status.group(1).decode() + (" " + reason if reason else "")


def _reach_one(host, port, *, timeout, environ, cafile):
    import socket
    import ssl
    proxy = _proxy_for(host, environ)
    row = {"via": "proxy" if proxy else "direct", "status": None, "detail": None}
    if proxy and proxy.get("error"):
        return dict(row, status="unreachable", detail=proxy["error"])
    try:
        sock = socket.create_connection((proxy["host"], proxy["port"]) if proxy else (host, port), timeout=timeout)
    except socket.gaierror:
        return dict(row, status="dns", detail="proxy" if proxy else "host")
    except ConnectionRefusedError:
        return dict(row, status="refused", detail="proxy" if proxy else "host")
    except (socket.timeout, TimeoutError):
        return dict(row, status="timeout")
    except OSError as error:
        return dict(row, status="unreachable", detail=type(error).__name__)
    try:
        if proxy:
            denied = _connect_via(sock, host, port, proxy)
            if denied:
                return dict(row, status="unreachable" if denied == "bad_proxy_reply" else "proxy_denied", detail=denied)
        context = ssl.create_default_context(cafile=cafile)
        with context.wrap_socket(sock, server_hostname=host) as tls:
            return dict(row, status="ok", detail=tls.version())
    except ssl.SSLError as error:
        return dict(row, status="tls_error", detail=getattr(error, "reason", None) or type(error).__name__)
    except (socket.timeout, TimeoutError):
        return dict(row, status="timeout")
    except OSError as error:
        return dict(row, status="unreachable", detail=type(error).__name__)
    finally:
        sock.close()


def reach(hosts, *, timeout=5, environ=None, cafile=None):
    """Opt-in HTTPS reachability: TCP (through HTTPS_PROXY with CONNECT unless NO_PROXY
    covers the host), then a TLS handshake. No HTTP request is sent to the site and
    nothing is read from it; the proxy URL and credentials are never reported.

    ``status`` per host: ``ok`` (``detail`` is the TLS version), ``proxy_denied``
    (``detail`` is the CONNECT status and the proxy's short reason), ``dns``,
    ``refused``, ``timeout``, ``tls_error`` (often a proxy CA missing from the trust
    store; ``SSL_CERT_FILE`` is used when set), ``unreachable`` or ``invalid_host``.
    Hosts are ``name`` or ``name:port`` (default 443).
    """
    import time
    if isinstance(hosts, str):
        raise TypeError("hosts must be a sequence, not a string")
    hosts = list(hosts)
    if not 1 <= len(hosts) <= 20:
        raise ValueError("give 1 to 20 hosts")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError("timeout must be a finite number in (0, 30]")
    environ = os.environ if environ is None else environ
    cafile = cafile or environ.get("SSL_CERT_FILE") or None
    rows = []
    for raw in hosts:
        match = _HOST.match(raw) if isinstance(raw, str) else None
        port = int(match.group(2) or 443) if match else 0
        if not match or ".." in raw or not 0 < port < 65536:
            rows.append({"host": str(raw)[:80], "via": None, "status": "invalid_host", "detail": None, "ms": None})
            continue
        started = time.monotonic()
        row = _reach_one(match.group(1), port, timeout=timeout, environ=environ, cafile=cafile)
        rows.append(dict({"host": raw}, **row, ms=int((time.monotonic() - started) * 1000)))
    return rows


def _playwright_dirs(environ):
    value = environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if value and value != "0":
        return [Path(value)]
    home = Path.home()
    if sys.platform == "win32":
        base = environ.get("LOCALAPPDATA")
        return [Path(base) / "ms-playwright"] if base else []
    if sys.platform == "darwin":
        return [home / "Library" / "Caches" / "ms-playwright"]
    return [Path(environ.get("XDG_CACHE_HOME") or home / ".cache") / "ms-playwright"]


def _uv_python_dirs(environ):
    value = environ.get("UV_PYTHON_INSTALL_DIR")
    if value:
        return [Path(value)]
    if sys.platform == "win32":
        base = environ.get("APPDATA")
        return [Path(base) / "uv" / "python"] if base else []
    return [Path(environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "uv" / "python"]


_VERSION_NAME = re.compile(r"v?(\d+\.\d+\.\d+)")
_PIN_TOKEN = r"(?:[<>=!~^]{0,2}\s*v?\d[\w.*+-]*|lts/[\w*-]+|latest|system|stable|[a-z][\w.-]*\d[\w.-]*)"
_PIN_VALUE = re.compile(_PIN_TOKEN + r"(?:(?:\s*,\s*|\s*\|\|\s*|\s+|:)" + _PIN_TOKEN + ")*")


def _pin_ok(value):
    """A version spec (3.12, >=3.10, lts/*, 3.12:3.11, ^20 || >=22), never free text."""
    return len(value) <= 64 and bool(_PIN_VALUE.fullmatch(value))
# Conventional parents of unpacked Node tarballs / versioned kegs (Windows uses fixed prefixes).
_NODE_PREFIX_PARENTS = {"linux": ("/opt", "/usr/local/lib/nodejs"),
                        "darwin": ("/opt/homebrew/opt", "/usr/local/opt", "/usr/local/lib/nodejs")}


def _node_manager_dirs(environ):
    """(manager, directory) pairs whose children are named after Node versions."""
    home, win, mac = Path.home(), sys.platform == "win32", sys.platform == "darwin"
    local = Path(environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    data = Path(environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    fnm = local / "fnm" if win else home / "Library" / "Application Support" / "fnm" if mac else data / "fnm"
    mise = local / "mise" if win else data / "mise"
    volta = local / "Volta" if win else home / ".volta"
    rows = [("nvm", Path(environ.get("NVM_DIR") or home / ".nvm") / "versions" / "node"),
            ("fnm", Path(environ.get("FNM_DIR") or fnm) / "node-versions"),
            ("volta", Path(environ.get("VOLTA_HOME") or volta) / "tools" / "image" / "node"),
            ("mise", Path(environ.get("MISE_DATA_DIR") or mise) / "installs" / "node"),
            ("asdf", Path(environ.get("ASDF_DATA_DIR") or home / ".asdf") / "installs" / "nodejs")]
    if environ.get("NVM_HOME"):
        rows.append(("nvm-windows", Path(environ["NVM_HOME"])))
    if not win:
        rows.append(("n", Path(environ.get("N_PREFIX") or "/usr/local") / "n" / "versions" / "node"))
    return rows


def _node_binary(prefix):
    for relative in ("bin/node", "node.exe"):
        candidate = prefix / relative
        if candidate.is_file():
            return candidate
    return None


def _node_prefixes(environ):
    """Directories that look like an unpacked Node install (``bin/node`` or ``node.exe`` inside)."""
    if sys.platform == "win32":
        bases = [Path(environ[k]) / rest for k, rest in (("ProgramFiles", "nodejs"), ("LOCALAPPDATA", "Programs/nodejs"))
                 if environ.get(k)]
        return [base for base in bases if _node_binary(base)]
    found = []
    for parent in _NODE_PREFIX_PARENTS.get(sys.platform, _NODE_PREFIX_PARENTS["linux"]):
        try:
            children = sorted(p for p in Path(parent).iterdir() if p.name.startswith("node") and p.is_dir())
        except OSError:
            continue
        found.extend(child for child in children if _node_binary(child))
    return found


def _read_runtime_text(path, limit, *, encoding="utf-8", errors="replace"):
    """Read at most limit bytes from a regular file, including after path races.

    Follow ordinary file symlinks (version-manager layouts use them). On POSIX,
    nonblocking open also prevents a file replaced by a FIFO from hanging.
    """
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise OSError("not a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(fd, "rb", buffering=0, closefd=False) as stream:
            return stream.read(limit).decode(encoding, errors)
    finally:
        os.close(fd)


def _node_header_version(binary):
    """Version from the ``node_version.h`` shipped next to the binary; None without running node."""
    real = Path(os.path.realpath(binary))
    for prefix in (real.parent.parent, real.parent):
        try:
            text = _read_runtime_text(prefix / "include" / "node" / "node_version.h", 65536, encoding="ascii")
        except OSError:
            continue
        parts = dict(re.findall(r"#define\s+NODE_(MAJOR|MINOR|PATCH)_VERSION\s+(\d+)", text))
        if len(parts) == 3:
            return ".".join(parts[k] for k in ("MAJOR", "MINOR", "PATCH"))
    return None


def node_installs(environ):
    """Node installs found by directory names and headers only (node is never run).

    ``source`` is the version manager, ``prefix`` (an unpacked install such as /opt/node24) or
    ``path`` (a binary on PATH that no other source explains). ``version`` is None when it
    cannot be read without running node. ``active`` marks what ``node`` resolves to.
    """
    installs = []
    for source, root in _node_manager_dirs(environ):
        try:
            names = sorted(p.name for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
        installs.extend({"source": source, "version": match.group(1), "path": str(root / name)}
                        for name in names for match in [_VERSION_NAME.fullmatch(name)] if match)
    for prefix in _node_prefixes(environ):
        installs.append({"source": "prefix", "version": _node_header_version(_node_binary(prefix)), "path": str(prefix)})
    on_path = []
    for part in (environ.get("PATH") or "").split(os.pathsep):
        candidate = Path(part) / ("node.exe" if sys.platform == "win32" else "node") if part else None
        try:
            if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
                on_path.append(os.path.realpath(candidate))
        except OSError:
            continue
    for entry in installs:
        root = os.path.realpath(entry["path"])
        entry["on_path"] = any(real == root or real.startswith(root + os.sep) for real in on_path)
        entry["active"] = bool(on_path) and (on_path[0] == root or on_path[0].startswith(root + os.sep))
    known = [os.path.realpath(entry["path"]) for entry in installs]
    for index, real in enumerate(on_path):
        if not any(real == root or real.startswith(root + os.sep) for root in known):
            known.append(real)
            installs.append({"source": "path", "version": _node_header_version(real), "path": real,
                             "on_path": True, "active": index == 0})
    return installs


def _read_pin(path):
    """First meaningful line of a small version file; None when absent, "(unreadable)" when odd."""
    try:
        text = _read_runtime_text(path, 512)
    except OSError:
        return None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            return line if _pin_ok(line) else "(unreadable)"
    return None


def _python_default_pins(environ):
    """Machine-wide Python choices: pyenv's global file and uv's user-level .python-version."""
    home = Path.home()
    pyenv = Path(environ.get("PYENV_ROOT") or home / ".pyenv" / ("pyenv-win" if sys.platform == "win32" else ""))
    base = environ.get("APPDATA") if sys.platform == "win32" else (environ.get("XDG_CONFIG_HOME") or home / ".config")
    rows = [("pyenv", _read_pin(pyenv / "version")),
            ("uv", _read_pin(Path(base) / "uv" / ".python-version") if base else None)]
    return [{"source": source, "value": value} for source, value in rows if value]


def _pyenv_pythons(environ):
    home = Path.home()
    root = Path(environ.get("PYENV_ROOT") or home / ".pyenv" / ("pyenv-win" if sys.platform == "win32" else ""))
    try:
        return sorted(p.name for p in (root / "versions").iterdir()
                      if p.is_dir() and re.fullmatch(r"[A-Za-z0-9._@+-]{1,64}", p.name))
    except OSError:
        return []


def version_pins(directory):
    """Versions the project near ``directory`` asks for, read from small files (nothing is run).

    ``.python-version``, ``.node-version`` and ``.nvmrc`` count from the nearest of six levels
    up (``up`` says how far); ``.venv/pyvenv.cfg``, ``pyproject.toml`` ``requires-python``,
    ``package.json`` ``engines.node`` and ``.tool-versions`` are read in ``directory`` only.
    """
    start = Path(directory).absolute()
    pins = {"python": [], "node": []}
    for name, runtime in ((".python-version", "python"), (".node-version", "node"), (".nvmrc", "node")):
        for up, folder in enumerate([start, *start.parents][:6]):
            value = _read_pin(folder / name)
            if value:
                pins[runtime].append({"source": name, "value": value, "up": up})
                break
    try:
        for line in _read_runtime_text(start / ".venv" / "pyvenv.cfg", 4096).splitlines():
            key, _, value = line.partition("=")
            match = re.match(r"\d+\.\d+(?:\.\d+)?", value.strip())
            if key.strip() in ("version", "version_info") and match:
                pins["python"].append({"source": ".venv/pyvenv.cfg", "value": match.group(0), "up": 0})
                break
    except OSError:
        pass
    try:
        section = None
        for line in _read_runtime_text(start / "pyproject.toml", 262144).splitlines():
            text = line.strip()
            if text.startswith("["):
                section = text
            match = re.fullmatch(r"requires-python\s*=\s*[\"']([^\"']{1,64})[\"']", text)
            if section == "[project]" and match and _pin_ok(match.group(1)):
                pins["python"].append({"source": "pyproject.toml requires-python", "value": match.group(1), "up": 0})
                break
    except OSError:
        pass
    try:
        package = start / "package.json"
        text = _read_runtime_text(package, 262144, errors="strict")
        engines = json.loads(text)["engines"] if len(text.encode("utf-8")) < 262144 else {}
        value = engines.get("node") if isinstance(engines, dict) else None
        if isinstance(value, str) and _pin_ok(value):
            pins["node"].append({"source": "package.json engines.node", "value": value, "up": 0})
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        for line in _read_runtime_text(start / ".tool-versions", 4096).splitlines():
            fields = line.split("#", 1)[0].split()
            runtime = {"python": "python", "nodejs": "node", "node": "node"}.get(fields[0]) if len(fields) >= 2 else None
            if runtime and _pin_ok(fields[1]):
                pins[runtime].append({"source": ".tool-versions", "value": fields[1], "up": 0})
    except OSError:
        pass
    return pins


def runtime_facts(*, environ=None, versions=False, timeout=2):
    """Installed runtimes from directory names only (nothing is run unless ``versions``).

    * Playwright browser builds (``PLAYWRIGHT_BROWSERS_PATH`` or the default cache):
      ``chromium`` (full) and ``chromium_headless_shell`` with revisions, so a job
      can tell whether ``--only-shell`` / ``--no-shell`` matches what is present;
    * uv-managed interpreters (``UV_PYTHON_INSTALL_DIR`` or uv's default);
    * ``python3.X`` executables on PATH (3.8-3.15);
    * pyenv's installed versions and the machine-wide Python choices (pyenv global, uv user pin);
    * Node installs (``node_installs``): version managers, unpacked installs such as /opt/node24,
      and PATH, with versions from directory names or ``node_version.h``;
    * with ``versions``: git's version and whether it has
      ``git merge-tree --write-tree`` (2.38+).
    """
    environ = os.environ if environ is None else environ
    facts = {"playwright": {"path": None, "builds": []}, "uv_pythons": [], "path_pythons": [], "git": None,
             "pyenv_pythons": _pyenv_pythons(environ), "python_defaults": _python_default_pins(environ),
             "node_installs": node_installs(environ)}
    for directory in _playwright_dirs(environ):
        try:
            names = sorted(p.name for p in directory.iterdir() if p.is_dir())
        except OSError:
            continue
        facts["playwright"]["path"] = str(directory)
        for name in names:
            match = re.fullmatch(r"([a-z_]+?)(?:-(\d+))?", name)
            if match and match.group(2):
                facts["playwright"]["builds"].append({"name": match.group(1), "revision": int(match.group(2))})
        break
    for directory in _uv_python_dirs(environ):
        try:
            names = sorted(p.name for p in directory.iterdir() if p.is_dir())
        except OSError:
            continue
        for name in names:
            match = re.fullmatch(r"(cpython|pypy|graalpy)-(\d+\.\d+\.\d+[a-z0-9+]*)-(.+)", name)
            if match:
                facts["uv_pythons"].append({"implementation": match.group(1), "version": match.group(2),
                                            "platform": match.group(3)})
    facts["path_pythons"] = ["3.%d" % minor for minor in range(8, 16) if shutil.which("python3.%d" % minor)]
    if versions:
        row = command_inventory(["git"], versions=True, timeout=timeout)[0]
        parts = tuple(int(x) for x in (row["version"] or "0").split(".")[:2])
        facts["git"] = {"version": row["version"], "status": row["status"],
                        "merge_tree_write_tree": parts >= (2, 38) if row["version"] else None}
    return facts


def python_packages(*, distributions=None):
    """Packages installed for the running interpreter, counted by who installed them.

    Each ``*.dist-info/INSTALLER`` is the one-word file pip, uv, conda and others write
    (``unknown`` when missing or unreadable, e.g. OS-packaged). Nothing is imported or run, but
    Python's installed metadata finder hooks are consulted and must be trusted. A name seen
    twice on ``sys.path`` counts once (first wins, as for import). Errors are reported by
    kind, never by message, and mark the result incomplete; lookup errors are not absence.
    """
    from importlib import metadata
    seen, errors = {}, []
    try:
        for dist in (metadata.distributions() if distributions is None else distributions):
            try:
                name = dist.metadata["Name"]
                if not isinstance(name, str) or not name:
                    raise ValueError("missing package name")
                key = re.sub(r"[-_.]+", "-", name).lower()
                if key in seen:
                    continue
            except Exception as error:
                # Finder implementations may fail too; preserve partial observations.
                errors.append("metadata:" + type(error).__name__)
                continue
            try:
                raw = (dist.read_text("INSTALLER") or "").strip().lower()
                installer = (raw if re.fullmatch(r"[a-z0-9][a-z0-9._+-]{0,31}", raw)
                             else ("other" if raw else "unknown"))
            except Exception as error:
                errors.append("installer:" + type(error).__name__)
                installer = "unknown"
            seen[key] = installer
    except Exception as error:
        errors.append("discovery:" + type(error).__name__)
    installers = {}
    for installer in seen.values():
        installers[installer] = installers.get(installer, 0) + 1
    return {"count": len(seen), "installers": dict(sorted(installers.items())),
            "complete": not errors, "errors": sorted(set(errors))}


def to_text(facts):
    """One "key: value" line per fact; tools as true/false. Easy to grep and paste."""
    def clean(value):
        text = str(value).lower() if isinstance(value, bool) else str(value)
        return "".join("\\u%04x" % ord(c) if ord(c) < 32 or ord(c) == 127 else c for c in text)
    lines = []
    put = lambda key, value: lines.append(clean(key) + ": " + clean(value))
    if facts.get("cwd"):
        put("cwd", facts["cwd"])
    session = facts.get("session")
    if session is not None:
        put("user", "%s (uid %s, root=%s)" % (session["user"], session["uid"], str(session["root"]).lower()))
        put("writable_cwd", session["writable_cwd"])
        put("shell", session["shell"] or "(unset)")
        put("lang", session["lang"] or "(unset)")
        put("timezone", session["timezone"] or "(unknown)")
        put("local_time", session["local_time"])
        put("display", any(session["display"].values()) or "false (headless)")
        put("python_executable", session["python_executable"])
        venv_str = ("true (%s)" % session["virtualenv_name"]) if session.get("virtualenv_name") else str(session["virtualenv"]).lower()
        put("virtualenv", venv_str)
        for name, value in session["ca_env"].items():
            put("ca_env." + name, value)
        put("ci", " ".join("%s=%s" % (k, str(v).lower()) for k, v in session["ci"].items()))
    put("os", " ".join(str(facts["os"][k]) for k in ("system", "release", "machine")))
    if facts.get("os_release"):
        put("os_release", " ".join(facts["os_release"].values()))
    runtime = facts["runtime"]
    put("python", "%s %s %sbit" % (runtime["implementation"], runtime["version"], runtime["bits"]))
    if facts.get("host"):
        put("host", facts["host"]["name"])
    container = facts.get("container")
    if container is not None:
        put("in_container", container["in_container"])
        if container["kinds"]:
            put("container_kinds", ", ".join(container["kinds"]))
        put("virtualized", container["virtualized"])
        if container.get("wsl"):
            put("wsl", container["wsl"])
    network = facts.get("network")
    if network is not None:
        put("hostname", network["hostname"])
        put("ipv4", ", ".join(network["ipv4"]) or "(none)")
        if network["ipv6"]:
            put("ipv6", ", ".join(x["address"] + "%" + x["interface"] for x in network["ipv6"]))
        put("interfaces", ", ".join(x["name"] + "(" + x["state"] + ")" for x in network["interfaces"]) or "(none)")
        route = network["default_route"]
        put("default_gateway", route["gateway"] + " via " + route["interface"] if route else "(none)")
        put("dns", ", ".join(network["dns"]["nameservers"]) or "(none)")
        if network["dns"]["search"]:
            put("dns_search", ", ".join(network["dns"]["search"]))
        for name, value in network["proxy_set"].items():
            put("proxy." + name, value)
        for name, value in (network.get("no_proxy_covers") or {}).items():
            put("proxy.no_proxy_covers." + name, value)
        if network["errors"]:
            put("network_errors", ", ".join(network["errors"]))
    hosts = facts.get("hosts")
    if hosts is not None:
        for name, addresses in hosts["names"].items():
            if addresses or name == "localhost":
                put("hosts." + name, ", ".join(addresses) or "(not in /etc/hosts)")
        if hosts.get("ipv6_loopback") is not None:
            put("localhost.ipv6_loopback", hosts["ipv6_loopback"])
    for name, result in (facts.get("probes") or {}).items():
        if result["ok"]:
            value = "true"
            if result["lines"]:
                value += " " + ("; ".join(result["lines"]) if len(result["lines"]) <= 10
                                else "; ".join(result["lines"][:10]) + "; ... (%d)" % len(result["lines"]))
        else:
            value = "false (" + result.get("error", "failed") + ")"
        put(name, value)
    res = facts.get("resources")
    if res is not None:
        put("cpus", "%s (usable %s, cgroup limit %s)" % (res["cpus"], res["usable_cpus"], res["cpu_limit"] or "none"))
        if res["memory_total_bytes"]:
            put("memory", "%s available of %s (cgroup limit %s, swap %s)" % (
                _gib(res["memory_available_bytes"] or 0), _gib(res["memory_total_bytes"]),
                _gib(res["memory_limit_bytes"]) if res["memory_limit_bytes"] else "none",
                _gib(res["swap_total_bytes"] or 0)))
        if res["load"]:
            put("load", " ".join(res["load"]))
        if res["uptime_seconds"] is not None:
            put("uptime", _duration(res["uptime_seconds"]))
        put("open_files_limit", res["open_files_limit"] or "unlimited")
    workspace = facts.get("workspace")
    if workspace:
        storage = workspace.get("storage")
        if storage:
            put("disk_free", _gib(storage["free_bytes"]) + " of " + _gib(storage["total_bytes"]))
        put("markers", ", ".join(workspace.get("markers", [])) or "(none)")
    for tool in facts.get("commands", []):
        value = tool.get("available")
        if tool.get("version"):
            value = "true " + tool["version"]
        put("tool." + tool["name"], value)
    runtimes = facts.get("runtimes")
    if runtimes is not None:
        builds = runtimes["playwright"]["builds"]
        put("playwright_browsers", ", ".join("%s-%d" % (b["name"], b["revision"]) for b in builds)
            or ("(none in %s)" % runtimes["playwright"]["path"] if runtimes["playwright"]["path"] else "(no cache)"))
        if builds:
            names = {b["name"] for b in builds}
            put("playwright_chromium", "full+shell" if {"chromium", "chromium_headless_shell"} <= names
                else "full only (--no-shell)" if "chromium" in names
                else "shell only (--only-shell)" if "chromium_headless_shell" in names else "none")
        put("uv_pythons", ", ".join(p["version"] for p in runtimes["uv_pythons"]) or "(none)")
        put("path_pythons", ", ".join(runtimes["path_pythons"]) or "(none)")
        if runtimes.get("pyenv_pythons"):
            put("pyenv_pythons", ", ".join(runtimes["pyenv_pythons"]))
        if runtimes.get("python_defaults") is not None:
            put("python_defaults", ", ".join("%(source)s=%(value)s" % d for d in runtimes["python_defaults"]) or "(none)")
        if runtimes.get("node_installs") is not None:
            put("node_installs", ", ".join(
                "%s [%s%s]" % (n["version"] or "?", n["source"], ", active" if n["active"] else ", on PATH" if n["on_path"] else "")
                for n in runtimes["node_installs"]) or "(none)")
        if runtimes["git"]:
            put("git_merge_tree_write_tree", runtimes["git"]["merge_tree_write_tree"])
    for runtime, pins in sorted((facts.get("pins") or {}).items()):
        put("pin." + runtime, ", ".join("%s=%s%s" % (d["source"], d["value"], " (up %d)" % d["up"] if d["up"] else "")
                                         for d in pins) or "(none)")
    packages = facts.get("python_packages")
    if packages is not None:
        put("python_packages", "%d (%s)%s" % (packages["count"], ", ".join(
            "%s %d" % item for item in packages["installers"].items()) or "none",
            " [partial]" if packages["errors"] else ""))
        if packages["errors"]:
            put("python_packages_errors", ", ".join(packages["errors"]))
    listeners = facts.get("listeners")
    if listeners is not None:
        if not listeners.get("measured"):
            put("listening", "unmeasured (" + ", ".join(listeners.get("errors") or ["unknown"]) + ")")
        elif "bindings" in listeners:
            show = lambda b: ("[%s]" % b["address"] if ":" in b["address"] else b["address"]) + ":%d" % b["port"]
            put("listening", ", ".join(show(b) for b in listeners["bindings"]) or "(none)")
        else:
            put("listening_tcp_ports", ", ".join(map(str, listeners["tcp_ports"])) or "(none)")
    return "\n".join(lines) + "\n"


def main(argv=None):
    """Direct single-file entry point; no-argument use observes current workspace."""
    import argparse
    parser = argparse.ArgumentParser(description="Read-only AI environment introduction")
    parser.suggest_on_error = True  # 🤔 argparse 3.14+: "maybe you meant" for choices; older Pythons ignore it
    parser.add_argument("--directory", default=".")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    parser.add_argument("--versions", action="store_true")
    parser.add_argument("--minimal", action="store_true",
                        help="OS/runtime only; omit workspace and tool observations")
    parser.add_argument("--no-network", action="store_true",
                        help="omit host name, addresses, routes, DNS and container hints")
    parser.add_argument("--no-probes", action="store_true",
                        help="do not run the docker / nvidia-smi probes")
    parser.add_argument("--reach", nargs="+", metavar="HOST",
                        help="opt-in: TCP + TLS handshake to each HOST[:PORT] (via HTTPS_PROXY unless NO_PROXY); "
                             "prints one line per host and exits 1 unless all are ok")
    parser.add_argument("--reach-timeout", type=float, default=5)
    parser.add_argument("--runner-env", action="store_true",
                        help="emit CI runner image fingerprint (offline by default)")
    parser.add_argument("--runner-env-json", action="store_true",
                        help="with --runner-env, print runner-fingerprint/1 JSON instead of summary")
    parser.add_argument("--runner-env-imds", action="store_true",
                        help="with --runner-env, also query cloud instance metadata (short timeout)")
    parser.add_argument("--runner-env-dpkg-list", metavar="PATH",
                        help="with --runner-env on Linux, write full dpkg-query list to PATH")
    parser.add_argument("--runner-env-github-summary", action="store_true",
                        help="with --runner-env, append summary to GITHUB_STEP_SUMMARY when set")
    args = parser.parse_args(argv)
    runner_flags = (args.runner_env_json or args.runner_env_imds or args.runner_env_dpkg_list
                    or args.runner_env_github_summary)
    if runner_flags and not args.runner_env:
        print("runner-env flags require --runner-env", file=sys.stderr)
        return 2
    if args.reach:
        try:
            rows = reach(args.reach, timeout=args.reach_timeout)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
        if args.format == "json":
            print(to_json({"reach": rows}), end="")
        else:
            for row in rows:
                detail = " (%s)" % row["detail"] if row["detail"] else ""
                via = " via " + row["via"] if row["via"] else ""
                ms = " %dms" % row["ms"] if row["ms"] is not None else ""
                print("reach.%s: %s%s%s%s" % (row["host"], row["status"], detail, via, ms))
        return 0 if all(row["status"] == "ok" for row in rows) else 1
    if args.runner_env:
        fingerprint = runner_fingerprint(dpkg_list_path=args.runner_env_dpkg_list,
                                         imds=args.runner_env_imds)
        if args.runner_env_json:
            print(to_json(fingerprint), end="")
        else:
            print(runner_fingerprint_summary(fingerprint), end="")
        if args.runner_env_github_summary:
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                try:
                    with open(summary_path, "a", encoding="utf-8") as stream:
                        stream.write("\n## Runner fingerprint\n\n")
                        stream.write(runner_fingerprint_summary(fingerprint))
                except OSError as error:
                    print("GITHUB_STEP_SUMMARY: " + type(error).__name__, file=sys.stderr)
        return 0
    try:
        facts = collect() if args.minimal else diagnose(
            directory=args.directory, versions=args.versions)
    except (OSError, ValueError) as error:
        print(type(error).__name__, file=sys.stderr)
        return 2
    if not args.minimal:
        facts["cwd"] = str(Path(args.directory).absolute())
        facts["session"] = session_facts()
        facts["resources"] = resource_facts()
        if not args.no_network:
            facts["listeners"] = listener_ports(addresses=True)
        if not args.no_network:
            facts["container"] = container_facts()
            facts["network"] = network_facts()
            facts["hosts"] = hosts_facts()
        if not args.no_probes:
            facts["probes"] = probe_all()
        facts["runtimes"] = runtime_facts(versions=args.versions)
        facts["pins"] = version_pins(args.directory)
        facts["python_packages"] = python_packages()
    render = {"json": to_json, "markdown": to_markdown, "text": to_text}[args.format]
    print(render(facts), end="")
    partial = bool(facts.get("workspace") and facts["workspace"]["errors"])
    partial |= bool(facts.get("python_packages", {}).get("errors"))
    partial |= any(row["status"] in ("timeout", "execution_error", "nonzero_exit",
                                    "unrecognized_version")
                   for row in facts.get("commands", []))
    return 2 if partial else 0


if __name__ == "__main__":
    raise SystemExit(main())

'''
# END BUNDLED YOURSELF

if __name__ == "__main__":
    sys.exit(main())
