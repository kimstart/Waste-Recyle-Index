# -*- coding: utf-8 -*-
"""태평양(BKL) 월간 '환경 주요 정책 동향' 뉴스레터 → data/bkl_policy.json
매달 중순 올라오는 PDF에서 ① 기후부 법령·고시 개정 ② 입법·행정예고 ③ 의원 입법 발의 표를 읽어
폐플라스틱·바이오가스 관련 항목만 고른다. 저작물 보호를 위해 요약문은 저장하지 않고
날짜·법령명·분야 같은 사실 정보와 원문 PDF 링크만 남긴다(본문은 분류에만 쓴다).
pdfplumber 필요."""
import io, re, time, urllib.request
from common import load, save, now_kst

OUT = "data/bkl_policy.json"
VER = 4          # 표 읽기 방식이 바뀌면 올려서 저장된 호를 다시 읽는다
BASE = "https://www.bkl.co.kr"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
TITLE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*환경\s*주요\s*정책\s*동향")
SEC = {"II": "법령·고시 개정", "III": "입법·행정예고", "IV": "의원 발의"}
# 법령명에서 찾을 낱말(넓게)과 주요 내용에서 찾을 낱말(좁게). 본문은 저장하지 않고 분류에만 쓴다
KW_NAME = {
    "plastic": re.compile(r"폐기물|재활용|재생원료|플라스틱|순환경제|자원의\s*절약|포장|1회용|일회용|생산자책임|분리\s*수거|분리\s*배출|선별시설"),
    "biogas": re.compile(r"바이오|유기성|음식물|가축분뇨|분뇨|(?<!지)하수\s*(?:찌꺼기|슬러지)|공급\s*의무화|혼합\s*의무화|재생에너지\s*개발|신에너지|도시가스|수소경제|배출권|탄소중립·녹색성장"),
}
KW_BODY = {
    "plastic": re.compile(r"재생원료|플라스틱|폐비닐|페트병|포장재|포장폐기물|1회용|일회용|생산자책임|EPR|재활용\s*(?:의무|목표|률|시설|업)|선별시설|분리\s*배출|순환경제"),
    "biogas": re.compile(r"바이오가스|바이오\s*메탄|바이오매스|유기성\s*폐자원|음식물|가축분뇨|RPS|REC|공급\s*의무화|혼합\s*의무화|청정수소|배출권"),
}
NOT_PLASTIC = re.compile(r"방사성|고준위|원자력")
# 표의 열 경계(x, pt): 날짜 | 법령명 | 주요 내용 | 분야 — 의원 발의 표는 제안자 칸이 넓다
COLS = {"II": (117, 257, 477), "III": (117, 257, 477), "IV": (144, 250, 482)}


def fetch(url, n=10_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as r:
        return r.read(n)


def page_title(no):
    for k in range(3):
        try:
            h = fetch(f"{BASE}/law/insight/newsletter/{no}", 400_000).decode("utf8", "ignore")
            break
        except Exception:
            if k == 2:
                raise
            time.sleep(3 + 3 * k)
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
                X_NAME, X_BODY, X_FIELD = COLS[sec]
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
                if not (name or body) or (not d and prev is None):
                    continue
                if re.search(r"\(\d+건\)|의원\s*입법\s*발의|입법\(행정\)\s*예고", name + d) and not re.search(r"\d+\.\s*\d", d):
                    continue                       # 장 제목
                if not d and prev is not None:     # 같은 날짜 칸을 여러 행이 나눠 쓰는 경우
                    d = prev["date_raw"]
                if not field and prev is not None:
                    field = prev["field"]
                prev = {"sec": SEC[sec], "date_raw": d, "name": name, "field": re.sub(r"\s+", "", field), "_body": body}
                rows.append(prev)
    out = []
    for r in rows:
        nm = re.sub(r"\s+", " ", r["name"]).strip()
        nm = re.sub(r"\s*\(이하[^)]*\)", "", nm)                    # '(이하 “신재생에너지법”)' 제거
        nm = re.sub(r"^\((.+)\)$", r"「\1」", nm)                     # 고시·지침 등 행정규칙은 괄호로 표기됨
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
        it["pages"] = [k for k in KW_NAME if KW_NAME[k].search(nm) or KW_BODY[k].search(r["_body"])]
        if "plastic" in it["pages"] and NOT_PLASTIC.search(nm):
            it["pages"].remove("plastic")
        it["kw"] = sorted({m.group(0) for k in it["pages"] for rx in (KW_NAME[k], KW_BODY[k]) for m in rx.finditer(f"{nm} {r['_body']}")})[:6]
        out.append(it)
    return out


def discover(st):
    """목록 페이지에 보이는 번호 + 처음에는 최근 번호를 거꾸로 훑어 지난 호를 찾는다"""
    h = fetch(f"{BASE}/law/insight/newsletter", 2_000_000).decode("utf8", "ignore")
    nos = sorted({int(n) for n in re.findall(r"(?:newsletter/|itemNo=|goPrevNext\(')(\d{4,5})", h)}, reverse=True)
    checked = set(st.get("checked", []))
    cand = [n for n in nos if n not in checked]
    if nos:          # 지난 호를 찾기 위해 최근 90개 번호를 한 번씩 확인(한 번 확인한 번호는 다시 보지 않음)
        cand += [n for n in range(nos[0] - 1, nos[0] - 90, -1) if n not in checked and n not in cand]
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
        if time.monotonic() - t0 > 200:
            print(">> 시간 한도 → 나머지 번호는 다음 실행에서")
            break
        try:
            title = page_title(no)
        except Exception as e:
            print(f">> {no} 제목 실패: {type(e).__name__}")
            continue
        checked.add(no)
        time.sleep(0.7)
        m = TITLE.search(title)
        if not m or (no in issues and issues[no].get("ver") == VER):
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
                      "url": f"{BASE}/law/insight/newsletter/{no}", "pdf": pdf, "ver": VER, "added": now_kst().strftime("%Y-%m-%d"),
                      "n_total": len(items), "items": [i for i in items if i["pages"]]}
        found += 1
        from collections import Counter
        print(f">> {no} {y}년 {mo}월호: 전체 {len(items)}건 {dict(Counter(i['sec'] for i in items))} → "
              f"폐플라스틱 {sum('plastic' in i['pages'] for i in items)} · 바이오가스 {sum('biogas' in i['pages'] for i in items)}")
        for i in items:
            print(f"   [{i['sec'][:4]}] {i['date']}{'~' + i['until'] if i.get('until') else ''}{' 시행 ' + i['effective'] if i.get('effective') else ''}"
                  f" | {i['field']} | {i['name'][:40]} | {i.get('by', '')[:16]} | {','.join(i['pages'])} {i['kw']}")
    lst = sorted(issues.values(), key=lambda i: i["month"], reverse=True)[:6]
    # 관련 항목의 대략적인 내용: 공식 원문(국회 의안·법령 제개정이유·입법/행정예고문)에서 요지를 가져온다
    from official_gist import lookup
    n_ok = n_try = 0
    for iss in lst[:2]:
        for it in iss.get("items", []):
            if it.get("gist") or it.get("gist_tries", 0) >= 3:
                continue
            if time.monotonic() - t0 > 330:
                print(">> [요지] 시간 한도 → 나머지는 다음 실행에서")
                break
            n_try += 1
            try:
                g = lookup(it)
            except Exception as e:
                g = None
                print(f">> [요지] {it['name'][:30]} 실패: {type(e).__name__}: {str(e)[:80]}")
            it["gist_tries"] = it.get("gist_tries", 0) + 1
            if g and g.get("gist"):
                it.update(gist=g["gist"], gist_src=g["src"], gist_url=g.get("url", ""))
                n_ok += 1
                print(f"   [요지] {it['sec'][:4]} {it['name'][:28]} ← {g['src']}: {g['gist'][:110]}")
            else:
                print(f"   [요지 없음] {it['sec'][:4]} {it['name'][:40]} {it.get('by', '')}")
            time.sleep(0.5)
    print(f">> [요지] 시도 {n_try}건 → 확인 {n_ok}건")
    # 읽기 방식이 바뀐 호는 다음 실행에서 다시 읽도록 확인 목록에서 뺀다
    checked -= {i["no"] for i in lst if i.get("ver") != VER}
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "checked": sorted(checked)[-400:], "issues": lst})
    print(f">> 저장: {len(lst)}개 호 ({', '.join(i['month'] for i in lst)})")


if __name__ == "__main__":
    main()
