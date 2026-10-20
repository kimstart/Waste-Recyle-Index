# -*- coding: utf-8 -*-
"""'최근 동향' 항목의 대략적인 내용을 공식 원문에서 가져온다(법령·고시·공고·의안은 저작권 보호 대상이 아님).
- 의원 발의: 열린국회정보 발의법률안 API(키 없이) → 국회 의안정보 '제안이유 및 주요내용'
- 법령 개정: 국가법령정보 API(LAW_API_KEY) '제개정이유'
- 고시·지침 개정: 국가법령정보 행정규칙 '제개정이유'
- 입법·행정예고: 국민참여입법센터 예고문 '개정이유'
요지는 '…하려는 것임' 같은 결론 문장을 골라 160자 안으로 줄인다."""
import os, re, json, html, urllib.parse, urllib.request

LAW = os.environ.get("LAW_API_KEY", "")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
LIKMS = "https://likms.assembly.go.kr"
OPINION = "https://opinion.lawmaking.go.kr"


def get(u, timeout=40):
    u = urllib.parse.quote(u, safe=":/?&=%#;,+@")
    with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout) as r:
        return r.read(4_000_000).decode("utf8", "ignore")


def nz(t):
    return re.sub(r"[\s「」()（）ㆍ·‧∙“”\"']", "", t or "")


def text(h):
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h or "", flags=re.S | re.I)
    h = re.sub(r"<!\[CDATA\[|\]\]>", "", h)
    h = re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", h, flags=re.I)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def gist(t, n=160):
    """결론 문장('이에 …하려는 것임') 우선, 없으면 첫 문장"""
    t = re.sub(r"\s+", " ", t or "").strip()
    t = re.sub(r"^(?:[◇□○ㅇ]\s*)?(?:제안이유|(?:제·?)?개정\s*이유|제정\s*이유|추진\s*배경)?\s*(?:및\s*주요\s*내용)?\s*[:：]?\s*", "", t)
    t = re.sub(r"\((?:안\s*)?제\d+조[^)]*\)", "", t)                       # '(안 제14조)' 같은 조문 표시 제거
    sents = [x.strip(" ㅇ○-·*") for x in re.split(r"(?<=것임)\.?\s*|(?<=[다함음])\.\s+", t) if len(x.strip()) > 15]
    def score(x):
        v = 0
        if re.match(r"이에\s|따라서\s", x): v += 3                                   # 결론 문장
        if re.search(r"하려는\s*것임$|하고자\s*함$|하려\s*함$|하려는\s*것$|것임$", x): v += 2
        if re.match(r"현행|해외|최근|그간|그동안|아울러|또한|이는|한편|프랑스|미국|정부는", x): v -= 2   # 배경·부연 문장
        if re.search(r"(?:있음|있다|실정임|실정이다|필요가\s*있다|필요함)$", x): v -= 1
        return v
    s = max(sents, key=lambda x: (score(x), -sents.index(x))) if sents else ""
    s = re.sub(r"^이에\s*(?:따라|따라서)?\s*,?\s*", "", s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def bill(name, by, date):
    """열린국회정보에서 같은 법률명·대표발의자·발의일의 의안을 찾아 제안이유 요지"""
    lead = re.sub(r"의원.*", "", by or "").strip()
    q = {"Type": "json", "pIndex": 1, "pSize": 5, "AGE": 22, "BILL_NAME": re.split(r"[·ㆍ]", name)[0].strip()}   # 가운뎃점 표기 차이 회피
    if lead:
        q["PROPOSER"] = lead
    j = json.loads(get("https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn?" + urllib.parse.urlencode(q)))
    rows = (j.get("nzmimeepazxkubdpn") or [{}, {}])[-1].get("row") or []
    rows = [r for r in rows if nz(r.get("BILL_NAME", "")).startswith(nz(name))] or rows
    r = next((r for r in rows if r.get("PROPOSE_DT") == date), rows[0] if rows else None)
    if not r:
        return None
    h = get(f"{LIKMS}/bill/bi/popup/billSummary.do?billId={r['BILL_ID']}")
    t = text(h)
    i = t.rfind("제안이유")                       # 창 제목 말고 본문 머리의 '제안이유 및 주요내용' 뒤부터
    body = t[i:] if i >= 0 else t
    body = re.split(r"참고사항|창닫기\s*$", body)[0]
    body = re.sub(r"^제안이유\s*및\s*주요내용\s*(?:창닫기)?\s*\[\d+\][^\n]*", "", body)
    return {"gist": gist(body), "src": "국회 의안정보", "url": r.get("DETAIL_LINK", "").replace("http://", "https://"),
            "title": r.get("BILL_NAME", "")}


def law_reason(name, date, admrul=False):
    if not LAW:
        return None
    tgt = "admrul" if admrul else "law"
    q = {"OC": LAW, "target": tgt, "type": "JSON", "query": re.sub(r"[「」]", "", name)}
    if not admrul:
        q["nw"] = 1          # 시행 예정 법령까지
    j = json.loads(get("https://www.law.go.kr/DRF/lawSearch.do?" + urllib.parse.urlencode(q)))
    box = j.get("AdmRulSearch" if admrul else "LawSearch", {})
    rows = box.get(tgt) or []
    rows = rows if isinstance(rows, list) else [rows]
    nm, dk = ("행정규칙명", "발령일자") if admrul else ("법령명한글", "공포일자")
    d8 = (date or "").replace("-", "")
    key = lambda t: re.sub(r"^신에너지및재생에너지|^신재생에너지", "재생에너지", nz(t))
    same = [r for r in rows if key(r.get(nm)) == key(name)] or [r for r in rows if key(name) in key(r.get(nm)) or key(r.get(nm)) in key(name)]
    r = next((r for r in same if r.get(dk) == d8), None)
    if not r:
        return None
    sid = r.get("행정규칙일련번호") if admrul else r.get("법령일련번호")
    x = get(f"https://www.law.go.kr/DRF/lawService.do?OC={LAW}&target={tgt}&type=XML&" + ("ID=" if admrul else "MST=") + str(sid))
    m = re.search(r"<제개정이유내용>(.*?)</제개정이유내용>", x, re.S)
    if not m:
        return None
    t = text(m.group(1))
    t = re.sub(r"^\[[^\]]*\]\s*", "", t)
    t = re.split(r"◇\s*(?:주요내용|개정\s*내용)", t)[0]
    return {"gist": gist(t), "src": "국가법령정보", "title": r.get(nm, ""),
            "url": "https://www.law.go.kr/" + ("행정규칙/" if admrul else "법령/") + urllib.parse.quote(r.get(nm, ""))}


def notice(name, date, admrul=False):
    """국민참여입법센터 입법예고(법령)·행정예고(행정규칙) 목록에서 같은 이름의 예고문을 찾아 개정이유 요지"""
    nm = re.sub(r"[「」]", "", name)
    if admrul:
        lists = [f"{OPINION}/gcom/admpp/list?asndOfiNm=기후에너지환경부&pageIndex={p}" for p in (1, 2, 3)]
        pat = r'href="([^"]*admpp/\d+[^"]*)"[^>]*title="([^"]+)"'
    else:
        lists = [f"{OPINION}/gcom/ogLmPp?lsNm={nm}&cptOfiOrgCd=1482000"]
        pat = r'href="([^"]*ogLmPp/\d+[^"]*)"[^>]*title="([^"]+)"'
    for lu in lists:
        h = get(lu)
        for href, title in re.findall(pat, h):
            if not nz(title).startswith(nz(nm)) and nz(nm) not in nz(title):
                continue
            u = html.unescape(href)
            u = OPINION + u if u.startswith("/") else u
            t = text(get(u))
            m = (re.search(r"1\.\s*(?:개정|제정)\s*이유\s*(.*?)(?:2\.\s*주요\s*내용|$)", t, re.S) or
                 re.search(r"(?<!취지)(?:개정|제정)\s*이유\s*(.*?)(?:2\.\s*주요\s*내용|주요\s*내용\s*가\.|$)", t, re.S))
            g = gist(m.group(1)[:3000]) if m else ""
            if not g or re.search(r"행정절차법|의견을\s*듣", g):
                continue
            return {"gist": g, "src": "국민참여입법센터", "url": u.split(";jsessionid")[0], "title": re.sub(r"\s*이동$", "", title)}
    return None


def lookup(it):
    """BKL 항목 하나 → {'gist','src','url'} 또는 None"""
    adm = it["name"].startswith("「")
    if it["sec"] == "의원 발의":
        return bill(it["name"], it.get("by", ""), it.get("date", ""))
    if it["sec"] == "법령·고시 개정":
        return law_reason(it["name"], it.get("date", ""), admrul=adm)
    if it["sec"] == "입법·행정예고":
        return notice(it["name"], it.get("date", ""), admrul=adm)
    return None
