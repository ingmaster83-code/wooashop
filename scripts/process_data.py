#!/usr/bin/env python3
"""
process_data.py (우아가게) - 행안부 LOCALDATA 세탁업·안경업소·인쇄사·이용업·동물미용업 CSV(영업/정상)를 가공한다.
입력: data/raw/{laundries,optical_shops,printing_shops,barber_shops,pet_grooming}.csv  출력: _rawdata/sh_{시도}.json, search_index.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_localdata import *  # noqa

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
CATMETA = {"세탁소": ("laundry", "👔"), "빨래방": ("self-laundry", "🧺"), "운동화세탁": ("shoe-wash", "👟"), "안경점": ("optical", "👓"),
           "인쇄소": ("printing", "🖨️"), "이발소": ("barber", "💈"), "애견미용": ("pet-grooming", "🐶")}


def rows(name):
    for r in read_csv_rows(RAW / f"{name}.csv"):
        if clean(r.get("영업상태명")) == "영업/정상":
            yield r


def base_record(r, tf, cat):
    lat, lng = to_wgs(tf, r.get("좌표정보(X)"), r.get("좌표정보(Y)"))
    return dict(name=clean(r.get("사업장명")), cat=cat, road=r.get("도로명주소"), lot=r.get("지번주소"), tel=r.get("전화번호"),
                permit=r.get("인허가일자"), upd=clean(r.get("최종수정시점"))[:10], lat=lat, lng=lng, extras=[], hrows=[], note="")


def main():
    tf = make_transformer()
    records = []

    for r in rows("laundries"):
        name = clean(r.get("사업장명"))
        biz = clean(r.get("업태구분명"))
        if "운동화" in biz or "운동화" in name:
            cat = "운동화세탁"
        elif biz == "빨래방업" or any(k in name for k in ("빨래방", "코인", "셀프", "워시")):
            cat = "빨래방"
        else:
            cat = "세탁소"
        rec = base_record(r, tf, cat)
        wm = int(num(r.get("세탁기수")))
        area = num(r.get("소재지면적"))
        if wm > 0:
            rec["extras"].append({"l": "세탁기 수", "v": f"{wm}대"})
            rec["hrows"].append({"i": "🧺", "t": f"세탁기 {wm}대"})
            rec["note"] = f"세탁기 {wm}대"
        if biz:
            rec["subtype"] = biz
        if area > 0:
            rec["extras"].append({"l": "면적", "v": f"{area:.0f}㎡"})
        records.append(rec)

    for r in rows("optical_shops"):
        rec = base_record(r, tf, "안경점")
        area = num(r.get("총면적")) or num(r.get("소재지면적"))
        if area > 0:
            rec["extras"].append({"l": "면적", "v": f"{area:.0f}㎡"})
        records.append(rec)

    for r in rows("printing_shops"):
        rec = base_record(r, tf, "인쇄소")
        area = num(r.get("시설면적")) or num(r.get("소재지면적"))
        if area > 0:
            rec["extras"].append({"l": "면적", "v": f"{area:.0f}㎡"})
        records.append(rec)

    for r in rows("barber_shops"):
        rec = base_record(r, tf, "이발소")
        chairs = int(num(r.get("의자수")))
        area = num(r.get("소재지면적"))
        if chairs > 0:
            rec["extras"].append({"l": "의자 수", "v": f"{chairs}개"})
            rec["hrows"].append({"i": "💈", "t": f"의자 {chairs}개"})
            rec["note"] = f"의자 {chairs}개"
        if area > 0:
            rec["extras"].append({"l": "면적", "v": f"{area:.0f}㎡"})
        records.append(rec)

    for r in rows("pet_grooming"):
        rec = base_record(r, tf, "애견미용")
        records.append(rec)

    finalize(records, ROOT / "_rawdata", "sh", ROOT, CATMETA)


if __name__ == "__main__":
    main()
