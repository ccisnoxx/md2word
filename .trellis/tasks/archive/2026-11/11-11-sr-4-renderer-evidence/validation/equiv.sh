#!/bin/zsh
# 用法：equiv.sh <输出名> [--compare 基线]；固定 PYTHONHASHSEED，避免 renderer_metadata 中 set 迭代顺序随进程变化；固定输入为提交样本 + 本地 mineru_result 下的全部包（只读；目录由 MD2WORD_MINERU_RESULT_DIR 指定，默认相对 worktree 根为 ../../../mineru_result）。
V=${0:A:h}; out=$1; shift
extra=(); for d in ${MD2WORD_MINERU_RESULT_DIR:-../../../mineru_result}/*(/); do extra+=(--extra-input "$d"); done
PYTHONHASHSEED=0 ../../../.venv/bin/python $V/../verify_render_equivalence.py --output $V/$out "${extra[@]}" "$@"
