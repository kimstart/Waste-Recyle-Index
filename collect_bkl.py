# -*- coding: utf-8 -*-
"""태평양(BKL) 월간 '환경 주요 정책 동향' 뉴스레터 → data/bkl_policy.json
매달 중순 올라오는 PDF에서 ① 기후부 법령·고시 개정 ② 입법·행정예고 ③ 의원 입법 발의 표를 읽어
폐플라스틱·바이오가스 관련 항목만 고른다. 저작물 보호를 위해 요약문은 저장하지 않고
날짜·법령명·분야 같은 사실 정보와 원문 PDF 링크만 남긴다(본문은 분류에만 쓴다).
pdfplumber 필요."""
import io, re, time, urllib.request
from common import load, save, now_kst

OUT = "data/bkl_policy.json"
BASE = "https://www.bkl.co.kr"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
TITLE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*환경\s*주요\s*정책\s*동향")
SEC = {"II": "법령·고시 개정", "III": "입법·행정예고", "IV": "의원 발의"}
KW = {
    "plastic": re.compile(r"폐기물|재활용|재생원료|플라스틱|순환경제|순환이용|자원의\s*절약|포장|1회용|일회용|생산자책임|EPR|분리\s*수거|분리\s*배출|선별시설|폐비닐|페트|용기"),
    "biogas": re.compile(r"바이오|유기성|음식물|가축분뇨|분뇨|슬러지|하수\s*찌꺼기|공급\s*의무화|혼합\s*의무화|RPS|REC|재생에너지\s*개발|재생에너지법|신에너지|도시가스|"
                         r"수소경제|청정수소|배출권|탄소중립·녹색성장|온실가스\s*감축"),
}
# 표의 열 경계(x, pt): 날짜 | 법령명 | 주요 내용 | 분야
X_NAME, X_BODY, X_FIELD = 117, 257, 477


def fetch(url, n=10_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r:
        return r.read(n)


def page_title(no):
    h = fetch(f"{BASE}/law/insight/newsletter/{no}", 400_000).decode("utf8", "ignore")
    m = re.search(r"<title>(.*?)</title>", h, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def ymd(txt, base_y, base_m):
    """'9. 15.' / '‘27. 3. 16.' → 'YYYY-MM-DD' (연도가 없으면 호의 연도, 호 월보다 3달 넘게 앞서면 다음 해)"""
    m = re.search(r"(?:[‘'’]?(\d{2})\.\s*)?(\d{1,2})\.\s*(\d{1,2})\.?", txt or "")
    if not m:
        return ""
    y = 2000 + int(m.group(1)) if m.group(1) else base_y
    mo, d = int(m.group(2)), int(m.group(3))
    if not m.group(1) and mo < base_m - 3:
        y += 1
    return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else ""


def parse(pdf_bytes, base_y, base_m):
    import pdfplumber
    rows, sec, prev = [], None, None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for p in pdf.pages:
            words = p.extract_words()
            # 장 제목(II. / III. / IV. / V.) 위치
            heads = sorted((w["top"], k) for w in words for k in ("II", "III", "IV", "V") if w["text"] == k + "." and w["x0"] < 80)
            ys = sorted({round(e["top"]) for e in p.horizontal_edges if e["x1"] - e["x0"] > 200})
            bands = [(a, b) for a, b in zip(ys, ys[1:]) if b - a > 12]
            first = True
            for top, bot in bands:
                for y, k in heads:
                    if y < top:
                        sec = k if k in SEC else None
                if not sec:
                    prev = None
                    continue
                ws = [w for w in words if top <= (w["top"] + w["bottom"]) / 2 < bot]
                col = lambda lo, hi: " ".join(w["text"] for w in sorted(ws, key=lambda w: (round(w["top"]), w["x0"])) if lo <= w["x0"] < hi)
                d, name, body, field = col(0, X_NAME), col(X_NAME, X_BODY), col(X_BODY, X_FIELD), col(X_FIELD, 999)
                if (re.search(r"법령명|행정규칙명|주요\s*(?:개정\s*)?내용|일자|예고기간|제안자|고시\s*등\)", d + name + body) and not re.search(r"\d", d)
                        and len(body) < 30):
                    continue                       # 머리글
                is_first, first = first, False
                if not d and not field and prev is not None and is_first:
                    prev["name"] = (prev["name"] + " " + name).strip()   # 페이지를 넘어간 행
                    prev["_body"] += " " + body
                    continue
                if not (name or body):
                    continue
                if not d and prev is not None:     # 같은 날짜 칸을 여러 행이 나눠 쓰는 경우
                    d = prev["date_raw"]
                if not field and prev is not None:
                    field = prev["field"]
                prev = {"sec": SEC[sec], "date_raw": d, "name": name, "field": re.sub(r"\s+", "", field), "_body": body}
                rows.append(prev)
    out = []
    for r in rows:
        nm = re.sub(r"\s+", " ", r["name"]).strip()
        d = r["date_raw"]
        it = {"sec": r["sec"], "name": nm, "field": r["field"]}
        if r["sec"] == "입법·행정예고":
            parts = re.split(r"[∼~]", d)
            it["date"] = ymd(parts[0], base_y, base_m)
            it["until"] = ymd(parts[1], base_y, base_m) if len(parts) > 1 else ""
        else:
            it["date"] = ymd(re.sub(r"\(.*", "", d), base_y, base_m)
            pm = re.search(r"\(([^)]*\d[^)]*)\)", d)
            it["effective"] = ymd(pm.group(1), base_y, base_m) if pm else ""
            if r["sec"] == "의원 발의":
                who = re.sub(r"[‘'’]?\d{2}\.\s*|\d{1,2}\.\s*\d{1,2}\.?|[()]", " ", d)
                it["by"] = re.sub(r"\s+", " ", who).strip()
        txt = f"{nm} {r['_body']}"
        it["pages"] = [k for k, rx in KW.items() if rx.search(txt)]
        it["kw"] = sorted({m.group(0) for k in it["pages"] for m in KW[k].finditer(txt)})[:6]
        out.append(it)
    return out


def discover(st):
    """목록 페이지에 보이는 번호 + 처음에는 최근 번호를 거꾸로 훑어 지난 호를 찾는다"""
    h = fetch(f"{BASE}/law/insight/newsletter", 2_000_000).decode("utf8", "ignore")
    nos = sorted({int(n) for n in re.findall(r"(?:newsletter/|itemNo=|goPrevNext\(')(\d{4,5})", h)}, reverse=True)
    checked = set(st.get("checked", []))
    cand = [n for n in nos if n not in checked]
    if not st.get("backfilled") and nos:
        cand += [n for n in range(nos[0] - 1, nos[0] - 160, -1) if n not in checked and n not in cand]
    return cand


def main():
    st = load(OUT, {}) or {}
    issues = {i["no"]: i for i in st.get("issues", [])}
    checked = set(st.get("checked", []))
    t0 = time.monotonic()
    try:
        cand = discover(st)
    except Exception as e:
        print(f">> 목록 실패: {type(e).__name__}: {str(e)[:120]}")
        cand = []
    found = 0
    for no in cand:
        if time.monotonic() - t0 > 240 or (found >= 6 and not st.get("backfilled")):
            break
        try:
            title = page_title(no)
        except Exception as e:
            print(f">> {no} 제목 실패: {type(e).__name__}")
            continue
        checked.add(no)
        m = TITLE.search(title)
        if not m or no in issues:
            continue
        y, mo = int(m.group(1)), int(m.group(2))
        pdf = f"{BASE}/newsLetter/itemUrl.do?itemNo={no}"
        try:
            items = parse(fetch(pdf), y, mo)
        except Exception as e:
            print(f">> {no} PDF 처리 실패: {type(e).__name__}: {str(e)[:120]}")
            checked.discard(no)
            continue
        issues[no] = {"no": no, "title": f"{y}년 {mo}월 환경 주요 정책 동향", "month": f"{y}-{mo:02d}",
                      "url": f"{BASE}/law/insight/newsletter/{no}", "pdf": pdf, "added": now_kst().strftime("%Y-%m-%d"),
                      "n_total": len(items), "items": [i for i in items if i["pages"]]}
        found += 1
        from collections import Counter
        print(f">> {no} {y}년 {mo}월호: 전체 {len(items)}건 {dict(Counter(i['sec'] for i in items))} → "
              f"폐플라스틱 {sum('plastic' in i['pages'] for i in items)} · 바이오가스 {sum('biogas' in i['pages'] for i in items)}")
        for i in items:
            print(f"   [{i['sec'][:4]}] {i['date']}{'~' + i['until'] if i.get('until') else ''}{' 시행 ' + i['effective'] if i.get('effective') else ''}"
                  f" | {i['field']} | {i['name'][:40]} | {i.get('by', '')[:16]} | {','.join(i['pages'])} {i['kw']}")
    lst = sorted(issues.values(), key=lambda i: i["month"], reverse=True)[:6]
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "backfilled": True if cand or st.get("backfilled") else False,
               "checked": sorted(checked)[-400:], "issues": lst})
    print(f">> 저장: {len(lst)}개 호 ({', '.join(i['month'] for i in lst)})")


if __name__ == "__main__":
    main()
