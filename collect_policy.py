# -*- coding: utf-8 -*-
"""제도 변경 감시 → data/policy.json(폐플라스틱), data/policy_biogas.json(바이오가스)
- 국가법령정보 공동활용 API(LAW_API_KEY): data/policy_watch.json 의 법령·행정규칙(고시) 공포/발령일·시행일 변화 감시
- 기후에너지환경부 보도자료·입법예고·행정예고·고시 게시판: 제목에 관련 단어가 들어간 새 글 감시
새로 감지된 변경은 events 에 쌓고(화면 상단 알림), GITHUB_TOKEN 이 있으면 저장소 이슈로도 등록한다(구독자 메일)."""
import socket
import os, re, json, html, urllib.parse, urllib.request
from datetime import timedelta
from common import get, retry, load, save, now_kst

OUT, WATCH = "data/policy.json", "data/policy_watch.json"
LAW_KEY = os.environ.get("LAW_API_KEY", "")
socket.setdefaulttimeout(40)
LAW_API = "https://www.law.go.kr/DRF/lawSearch.do"
MCEE = "https://www.mcee.go.kr"
BOARDS = [("보도자료", 10598), ("입법예고", 68), ("행정예고", 10557), ("고시·훈령·예규", 71)]
KEYWORDS = re.compile(r"재생원료|재활용의무|생산자책임재활용|EPR|자원재활용법|자원의 절약|분담금|포장재|플라스틱|페트|폐기물부담금|"
                      r"순환경제|재활용 용이성|일회용|폐비닐|재활용품|선별|순환자원|직매립")
KW_BIO = re.compile(r"바이오가스|바이오메탄|유기성 ?폐자원|생산목표|음식물류? ?폐기물|가축분뇨|하수찌꺼기|하수 ?슬러지|혐기성|소화가스|"
                    r"신재생|공급인증서|REC|청정수소|상쇄|외부사업|에너지화")
PAGES = [  # (화면 이름, 결과 파일, 감시 법령 목록, 게시글 단어)
    ("폐플라스틱", "data/policy.json", "data/policy_watch.json", KEYWORDS),
    ("바이오가스", "data/policy_biogas.json", "data/policy_watch_biogas.json", KW_BIO),
]
_BOARD_HTML = {}


def norm(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def ymd(s):
    s = re.sub(r"\D", "", s or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else ""


def law_search(target, query):
    q = {"OC": LAW_KEY, "target": target, "type": "XML", "query": query, "display": 20}
    xml = retry(lambda: get(LAW_API + "?" + urllib.parse.urlencode(q), timeout=40), tries=3)
    tag = "law" if target == "law" else "admrul"
    out = []
    for blk in re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", xml, re.S):
        f = {k: norm(v.replace("<![CDATA[", "").replace("]]>", "")) for k, v in re.findall(r"<([^/>\s]+)>(.*?)</\1>", blk, re.S)}
        out.append(f)
    return out


def watch_laws(state, watch_file):
    if not LAW_KEY:
        print(">> [법령] LAW_API_KEY 없음 → 건너뜀")
        return state.get("laws", {}), []
    prev = state.get("laws", {})
    laws, events = {}, []
    for w in load(watch_file, []):
        name, target = w["name"], w["target"]
        query = re.sub(r"^\d{4}년\s*", "", name)          # 연도별 고시는 연도를 빼고 검색해 최신 것을 찾는다
        try:
            rows = law_search(target, query)
        except Exception as e:
            print(f">> [법령] {name} 조회 실패: {type(e).__name__}")
            if name in prev:
                laws[name] = prev[name]
            continue
        nm_key = "법령명한글" if target == "law" else "행정규칙명"
        cands = [r for r in rows if r.get(nm_key)]
        nz = lambda t: re.sub(r"[ㆍ·‧∙]", "·", re.sub(r"\s+", "", t or ""))     # 띄어쓰기·가운뎃점(ㆍ/·) 차이 무시
        exact = [r for r in cands if nz(r[nm_key]) == nz(name)]
        pool = exact or [r for r in cands if nz(query) in nz(r[nm_key])]
        if not pool:
            print(f">> [법령] {name}: 결과 없음 ({len(rows)}건 중)")
            continue
        date_key = "공포일자" if target == "law" else "발령일자"
        r = max(pool, key=lambda x: (x.get(date_key, ""), x.get("시행일자", "")))
        title = r[nm_key]
        rec = {"name": title, "target": target, "kind": r.get("제개정구분명", ""), "promulgated": ymd(r.get(date_key)),
               "effective": ymd(r.get("시행일자")), "no": r.get("공포번호") or r.get("발령번호") or "",
               "ministry": r.get("소관부처명", ""), "why": w.get("why", ""),
               "url": "https://www.law.go.kr/" + ("법령/" if target == "law" else "행정규칙/") + urllib.parse.quote(title)}
        laws[name] = rec
        old = prev.get(name)
        if old and (old.get("promulgated"), old.get("effective"), old.get("no")) != (rec["promulgated"], rec["effective"], rec["no"]):
            events.append({"date": now_kst().strftime("%Y-%m-%d"), "type": "법령·고시",
                           "title": f"{title} {rec['kind']} ({'공포' if target == 'law' else '발령'} {rec['promulgated']}, 시행 {rec['effective']})",
                           "url": rec["url"]})
        print(f">> [법령] {title}: {rec['kind']} {rec['promulgated']} 시행 {rec['effective']}")
    return laws, events


def watch_boards(state, kw):
    seen = set(state.get("board_seen", []))
    first = not seen
    posts, events = [], []
    for label, mid in BOARDS:
        if mid not in _BOARD_HTML:      # 게시판은 한 번만 받아 두 화면이 같이 쓴다
            try:
                _BOARD_HTML[mid] = retry(lambda: get(f"{MCEE}/home/web/index.do?menuId={mid}", timeout=40), tries=3)
            except Exception as e:
                print(f">> [부처] {label} 실패: {type(e).__name__}")
                _BOARD_HTML[mid] = None
        h = _BOARD_HTML[mid]
        if h is None:
            continue
        n = 0
        board_new = not any(k.startswith(f"{mid}:") for k in seen)     # 처음 제대로 읽히는 게시판은 최근 2주 글만 알림
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
            # 보도자료·행정예고는 board/read.do, 고시는 law/read.do, 입법예고는 국민참여입법센터(opinion.lawmaking.go.kr) 링크
            a = None
            for m in re.finditer(r"<a\b([^>]*)>", tr):
                at = m.group(1)
                hm, tm = re.search(r'href="([^"]+)"', at), re.search(r'title="([^"]+)"', at)
                if hm and tm and re.search(r"read\.do|lawmaking\.go\.kr/gcom/ogLmPp/\d", hm.group(1)):
                    a = (tm.group(1), hm.group(1))
                    break
            if not a:
                continue
            title, href = a
            title = re.sub(r"\s*새\s*창으로\s*연결$", "", norm(title))
            title = re.sub(r"^\[(?:진행|종료)\]\s*", "", title)
            bid = re.search(r"boardId=(\d+)|lawSeq=(\d+)|ogLmPp/(\d+)", href)
            bid = next((g for g in bid.groups() if g), None) if bid else None
            d = re.search(r"(\d{4})\s*[.-]\s*(\d{1,2})\s*[.-]\s*(\d{1,2})", norm(tr))
            date = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}" if d else ""
            href = html.unescape(href)
            href = re.sub(r";jsessionid=[^?]*", "", href)
            url = MCEE + href if href.startswith("/") else href
            key = f"{mid}:{bid or title}"
            n += 1
            if not kw.search(title):
                continue
            posts.append({"key": key, "board": label, "title": title, "date": date, "url": url})
            recent = date and date >= (now_kst() - timedelta(days=14)).strftime("%Y-%m-%d")
            if key not in seen and not first and (not board_new or recent):
                events.append({"date": now_kst().strftime("%Y-%m-%d"), "type": label, "title": title, "url": url})
            seen.add(key)
        print(f">> [부처] {label}: 글 {n}건 확인")
    return posts, events, sorted(seen)[-1000:]


def open_issues(events, label=""):
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (tok and repo and events):
        return
    for e in events[:10]:
        body = json.dumps({"title": f"[제도 변경 감지{' · ' + label if label else ''}] {e['title'][:110]}",
                           "body": f"- 구분: {e['type']}\n- 감지일: {e['date']}\n- 원문: {e['url']}\n\n폐플라스틱 데일리 리포트가 자동으로 등록한 알림입니다."}).encode()
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
        try:
            urllib.request.urlopen(req, timeout=30).read()
            print(f">> [알림] 이슈 등록: {e['title'][:60]}")
        except Exception as ex:
            print(f">> [알림] 이슈 등록 실패: {type(ex).__name__} {str(ex)[:120]}")


def run_page(label, out, watch_file, kw):
    st = load(out, {}) or {}
    laws, ev1 = watch_laws(st, watch_file)
    posts, ev2, seen = watch_boards(st, kw)
    old_posts = {p["key"]: p for p in st.get("posts", [])}
    for p in posts:
        old_posts[p["key"]] = p
    cut = (now_kst() - timedelta(days=365)).strftime("%Y-%m-%d")
    posts_all = sorted((p for p in old_posts.values() if (p.get("date") or "9999") >= cut), key=lambda p: p.get("date", ""), reverse=True)[:60]
    events = (ev1 + ev2 + st.get("events", []))[:50]
    save(out, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "laws": laws, "posts": posts_all, "events": events,
               "board_seen": seen})
    open_issues(ev1 + ev2, label)
    print(f">> [{label}] 저장: 법령 {len(laws)}건, 관련 게시글 {len(posts_all)}건, 새 변경 {len(ev1) + len(ev2)}건")


def main():
    for label, out, watch_file, kw in PAGES:
        print(f"==== {label}")
        try:
            run_page(label, out, watch_file, kw)
        except Exception as e:
            print(f">> [{label}] 실패: {type(e).__name__}: {str(e)[:200]}")


if __name__ == "__main__":
    main()
