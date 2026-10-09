#!/usr/bin/env python3
"""
lib_localdata.py - 행안부 LOCALDATA 업종 CSV(CP949, EPSG:5174) / 표준데이터 JSON 을 종류·동 허브용 JSON 으로 가공하는 공용 함수.
우아놀거리·우아가게·우아화장실이 같은 파일을 각자 scripts/ 에 복사해 쓴다.
"""
import csv, hashlib, io, json, re
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)

DO_MAP = {
    "서울특별시": "서울", "서울": "서울", "부산광역시": "부산", "부산": "부산", "대구광역시": "대구", "대구": "대구", "인천광역시": "인천", "인천": "인천",
    "광주광역시": "광주", "광주": "광주", "대전광역시": "대전", "대전": "대전", "울산광역시": "울산", "울산": "울산", "세종특별자치시": "세종", "세종": "세종",
    "경기도": "경기", "경기": "경기", "강원특별자치도": "강원", "강원도": "강원", "강원": "강원", "충청북도": "충북", "충북": "충북", "충청남도": "충남", "충남": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북", "전라남도": "전남", "전남": "전남", "경상북도": "경북", "경북": "경북", "경상남도": "경남", "경남": "경남",
    "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
}
DONG_TOKEN = re.compile(r"^[가-힣][가-힣0-9]*(?:동|읍|면)$|^[가-힣]+\d+가$")
BUILDING_LABEL = re.compile(r"^[가나다라마바사아자차카타파하]동$")
CATSLUG = {}


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def num(s):
    try:
        v = float(str(s).replace(",", "").strip())
        return v
    except (ValueError, TypeError):
        return 0.0


def split_address(addr):
    toks = addr.split()
    if len(toks) < 2:
        return None, None, []
    sido_full = toks[0]
    if sido_full in ("세종특별자치시", "세종"):
        return sido_full, "세종시", toks[1:]
    sg = toks[1]
    rest = toks[2:]
    if sg.endswith("시") and rest and rest[0].endswith("구") and len(rest[0]) > 1:
        sg = f"{sg} {rest[0]}"
        rest = rest[1:]
    return sido_full, sg, rest


def find_dong(tokens):
    for t in tokens[:4]:
        t = t.strip("(),")
        if DONG_TOKEN.match(t) and not BUILDING_LABEL.match(t):
            return t
    return None


def dong_from_paren(addr):
    for m in re.finditer(r"\(([^)]*)\)", addr):
        for part in re.split(r"[,\s]+", m.group(1)):
            if DONG_TOKEN.match(part) and not BUILDING_LABEL.match(part):
                return part
    return None


def fmt_tel(t):
    d = re.sub(r"\D", "", t or "")
    if len(d) < 8:
        return ""
    if d.startswith("02"):
        return f"02-{d[2:-4]}-{d[-4:]}" if len(d) >= 9 else ""
    if len(d) in (10, 11) and d.startswith("0"):
        return f"{d[:3]}-{d[3:-4]}-{d[-4:]}"
    if len(d) == 8:
        return f"{d[:4]}-{d[4:]}"
    return ""


def make_slug(name, addr):
    base = re.sub(r"[^\w가-힣\s-]", "", name).strip()
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base)[:24].strip("-")
    h = hashlib.md5(f"{name}|{addr}".encode("utf-8")).hexdigest()[:6]
    return f"{base}-{h}" if base else h


def read_csv_rows(path):
    with open(path, "rb") as f:
        rdr = csv.DictReader(io.TextIOWrapper(f, encoding="cp949", errors="replace", newline=""))
        for r in rdr:
            yield r


def make_transformer():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)


def to_wgs(tf, x, y):
    try:
        x, y = clean(x), clean(y)
        if x and y:
            lo, la = tf.transform(float(x), float(y))
            if 33 <= la <= 39 and 124 <= lo <= 132:
                return round(la, 6), round(lo, 6)
    except ValueError:
        pass
    return None, None


def region_of(lot, road):
    """(doShort, sigungu, dong) — 지번주소 우선, 동은 지번→도로명 괄호 순."""
    sido_full, sg, rest = split_address(lot or road)
    if not sido_full:
        return None, None, None
    if sido_full == "전남광주통합특별시":
        do = "광주" if (sg or "").endswith("구") else "전남"
    else:
        do = DO_MAP.get(sido_full)
    if not do or not sg:
        return None, None, None
    dong = find_dong(rest) or dong_from_paren(road or "") or "기타"
    return do, sg, dong


def finalize(records, out_dir, prefix, root, catmeta, search_index_name="search_index.json"):
    """records: dict 목록(name, cat, road, lot, tel, permit, upd, lat, lng, extras, hrows, note, subtype)
    catmeta: {cat: (slug, icon)}. 시도별 샤드 + 검색 인덱스를 쓴다."""
    items, seen, dedupe, skipped = [], Counter(), set(), Counter()
    for r in records:
        name = clean(r["name"])
        road, lot = clean(r.get("road")), clean(r.get("lot"))
        addr = road or lot
        if not name or not addr:
            skipped["no_name_addr"] += 1
            continue
        do, sg, dong = region_of(lot, road)
        if not do:
            skipped["bad_region"] += 1
            continue
        key = (name, addr, r["cat"])
        if key in dedupe:
            skipped["duplicate"] += 1
            continue
        dedupe.add(key)
        slug = make_slug(name, addr)
        seen[slug] += 1
        if seen[slug] > 1:
            slug = f"{slug}-{seen[slug]}"
        cslug, icon = catmeta[r["cat"]]
        items.append({
            "slug": slug, "facilityName": name, "cat": r["cat"], "catSlug": cslug, "catLabel": r["cat"], "catIcon": icon,
            "doShort": do, "sigungu": sg, "sgSlug": sg.replace(" ", "-"), "dong": dong,
            "road": road, "lot": lot, "tel": fmt_tel(r.get("tel")), "lat": r.get("lat") or "", "lng": r.get("lng") or "",
            "permit": clean(r.get("permit")), "upd": clean(r.get("upd")),
            "extras": r.get("extras") or [], "hrows": r.get("hrows") or [], "note": clean(r.get("note")), "subtype": clean(r.get("subtype")),
            "openTime": clean(r.get("openTime")),
        })
    by_dong_cat = defaultdict(list)
    for i in items:
        by_dong_cat[(i["doShort"], i["sigungu"], i["dong"], i["cat"])].append(i)
    for lst in by_dong_cat.values():
        lst.sort(key=lambda x: (x["permit"] or "9999", x["slug"]))
        for rank, i in enumerate(lst, 1):
            i["catDongCount"] = len(lst)
            i["catDongRank"] = rank
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{prefix}_*.json"):
        old.unlink()
    by_do = defaultdict(list)
    for i in items:
        by_do[i["doShort"]].append(i)
    for do, group in by_do.items():
        (out_dir / f"{prefix}_{do}.json").write_text(json.dumps(group, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    index = [{"n": i["facilityName"], "s": i["slug"], "do": i["doShort"], "sg": i["sigungu"], "dg": i["dong"], "c": i["catLabel"]} for i in items]
    Path(root, search_index_name).write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cats = Counter(i["cat"] for i in items)
    dongs = Counter((i["doShort"], i["sigungu"], i["dong"]) for i in items)
    catdongs = Counter((i["cat"], i["doShort"], i["sigungu"], i["dong"]) for i in items)
    print(f"총 {len(items):,}곳 (제외 {dict(skipped)}), 종류별 {dict(cats)}")
    print(f"시군구 {len({(i['doShort'], i['sigungu']) for i in items})}개, 동 {len(dongs)}개, 종류×동(≥2) {sum(1 for v in catdongs.values() if v >= 2)}개, 동 '기타' {sum(1 for i in items if i['dong'] == '기타')}")
    return items
