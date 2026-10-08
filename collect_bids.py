# -*- coding: utf-8 -*-
"""폐플라스틱 매각입찰 수집 → data/bids.json
- 순환자원정보센터 전자입찰(re.or.kr): 지자체·공단·민간 재활용품 매각 공고와 개찰 결과(낙찰 단가 공개). 키 불필요.
- 나라장터(조달청 입찰공고·낙찰정보 API): 공고명에 '매각'이 들어간 용역·물품 공고와 낙찰률. DATA_GO_KR_KEY 필요.
플라스틱 관련 공고만 남기고, 화성·수원·평택·오산(중점)과 서울·인천·경기(수도권)를 표시한다.
처음 실행 때는 과거 공고를 BACKFILL_FROM 까지 거슬러 모으고, 이후에는 최근 페이지만 확인한다."""
import os, re, json, html, time, urllib.parse
from datetime import timedelta
from common import get, retry, load, save, now_kst

OUT = "data/bids.json"
RE_BASE = "https://www.re.or.kr"
BACKFILL_FROM = "2024-01-01"
DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
G2B = "https://apis.data.go.kr/1230000"
T0 = time.monotonic()
BUDGET = {"순환자원정보센터": 22 * 60, "나라장터": 12 * 60}   # 수집기별 최대 실행 시간(초). 넘으면 모은 것까지만 저장
CUT = {"hit": False}


def over(name, since):
    if time.monotonic() - since > BUDGET[name]:
        if not CUT["hit"]:
            print(f">> [{name}] 시간 한도 도달 → 여기까지 저장하고 다음 실행에서 이어서 수집")
        CUT["hit"] = True
        return True
    return False

FOCUS = ["화성", "수원", "평택", "오산"]
GG = ["수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "화성", "평택", "의정부", "시흥", "파주", "김포", "광명",
      "군포", "하남", "오산", "이천", "안성", "의왕", "양주", "구리", "포천", "여주", "동두천", "과천", "가평", "양평", "연천", "경기"]
SEOUL = ["서울", "종로구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구",
         "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구", "SH공사"]
INCHEON = ["인천", "미추홀구", "연수구", "남동구", "부평구", "계양구", "강화군", "옹진군"]
# 검색어: 지역명(수도권 공고를 빠짐없이) + 품목명(전국 단가 추이)
RE_QUERIES = ["화성", "수원", "평택", "오산", "서울", "인천", "경기", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "시흥",
              "김포", "파주", "의정부", "광명", "군포", "하남", "이천", "안성", "구리", "포천", "양주", "의왕", "여주", "과천", "동작구",
              "PET", "페트", "플라스틱", "합성수지", "선별품", "폐비닐", "스티로폼", "잉고트"]
PLASTIC = re.compile(r"PET|페트|플라스틱|합성수지|선별품|폐비닐|비닐|스티로폼|발포|잉고트|\bPP\b|\bPE\b|EPS|재활용품|재활용가능자원|재활용자원|재활용 ?선별", re.I)
NON_PLASTIC_ONLY = re.compile(r"\((?:[^()]*(?:고철|캔|유리|병|폐지|파지|종이|우유팩|종이팩|배터리|소화기|번호판|의류|식용유|형광등|전지|가전|고무|타이어|목재)[^()]*)\)")
NON_PLASTIC_WORD = re.compile(r"폐지류|잡파지|파지|우유팩|종이팩|폐의류|고철|폐유리|유리병|폐건전지|폐형광등|폐배터리|소화기|번호판|폐식용유")
CATS = [("PET", r"PET|페트"), ("폐비닐", r"비닐|필름"), ("스티로폼", r"스티로폼|발포|잉고트|EPS"),
        ("PP·PE", r"\bPP\b|\bPE\b|폴리프로필렌|폴리에틸렌"), ("혼합플라스틱", r"플라스틱|합성수지"), ("재활용품 일괄", r"재활용")]


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def num(s):
    s = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", s or "")      # '82 . 2' → '82.2'
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", s)
    return float(m.group(0).replace(",", "")) if m else None


def region_of(text):
    t = text or ""
    focus = [c for c in FOCUS if c in t]
    if focus:
        return "중점", focus[0]
    for c in SEOUL:
        if c in t:
            return "수도권", "서울"
    for c in INCHEON:
        if c in t:
            return "수도권", "인천"
    for c in GG:
        if c in t:
            return "수도권", "경기" if c == "경기" else c
    return "기타", ""


def category(title):
    for name, pat in CATS:
        if re.search(pat, title, re.I):
            return name
    return "기타"


def is_plastic(title):
    if not PLASTIC.search(title):
        return False
    # '재활용품(고철)', '재활용품(혼합병)'처럼 괄호 안이 비플라스틱뿐이면 제외
    has_pl = re.search(r"PET|페트|플라스틱|합성수지|비닐|스티로폼|잉고트|\bPP\b|\bPE\b|선별품", title, re.I)
    if (NON_PLASTIC_ONLY.search(title) or NON_PLASTIC_WORD.search(title)) and not has_pl:
        return False
    return True


# ---------------------------------------------------------------- 순환자원정보센터
def re_list(path, query, page):
    body = urllib.parse.urlencode({"page": page, "searchText": query, "prePage": path}).encode()
    h = retry(lambda: get(RE_BASE + path, data=body, headers={"Content-Type": "application/x-www-form-urlencoded",
                                                              "Referer": RE_BASE + path}, timeout=40), tries=3)
    rows = []
    for tr in re.findall(r"<tr>\s*<td>(.*?)</tr>", h, re.S):
        m = re.search(r"fn_view\('(\d+)','(\d+)'", tr)
        if not m:
            continue
        tds = [norm(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", "<td>" + tr, re.S)]
        if len(tds) < 8:
            continue
        rows.append({"no": m.group(1), "ord": m.group(2), "kind": tds[0], "title": tds[2], "org": tds[3],
                     "start": tds[4][:10], "end": tds[5][:10], "open": tds[6][:10], "status": tds[7].split("(")[0].strip()})
    return rows


def _fields(h):
    f = {}
    for th, td in re.findall(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", h, re.S):
        f[norm(th)] = norm(td)
    return f


def re_detail(b):
    """개찰 완료 건은 결과 화면, 진행 중인 건은 공고 화면에서 수량·예정가격·낙찰금액을 읽는다"""
    done = b["status"] in ("낙찰", "부분낙찰", "유찰", "유찰(공고취소)", "개찰완료")
    path = "/bid/viewBidResultPage.do" if done else "/bid/viewBidAdPage.do"
    h = retry(lambda: get(f"{RE_BASE}{path}?bidAdNum={b['no']}&bidTimeNum={b['ord']}", timeout=40), tries=2)
    f = _fields(h)
    qty = f.get("수량", "")
    b["qty_kg"] = num(qty) * (1000 if "톤" in qty else 1) if num(qty) else None
    b["item_cls"] = f.get("물품분류", "")
    b["price_type"] = f.get("가격구분", "").split("(")[0].strip()
    b["area"] = f.get("입찰가능지역", "")
    pre = next((v for k, v in f.items() if "예정가격" in k or "최저입찰가" in k), "")
    b["pre_raw"] = pre
    b["pre_amt"] = num(pre) if "비공개" not in pre else None
    b["pre_unit"] = "원/kg" if "kg" in pre else "원" if b["pre_amt"] is not None else ""
    if done:
        win = None
        for tr in re.findall(r"<tr>(.*?)</tr>", h.split("입찰참가", 1)[-1], re.S):
            tds = [norm(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) >= 4 and tds[3].startswith("낙찰"):
                win = tds
                break
        b["bidders"] = len(re.findall(r"<tr>\s*<td>\s*\d+\s*</td>", h.split("입찰참가", 1)[-1]))
        if b["status"] == "개찰완료":
            b["status"] = "낙찰" if win else "유찰"
        if win:
            b["win_raw"] = win[2]
            amt = num(win[2])
            if "kg" in win[2]:
                b["win_unit_price"] = amt
            elif amt and b.get("qty_kg"):
                b["win_amt"] = amt
                b["win_unit_price"] = round(amt / b["qty_kg"], 1)
            if b["pre_amt"]:
                pre_unit = b["pre_amt"] if b["pre_unit"] == "원/kg" else (b["pre_amt"] / b["qty_kg"] if b.get("qty_kg") else None)
                if pre_unit and b.get("win_unit_price"):
                    b["win_ratio"] = round(b["win_unit_price"] / pre_unit * 100, 1)
    if b["pre_amt"] is not None:
        b["pre_unit_price"] = b["pre_amt"] if b["pre_unit"] == "원/kg" else (round(b["pre_amt"] / b["qty_kg"], 1) if b.get("qty_kg") else None)
    b["url"] = f"{RE_BASE}{path}?bidAdNum={b['no']}&bidTimeNum={b['ord']}"
    return b


def collect_re(old, first_run):
    found, pages_max, t = {}, (40 if first_run else 2), time.monotonic()
    for path, label in (("/bid/listBidResultPage.do", "결과"), ("/bid/listBidPartPage.do", "공고")):
        for q in RE_QUERIES:
            if over("순환자원정보센터", t):
                break
            for page in range(1, pages_max + 1):
                try:
                    rows = re_list(path, q, page)
                except Exception as e:
                    print(f">> [순환자원] {label} '{q}' p{page} 실패: {type(e).__name__}")
                    break
                for r in rows:
                    if "매각" in r["kind"] or "매각" in r["title"] or "판매" in r["title"]:
                        k = f"re:{r['no']}:{r['ord']}"
                        if k not in found or label == "결과":
                            found[k] = r
                if not rows or rows[-1]["start"] < BACKFILL_FROM:
                    break
                time.sleep(0.3)
    print(f">> [순환자원] 목록에서 매각 공고 {len(found)}건")
    out, fetched = {}, 0
    for key, r in found.items():
        if r["start"] < BACKFILL_FROM:
            continue
        title = r["title"]
        if not is_plastic(title):
            continue
        reg, city = region_of(f"{title} {r['org']}")
        prev = old.get(key)
        if prev and prev.get("status") in (r["status"], "낙찰", "유찰") and prev.get("detail_ok") == 2:
            out[key] = prev
            continue
        if over("순환자원정보센터", t):
            if prev:
                out[key] = prev
            continue
        b = {"id": key, "src": "순환자원정보센터", **r, "cat": category(title), "region": reg, "city": city}
        try:
            re_detail(b)
            b["detail_ok"] = 2
            if reg == "기타":
                reg2, city2 = region_of(b.get("area", ""))
                if reg2 != "기타" and b.get("area") and len(b["area"]) < 12:   # 입찰가능지역이 수도권 한 곳으로 제한된 경우
                    b["region"], b["city"] = reg2, city2
            fetched += 1
            time.sleep(0.25)
        except Exception as e:
            print(f">> [순환자원] 상세 실패 {r['no']}: {type(e).__name__}")
            if prev:
                b = {**prev, **{k: r[k] for k in ("status", "open", "end")}}
        out[key] = b
    print(f">> [순환자원] 플라스틱 매각 {len(out)}건 (상세 새로 읽음 {fetched}건)")
    return out


# ---------------------------------------------------------------- 나라장터
def g2b(path, params):
    q = {"serviceKey": DATA_KEY, "pageNo": 1, "numOfRows": 100, "type": "json", **params}
    txt = retry(lambda: get(f"{G2B}{path}?" + urllib.parse.urlencode(q), timeout=30), tries=2, wait=2)
    j = json.loads(txt)
    body = j.get("response", {}).get("body", {})
    its = body.get("items") or []
    return its if isinstance(its, list) else its.get("item", [])


def collect_g2b(old, first_run):
    if not DATA_KEY:
        print(">> [나라장터] DATA_GO_KR_KEY 없음 → 건너뜀")
        return {}
    now = now_kst()
    days = 400 if first_run else 21
    out, wins, t, fails = {}, {}, time.monotonic(), 0
    for kind in ("Servc", "Thng"):
        # 한 번에 조회할 수 있는 기간이 짧아 30일씩 나눠 조회
        for k in range(0, days, 30):
            if over("나라장터", t) or fails >= 6:
                if fails >= 6:
                    print(">> [나라장터] 연속 실패로 이번 실행은 중단")
                    CUT["hit"] = True
                break
            e, s = now - timedelta(days=k), now - timedelta(days=min(k + 30, days))
            rng = {"inqryDiv": 1, "inqryBgnDt": s.strftime("%Y%m%d0000"), "inqryEndDt": e.strftime("%Y%m%d2359")}
            for kw in ("매각", "판매"):
                try:
                    for x in g2b(f"/ad/BidPublicInfoService/getBidPblancListInfo{kind}PPSSrch", {**rng, "bidNtceNm": kw}):
                        title = x.get("bidNtceNm", "")
                        if not is_plastic(title) or "매각" not in title + kw:
                            continue
                        key = f"g2b:{x.get('bidNtceNo')}:{x.get('bidNtceOrd')}"
                        org = x.get("dminsttNm") or x.get("ntceInsttNm") or ""
                        reg, city = region_of(f"{title} {org} {x.get('ntceInsttNm', '')}")
                        out[key] = {"id": key, "src": "나라장터", "no": x.get("bidNtceNo"), "title": title, "org": org,
                                    "start": (x.get("bidNtceDt") or "")[:10], "end": (x.get("bidClseDt") or "")[:10],
                                    "open": (x.get("opengDt") or "")[:10], "status": "공고", "cat": category(title),
                                    "region": reg, "city": city, "pre_amt": num(x.get("presmptPrce")) or None,
                                    "url": x.get("bidNtceDtlUrl") or "", "kind": kind}
                    for x in g2b(f"/as/ScsbidInfoService/getScsbidListSttus{kind}PPSSrch", {**rng, "bidNtceNm": kw}):
                        wins[f"g2b:{x.get('bidNtceNo')}:{x.get('bidNtceOrd')}"] = x
                    fails = 0
                except Exception as ex:
                    fails += 1
                    print(f">> [나라장터] {kind} {kw} {s:%Y-%m-%d} 실패: {type(ex).__name__}: {str(ex)[:120]}")
                time.sleep(0.2)
    for key, x in wins.items():
        b = out.get(key) or old.get(key)
        if not b:
            continue
        b["status"] = "낙찰"
        b["win_amt"] = num(x.get("sucsfbidAmt"))
        b["win_ratio"] = num(x.get("sucsfbidRate"))
        b["bidders"] = int(num(x.get("prtcptCnum")) or 0)
        b["open"] = (x.get("rlOpengDt") or b.get("open") or "")[:10]
        out[key] = b
    print(f">> [나라장터] 플라스틱 매각 공고 {len(out)}건 (낙찰 {sum(1 for b in out.values() if b['status'] == '낙찰')}건)")
    return out


def derive(b):
    """원문 문자열(예정가격·낙찰금액)에서 원/kg 단가와 낙찰/예정 비율을 다시 계산"""
    q = b.get("qty_kg")
    pre = b.get("pre_raw") or ""
    if pre and "비공개" not in pre and b.get("src") != "나라장터":
        amt = num(pre)
        # '30 원'처럼 단위가 원이어도 금액이 작으면 kg당 단가로 본다
        unit = "kg" in pre or (amt is not None and amt < 5000)
        b["pre_unit_price"] = amt if unit else (round(amt / q, 1) if amt and q else None)
    win = b.get("win_raw") or ""
    if win:
        amt = num(win)
        unit = "kg" in win or (amt is not None and amt < 5000)
        b["win_unit_price"] = amt if unit else (round(amt / q, 1) if amt and q else None)
    if b.get("pre_unit_price") and b.get("win_unit_price"):
        b["win_ratio"] = round(b["win_unit_price"] / b["pre_unit_price"] * 100, 1)
    return b


def main():
    st = load(OUT, {}) or {}
    old = {b["id"]: b for b in st.get("bids", []) if is_plastic(b.get("title", ""))}   # 필터가 바뀌면 예전 비플라스틱 건 정리
    first = not st.get("backfilled")
    bids = dict(old)
    ok = False
    for name, fn in (("순환자원정보센터", collect_re), ("나라장터", collect_g2b)):
        try:
            got = fn({k: v for k, v in old.items() if v.get("src") == name}, first)
            bids.update(got)
            ok = ok or bool(got)
        except Exception as e:
            print(f">> [{name}] 실패: {type(e).__name__}: {str(e)[:200]} → 이전 값 유지")
    lst = sorted((derive(b) for b in bids.values()), key=lambda b: (b.get("start") or "", b["id"]), reverse=True)
    done = st.get("backfilled") or (ok and not CUT["hit"])
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "backfilled": done,
                               "focus": FOCUS, "bids": lst})
    print(f">> 저장: 전체 {len(lst)}건 (중점 {sum(b['region'] == '중점' for b in lst)} · 수도권 {sum(b['region'] == '수도권' for b in lst)})")


if __name__ == "__main__":
    main()
