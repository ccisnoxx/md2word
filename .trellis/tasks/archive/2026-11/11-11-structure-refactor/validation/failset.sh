#!/bin/sh
# 从 unittest 日志提取失败/错误用例标识（含子测试参数），排序去重，用于与基线对比。
grep -E "^(ERROR|FAIL): " "$1" | sed -E 's/^(ERROR|FAIL): //' | sort
