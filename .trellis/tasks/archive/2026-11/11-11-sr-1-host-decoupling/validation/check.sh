#!/bin/zsh
# 用法：check.sh <标签> <测试模块...>；运行指定模块，并与基线中这些模块的失败集合对比。
V=${0:A:h}; label=$1; shift
../../../.venv/bin/python -m unittest "$@" > $V/$label.log 2>&1
tail -1 $V/$label.log
$V/failset.sh $V/baseline-targeted.log | grep -E "$(printf '%s\\.|' "$@" | sed 's/|$//')" > $V/$label.expected
$V/failset.sh $V/$label.log > $V/$label.actual
if diff -q $V/$label.expected $V/$label.actual >/dev/null; then echo "失败集合与基线一致（$(wc -l < $V/$label.actual | tr -d ' ') 项）"; else echo "失败集合有差异："; diff $V/$label.expected $V/$label.actual | head -20; fi
