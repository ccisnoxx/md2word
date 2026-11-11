#!/bin/zsh
# 用法：equiv.sh <输出名> [--compare 基线]；固定 PYTHONHASHSEED，避免 renderer_metadata 中 set 迭代顺序随进程变化；固定输入为提交样本 + 主仓库本地 mineru_result 下的全部包（只读）。
V=${0:A:h}; out=$1; shift
extra=(); for d in /Users/sc/PycharmProjects/md2word/mineru_result/*(/); do extra+=(--extra-input "$d"); done
PYTHONHASHSEED=0 ../../../.venv/bin/python $V/../verify_render_equivalence.py --output $V/$out "${extra[@]}" "$@"
