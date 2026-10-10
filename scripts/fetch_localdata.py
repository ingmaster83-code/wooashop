#!/usr/bin/env python3
"""LOCALDATA 업종 CSV 다운로드: python scripts/fetch_localdata.py key1 key2 ... -> data/raw/{key}.csv
(월간 갱신 워크플로용. 응답이 너무 작거나 '영업상태명' 헤더가 없으면 실패한다.)"""
import sys, time
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8")
RAW = Path(__file__).parent.parent / "data" / "raw"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

RAW.mkdir(parents=True, exist_ok=True)
for key in sys.argv[1:]:
    url = f"https://file.localdata.go.kr/file/download/{key}/info"
    h = dict(H, Referer=f"https://file.localdata.go.kr/file/{key}/info")
    for attempt in range(3):
        try:
            r = requests.get(url, headers=h, timeout=600)
            r.raise_for_status()
            if len(r.content) < 2000:
                raise ValueError(f"응답이 너무 작음({len(r.content)}B)")
            if "영업상태명" not in r.content[:2000].decode("cp949", errors="replace"):
                raise ValueError("헤더에 영업상태명이 없음")
            (RAW / f"{key}.csv").write_bytes(r.content)
            print(f"[{key}] {len(r.content) / 1e6:.1f}MB", flush=True)
            break
        except Exception as e:
            print(f"[{key}] 재시도 {attempt + 1}: {e}", flush=True)
            time.sleep(3)
    else:
        raise SystemExit(f"[{key}] 다운로드 실패")
