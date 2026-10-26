# -*- coding: utf-8 -*-
"""uploads/kapt/ 에 올린 K-APT '입찰결과' 엑셀 → data/apt_sales.json 의 결과(낙찰금액·낙찰업체·세대수)
엑셀 형식이 xlsx·xls·HTML 표(.xls 확장자) 어느 것이든 머리글 이름으로 열을 찾는다.
같은 공고(단지명+공고명+마감일)는 한 번만 반영하고, 목록 공고와 맞으면 그 공고에 결과를 붙인다.
처리한 원본 파일 목록을 출력한다(워크플로가 원본을 지우고 결과만 커밋)."""
import io, os, re, sys, glob, html, zipfile
from collections import Counter
from common import load, save, now_kst
from collect_apt import KEEP, DROP, OUT

UP = "uploads/kapt"
COLS = {"apt": r"단지명", "hh": r"세대수", "title": r"(?:입찰)?공고명|입찰명", "end": r"마감|개찰|계약일|등록일",
        "amount": r"낙찰금액|계약금액", "winner": r"낙찰업체|계약업체|업체명", "bid": r"응찰금액", "area": r"지역|주소|시도"}


def rows_xlsx(b):
    from collect_biogas import _xlsx_sheets
    out = []
    for rows in _xlsx_sheets(b).values():
        for r in rows:                    # 빈 칸이 있어도 열 위치가 밀리지 않게 열 문자 → 번호로 채운다
            idx = lambda c: sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(c))) - 1
            n = max(idx(c) for c in r) + 1
            row = [""] * n
            for c, v in r.items():
                row[idx(c)] = str(v)
            out.append(row)
    return out


def rows_xls(b):
    import xlrd
    wb = xlrd.open_workbook(file_contents=b)
    out = []
    for sh in wb.sheets():
        for i in range(sh.nrows):
            out.append([str(v).strip() for v in sh.row_values(i)])
    return out


def rows_html(b):
    t = b.decode("utf8", "ignore")
    if "<td" not in t.lower():
        t = b.decode("cp949", "ignore")
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S | re.I)]
        if cells:
            out.append(cells)
    return out


def read_any(path):
    b = open(path, "rb").read()
    if b[:2] == b"PK":
        return rows_xlsx(b)
    if b[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return rows_xls(b)
    return rows_html(b)


def num(s):
    s = re.sub(r"[^\d.\-]", "", str(s or ""))
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def nz(t):
    return re.sub(r"[\s\[\]()（）·ㆍ\-_,.]", "", t or "")


def parse(rows):
    hi = next((i for i, r in enumerate(rows) if any(re.search(COLS["apt"], c) for c in r) and
               any(re.search(COLS["amount"], c) for c in r)), None)
    if hi is None:
        raise ValueError("머리글(단지명·낙찰금액) 행을 찾지 못함")
    head = rows[hi]
    idx = {}
    for k, rx in COLS.items():
        j = next((j for j, c in enumerate(head) if re.search(rx, c) and j not in idx.values()), None)
        if j is not None:
            idx[k] = j
    print(f">> 머리글: {head}\n>> 열 대응: {idx}")
    out = []
    for r in rows[hi + 1:]:
        g = lambda k: r[idx[k]].strip() if k in idx and idx[k] < len(r) else ""
        if not g("apt") or not g("title"):
            continue
        end = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", g("end"))
        out.append({"apt": g("apt"), "households": int(num(g("hh")) or 0) or None, "title": g("title"),
                    "end": f"{end.group(1)}-{int(end.group(2)):02d}-{int(end.group(3)):02d}" if end else "",
                    "amount": num(g("amount")), "winner": g("winner"), "bid_amount": num(g("bid")), "area": g("area")})
    return out


def main():
    files = sorted(glob.glob(f"{UP}/*.xls*") + glob.glob(f"{UP}/*.htm*") + glob.glob(f"{UP}/*.csv"))
    if not files:
        print(">> 올라온 엑셀 없음")
        return
    st = load(OUT, {}) or {}
    res = {r["key"]: r for r in st.get("results", [])}
    items = st.get("items", [])
    n_add = n_match = 0
    for f in files:
        try:
            got = parse(read_any(f))
        except Exception as e:
            print(f">> {f} 읽기 실패: {type(e).__name__}: {e}")
            continue
        keep = [r for r in got if KEEP.search(r["title"]) and not DROP.search(r["title"])]
        print(f">> {os.path.basename(f)}: {len(got)}행 중 재활용 관련 {len(keep)}행")
        for r in keep:
            r["key"] = f"{nz(r['apt'])}|{nz(r['title'])[:30]}|{r['end']}"
            if r["key"] not in res:
                n_add += 1
            res[r["key"]] = {**res.get(r["key"], {}), **r, "file": os.path.basename(f), "added": now_kst().strftime("%Y-%m-%d")}
    # 목록 공고와 맞추기: 같은 단지 + 공고명이 겹치고 마감일이 같은(±3일) 공고
    for r in res.values():
        for it in items:
            if nz(it.get("apt")) != nz(r["apt"]):
                continue
            t1, t2 = nz(re.sub(r"^\[[^\]]+\]", "", it.get("title", ""))), nz(r["title"])
            same_title = t1[:12] == t2[:12] or t1 in t2 or t2 in t1
            d1, d2 = (it.get("end") or "")[:10], r["end"]
            near = d1 and d2 and abs((int(d1.replace("-", "")) - int(d2.replace("-", "")))) <= 3
            if same_title and (near or not d2):
                it.update(win_amt=r["amount"], winner=r["winner"], households=r["households"], result_key=r["key"])
                r["matched"] = it["id"]
                n_match += 1
                break
    st["results"] = sorted(res.values(), key=lambda r: r.get("end") or "", reverse=True)
    st["items"] = items
    st["results_updated"] = now_kst().strftime("%Y-%m-%d %H:%M")
    save(OUT, st)
    print(f">> 결과 반영: 새로 {n_add}건, 누적 {len(res)}건, 공고와 연결 {n_match}건")
    print("PROCESSED:" + "|".join(files))
    for r in st["results"][:10]:
        hh = r.get("households") or 0
        per = f" · 세대당 {r['amount'] / hh:,.0f}원" if r.get("amount") and hh else ""
        print(f"   {r['end']} | {r['apt'][:14]} ({hh}세대) | {r['title'][:30]} | 낙찰 {r.get('amount')}{per} | {r.get('winner', '')[:14]}")


if __name__ == "__main__":
    main()
