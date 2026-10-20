# -*- coding: utf-8 -*-
import os, re, json, urllib.parse, urllib.request
LAW = os.environ.get("LAW_API_KEY", "")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"}
def get(u, n=3_000_000, data=None, hdr=None):
    with urllib.request.urlopen(urllib.request.Request(u, data=data, headers={**H, **(hdr or {})}), timeout=40) as r:
        return r.read(n).decode("utf8", "ignore")
q = urllib.parse.quote
bid = "PRC_2CE1D6BED1FC48AF8E69CB92893E04"
h = get(f"https://likms.assembly.go.kr/bill/bi/billDetailPage.do?billId={bid}")
print("제안이유 위치:", [m.start() for m in re.finditer("제안이유", h)][:5])
for m in re.finditer("제안이유", h):
    print("  ctx:", re.sub(r"\s+", " ", h[max(0, m.start() - 300):m.start() + 500])[:800]); break
print("ajax/url 후보:", sorted(set(re.findall(r"['\"](/bill/[^'\"]{3,80}\.(?:do|json))", h)))[:40])
# 법령 검색 JSON 구조
if LAW:
    s = get(f"https://www.law.go.kr/DRF/lawSearch.do?OC={LAW}&target=law&type=JSON&query=" + q("폐기물의 국가 간 이동 및 그 처리에 관한 법률"))
    print("\n법령검색:", s[:700].replace(LAW, "<KEY>"))
    mst = re.search(r'"법령일련번호"\s*:\s*"?(\d+)', s)
    if mst:
        x = get(f"https://www.law.go.kr/DRF/lawService.do?OC={LAW}&target=law&type=XML&MST={mst.group(1)}")
        print("법령본문 태그:", sorted(set(re.findall(r"<([가-힣]+)>", x)))[:50])
        for t in ("제개정이유내용", "제개정이유", "개정문내용"):
            m = re.search(f"<{t}>(.*?)</{t}>", x, re.S)
            if m: print(f"  {t}:", re.sub(r"\s+", " ", re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)))[:700]); break
    s = get(f"https://www.law.go.kr/DRF/lawSearch.do?OC={LAW}&target=admrul&type=JSON&query=" + q("공급의무화제도"))
    print("\n행정규칙검색:", s[:600].replace(LAW, "<KEY>"))
    aid = re.search(r'"행정규칙일련번호"\s*:\s*"?(\d+)', s)
    if aid:
        x = get(f"https://www.law.go.kr/DRF/lawService.do?OC={LAW}&target=admrul&type=XML&ID={aid.group(1)}")
        print("행정규칙 태그:", sorted(set(re.findall(r"<([가-힣]+)>", x)))[:50])
        m = re.search(r"<제개정이유[^>]*>(.*?)</제개정이유", x, re.S)
        print("  제개정이유:", re.sub(r"\s+", " ", m.group(1))[:500] if m else "없음")
# 행정예고 상세
h = get("https://opinion.lawmaking.go.kr/gcom/admpp/list?asndOfiNm=" + q("기후에너지환경부"))
m = re.search(r'href="([^"]*admpp/(\d+)[^"]*)"[^>]*title="([^"]*분리[^"]*|[^"]*선별[^"]*)"', h)
print("\n행정예고 분리/선별 글:", m.group(3) if m else None)
first = re.search(r'href="([^"]*admpp/\d+[^"]*)"', h)
u = (m or first).group(1)
u = "https://opinion.lawmaking.go.kr" + u.replace("&amp;", "&") if u.startswith("/") else u.replace("&amp;", "&")
d = get(u)
i = d.find("주요내용")
print("행정예고 상세 주요내용:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", d[i - 200:i + 1200]))[:900] if i > 0 else "없음")
