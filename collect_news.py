# -*- coding: utf-8 -*-
"""뉴스 수집 → data/news_plastic.json, data/news_biogas.json (각각 국내·해외)
- 국내: 구글 뉴스(한국어) 키워드 검색
- 해외: 구글 뉴스(영문) 키워드 검색 + 전문지 우대/광고성 매체 제외, 폐플라스틱은 Recycling Today RSS 추가
같은 내용의 기사는 하나로 합치고, 관련도 점수 → 최신순으로 상위만 남긴다.
키워드·매체 목록은 아래 CONFIG 에서 이름만 고치면 된다."""
import re, sys, time, difflib, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from common import KST, get, now_kst, save_with_history

CONFIG = {
    "plastic": {
        "ko_keywords": ["폐플라스틱", "재생원료 플라스틱", "재생플라스틱", "플라스틱 재활용", "페트 재활용", "열분해유",
                        "화학적 재활용", "폐비닐", "재생원료 사용 의무", "플라스틱 협약", "순환경제 플라스틱", "재활용 선별장"],
        "ko_core": ["플라스틱", "재생원료", "재활용", "페트", "PET", "열분해", "폐비닐", "순환경제", "선별", "EPR", "협약",
                    "rPET", "PE", "PP", "가격", "단가", "의무", "규제", "수출", "수입"],
        "en_queries": ["rPET", '"recycled PET"', '"chemical recycling"', '"plastic pyrolysis"', '"recycled content" plastic',
                       '"plastics treaty"', '"recycled polypropylene"', '"plastic recycling"', "PPWR recycled",
                       '"recycled plastic" prices'],
        "en_core": ["plastic", "rpet", "pet", "recycl", "pyrolysis", "resin", "polypropylene", "polyethylene", "hdpe",
                    "ppwr", "epr", "treaty", "packaging", "price", "flake", "pellet", "circular"],
        "en_sources": ["Plastics News", "PlasticsToday", "Recycling Today", "Resource Recycling", "Recycling International",
                       "Packaging Insights", "EUWID", "Circular Online", "ChemAnalyst", "Packaging Gateway", "Packaging Europe",
                       "Sustainable Plastics", "letsrecycle", "Waste Dive", "Packaging Dive", "ENDS", "Reuters", "Bloomberg",
                       "S&P Global", "ICIS", "OPIS", "Argus", "Chemical Week", "C&EN", "Financial Times", "Plastics Engineering",
                       "European Plastics News", "Plastics & Rubber Weekly", "Waste Management World", "Recycling Magazine",
                       "Plastics Recycling Update", "Innovation News Network", "Interplas"],
        "ko_require": ["플라스틱", "페트", "PET", "재생원료", "열분해", "비닐", "일회용", "1회용", "재활용", "포장재", "용기", "순환경제"],
        "en_require": ["plastic", "PET", "rPET", "PP", "PE", "HDPE", "LDPE", "PVC", "PS", "EPS", "polymer", "resin", "pyrolysis",
                       "polyethylene", "polypropylene", "polystyrene", "film", "flexibles", "bale",
                       "ppwr", "bottle", "food-grade", "packaging waste", "recycled content"],
        # 전문지별 추가 검색 (구글 뉴스 site: 검색, 앞 괄호는 검색어)
        "en_sites": ["plasticsnews.com", "plasticstoday.com", "packaginginsights.com", "resource-recycling.com",
                     "recyclingtoday.com", "recyclinginternational.com", "sustainableplastics.com", "euwid-recycling.com",
                     "packagingeurope.com", "packaging-gateway.com", "letsrecycle.com", "icis.com"],
        "en_site_query": "(recycling OR recycled OR rPET OR resin OR prices OR PPWR)",
        "en_whitelist_only": True,
        "rss": [("Recycling Today", "https://www.recyclingtoday.com/rss/",
                 r"plastic|\bpet\b|rpet|hdpe|polypropylene|polyethylene|resin|pyrolysis|bottle|film|flexible|packaging")],
    },
    "biogas": {
        "ko_keywords": ["바이오가스", "바이오메탄", "바이오가스 생산목표제", "유기성폐자원", "음식물류폐기물 바이오가스",
                        "가축분뇨 바이오가스", "혐기성소화", "하수슬러지 바이오가스", "바이오가스화시설", "음식물쓰레기 처리"],
        "ko_core": ["바이오가스", "바이오메탄", "생산목표제", "유기성", "음식물", "가축분뇨", "혐기성", "소화", "슬러지",
                    "도시가스", "수소", "에너지화", "REC", "배출권", "감축", "의무", "정책", "가격", "요금"],
        "en_queries": ["biomethane", "biogas", '"renewable natural gas"', '"anaerobic digestion"', "biomethane price",
                       '"guarantees of origin" biomethane', "biomethane grid injection", "RNG landfill gas"],
        "en_core": ["biomethane", "biogas", "rng", "renewable natural gas", "anaerobic", "digest", "guarantee", "price",
                    "gas", "grid", "certificate", "landfill", "manure", "food waste"],
        "en_sources": ["Bioenergy Insight", "Bioenergy News", "gasworld", "ENDS", "Argus", "Quantum Commodity", "Montel", "Biomass Magazine",
                       "European Biogas", "Biogas World", "Reuters", "Bloomberg", "S&P Global", "Waste Dive", "Biofuels Digest",
                       "Renewable Energy World", "Energy Voice", "Recharge", "Gas Processing", "World Bio Market Insights",
                       "Waste Management World", "Financial Times", "Euractiv", "Clean Energy Wire", "letsrecycle",
                       "Bioenergy International", "RNG Coalition", "energynews.pro", "ICIS"],
        "ko_require": ["바이오가스", "바이오메탄", "생산목표제", "혐기성", "에너지화", "유기성폐자원", "소화가스", "바이오가스화"],
        "en_require": ["biomethane", "biogas", "rng", "renewable natural gas", "anaerobic", "digester", "green gas",
                       "landfill gas", "renewable gas", "bio-cng", "biocng"],
        "en_sites": ["bioenergy-news.com", "gasworld.com", "endswasteandbioenergy.com", "argusmedia.com", "qcintel.com",
                     "biomassmagazine.com", "europeanbiogas.eu", "biogasworld.com", "montelnews.com", "wastedive.com"],
        "en_site_query": "(biomethane OR biogas OR RNG OR \"renewable gas\" OR \"anaerobic digestion\")",
        "en_whitelist_only": False,
        "rss": [],
    },
}

# 광고성·주가·시장보고서 매체 (해외)
EN_BLOCK = ["AD HOC NEWS", "kalkine", "KLSE Screener", "IndexBox", "TradingView", "Stock Titan", "IMARC", "Grand View Research",
            "Kings Research", "Mordor", "openPR", "MarketsandMarkets", "Market.us", "GlobeNewswire", "EIN Presswire",
            "Business Research", "Fortune Business Insights", "Precedence Research", "Allied Market", "MarketBeat",
            "Zacks", "Simply Wall St", "Investing News Network", "LatestLY", "Yahoo Finance"]
EN_NOISE = ["stock", "shares", "market size", "cagr", "forecast 20", "market report", "obituary", "recipe", "cookie",
            "sign up", "webinar", "register now", "podcast", "award nominations", "appointed", "appoints", "names new"]
KO_SRC_BLOCK = ["Vietnam.vn", "Daum"]   # 기계번역·포털 재게시
KO_NOISE = ["연봉", "채용", "인사", "부고", "결혼", "장학", "봉사", "기부", "특징주", "목표주가", "주가", "수상", "표창", "시상",
            "동정", "화재", "합작법인", "산업전", "농구", "배구", "야구", "축구", "시즌", "후원", "나눔", "캠페인", "공모전"]
KO_SOFT = ["설명회", "포럼", "세미나", "워크숍", "개최", "성료", "간담회", "발대식", "업무협약", "MOU", "협약식", "맞손"]
POLICY = ["정책", "제도", "개편", "기본계획", "정부", "국회", "법안", "개정", "시행령", "고시", "규제", "의무", "목표제", "기후부",
          "환경부", "산업부", "가격", "단가", "요금"]

TOP_KO, TOP_EN = 12, 10
PER_SOURCE = 3
SIM, JAC = 0.50, 0.25
HOLIDAYS = {"2026-10-05", "2026-10-09", "2026-12-25", "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-01", "2027-05-05",
            "2027-05-13", "2027-06-07", "2027-08-16", "2027-09-14", "2027-09-15", "2027-09-16", "2027-10-04", "2027-10-11",
            "2027-12-27"}


def lookback_hours(now, base=36):
    """직전 영업일 낮 12시 이후 기사부터 포함 (주말·휴일이 끼면 자동으로 늘어남)"""
    d = now.date()
    while True:
        d -= timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            break
    cut = datetime(d.year, d.month, d.day, 12, 0, tzinfo=KST)
    return max(base, int((now - cut).total_seconds() // 3600) + 1)


def gnews(q, when, lang):
    hl = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " " + when) + "&" + hl
    return get(url, raw=True, timeout=30)


def parse_rss(xml_bytes, default_source=""):
    out = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        title = re.sub(r"\s+", " ", (it.findtext("title") or "")).strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else default_source
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(KST)
        except Exception:
            continue
        if title and link:
            out.append({"title": title, "source": source, "link": link, "pub": pub,
                        "desc": re.sub(r"<[^>]+>", " ", it.findtext("description") or "")})
    return out


def hangul_ratio(t):
    letters = re.findall(r"[A-Za-z가-힣]", t)
    return (sum(1 for c in letters if "가" <= c <= "힣") / len(letters)) if letters else 0


def norm(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】", " ", t)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t).lower()


def grams(n):
    return {n[i:i + 2] for i in range(len(n) - 1)} or {n}


def dedup(items):
    seen, uniq = set(), []
    for x in items:
        if x["link"] not in seen:
            seen.add(x["link"])
            uniq.append(x)
    uniq.sort(key=lambda x: x["pub"])
    groups = []
    for x in uniq:
        nx = norm(x["title"])
        if not nx:
            continue
        gx = grams(nx)
        for g in groups:
            if nx == g["n"] or difflib.SequenceMatcher(None, nx, g["n"]).ratio() >= SIM or len(gx & g["g"]) / max(1, len(gx | g["g"])) >= JAC:
                g["more"] += 1
                break
        else:
            groups.append({"n": nx, "g": gx, "item": x, "more": 0})
    return groups


def title_has(title, words):
    """대소문자가 섞인 단어(PET, rPET)는 그대로, 소문자 단어는 대소문자 무시하고 단어 앞머리 일치"""
    for w in words:
        if w != w.lower():
            if re.search(r"\b" + re.escape(w) + r"\b", title):
                return True
        elif re.search(r"\b" + re.escape(w), title.lower()):
            return True
    return False


def in_list(src, names):
    s = (src or "").lower()
    return any(n.lower() in s for n in names)


def pack(groups):
    return [{"title": g["item"]["title"], "source": g["item"]["source"], "link": g["item"]["link"],
             "pub": g["item"]["pub"].strftime("%Y-%m-%d %H:%M"), "more": g["more"]} for g in groups]


def collect_ko(cfg, now, hours, when):
    allit = []
    for q in cfg["ko_keywords"]:
        try:
            rows = parse_rss(gnews(q, when, "ko"))
        except Exception as e:
            print(f"   [국내] '{q}' 실패: {type(e).__name__}")
            continue
        rows = [r for r in rows if now - r["pub"] <= timedelta(hours=hours) and hangul_ratio(r["title"]) >= 0.5
                and not any(w in r["title"] for w in KO_NOISE) and not in_list(r["source"], KO_SRC_BLOCK)
                and any(w.lower() in r["title"].lower() for w in cfg["ko_require"])][:25]
        print(f"   [국내] '{q}' {len(rows)}건")
        allit += rows
        time.sleep(1)
    groups = dedup(allit)

    def score(g):
        t = g["item"]["title"]
        core = sum(1 for w in cfg["ko_core"] if w.lower() in t.lower())
        pol = 6 if any(w in t for w in POLICY) else 0
        return min(core, 4) * 3 + pol + min(g["more"], 3) - 3 * sum(1 for w in KO_SOFT if w in t), core

    groups = [g for g in groups if score(g)[1] >= 1]
    groups.sort(key=lambda g: (score(g)[0], g["item"]["pub"].timestamp()), reverse=True)
    top = groups[:TOP_KO]
    top.sort(key=lambda g: -g["item"]["pub"].timestamp())
    return pack(top), len(allit)


def collect_en(cfg, now, hours, when):
    allit = []
    for q in cfg["en_queries"]:
        try:
            rows = parse_rss(gnews(q, when, "en"))
        except Exception as e:
            print(f"   [해외] '{q}' 실패: {type(e).__name__}")
            continue
        allit += rows
        print(f"   [해외] '{q}' {len(rows)}건")
        time.sleep(1)
    for dom in cfg.get("en_sites", []):
        q = f'{cfg["en_site_query"]} site:{dom}'
        try:
            rows = parse_rss(gnews(q, when, "en"))
        except Exception as e:
            print(f"   [해외 전문지] {dom} 실패: {type(e).__name__}")
            continue
        allit += rows
        print(f"   [해외 전문지] {dom} {len(rows)}건")
        time.sleep(1)
    for name, url, pat in cfg["rss"]:
        try:
            rows = parse_rss(get(url, raw=True, timeout=30), default_source=name)
            rows = [r for r in rows if re.search(pat, r["title"] + " " + r["desc"], re.I)]
            for r in rows:
                r["source"] = r["source"] or name
            print(f"   [해외 RSS] {name} {len(rows)}건")
            allit += rows
        except Exception as e:
            print(f"   [해외 RSS] {name} 실패: {type(e).__name__}")
    rows = [r for r in allit if now - r["pub"] <= timedelta(hours=hours)
            and not in_list(r["source"], EN_BLOCK) and not any(w in r["title"].lower() for w in EN_NOISE)
            and hangul_ratio(r["title"]) < 0.2
            and title_has(r["title"], cfg["en_require"])]
    if cfg["en_whitelist_only"]:
        dropped = sorted({r["source"] for r in rows if not in_list(r["source"], cfg["en_sources"])})
        rows = [r for r in rows if in_list(r["source"], cfg["en_sources"])]
        print(f"   [해외] 전문지 외 제외: {', '.join(dropped[:30])}")
    groups = dedup(rows)

    def score(g):
        t = g["item"]["title"].lower()
        core = sum(1 for w in cfg["en_core"] if w in t)
        trade = 5 if in_list(g["item"]["source"], cfg["en_sources"]) else 0
        return min(core, 4) * 3 + trade + min(g["more"], 3), core

    groups = [g for g in groups if score(g)[1] >= 1]
    groups.sort(key=lambda g: (score(g)[0], g["item"]["pub"].timestamp()), reverse=True)
    top, per = [], {}
    for g in groups:                       # 한 매체가 목록을 독차지하지 않도록 매체당 최대 PER_SOURCE건
        src = g["item"]["source"] or ""
        if per.get(src, 0) >= PER_SOURCE:
            continue
        per[src] = per.get(src, 0) + 1
        top.append(g)
        if len(top) >= TOP_EN:
            break
    top.sort(key=lambda g: -g["item"]["pub"].timestamp())
    return pack(top), len(allit)


def main(pages):
    now = now_kst()
    hours = lookback_hours(now)
    hours_en = max(hours, 72)       # 해외는 시차·발행 빈도를 고려해 최소 72시간
    when = "when:%dd" % (hours // 24 + 2)
    when_en = "when:%dd" % (hours_en // 24 + 1)
    for page in pages:
        cfg = CONFIG[page]
        print(f">> [{page}] 수집 범위 국내 {hours}시간 / 해외 {hours_en}시간")
        ko, nko = collect_ko(cfg, now, hours, when)
        en, nen = collect_en(cfg, now, hours_en, when_en)
        print(f">> [{page}] 국내 {nko}건 → {len(ko)}건, 해외 {nen}건 → {len(en)}건")
        for x in ko + en:
            print(f"   - [{x['source']}] {x['title']}")
        if not ko and not en:
            print(f">> [{page}] 기사가 없어 기존 파일 유지")
            continue
        save_with_history(f"news_{page}", {"updated": now.strftime("%Y-%m-%d %H:%M"), "domestic": ko, "overseas": en})


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIG))
