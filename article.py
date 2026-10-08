# -*- coding: utf-8 -*-
"""기사 원문 다루기: 구글 뉴스 링크 → 원문 주소, 본문 텍스트, 국내 기사 2~3줄 발췌 요약"""
import re, json, html, urllib.parse
from common import get


def resolve_gnews(link):
    """구글 뉴스 RSS 링크(news.google.com/rss/articles/...)를 원문 주소로 바꾼다. 실패하면 None"""
    if "news.google.com" not in link:
        return link
    m = re.search(r"/articles/([^?/]+)", link)
    if not m:
        return None
    aid = m.group(1)
    page = get(f"https://news.google.com/rss/articles/{aid}", timeout=20)
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sg and ts):
        return None
    inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
             f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts.group(1)},"{sg.group(1)}"]')
    body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner, None, "generic"]]]))
    txt = get("https://news.google.com/_/DotsSplashUi/data/batchexecute",
              headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}, data=body.encode(), timeout=20)
    u = re.search(r'garturlres\\",\\"(https?://.+?)\\"', txt)
    if not u:
        return None
    url = u.group(1)
    for _ in range(3):                      # JSON 안의 JSON이라 \\u003d 같은 이스케이프가 겹쳐 있음
        if "\\" not in url:
            break
        url = url.encode("latin-1", "backslashreplace").decode("unicode_escape")
    return url


def page_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form|figure|figcaption|aside|button)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>|</td>|</tr>", "\n", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t\xa0]+", " ", t)


# ---------------------------------------------------------------- 국내 기사 발췌 요약
BODY_PATS = [r'id="article-view-content-div"', r'itemprop="articleBody"', r'id="articleBody"', r'id="article_body"',
             r'id="newsct_article"', r'id="articeBody"', r'id="textBody"', r'id="news_body_id"', r'id="newsEndContents"',
             r'class="[^"]*\b(?:article_body|article-body|article_txt|news_body|news-body|art_body|view_con|article_view|'
             r'news_cnt_detail_wrap|story-news|article-text|cont_view|news_text|view_cont|txt_article|article_content|articleView)\b[^"]*"',
             r"<article\b"]
DROP = re.compile(r"기자\s*$|기자\s*=|@[\w.-]+\.\w+|ⓒ|©|무단\s*전재|재배포|저작권|Copyright|구독|▶|☞|관련기사|사진\s*=|제공\s*=|"
                  r"뉴스레터|카카오톡|네이버|광고문의|거래되고 있다|주가|장중|목표주가|시가총액|종가 기준|기사제보|많이 본|인기기사|앱 다운|입력\s*\d{4}|수정\s*\d{4}|\[사진\]|\(사진\)|그래픽=")
LEAD = re.compile(r"^\s*(?:\[[^\]]{1,40}\]|\([^)]{1,40}=[^)]{0,30}\)|【[^】]{1,40}】)\s*|^\s*[가-힣]{2,4}\s*(?:기자|특파원)\s*=\s*")
BIZ = re.compile(r"\d|재생원료|단가|가격|톤|억|만원|의무|선별|입찰|투자|설비|공장|수요|계약|목표|규제|시행|확대|감축|EPR|분담금|생산")


def _body_html(raw):
    for p in BODY_PATS:
        m = re.search(p, raw)
        if not m:
            continue
        start = raw.rfind("<", 0, m.start())
        chunk = raw[start:start + 60000]
        txt = page_text(chunk)
        if len(re.sub(r"\s", "", txt)) > 120:
            return txt
    return None


def k_sentences(text):
    out = []
    for block in text.split("\n"):
        block = LEAD.sub("", block.strip())
        if len(block) < 15:
            continue
        for s in re.split(r"(?<=다\.)\s+|(?<=[.?!])\s+(?=[가-힣A-Z\"'“‘(])", block):
            s = LEAD.sub("", s.strip())
            if 25 <= len(s) <= 260 and not DROP.search(s) and re.search(r"[가-힣]{4}", s):
                out.append(s)
    return out


def summarize_ko(raw, title="", limit=230):
    """본문 앞부분에서 2~3문장을 발췌: 첫 문장(리드) + 숫자·사업 관련 단어가 있는 문장 우선, 원래 순서 유지"""
    body = _body_html(raw)
    if not body:
        return ""
    sents = k_sentences(body)[:12]
    if not sents:
        return ""
    tnorm = re.sub(r"\W", "", title)
    sents = [s for s in sents if re.sub(r"\W", "", s) != tnorm]
    if not sents:
        return ""
    pick = [0]
    ranked = sorted(range(1, min(len(sents), 10)), key=lambda i: (-len(BIZ.findall(sents[i])), i))
    total = len(sents[0])
    for i in ranked:
        if len(pick) >= 3 or total + len(sents[i]) > limit:
            continue
        pick.append(i)
        total += len(sents[i])
    if len(pick) == 1 and len(sents) > 1 and total + len(sents[1]) <= limit + 60:
        pick.append(1)
    s = " ".join(sents[i] for i in sorted(pick))
    return s if len(s) <= limit + 60 else s[:limit + 57].rstrip() + "…"
