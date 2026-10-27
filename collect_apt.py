# -*- coding: utf-8 -*-
"""아파트 단지 재활용품 매각·수거업체 선정 → data/apt_sales.json
K-APT(공동주택관리정보시스템) '사업자 선정(경쟁입찰) 결과 공개' 공개 목록(/bid/bidList.do?type=3)에서
제목에 '재활용'이 들어간 서울·인천·경기 건의 상태(낙찰·유찰·취소·진행)와 낙찰금액을 읽는다.
K-APT 자체 공고뿐 아니라 KG2B 등 민간 전자입찰 건도 이 목록에 함께 나온다.
공공 화면을 하루 한 번, 요청 사이 3초씩 쉬며 읽는다: 최근 45일 + (처음 1년 채우기) 지난 달 한 구간씩.
K-APT 자체 공고는 상세를 한 번 읽어 입찰분류·주소(시군구)를 붙인다(하루 최대 80건).
세대수는 목록에 없어, '사업비 비교검색' EXCEL을 uploads/kapt/ 에 올리면 ingest_kapt.py 가 붙인다(선택)."""
import re, time, html, urllib.parse, urllib.request, http.cookiejar
from datetime import timedelta
from common import UA, load, save, now_kst

OUT = "data/apt_sales.json"
B = "https://www.k-apt.go.kr"
AREA = "11|28|41"                       # 서울·인천·경기
KW = ["재활용"]
FOCUS = ["화성", "수원", "평택", "오산"]
KEEP = re.compile(r"재활용|폐지|고철|캔|페트|PET|폐비닐|스티로폼|수거")
DROP = re.compile(r"음식물|폐가전|폐변압기|미디어보드|광고|승강기|자전거|공사|확장|설치|도색|보수")
DROP_CLS = re.compile(r"공사|주택관리업자")      # 재활용장 공사·위탁관리 공고 제외
T0 = time.monotonic()
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
    q = {"type": "3", "bidArea": AREA, "searchBidGb": "bid_gb_1", "bidTitle": kw, "searchDateGb": "reg",
         "dateStart": d0, "dateEnd": d1, "dateArea": "", "pageNo": str(page), "bidState": "",
         "codeAuth": "", "codeWay": "", "codeAuthSub": "", "codeSucWay": "",
         "codeClassifyType1": "", "codeClassifyType2": "", "codeClassifyType3": ""}
    h = fetch("/bid/bidList.do", q)
    if h is None:
        return None
    tb = h[h.find("<tbody"):h.find("</tbody>")]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) < 9:
            continue
        bid = re.search(r"goView\('([^']+)'\)", tr)
        code = re.search(r"initList\(\d+,\s*'([AB]\d{6,})'\)", tr)
        # 순번 | 종류(입찰시스템) | 낙찰방법 | 입찰공고명 | 입찰마감일 | 상태 | 낙찰금액 | 단지명 | 공고일
        key = bid.group(1) if bid else "x" + re.sub(r"\D", "", tds[8])[:14] + "_" + re.sub(r"\W", "", tds[7])[:12]
        amt = re.sub(r"[^\d]", "", tds[6])
        rows.append({"id": key, "sys": tds[1], "way": tds[2], "title_raw": tds[3], "end": tds[4][:16], "state": tds[5],
                     "win_amt": float(amt) if amt else None, "apt": tds[7], "reg": tds[8][:10], "reg_dt": tds[8][:19],
                     "kapt": bool(bid) and key.isdigit(), "kapt_code": code.group(1) if code else ""})
    return rows


def notice_page(kw, d0, d1, page):
    """진행 중 공고(입찰공고 목록, type=4): 결과 공개 목록에는 마감 전 공고가 아직 없다"""
    q = {"type": "4", "bidArea": AREA, "searchBidGb": "bid_gb_1", "bidTitle": kw, "searchDateGb": "reg",
         "dateStart": d0, "dateEnd": d1, "dateArea": "", "pageNo": str(page), "bidState": "",
         "codeAuth": "", "codeWay": "", "codeAuthSub": "", "codeSucWay": "",
         "codeClassifyType1": "", "codeClassifyType2": "", "codeClassifyType3": ""}
    h = fetch("/bid/bidList.do", q)
    if h is None:
        return None
    tb = h[h.find("<tbody"):h.find("</tbody>")]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        bid = re.search(r"goView\('(\d+)'\)", tr)
        code = re.search(r"initList\(\d+,\s*'([AB]\d{6,})'\)", tr)
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if bid and len(tds) >= 8:
            # 순번 | 종류 | 낙찰방법 | 공고명 | 마감 | 상태(신규공고·재공고·입찰마감) | 단지명 | 등록일시
            rows.append({"id": bid.group(1), "sys": tds[1], "way": tds[2], "title_raw": tds[3], "end": tds[4][:16],
                         "state": tds[5], "win_amt": None, "apt": tds[6], "reg": tds[7][:10], "reg_dt": tds[7][:19], "kapt": True,
                         "kapt_code": code.group(1) if code else ""})
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


INFO = "data/apt_info.json"
DATA_KEY = urllib.parse.unquote(__import__("os").environ.get("DATA_GO_KR_KEY", ""))


def apt_info(codes, limit=400):
    """국토교통부_공동주택 기본 정보제공 서비스(V5): 단지코드 → 세대수·주소. 결과는 data/apt_info.json 에 모아 두고 180일마다 갱신."""
    cache = load(INFO, {}) or {}
    if not DATA_KEY:
        return cache
    today = now_kst().strftime("%Y-%m-%d")
    stale = (now_kst() - timedelta(days=180)).strftime("%Y-%m-%d")
    todo = [c for c in dict.fromkeys(codes) if c and (c not in cache or cache[c].get("t", "") < stale)][:limit]
    n = 0
    for c in todo:
        u = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5?" + urllib.parse.urlencode(
            {"serviceKey": DATA_KEY, "kaptCode": c, "_type": "json"})
        try:
            t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf8", "ignore")
        except urllib.error.HTTPError as e:
            body = e.read()[:400].decode("utf8", "ignore")
            if "NOT_REGISTERED" in body or e.code in (401, 403):
                print(">> [세대수] 공공데이터포털 '국토교통부_공동주택 기본 정보제공 서비스' 활용신청이 필요합니다(승인 전이라 건너뜀)")
                break
            print(f">> [세대수] {c} HTTP {e.code}")
            continue
        except Exception as e:
            print(f">> [세대수] {c} {type(e).__name__}")
            continue
        try:
            it = __import__("json").loads(t).get("response", {}).get("body", {}).get("item") or {}
        except ValueError:
            it = {}
        if n == 0 and it:
            print(f">> [세대수] 응답 항목: {sorted(it.keys())}")
        hh = next((it.get(k) for k in ("kaptdaCnt", "hoCnt", "kaptHoCnt") if str(it.get(k) or "").strip()), None)
        addr = it.get("doroJuso") or it.get("kaptAddr") or ""
        cache[c] = {"t": today, "name": it.get("kaptName", ""), "households": int(float(hh)) if hh else None, "addr": addr,
                    "approve": it.get("kaptUsedate", "")}
        n += 1
        time.sleep(0.15)
    if n:
        save(INFO, cache)
    print(f">> [세대수] 새로 조회 {n}건, 누적 {len(cache)}개 단지")
    return cache


def region_of(title, it):
    sido = (re.match(r"\[(서울|인천|경기)\]", title) or [None, ""])[1] or {"서울특별시": "서울", "인천광역시": "인천", "경기도": "경기"}.get(it.get("addr_sido"), "")
    city = it.get("addr_city", "")
    if any(c in city for c in FOCUS):
        return "중점", city
    return ("수도권" if sido else "기타"), (city if sido == "경기" and city else sido)


def main():
    st = load(OUT, {}) or {}
    if st.get("ver") != 2:                  # 예전(공고 목록 기준) 자료는 새 기준으로 다시 모은다
        st = {"results": st.get("results", []), "results_updated": st.get("results_updated")}
    if not st.get("codes"):                 # 단지코드를 받기 전 자료: 1년 채우기를 처음부터 다시(단지코드 붙이기)
        st["bf_to"], st["bf_done"], st["codes"] = None, False, True
    items = {x["id"]: x for x in st.get("items", [])}
    now = now_kst()
    last = st.get("updated")
    if st.get("bf_done") and last and (now.replace(tzinfo=None) - __import__("datetime").datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() < 20 * 3600:
        print(f">> 오늘 이미 확인함({last}) → 하루 한 번만 조회")
        return
    # 조회 구간: 최근 45일 + 아직 1년을 다 못 채웠으면 그 이전 30일 한 구간
    spans = [((now - timedelta(days=45)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))]
    bf_to = st.get("bf_to") or (now - timedelta(days=45)).strftime("%Y-%m-%d")
    limit = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    if not st.get("bf_done"):               # 하루에 지난 한 달씩 채운다(상세 읽을 시간 확보)
        e = __import__("datetime").datetime.strptime(bf_to, "%Y-%m-%d")
        spans.append(((e - timedelta(days=30)).strftime("%Y-%m-%d"), bf_to))
    n_rows, ok = 0, True
    for d0, d1 in spans:
        seen = set()
        for page in range(1, 60):
            if time.monotonic() - T0 > 10.5 * 60:
                print(">> 목록 시간 한도 → 이 구간은 다음 실행에서 다시")
                ok = False
                break
            rows = list_page(KW[0], d0, d1, page)
            if rows is None:
                ok = False
                break
            fresh = [r for r in rows if r["id"] not in seen]
            if not fresh:
                break
            for r in fresh:
                seen.add(r["id"])
                if not KEEP.search(r["title_raw"]) or DROP.search(r["title_raw"]):
                    continue
                old = items.get(r["id"], {})
                items[r["id"]] = {**old, **r, "title": re.sub(r"^\[[^\]]+\]\s*", "", r["title_raw"]),
                                  "url": f"{B}/bid/bidDetail.do?bidNum={r['id']}" if r["kapt"] else f"{B}/bid/bidList.do?type=3"}
            n_rows += len(fresh)
        print(f">> [K-APT 결과공개] {d0}~{d1}: {len(seen)}건 확인")
    # 진행 중 공고: 입찰공고 목록(최근 45일). 결과 목록에 같은 공고가 있으면 결과 쪽 상태를 우선한다
    seen = set()
    for page in range(1, 8):
        rows = notice_page(KW[0], spans[0][0], spans[0][1], page)
        if not rows or all(r["id"] in seen for r in rows):
            break
        for r in rows:
            seen.add(r["id"])
            if not KEEP.search(r["title_raw"]) or DROP.search(r["title_raw"]):
                continue
            old = items.get(r["id"], {})
            if old.get("state") in ("낙찰", "유찰", "취소", "낙찰무효"):
                continue
            items[r["id"]] = {**old, **r, "title": re.sub(r"^\[[^\]]+\]\s*", "", r["title_raw"]),
                              "url": f"{B}/bid/bidDetail.do?bidNum={r['id']}"}
    print(f">> [K-APT 입찰공고] 진행 공고 확인 {len(seen)}건")
    if ok and len(spans) > 1:
        st["bf_to"] = spans[-1][0]
        st["bf_done"] = spans[-1][0] <= limit
    def store():
        # 같은 건이 다른 번호로 두 번 저장된 경우(예전 'x…' 임시 번호 ↔ 'kg2b_…' 번호) 단지·등록시각·공고명으로 합친다
        nk = lambda x: (re.sub(r"\s", "", x.get("apt", "")), x.get("reg_dt", ""), re.sub(r"\W", "", x.get("title_raw", "")))
        best = {}
        for k, x in list(items.items()):
            key = nk(x)
            o = best.get(key)
            if o is None:
                best[key] = k
                continue
            a, b = items[o], x
            keep, drop = (o, k) if (not o.startswith("x") or k.startswith("x")) else (k, o)
            items[keep] = {**items[drop], **{f: v for f, v in items[keep].items() if v not in (None, "")}}
            items.pop(drop, None)
            best[key] = keep
        for x in items.values():
            x["region"], x["city"] = region_of(x["title_raw"], x)
        keep = [v for v in items.values() if not DROP_CLS.search(v.get("cls", "") or "")]
        lst = sorted(keep, key=lambda x: (x.get("reg_dt") or "", x["id"]), reverse=True)
        save(OUT, {"ver": 2, "codes": True, "updated": now.strftime("%Y-%m-%d %H:%M"), "bf_to": st.get("bf_to"), "bf_done": st.get("bf_done", False),
                   "results_updated": st.get("results_updated"), "items": lst, "results": st.get("results", [])})
        return lst
    # 세대수·주소: 국토부 공동주택 기본정보 API(단지코드). 주소의 시·군·구로 중점 지역도 가린다
    info = apt_info([x.get("kapt_code") for x in sorted(items.values(), key=lambda x: x.get("reg_dt") or "", reverse=True)])
    for x in items.values():
        i = info.get(x.get("kapt_code") or "")
        if i:
            x["households"] = i.get("households")
            m = re.search(r"(서울특별시|인천광역시|경기도)\s*([가-힣]+?(?:시|군|구))", i.get("addr", ""))
            if m and not x.get("addr_city"):
                x["addr_sido"], x["addr_city"] = m.group(1), m.group(2)
    store()                                  # 목록까지 먼저 저장(상세 읽다 시간이 끝나도 남게)
    # 상세(입찰분류·주소): K-APT 자체 공고 중 아직 안 읽은 것, 최신부터. 실행 시간 12분 안에서만
    # 주소는 국토부 API로 받으므로, 상세는 주소를 못 받은 K-APT 건만 읽는다
    todo = sorted([x for x in items.values() if x.get("kapt") and "cls" not in x and not x.get("addr_city")], key=lambda x: x["reg_dt"], reverse=True)
    done = 0
    for x in todo:
        if time.monotonic() - T0 > 13 * 60:
            print(f">> 상세 시간 한도 → 남은 {len(todo) - done}건은 다음 실행에서")
            break
        x.update(detail(x["id"]) or {"cls": ""})
        done += 1
    todo = todo[:done]
    lst = store()
    from collections import Counter
    print(f">> 저장: {len(lst)}건 · 상태 {dict(Counter(x['state'] for x in lst))} · 시스템 {dict(Counter(x['sys'] for x in lst))} · "
          f"상세 {len(todo)}건 읽음 · 1년 채우기 {'완료' if st.get('bf_done') else st.get('bf_to')}")
    for x in [x for x in lst if x.get("win_amt")][:10]:
        print(f"   {x['reg']} {x.get('city', ''):5} | {x['sys'][:8]} | {x['apt'][:14]} | {x['title'][:30]} | 낙찰 {x['win_amt']:,.0f}")


if __name__ == "__main__":
    main()
