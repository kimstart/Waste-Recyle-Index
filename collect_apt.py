# -*- coding: utf-8 -*-
"""아파트 단지 재활용품 매각·수거업체 선정 공고 → data/apt_sales.json
① K-APT(공동주택관리정보시스템) 입찰공고 목록: 제목에 '재활용'이 들어간 서울·인천·경기 공고(분류 무관 — 물품 매각·기타 용역·잡수입으로 섞여 등록됨).
   민간 전자입찰(KG2B·아파트비드포유·아파트장터) 공고도 K-APT에 함께 등록되므로 K-APT만 본다.
   공공 화면을 하루 한 번, 요청 사이 3초씩 쉬며 몇 쪽만 읽는다. 새 공고만 상세를 한 번 읽는다(입찰분류·주소).
② 입찰결과(낙찰금액·낙찰업체·세대수): K-APT가 자동 조회를 허용하지 않아, 사용자가 '입찰결과' 엑셀을 내려받아
   uploads/kapt/ 에 올리면 ingest_kapt.py 가 읽어 이 파일에 합친다(이 스크립트는 결과를 건드리지 않음)."""
import re, time, html, urllib.parse, urllib.request, http.cookiejar
from datetime import timedelta
from common import UA, load, save, now_kst

OUT = "data/apt_sales.json"
B = "https://www.k-apt.go.kr"
AREA = "11|28|41"                       # 서울·인천·경기
KW = ["재활용"]
FOCUS = ["화성", "수원", "평택", "오산"]
KEEP = re.compile(r"재활용|폐지|고철|캔|페트|PET|폐비닐|스티로폼|수거")
DROP = re.compile(r"음식물|폐가전|폐변압기|미디어보드|광고|승강기|자전거")
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def fetch(path, params=None):
    url = B + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for k in range(2):
        time.sleep(3)                    # 공공 사이트 부담을 줄이려 요청 사이를 띄운다
        try:
            with _op.open(urllib.request.Request(url, headers={**UA, "Referer": B + "/bid/bidList.do"}), timeout=60) as r:
                return r.read(4_000_000).decode("utf8", "ignore")
        except Exception as e:
            print(f">> [K-APT] {path} 응답 없음({type(e).__name__}) → {'잠시 후 한 번 더' if k == 0 else '건너뜀'}")
            time.sleep(15)
    return None


def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def list_page(kw, d0, d1, page):
    q = {"type": "4", "bidArea": AREA, "searchBidGb": "bid_gb_1", "bidTitle": kw, "searchDateGb": "reg",
         "dateStart": d0, "dateEnd": d1, "dateArea": "4", "pageNo": str(page), "bidState": "",
         "codeAuth": "", "codeWay": "", "codeAuthSub": "", "codeSucWay": "",
         "codeClassifyType1": "", "codeClassifyType2": "", "codeClassifyType3": ""}
    h = fetch("/bid/bidList.do", q)
    if h is None:
        return None
    tb = h[h.find("<tbody"):h.find("</tbody>")]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        bid = re.search(r"goView\('(\d+)'\)", tr)
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        code = re.search(r"initList\(\d+,\s*'([A-Z]\d+)'\)", tr)
        if bid and len(tds) >= 8:
            rows.append({"id": bid.group(1), "sys": tds[1], "way": tds[2], "title_raw": tds[3], "end": tds[4][:16],
                         "state": tds[5], "apt": tds[6], "reg": tds[7][:10], "kapt_code": code.group(1) if code else ""})
    return rows


def detail(bid):
    h = fetch("/bid/bidDetail.do", {"bidNum": bid})
    if not h:
        return {}
    f = {clean(a): clean(b) for a, b in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", h, re.S)}
    addr = re.search(r"(서울특별시|인천광역시|경기도)\s*([가-힣]+?(?:시|군|구))(?:\s*([가-힣]+구))?", clean(h))
    return {"cls": f.get("입찰분류", ""), "kind": f.get("입찰종류", ""), "way": f.get("낙찰방법", ""),
            "addr_city": (addr.group(2) if addr else ""), "addr_sido": (addr.group(1) if addr else ""),
            "content": f.get("내용", "")[:200]}


def region_of(title, it):
    sido = (re.match(r"\[(서울|인천|경기)\]", title) or [None, ""])[1] or {"서울특별시": "서울", "인천광역시": "인천", "경기도": "경기"}.get(it.get("addr_sido"), "")
    city = it.get("addr_city", "")
    if any(c in city for c in FOCUS):
        return "중점", city
    return ("수도권" if sido else "기타"), (city if sido == "경기" and city else sido)


def main():
    st = load(OUT, {}) or {}
    items = {x["id"]: x for x in st.get("items", [])}
    now = now_kst()
    last = st.get("updated")
    if st.get("backfilled") and last and (now.replace(tzinfo=None) - __import__("datetime").datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() < 20 * 3600:
        print(f">> 오늘 이미 확인함({last}) → 하루 한 번만 조회")
        return
    first = not st.get("backfilled")
    d0 = (now - timedelta(days=364 if first else 40)).strftime("%Y-%m-%d")
    d1 = now.strftime("%Y-%m-%d")
    seen, n_new, ok = set(), 0, True
    for kw in KW:
        for page in range(1, 12):
            rows = list_page(kw, d0, d1, page)
            if rows is None:
                ok = False
                break
            fresh = [r for r in rows if r["id"] not in seen]
            if not fresh:
                break
            for r in fresh:
                seen.add(r["id"])
                title = r["title_raw"]
                if not KEEP.search(title) or DROP.search(title):
                    continue
                old = items.get(r["id"], {})
                it = {**old, **r, "title": re.sub(r"^\[[^\]]+\]\s*", "", title), "src": "K-APT",
                      "url": f"{B}/bid/bidDetail.do?bidNum={r['id']}"}
                if "cls" not in old:                       # 새 공고만 상세 한 번
                    it.update(detail(r["id"]))
                    n_new += 1
                it["region"], it["city"] = region_of(title, it)
                items[r["id"]] = it
    lst = sorted(items.values(), key=lambda x: (x.get("reg") or "", x["id"]), reverse=True)
    save(OUT, {"updated": now.strftime("%Y-%m-%d %H:%M"), "backfilled": st.get("backfilled") or (first and ok),
               "results_updated": st.get("results_updated"), "items": lst, "results": st.get("results", [])})
    from collections import Counter
    print(f">> 저장: 아파트 재활용 공고 {len(lst)}건 (이번 확인 {len(seen)}건, 새 상세 {n_new}건) · "
          f"분류 {dict(Counter(x.get('cls', '') for x in lst))} · 지역 {dict(Counter(x.get('city', '') for x in lst))}")
    for x in lst[:12]:
        print(f"   {x['reg']} {x.get('city', ''):4} | {x['way']:6} | {x['apt'][:14]} | {x['title'][:40]} | {x.get('cls', '')} | {x['state']}")


if __name__ == "__main__":
    main()
