#!/usr/bin/env python3
"""_rawdata/{prefix}*.json 샤드의 전체 항목 수를 출력한다. (월간 갱신 워크플로의 전후 비교용)
사용: python scripts/count_rawdata.py sh_
"""
import glob, json, sys
from pathlib import Path

prefix = sys.argv[1] if len(sys.argv) > 1 else "sh_"
root = Path(__file__).parent.parent / "_rawdata"
total = 0
for f in sorted(glob.glob(str(root / f"{prefix}*.json"))):
    if "raw" in Path(f).name:
        continue
    total += len(json.loads(Path(f).read_text(encoding="utf-8")))
print(total)
