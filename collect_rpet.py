# -*- coding: utf-8 -*-
"""rPET 가격 (기사 기준) → data/rpet.json
- data/rpet_seed.json: 사람이 기사 원문을 확인해 넣은 가격 (auto=false). 직접 고치거나 추가해도 된다.
- 자동 추출: 구글 뉴스·전문지에서 rPET 가격 기사를 찾아 본문 문장에서 가격을 뽑는다 (auto=true).
  기사 게재일을 가격 시점으로 쓰고, 근거 문장(quote)을 함께 저장해 화면에서 확인할 수 있게 한다.
- 원/kg 환산: 기사일의 ECB 기준환율(frankfurter)로 환산해 시점 간 비교가 가능하게 한다."""
import re, json, html, hashlib, urllib.parse
from datetime import timedelta
from common import get, get_json, load, now_kst, save_with_history
from collect_news import parse_rss, EN_BLOCK

SEED, OUT = "data/rpet_seed.json", "data/rpet.json"
EN_Q = ['"rPET" prices', '"rPET" price tonne', '"recycled PET" prices', '"food-grade" rPET pellets', "rPET flakes prices",
        '"recycled polymer" prices PET', "rPET site:opis.com", "rPET site:argusmedia.com", "rPET site:spglobal.com",
        "rPET site:chemorbis.com", "rPET site:euwid-recycling.com", '"PET bales" prices']
KO_Q = ["rPET 가격", "재생 페트 가격", "식품용 rPET", "재생 PET 칩 가격", "페트 플레이크 가격", "재생원료 페트 단가"]
RSS = [("Recycling Today", "https://www.recyclingtoday.com/rss/")]
MAX_FETCH = 30

NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
CUR = r"€|EUR|Eur|euros?|US\$|\$|USD|£|GBP"
PER = r"metric tons?|metric tonnes?|mt|tonnes?|tons?|t|lb|pounds?|kg"
PATS = [
    ("sym", re.compile(rf"(?P<cur>{CUR})\s?(?P<a>{NUM})(?:\s?(?:-|–|to)\s?(?:{CUR})?\s?(?P<b>{NUM}))?\s?(?:/|per\s|a\s)\s?(?P<per>{PER})\b")),
    ("yuan", re.compile(rf"(?P<a>{NUM})(?:\s?(?:-|–|to)\s?(?P<b>{NUM}))?\s?(?P<cur>yuan|CNY|RMB)\s?(?:/|per\s)\s?(?P<per>{PER})\b", re.I)),
    ("cent", re.compile(rf"(?P<a>{NUM})(?:\s?(?:-|–|to)\s?(?P<b>{NUM}))?\s?(?P<cur>cents?|¢)\s?(?:/|per\s|a\s)\s?(?P<per>lb|pound)", re.I)),
    ("krw1", re.compile(rf"(?:kg당|㎏당|킬로그램당)\s?(?P<a>{NUM})\s?(?P<man>만)?\s?원")),
    ("krw2", re.compile(rf"(?P<a>{NUM})\s?(?P<man>만)?\s?원\s?/\s?(?P<per>kg|㎏|톤)")),
    ("krw3", re.compile(rf"톤당\s?(?P<a>{NUM})\s?(?P<man>만)?\s?원")),
]
RPET = re.compile(r"\br-?pet\b|recycled pet|recycled polyethylene terephthalate|food[- ]grade pellet|\bfgp\b|재생\s?페트|재생\s?pet|"
                  r"식품용\s?(?:재생|페트|rpet)|재활용\s?페트|페트\s?플레이크|pet\s?플레이크|\bpet\b.{0,30}\bbales?\b|\bbales?\b.{0,30}\bpet\b", re.I)
GRADES = [("식품용 펠렛", r"pellets?|regranulates?|\bchips?\b|펠렛|칩|resin"), ("플레이크", r"flakes?|플레이크"), ("베일", r"\bbales?\b|베일|압축")]
REGIONS = [("유럽", r"europe|\bnwe\b|\beu\b|german|ital|spain|spanish|france|french|\buk\b|britain|british|netherlands|유럽|독일"),
           ("아시아", r"\basia|china|chinese|thai|vietnam|indonesia|india|japan|taiwan|malaysia|중국|아시아|동남아|일본"),
           ("북미", r"\bus\b|u\.s\.|united states|north america|west coast|east coast|canada|mexico|미국|북미")]
VIRGIN = re.compile(r"virgin|\bvpet\b|prime|신재|버진", re.I)
DELTA = re.compile(r"\b(?:by|up|down|rose|fell|gain(?:ed)?|lost|increase[sd]?|decrease[sd]?|change[sd]?|drop(?:ped)?|added|shed)\s*(?:of\s*)?$|[+−-]\s*$|상승|하락|올라|내려", re.I)
SPREAD_AFTER = re.compile(r"^\W{0,3}(?:\w+\s){0,2}(premium|discount|spread|differential|gap|프리미엄|할인)", re.I)
PREV_AFTER = re.compile(r"^.{0,40}?(previous|prior|last (?:week|month)|a (?:week|month) (?:earlier|ago)|전주|전월|지난주|지난달)", re.I)
OTHER = re.compile(r"\br-?(?:pp|hdpe|ldpe|lldpe|pe|ps)\b|polypropylene|polyethylene|polystyrene|\bhdpe\b|\bldpe\b|\bpp\b|\bpe\b|\bpvc\b|\bpaper|cardboard|alumin|steel|glass|PP|PE\s", re.I)
BOUNDS = {"식품용 펠렛": (500, 6000), "플레이크": (300, 4000), "베일": (30, 2000), "rPET": (200, 6000)}


def _f(s):
    return float(s.replace(",", ""))


def _pid(p):
    return hashlib.md5(f"{p['url']}|{p['grade']}|{p['region']}|{p['low']}".encode()).hexdigest()[:10]


# ---------------------------------------------------------------- 구글 뉴스 링크 → 원문 주소
def resolve_gnews(link):
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
    u = re.search(r'garturlres\\",\\"(https?://[^\\"]+)', txt)
    return u.group(1).encode().decode("unicode_escape") if u else None


# ---------------------------------------------------------------- 본문 → 가격 문장
def page_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>|</td>|</tr>", "\n", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t\xa0]+", " ", t)


def sentences(text):
    for block in text.split("\n"):
        block = block.strip()
        if len(block) < 20:
            continue
        for s in re.split(r"(?<=[.!?。])\s+(?=[A-Z가-힣\"'(])", block):
            if 20 <= len(s) <= 600:
                yield s.strip()


def _pick(rules, text, pos=None):
    """pos 앞에서 가장 가까운 키워드의 구분, 없으면 문장 전체에서 처음 나오는 것"""
    best, bpos = None, -1
    for name, pat in rules:
        for m in re.finditer(pat, text, re.I):
            if pos is not None and m.start() <= pos and m.start() > bpos:
                best, bpos = name, m.start()
    if best:
        return best
    hits = [(m.start(), name) for name, pat in rules for m in [re.search(pat, text, re.I)] if m]
    return min(hits)[1] if hits else None


def extract(text, title, lang):
    """문장마다 rPET 가격 후보 → [{grade, region, cur, per, low, high, virgin_*, premium, quote}]"""
    head_region = _pick(REGIONS, title) or _pick(REGIONS, text[:2000])
    out, ctx = [], None
    for s in sentences(text):
        is_pet, other = bool(RPET.search(s)), bool(OTHER.search(s))
        if is_pet and not other:
            ctx = "pet"
        elif other and not is_pet:
            ctx = "other"
        # rPET 단어가 없는 문장도 바로 앞 문맥이 rPET이고 등급어(플레이크·펠렛·베일)가 있으면 가격 문장으로 본다
        if not is_pet and not (ctx == "pet" and not other and _pick(GRADES, s)):
            continue
        rec = {"quote": s[:300], "prices": [], "virgin": None, "premium": None}
        for kind, pat in PATS:
            for m in pat.finditer(s):
                a, b = _f(m.group("a")), _f(m.group("b")) if m.groupdict().get("b") else None
                pre, post = s[max(0, m.start() - 40):m.start()], s[m.end():m.end() + 30]
                if DELTA.search(pre[-15:]) or PREV_AFTER.search(post):
                    continue
                if kind.startswith("krw"):
                    cur, per = "KRW", ("t" if (m.groupdict().get("per") == "톤" or kind == "krw3") else "kg")
                    mul = 10000 if m.groupdict().get("man") else 1
                    a, b = a * mul, (b * mul if b else None)
                elif kind == "cent":
                    cur, per, a, b = "USD", "lb", round(a / 100, 4), (round(b / 100, 4) if b else None)
                elif kind == "yuan":
                    cur, per = "CNY", "t"
                else:
                    c = m.group("cur").lower()
                    cur = "EUR" if c.startswith(("€", "eur")) else "GBP" if c in ("£", "gbp") else "USD"
                    pw = m.group("per").lower()
                    per = "lb" if pw.startswith(("lb", "pound")) else "kg" if pw == "kg" else "t"
                lo, hi = (min(a, b), max(a, b)) if b else (a, a)
                sp = SPREAD_AFTER.search(post)
                if sp:
                    sign = -1 if re.search(r"discount|할인", sp.group(1), re.I) else 1
                    rec["premium"] = (cur, per, sign * (lo + hi) / 2)
                    continue
                if VIRGIN.search(pre):
                    rec["virgin"] = (cur, per, lo, hi)
                    continue
                grade = _pick(GRADES, s, m.start()) or "rPET"
                if grade == "식품용 펠렛" and not re.search(r"food|fgp|bottle|beverage|식품|음료|pellet|칩|chip", s, re.I):
                    grade = "rPET"
                region = "국내" if cur == "KRW" else (_pick(REGIONS, s, m.start()) or head_region)
                if not region:
                    continue
                rec["prices"].append({"grade": grade, "region": region, "cur": cur, "per": per, "low": lo, "high": hi})
        for p in rec["prices"]:
            v = rec["virgin"]
            pr = rec["premium"]
            out.append({**p, "virgin_low": v[2] if v and v[:2] == (p["cur"], p["per"]) else None,
                        "virgin_high": v[3] if v and v[:2] == (p["cur"], p["per"]) else None,
                        "premium": round(pr[2], 1) if pr and pr[:2] == (p["cur"], p["per"]) else None, "quote": rec["quote"]})
    return out


# ---------------------------------------------------------------- 환율·원/kg
def fx_on(cur, date, cache):
    if cur == "KRW":
        return 1.0
    k = f"{cur}:{date}"
    if k not in cache:
        j = get_json(f"https://api.frankfurter.dev/v1/{date}?base={cur}&symbols=KRW", timeout=20)
        cache[k] = j["rates"]["KRW"]
    return cache[k]


def per_kg(v, per):
    return None if v is None else v / 1000 if per == "t" else v * 2.20462 if per == "lb" else v


def add_krw(p, cache):
    try:
        fx = fx_on(p["cur"], p["date"], cache)
    except Exception as e:
        print(f">> [환율] {p['cur']} {p['date']} 실패: {type(e).__name__}")
        return
    p["fx"] = fx
    for k in ("low", "high"):
        v = per_kg(p.get(k), p["per"])
        p[f"krw_{k}"] = round(v * fx, 1) if v is not None else None
    if p.get("krw_low") is not None:
        p["krw_kg"] = round((p["krw_low"] + p["krw_high"]) / 2, 1)
    if p.get("premium") is not None:
        p["premium_krw_kg"] = round(per_kg(p["premium"], p["per"]) * fx, 1)


# ---------------------------------------------------------------- 수집
def candidates(seen):
    items = []
    for q in EN_Q:
        try:
            items += [(x, "en") for x in parse_rss(get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:21d")
                                                       + "&hl=en-US&gl=US&ceid=US:en", raw=True, timeout=30))]
        except Exception as e:
            print(f">> [검색] {q} 실패: {type(e).__name__}")
    for q in KO_Q:
        try:
            items += [(x, "ko") for x in parse_rss(get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:21d")
                                                       + "&hl=ko&gl=KR&ceid=KR:ko", raw=True, timeout=30))]
        except Exception as e:
            print(f">> [검색] {q} 실패: {type(e).__name__}")
    for name, url in RSS:
        try:
            items += [(x, "en") for x in parse_rss(get(url, raw=True, timeout=30), name)]
        except Exception as e:
            print(f">> [RSS] {name} 실패: {type(e).__name__}")
    out, keys = [], set()
    for x, lang in items:
        key = re.sub(r"\W+", "", x["title"].lower())[:80]
        if key in keys or key in seen or any(b.lower() in (x.get("source") or "").lower() for b in EN_BLOCK):
            continue
        if not re.search(r"pet|페트|플라스틱|recycl|재생", x["title"], re.I):
            continue
        keys.add(key)
        out.append((key, x, lang))
    out.sort(key=lambda t: t[1].get("pub") or now_kst(), reverse=True)
    return out


def main():
    seed = load(SEED, [])
    st = load(OUT, {})
    seen, cache = st.get("seen", {}), st.get("fx", {})
    auto = [p for p in st.get("points", []) if p.get("auto")]
    today = now_kst().date()
    fetched = added = 0
    for key, x, lang in candidates(seen):
        if fetched >= MAX_FETCH:
            break
        seen[key] = today.isoformat()
        fetched += 1
        try:
            url = resolve_gnews(x["link"])
            if not url:
                print(f">> [원문] 주소 확인 실패: {x['title'][:60]}")
                continue
            raw = get(url, timeout=25)
        except Exception as e:
            print(f">> [원문] {type(e).__name__}: {x['title'][:60]}")
            continue
        found = extract(page_text(raw), x["title"], lang)
        date = (x.get("pub") or now_kst()).date().isoformat()
        for f in found:
            p = {"date": date, "basis": "", **f, "title": x["title"], "source": x.get("source") or urllib.parse.urlparse(url).netloc,
                 "url": url, "auto": True}
            p["id"] = _pid(p)
            add_krw(p, cache)
            lo, hi = BOUNDS.get(p["grade"], (0, 1e9))
            if p.get("krw_kg") is not None and not (lo <= p["krw_kg"] <= hi):
                print(f">> [제외] 범위 밖 {p['grade']} {p['krw_kg']}원/kg: {p['quote'][:80]}")
                continue
            d0 = today.fromisoformat(p["date"]).toordinal()
            dup = any(q["id"] == p["id"] or (q["region"] == p["region"] and q["grade"] == p["grade"] and q.get("low") == p["low"]
                                              and abs(today.fromisoformat(q["date"]).toordinal() - d0) <= 10)
                      for q in seed + auto)
            if dup:
                continue
            auto.append(p)
            added += 1
            print(f">> [추가] {p['date']} {p['region']} {p['grade']} {p['cur']} {p['low']}-{p['high']}/{p['per']} | {p['source']} | {p['quote'][:90]}")
    pts = []
    for p in seed + auto:
        if p.get("krw_kg") is None or "fx" not in p:
            add_krw(p, cache)
        pts.append(p)
    pts.sort(key=lambda p: (p["date"], p["region"], p["grade"]))
    cut = (today - timedelta(days=180)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cut}
    print(f">> 기사 {fetched}건 확인, 자동 추출 {added}건 추가 (확인 {len(seed)} · 자동 {len(auto)})")
    save_with_history("rpet", {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "points": pts, "fx": cache, "seen": seen})


if __name__ == "__main__":
    main()
