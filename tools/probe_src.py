# -*- coding: utf-8 -*-
"""최근 동향 '내용' 원천 점검: 국회 의안정보 / 법령 제개정이유 / 국민참여입법센터 (키는 출력하지 않음)"""
import os, re, json, urllib.parse, urllib.request
LAW = os.environ.get("LAW_API_KEY", "")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"}
def get(u, n=3_000_000):
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40) as r:
        return r.status, r.geturl(), r.read(n).decode("utf8", "ignore")
def show(tag, u, pat=None, n=600):
    try:
        st, fin, h = get(u)
        print(f"\n== {tag}: {st} {len(h)}자 → {fin[:90]}")
        if pat:
            m = re.search(pat, h, re.S)
            print("   ", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0) if m else h[:n]))[:n])
        return h
    except Exception as e:
        print(f"\n== {tag}: 실패 {type(e).__name__}: {str(e)[:120]}")
        return ""
q = urllib.parse.quote
# 1) 열린국회정보 국회의원 발의법률안 (키 없이)
h = show("열린국회 발의법률안", "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn?Type=json&pIndex=1&pSize=5&AGE=22&BILL_NAME=" + q("폐기물관리법"), None)
print("   ", h[:900])
link = re.search(r'"DETAIL_LINK":"([^"]+)"', h)
bid = re.search(r'"BILL_ID":"([^"]+)"', h)
if link:
    show("의안 상세(DETAIL_LINK)", link.group(1).replace("\\/", "/"), r"제안이유.{0,1500}")
if bid:
    show("의안 상세 likms", f"https://likms.assembly.go.kr/bill/billDetail.do?billId={bid.group(1)}", r"제안이유.{0,1500}")
    show("의안 요약 ajax", f"https://likms.assembly.go.kr/bill/bi/bill/detail/summary.do?billId={bid.group(1)}", None)
# 2) 법령 제개정이유
if LAW:
    s = show("법령 검색", f"https://www.law.go.kr/DRF/lawSearch.do?OC={LAW}&target=law&type=JSON&query=" + q("폐기물의 국가 간 이동 및 그 처리에 관한 법률"))
    mst = re.search(r'"법령일련번호":"?(\d+)', s)
    if mst:
        show("법령 본문(제개정이유)", f"https://www.law.go.kr/DRF/lawService.do?OC={LAW}&target=law&type=XML&MST={mst.group(1)}", r"<제개정이유>.{0,1500}|<개정문>.{0,1500}")
    s = show("행정규칙 검색", f"https://www.law.go.kr/DRF/lawSearch.do?OC={LAW}&target=admrul&type=JSON&query=" + q("공급의무화제도"))
    aid = re.search(r'"행정규칙일련번호":"?(\d+)', s)
    if aid:
        h2 = show("행정규칙 본문", f"https://www.law.go.kr/DRF/lawService.do?OC={LAW}&target=admrul&type=XML&ID={aid.group(1)}", r"<제개정이유[^>]*>.{0,1200}")
        print("    태그들:", sorted(set(re.findall(r"<([가-힣A-Za-z]+)>", h2)))[:60])
# 3) 국민참여입법센터 입법예고 상세(기후부 게시판에서 본 번호)
show("입법예고 상세 89078", "https://opinion.lawmaking.go.kr/gcom/ogLmPp/89078?opYn=Y&cptOfiOrgCd=1482000&isOgYn=Y&myOpnYn=N&btnType=1", r"(주요내용|개정이유).{0,1500}")
show("입법예고 목록 검색", "https://opinion.lawmaking.go.kr/gcom/ogLmPp?lsNm=" + q("재생에너지") + "&cptOfiOrgCd=1482000", r"ogLmPp/\d+.{0,300}")
show("행정예고 목록", "https://opinion.lawmaking.go.kr/gcom/admpp/list?asndOfiNm=" + q("기후에너지환경부"), r"admpp/\d+.{0,300}")
