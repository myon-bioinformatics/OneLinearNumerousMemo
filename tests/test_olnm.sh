#!/usr/bin/env bash
# 🧪 smoke test: syntax, step budget, every helped function is defined, offline helpers work
set -eu; cd "$(dirname "$0")/.."
bash -n olnm.sh && echo "✅ syntax"
. ./olnm.sh
n=$(olnm_steps); [ "$n" -lt 1000 ] && echo "✅ steps $n < 1000" || { echo "❌ steps $n"; exit 1; }
miss=0; for f in $(grep -oE '^# [^ ]+ [a-zA-Z_0-9]+:' olnm.sh | awk '{sub(/:$/,"",$3);print $3}'); do declare -F "$f" >/dev/null || { echo "❌ no function $f"; miss=1; }; done
[ $miss = 0 ] && echo "✅ every help line has a function"
dup=$(grep -oE '^[a-zA-Z_0-9]+\(\)' olnm.sh | sort | uniq -d); [ -z "$dup" ] && echo "✅ no duplicate names" || { echo "❌ dup: $dup"; exit 1; }
[ "$(pycalc '2**10')" = 1024 ] && [ "$(ncalc '2**10')" = 1024 ] && echo "✅ calc"
[ "$(printf '1\n2\n' | nums)" = "n=2 sum=3 avg=1.5 min=1 max=2" ] && echo "✅ nums"
[ "$(echo 'x a@b.co 10.0.0.1' | redact)" = "x <email> <ip>" ] && echo "✅ redact"
d=$(mktemp -d); echo hi > "$d/a"; hashdir "$d" >/dev/null && verifydir "$d" >/dev/null && echo "✅ hashdir/verifydir"
echo '{"a":1}' | jsonf >/dev/null && echo "✅ jsonf"
[ "$(olnm_offline | grep -c 🌍)" = 0 ] && echo "✅ offline list clean"
echo "🎉 ok"
