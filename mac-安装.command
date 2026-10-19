#!/bin/bash
# macOS 安装：在“终端”里运行，或右键 → 打开
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "没有找到 python3，请先安装 Python 3.10+：https://www.python.org/downloads/"
  exit 1
fi
python3 tools/setup.py
