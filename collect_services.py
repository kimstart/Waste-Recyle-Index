# -*- coding: utf-8 -*-
"""수도권 선별·처리 대행 용역 수집 → data/services.json
지자체가 재활용품을 팔지 않고 민간에 선별·처리를 맡기는 용역(예: 오산시 '재활용품 선별 대행 처리용역') 공고와 낙찰 결과.
선별장 입장에서는 수주 기회이며, 추정가격·낙찰금액으로 대행 단가 수준을 가늠할 수 있다.
- 나라장터 입찰공고·낙찰정보 API(용역): DATA_GO_KR_KEY 필요
- 순환자원정보센터 전자입찰 중 '용역' 공고: 키 불필요
처음 실행 때는 최근 13개월, 이후에는 최근 3주를 다시 확인한다."""
import os, re, time, json, urllib.parse
from datetime import timedelta
from common import get, retry, load, save, now_kst
from collect_bids import region_of, re_list, RE_BASE, num

OUT = "data/services.json"
DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
G2B = "https://apis.data.go.kr/1230000"
KWS = ["재활용", "선별", "폐합성수지", "폐비닐", "플라스틱", "스티로폼"]
RE_KWS = ["선별", "위탁", "대행", "재활용"]
# 생활계 재활용품 선별·처리·운영 대행만 남긴다
KEEP = re.compile(r"(재활용|선별|폐합성수지|폐비닐|플라스틱|스티로폼|발포).*(대행|위탁|처리|운영|선별|용역)|(대행|위탁|운영).*(재활용|선별|폐합성수지|폐비닐)")
DROP = re.compile(r"건설|슬러지|폐수|의료|음식물|하수|분뇨|토사|아스콘|석면|폐목재|폐타이어|폐유|실험|인조잔디|철거|도로|공사|청소용역|폐가전|폐의약품|소각재|매립")
T0, BUDGET = time.monotonic(), 14 * 60


def tag(title):
    if re.search(r"운영", title):
        return "시설 운영 위탁"
    if re.search(r"(?<!미)선별", title):
        return "선별 대행"
    if re.search(r"수집|운반", title):
        return "수집·운반·처리"
    return "처리 대행"


def g2b(path, params):
    q = {"serviceKey": DATA_KEY, "pageNo": 1, "numOfRows": 999, "type": "json", **params}
    txt = retry(lambda: get(f"{G2B}{path}?" + urllib.parse.urlencode(q), timeout=30), tries=2, wait=2)
    body = json.loads(txt).get("response", {}).get("body", {})
    its = body.get("items") or []
    return its if isinstance(its, list) else its.get("item", [])


def collect_g2b(first):
    if not DATA_KEY:
        print(">> [나라장터] DATA_GO_KR_KEY 없음 → 건너뜀")
        return {}, False, {}
    now, days = now_kst(), (400 if first else 21)
    out, wins, fails, cut = {}, {}, 0, False
    for k in range(0, days, 30):
        if time.monotonic() - T0 > BUDGET or fails >= 6:
            cut = True
            print(">> [나라장터] 시간 한도 또는 연속 실패 → 여기까지 저장")
            break
        e, s = now - timedelta(days=k), now - timedelta(days=min(k + 30, days))
        rng = {"inqryDiv": 1, "inqryBgnDt": s.strftime("%Y%m%d0000"), "inqryEndDt": e.strftime("%Y%m%d2359")}
        for kw in KWS:
            try:
                for x in g2b("/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch", {**rng, "bidNtceNm": kw}):
                    title = x.get("bidNtceNm", "")
                    if not KEEP.search(title) or DROP.search(title) or "매각" in title:
                        continue
                    org, inst = x.get("dminsttNm") or "", x.get("ntceInsttNm") or ""
                    reg, city = region_of(f"{title} {org} {inst}")
                    if reg == "기타":
                        continue
                    key = f"g2b:{x.get('bidNtceNo')}"
                    ordn = x.get("bidNtceOrd") or "000"
                    if key in out and out[key]["ord"] >= ordn:
                        continue
                    out[key] = {"id": key, "src": "나라장터", "no": x.get("bidNtceNo"), "ord": ordn, "title": title,
                                "org": org or inst, "region": reg, "city": city, "type": tag(title),
                                "start": (x.get("bidNtceDt") or "")[:10], "end": (x.get("bidClseDt") or "")[:10],
                                "open": (x.get("opengDt") or "")[:10], "method": x.get("cntrctCnclsMthdNm") or "",
                                "est": num(x.get("presmptPrce") or "") or None, "budget": num(x.get("asignBdgtAmt") or "") or None,
                                "status": "공고", "url": x.get("bidNtceDtlUrl") or ""}
                for x in g2b("/as/ScsbidInfoService/getScsbidListSttusServcPPSSrch", {**rng, "bidNtceNm": kw}):
                    wins[f"g2b:{x.get('bidNtceNo')}"] = x
                fails = 0
            except Exception as ex:
                fails += 1
                print(f">> [나라장터] '{kw}' {s:%Y-%m-%d} 실패: {type(ex).__name__}: {str(ex)[:100]}")
            time.sleep(0.2)
    return out, cut, wins


def collect_re(first):
    out, pages = {}, (8 if first else 2)
    for path, label in (("/bid/listBidResultPage.do", "결과"), ("/bid/listBidPartPage.do", "공고")):
        for q in RE_KWS:
            for page in range(1, pages + 1):
                try:
                    rows = re_list(path, q, page)
                except Exception as e:
                    print(f">> [순환자원] {label} '{q}' p{page} 실패: {type(e).__name__}")
                    break
                for r in rows:
                    title = r["title"]
                    if "용역" not in r["kind"] or not KEEP.search(title) or DROP.search(title):
                        continue
                    reg, city = region_of(f"{title} {r['org']}")
                    if reg == "기타":
                        continue
                    key = f"re:{r['no']}:{r['ord']}"
                    if key in out and label != "결과":
                        continue
                    done = r["status"] not in ("입찰중", "입찰예정", "공고")
                    out[key] = {"id": key, "src": "순환자원정보센터", "no": r["no"], "ord": r["ord"], "title": title, "org": r["org"],
                                "region": reg, "city": city, "type": tag(title), "start": r["start"], "end": r["end"], "open": r["open"],
                                "status": r["status"], "method": r["kind"], "est": None,
                                "url": f"{RE_BASE}/bid/{'viewBidResultPage' if done else 'viewBidAdPage'}.do?bidAdNum={r['no']}&bidTimeNum={r['ord']}"}
                if not rows or rows[-1]["start"] < "2025-01-01":
                    break
                time.sleep(0.3)
    return out


def main():
    st = load(OUT, {}) or {}
    first = not st.get("backfilled")
    items = {x["id"]: x for x in st.get("items", [])}
    g, cut, wins = collect_g2b(first) if DATA_KEY else ({}, False, {})
    for k, v in g.items():
        old = items.get(k, {})
        items[k] = {**old, **v, **{f: old[f] for f in ("status", "win_amt", "win_rate", "winner", "bidders", "open") if f in old and old.get("status") == "낙찰"}}
    for k, x in wins.items():
        if k not in items:
            continue
        b = items[k]
        b.update(status="낙찰", win_amt=num(x.get("sucsfbidAmt") or "") or None, win_rate=num(x.get("sucsfbidRate") or "") or None,
                 winner=x.get("bidwinnrNm") or "", bidders=int(num(x.get("prtcptCnum") or "") or 0),
                 open=(x.get("rlOpengDt") or b.get("open") or "")[:10])
    try:
        items.update(collect_re(first))
    except Exception as e:
        print(f">> [순환자원] 실패: {type(e).__name__}: {str(e)[:150]}")
    lst = sorted(items.values(), key=lambda b: (b.get("start") or "", b["id"]), reverse=True)
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "backfilled": st.get("backfilled") or (bool(g) and not cut), "items": lst})
    print(f">> 저장: 선별·처리 대행 용역 {len(lst)}건 (중점 {sum(b['region'] == '중점' for b in lst)} · "
          f"수도권 {sum(b['region'] == '수도권' for b in lst)} · 낙찰 {sum(b.get('status') == '낙찰' for b in lst)})")
    for b in lst[:15]:
        print(f"   {b['start']} {b['city']} | {b['org'][:16]} | {b['title'][:46]} | 추정 {b.get('est')} | {b.get('status')} {b.get('win_amt') or ''}")


if __name__ == "__main__":
    main()
