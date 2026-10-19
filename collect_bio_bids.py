# -*- coding: utf-8 -*-
"""수도권 유기성폐자원 입찰·용역·공사 수집 → data/bio_bids.json
음식물류폐기물·음폐수·동식물성잔재물·유기성오니(하수찌꺼기)·가축분뇨 등 바이오가스 원료가 되는 폐기물의
처리·운영·수집운반 용역과 처리시설 공사(EPC), 순환자원정보센터 매각·용역 입찰을 모은다.
- 순환자원정보센터 전자입찰·수의견적 API(공공데이터포털): 품목 분류가 유기성인 공고
- 나라장터 입찰공고·낙찰정보 API(용역·공사): 공고명에 유기성폐자원 낱말이 들어간 공고
유형: 시설 운영 / 처리 대행 / 수집·운반 / EPC·공사 / 매각·매입 (선별 대행은 없음)
처음 실행 때는 최근 13개월, 이후에는 최근 3주를 다시 확인한다. DATA_GO_KR_KEY 필요."""
import os, re, time, json, urllib.parse
from datetime import timedelta
from common import get, retry, load, save, now_kst
from collect_bids import region_of, num, norm, keco_all, _ymd, re_detail, RE_BASE

OUT = "data/bio_bids.json"
DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
G2B = "https://apis.data.go.kr/1230000"
SINCE = "2024-01-01"
# 나라장터 공고명 검색어 (부분 일치 검색이라 '분뇨'가 '가축분뇨'도 잡는다)
KWS = ["음식물", "음폐수", "바이오가스", "슬러지", "하수찌꺼기", "분뇨", "유기성", "동식물성", "소화조"]
ORG = re.compile(r"음식물|음식폐기물|남은\s*음식|음폐수|바이오\s*가스|슬러지|찌꺼기|분뇨|유기성|동식물성|소화조|혐기성|소화\s*가스|폐식용유|축산\s*폐수")
ORG_CLS = re.compile(r"음식물|유기성오니|동식물성|폐식용유|분뇨|가축|처리오니|하수")
DROP = re.compile(r"급식|식당|조리|식재료|식자재|RFID|종량|감량기|계량|수거\s*용기|전용\s*용기|용기\s*(?:구입|구매|제작)|봉투|스티커|납부필증|홍보|교육|연구|타당성|"
                  r"기본\s*계획|기본구상|컨설팅|평가|조사|진단|측정|분석|모니터링|정수|무기성|준설|토사|건설폐기물|석면|의료|지정폐기물|소화기|소화전|소화설비|"
                  r"구입|구매|임차|렌탈|청소차|집하장|분리수거장|거점|보험|검사|수질|TMS|전산|시스템|프로그램|앱|플랫폼|인허가|보상|감정|수목|조경|도색|"
                  r"수거함|화장실|정화조\s*청소|대행료\s*산정|원가\s*산정|원가계산|정산|용역비|퇴비\s*살포|비료\s*(?:구입|공급)|사료\s*구입|"
                  # 하수처리장·처리시설의 부품 정비·보수(사업 기회가 아닌 유지관리)는 뺀다
                  r"정비|유지\s*보수|보수|수리|교체|차륜|펌프|밸브|배관|케이블|MCC|점검|검교정|교정|오일|부품|수집기|탈취기|탈황|스컴|스키머|계장|"
                  r"감시제어|도장|방수|누수|철거|기술지도|안전|제작\s*설치|부대설비|전기설비|임시\s*운영|호퍼|교반기|윤활|세척|청소|유량계|협잡물|오버홀|대수선|"
                  r"연결부|유입관|제어실|공동구|폴리머|정보통신|혼합폐기물|대응\s*방안|방안\s*마련|전략|정책|수의시담")
T0, BUDGET = time.monotonic(), 16 * 60


def tag(title, cnstwk=False):
    t = title or ""
    if re.search(r"매각|매입|판매", t):
        return "매각·매입"
    if cnstwk or re.search(r"공사|시공|설계|감리|EPC|턴키|설치사업|건설|증설|신설|확충|현대화|개량|증축|신축|대보수|설비\s*(?:교체|보강|개선)", t, re.I):
        if not re.search(r"운영|관리\s*대행|위탁\s*관리", t) or cnstwk:
            return "EPC·공사"
    if re.search(r"운영|관리\s*대행|위탁\s*관리|운전", t):
        return "시설 운영"
    if re.search(r"수집|운반|운송|수거", t) and not re.search(r"(?<!감량)처리(?!\s*(?:시설|장|장치))", t):
        return "수집·운반"
    return "처리 대행"


def waste_of(text):
    t = text or ""
    for name, rx in (("음폐수", r"음폐수"), ("음식물", r"음식물|음식폐기물|남은\s*음식"), ("하수찌꺼기·슬러지", r"슬러지|찌꺼기|오니|하수"),
                     ("가축분뇨·분뇨", r"분뇨|축산"), ("동식물성잔재물", r"동식물성|폐식용유"), ("바이오가스", r"바이오\s*가스|소화"), ("유기성폐자원", r"유기성")):
        if re.search(rx, t):
            return name
    return "유기성폐자원"


def keep(title):
    return bool(ORG.search(title or "")) and not DROP.search(title or "")


OTHER = re.compile(r"경상|경북|경남|충청|충북|충남|전라|전북|전남|강원|제주|세종|대전|대구|부산|광주광역|울산|원주|춘천|강릉|속초|삼척|태백|홍천|횡성|"
                   r"청주|충주|제천|천안|공주|보령|아산|서산|논산|당진|홍성|전주|군산|익산|목포|여수|순천|포항|경주|김천|안동|구미|창원|진주|김해|양산|통영|거제")


def region(*texts):
    """공고명 → 수요기관 → 공고기관 순으로 본다 (예: 서울지방교정청이 낸 '의정부교도소' 건은 의정부)"""
    for t in texts:
        t = t or ""
        if "수도권매립지" in t:
            return "수도권", "인천"
        r = region_of(t)
        if r[0] != "기타" or OTHER.search(t):
            return r
    return "기타", ""


def g2b(path, params):
    out, page = [], 1
    while page <= 5:
        q = {"serviceKey": DATA_KEY, "pageNo": page, "numOfRows": 999, "type": "json", **params}
        txt = retry(lambda: get(f"{G2B}{path}?" + urllib.parse.urlencode(q), timeout=30), tries=2, wait=2)
        body = json.loads(txt).get("response", {}).get("body", {})
        its = body.get("items") or []
        its = its if isinstance(its, list) else its.get("item", [])
        out += its
        if len(out) >= int(body.get("totalCount") or 0) or not its:
            break
        page += 1
    return out


def docs_of(x):
    return [[x.get(f"ntceSpecFileNm{i}") or "", x[f"ntceSpecDocUrl{i}"]] for i in range(1, 11) if x.get(f"ntceSpecDocUrl{i}")]


def enrich(items, stop_at):
    """① 개찰일이 지났는데 결과가 없는 공고 → 공고번호로 다시 조회해 취소공고인지 확인
       ② 처리 대행 → 첨부 공고문·과업지시서에서 예상 처리물량(톤)을 읽어 톤당 단가 계산에 쓴다"""
    from doc_qty import qty_from_docs
    today = now_kst().strftime("%Y-%m-%d")
    lim = (now_kst() - timedelta(days=2)).strftime("%Y-%m-%d")
    todo = [b for b in items.values() if b.get("src") == "나라장터" and (
        (b.get("type") == "처리 대행" and not b.get("qty_checked")) or
        (b.get("status") == "공고" and (b.get("open") or "9999") < lim and b.get("kind_checked") != b.get("open")))]
    todo.sort(key=lambda b: b.get("start") or "", reverse=True)
    n_q = n_c = 0
    for b in todo:
        if time.monotonic() > stop_at:
            print(f">> [첨부 확인] 시간 한도 → 남은 {len(todo) - todo.index(b)}건은 다음 실행에서")
            break
        need_kind = b.get("status") == "공고" and (b.get("open") or "9999") < lim and b.get("kind_checked") != b.get("open")
        if need_kind or not b.get("docs"):
            ep = "Cnstwk" if b.get("kind") == "공사" else "Servc"
            try:
                rows = g2b(f"/ad/BidPublicInfoService/getBidPblancListInfo{ep}", {"inqryDiv": 2, "bidNtceNo": b["no"]})
                if rows:
                    x = max(rows, key=lambda r: r.get("bidNtceOrd") or "")
                    b["ntce_kind"] = x.get("ntceKindNm") or b.get("ntce_kind", "")
                    b["docs"] = docs_of(x) or b.get("docs") or []
                    if "취소" in b["ntce_kind"] and b.get("status") != "낙찰":
                        b["status"] = "공고취소"
                        n_c += 1
                if need_kind:
                    b["kind_checked"] = b.get("open")
            except Exception as ex:
                print(f">> [첨부 확인] {b['no']} 조회 실패: {type(ex).__name__}: {str(ex)[:80]}")
                continue
        if b.get("type") == "처리 대행" and not b.get("qty_checked") and b.get("docs"):
            q, note = qty_from_docs(b["docs"], b.get("est"))
            b["qty_checked"] = today
            if q:
                b["qty_t"], b["qty_note"] = q, note
                n_q += 1
        time.sleep(0.2)
    print(f">> [첨부 확인] 대상 {len(todo)}건 → 예상물량 확인 {n_q}건, 취소공고 {n_c}건")


def collect_g2b(first, start_k=0):
    """30일 창으로 거꾸로 훑는다. 처음 모으기(400일)가 시간 한도에 걸리면 멈춘 위치(bf_k)를 저장해 다음 실행에서 이어 간다."""
    now, days = now_kst(), (400 if first else 21)
    out, wins, fails, cut = {}, {}, 0, False
    ks = [0] + [k for k in range(max(start_k, 30) if first and start_k else 30, days, 30)] if first else [0]
    done_k = start_k
    for k in ks:
        if time.monotonic() - T0 > BUDGET or fails >= 8:
            cut = True
            print(f">> [나라장터] 시간 한도 또는 연속 실패 → {k}일 전까지 저장, 다음 실행에서 이어서 수집")
            break
        e, s = now - timedelta(days=k), now - timedelta(days=min(k + 30, days))
        rng = {"inqryDiv": 1, "inqryBgnDt": s.strftime("%Y%m%d0000"), "inqryEndDt": e.strftime("%Y%m%d2359")}
        for kw in KWS:
            for kind, ep in (("용역", "Servc"), ("공사", "Cnstwk")):
                try:
                    for x in g2b(f"/ad/BidPublicInfoService/getBidPblancListInfo{ep}PPSSrch", {**rng, "bidNtceNm": kw}):
                        title = norm(x.get("bidNtceNm", ""))
                        if not keep(title):
                            continue
                        org, inst = x.get("dminsttNm") or "", x.get("ntceInsttNm") or ""
                        reg, city = region(title, org, inst)
                        if reg == "기타":
                            continue
                        key = f"g2b:{x.get('bidNtceNo')}"
                        ordn = x.get("bidNtceOrd") or "000"
                        if key in out and out[key]["ord"] >= ordn:
                            continue
                        out[key] = {"id": key, "src": "나라장터", "kind": kind, "no": x.get("bidNtceNo"), "ord": ordn, "title": title,
                                    "org": org or inst, "region": reg, "city": city, "type": tag(title, kind == "공사"), "waste": waste_of(title),
                                    "start": (x.get("bidNtceDt") or "")[:10], "end": (x.get("bidClseDt") or "")[:10],
                                    "open": (x.get("opengDt") or "")[:10], "method": x.get("cntrctCnclsMthdNm") or "",
                                    "est": num(x.get("presmptPrce") or "") or None, "budget": num(x.get("asignBdgtAmt") or "") or None,
                                    "status": "공고취소" if "취소" in (x.get("ntceKindNm") or "") else "공고",
                                    "ntce_kind": x.get("ntceKindNm") or "", "docs": docs_of(x), "url": x.get("bidNtceDtlUrl") or ""}
                    for x in g2b(f"/as/ScsbidInfoService/getScsbidListSttus{ep}PPSSrch", {**rng, "bidNtceNm": kw}):
                        wins[f"g2b:{x.get('bidNtceNo')}"] = x
                    fails = 0
                except Exception as ex:
                    fails += 1
                    print(f">> [나라장터] {kind} '{kw}' {s:%Y-%m-%d} 실패: {type(ex).__name__}: {str(ex)[:100]}")
                time.sleep(0.15)
        if fails == 0:
            done_k = max(done_k, k + 30)
    print(f">> [나라장터] 수도권 유기성 용역·공사 {len(out)}건, 낙찰 후보 {len(wins)}건 (처음 모으기 {done_k}/{days}일)")
    return out, cut, wins, done_k


def collect_re(old):
    """순환자원정보센터 전자입찰·수의견적 중 유기성 품목"""
    out = {}
    ads = keco_all("bidPbancService/getBidPbancInfo", SINCE)
    res = {x.get("pbancNo"): x for x in keco_all("bidPbancService/getBidPbancRsltInfo", SINCE)}
    today = now_kst().strftime("%Y-%m-%d")
    seen = set()
    for x in ads + [r for k, r in res.items() if k not in {a.get("pbancNo") for a in ads}]:
        no, title = x.get("pbancNo"), norm(x.get("pbancNm", ""))
        cls = " ".join(x.get(f) or "" for f in ("cmdtyLclsfNm", "cmdtyMclsfNm", "cmdtySclsfNm"))
        if not no or no in seen or not (ORG_CLS.search(cls) or ORG.search(title)):
            continue
        seen.add(no)
        reg, city = region(title, x.get("pbancIsrNm", ""))
        if reg == "기타":
            continue
        ordn = (re.search(r"bidTimeNum=(\d+)", x.get("dtlInfoUrlAddr") or "") or [None, "0"])[1]
        r = res.get(no) or {}
        end, opn = _ymd(x.get("bidDdlnDt")), _ymd(x.get("bdopnYmd"))
        status = (r.get("pbancRsltNm") or ("공고취소" if "취소" in (x.get("pbancSttsNm") or "") else
                                          "개찰완료" if (opn or end) and (opn or end) < today else "입찰중")).split("(")[0].strip()
        se = x.get("bidSeNm") or ""
        key = f"re:{no}:{ordn}"
        b = {**old.get(key, {}), "id": key, "src": "순환자원정보센터", "kind": se.split("(")[0].strip() or "입찰", "no": no, "ord": ordn,
             "title": title, "org": norm(x.get("pbancIsrNm", "")), "region": reg, "city": city, "start": _ymd(x.get("bidBgngDt")),
             "end": end, "open": opn, "status": status, "cls": x.get("cmdtyMclsfNm") or "",
             "type": "매각·매입" if re.search(r"매각|매입", se) else tag(title), "waste": waste_of(f"{title} {cls}"),
             "url": x.get("dtlInfoUrlAddr") or f"{RE_BASE}/bid/viewBidAdPage.do?bidAdNum={no}&bidTimeNum={ordn}"}
        if b.get("detail_status") != status:
            try:
                d = re_detail({"no": no, "ord": ordn, "status": status})
                b.update({k: d.get(k) for k in ("qty_kg", "pre_raw", "win_raw", "bidders", "url") if d.get(k) is not None})
                if d.get("status") in ("낙찰", "유찰"):
                    b["status"] = d["status"]
                b["detail_status"] = status
            except Exception as ex:
                print(f">> [순환자원] 상세 {no} 실패: {type(ex).__name__}")
            time.sleep(0.3)
        out[key] = b
    n_bid = len(out)
    ea = keco_all("pvctEstmtPbancService/getPvctEstmtPbancInfo", SINCE)
    er = {x.get("pbancNo"): x for x in keco_all("pvctEstmtPbancService/getPvctEstmtPbancRsltInfo", SINCE)}
    for x in list(er.values()) + [a for a in ea if a.get("pbancNo") not in er]:
        title = norm(x.get("pbancNm", ""))
        cls = " ".join(x.get(f) or "" for f in ("cmdtyLclsfNm", "cmdtyMclsfNm", "cmdtySclsfNm"))
        if not (ORG_CLS.search(cls) or ORG.search(title)):
            continue
        reg, city = region(title, x.get("pbancIsrNm", ""))
        if reg == "기타":
            continue
        st, se = x.get("pbancSttsNm") or "", x.get("estmtSeNm") or ""
        dd = _ymd(x.get("pbancDdlnDt"))
        qty = x.get("pbancCmdtyQtyCn") or ""
        b = {"id": f"esti:{x.get('pbancNo')}", "src": "순환자원정보센터(수의)", "kind": "수의견적 " + se.split("/")[0], "no": x.get("pbancNo"),
             "ord": "0", "title": title, "org": norm(x.get("pbancIsrNm", "")), "region": reg, "city": city, "start": _ymd(x.get("pbancBgngDt")),
             "end": dd, "open": dd, "cls": x.get("cmdtyMclsfNm") or "",
             "status": "낙찰" if st == "선정" else "유찰" if st in ("미선정", "유찰") else "개찰완료" if "완료" in st or (dd or "9999") < today else "입찰중",
             "type": "매각·매입" if re.search(r"매각|매입", se) else tag(title), "waste": waste_of(f"{title} {cls}"),
             "qty_kg": num(qty) * (1000 if "톤" in qty else 1) if num(qty) and ("kg" in qty or "톤" in qty) else None,
             "pre_raw": (x.get("estmtPrnmntPrcCn") or "").strip(), "url": x.get("dtlInfoUrlAddr") or ""}
        if b["status"] == "낙찰":
            b["win_raw"] = x.get("estmtAmtCn") or ""
        out[b["id"]] = b
    print(f">> [순환자원 API] 전자입찰 {len(ads)}건·수의견적 {len(ea)}건 중 수도권 유기성 {n_bid}건 + {len(out) - n_bid}건")
    return out


def main():
    st = load(OUT, {}) or {}
    first = not st.get("backfilled")
    items = {}
    for x in st.get("items", []):        # 거르기 기준·분류가 바뀌어도 저장된 건에 다시 적용
        if x.get("src") == "나라장터" and not keep(x.get("title", "")):
            continue
        reg, city = region(x.get("title", ""), x.get("org", ""))
        if reg == "기타":
            continue
        typ = x.get("type") if x.get("src") != "나라장터" else tag(x.get("title", ""), x.get("kind") == "공사")
        items[x["id"]] = {**x, "region": reg, "city": city, "type": typ, "waste": waste_of(f"{x.get('title', '')} {x.get('cls', '')}")}
    g, cut, wins, bf_k = ({}, False, {}, st.get("bf_k", 0))
    if DATA_KEY:
        g, cut, wins, bf_k = collect_g2b(first, st.get("bf_k", 0))
        try:
            items.update(collect_re({k: v for k, v in items.items() if k.startswith("re:")}))
        except Exception as e:
            print(f">> [순환자원] 실패: {type(e).__name__}: {str(e)[:150]}")
    else:
        print(">> DATA_GO_KR_KEY 없음 → 건너뜀")
    for k, v in g.items():
        old = items.get(k, {})
        items[k] = {**old, **v, **{f: old[f] for f in ("status", "win_amt", "win_rate", "winner", "bidders", "open") if f in old and old.get("status") == "낙찰"}}
    if DATA_KEY:
        try:
            enrich(items, T0 + 22 * 60)
        except Exception as e:
            print(f">> [첨부 확인] 실패: {type(e).__name__}: {str(e)[:150]}")
    for k, x in wins.items():
        if k not in items:
            continue
        items[k].update(status="낙찰", win_amt=num(x.get("sucsfbidAmt") or "") or None, win_rate=num(x.get("sucsfbidRate") or "") or None,
                        winner=x.get("bidwinnrNm") or "", bidders=int(num(x.get("prtcptCnum") or "") or 0),
                        open=(x.get("rlOpengDt") or items[k].get("open") or "")[:10])
    lst = sorted(items.values(), key=lambda b: (b.get("start") or "", b["id"]), reverse=True)
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "backfilled": st.get("backfilled") or (first and bf_k >= 400),
               "bf_k": bf_k, "items": lst})
    from collections import Counter
    print(f">> 저장: 유기성폐자원 입찰·용역·공사 {len(lst)}건 · 유형 {dict(Counter(b['type'] for b in lst))} · "
          f"폐기물 {dict(Counter(b['waste'] for b in lst))} · 낙찰 {sum(b.get('status') == '낙찰' for b in lst)}")
    pq = [b for b in lst if b.get("qty_t")]
    print(f">> 처리 대행 예상물량 확인 {len(pq)}건 / 확인 시도 {sum(1 for b in lst if b.get('qty_checked'))}건")
    for b in pq[:25]:
        wt = (b["win_amt"] / b["qty_t"] if b.get("win_amt") and b["win_amt"] > b.get("est", 0) / 500 else None)
        print(f"   {b['city']} | {b['title'][:40]} | 추정 {b.get('est')} | {b['qty_t']:,.1f}톤 → 추정 {(b.get('est') or 0) / b['qty_t'] / 1e4:.1f}만원/톤"
              f"{f' · 낙찰 {wt / 1e4:.1f}만원/톤' if wt else ''} | {b['qty_note'][:60]}")
    for b in lst[:40]:
        print(f"   {b['start']} {b['city']:4} | {b['type']:6} | {b['src'][:6]} | {b['org'][:14]} | {b['title'][:50]} | 추정 {b.get('est')} | {b.get('status')} {b.get('win_amt') or b.get('win_raw') or ''}")


if __name__ == "__main__":
    main()
