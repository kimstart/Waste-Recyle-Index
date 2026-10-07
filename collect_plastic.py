# -*- coding: utf-8 -*-
"""폐플라스틱 페이지 지표 수집 → data/plastic.json
- 월간: 국내 재생원료 단가 (한국환경공단 순환자원정보센터 '재활용가능자원 가격조사', 전국평균, 원/kg, VAT 포함)
- 일간: 중국 신재 플라스틱 선물 (정저우·다롄 상품거래소 연속물 종가, Sina Finance, 위안/톤) + 원/kg 환산
- 일간: 국제유가 (오피넷), 환율 (수출입은행 → ECB → Yahoo)
수집에 실패한 항목은 이전 값을 그대로 둔다."""
import re, json, http.cookiejar, urllib.request
from common import UA, get, retry, run_all, now_kst
from sources import fetch_fx, fx_items, fetch_oil

RECYCLE_URL = "https://www.recycling-info.or.kr/sds/marketIndex.do?menuNo=M130301"
# (키, 사이트 품목명, 화면 표시명)
RECYCLE_ITEMS = [
    ("r_comp_pet", "압축 (PET)", "압축 PET"),
    ("r_comp_pe", "압축 (PE)", "압축 PE"),
    ("r_comp_pp", "압축 (PP)", "압축 PP"),
    ("r_flk_pet_clear", "플레이크 (PET무색)", "플레이크 PET(무색)"),
    ("r_flk_pet_color", "플레이크 (PET유색)", "플레이크 PET(유색)"),
    ("r_flk_pe", "플레이크 (PE)", "플레이크 PE"),
    ("r_flk_pp", "플레이크 (PP)", "플레이크 PP"),
    ("r_flk_pvc", "플레이크 (PVC)", "플레이크 PVC"),
    ("r_pel_pe", "펠렛 (PE)", "펠렛 PE"),
    ("r_pel_pp", "펠렛 (PP)", "펠렛 PP"),
]
REGIONS = ["수도권", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "전국평균"]

# Sina 연속물 코드, 화면 표시명, 거래소
FUTURES = [
    ("cn_pet", "PR0", "PET 병 칩", "정저우"),
    ("cn_pe", "L0", "PE (LLDPE)", "다롄"),
    ("cn_pp", "PP0", "PP", "다롄"),
    ("cn_pvc", "V0", "PVC", "다롄"),
]


def _num(s):
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _prev_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y:04d}.{m:02d}"


def _recycle_rows(html):
    rows = []
    for tr in re.findall(r'<tr class="rrm">(.*?)</tr>', html, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip() for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 3 and re.fullmatch(r"\d{4}\.\d{2}", cells[0]):
            rows.append(cells)
    return rows


def _recycle_session():
    """첫 화면에서 쿠키를 받은 뒤 가격조사 화면을 요청"""
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    H = dict(UA)
    op.open(urllib.request.Request("https://www.recycling-info.or.kr/rrs/main.do", headers=H), timeout=40).read()
    H["Referer"] = "https://www.recycling-info.or.kr/rrs/main.do"
    b = op.open(urllib.request.Request(RECYCLE_URL, headers=H), timeout=40).read()
    return b.decode("utf-8", "ignore")


def fetch_recycle(items, extra):
    """페이지 첫 화면에 최신 실적월 표가 그대로 들어 있다(로그인·자바스크립트 불필요).
    기간 지정 조회는 막혀 있어, 매달 받은 값을 extra.recycle_months 에 쌓아 전월 대비를 계산한다."""
    rows = []
    for how, fn in (("바로 요청", lambda: get(RECYCLE_URL)), ("쿠키 세션", _recycle_session), ("http 주소", lambda: get(RECYCLE_URL.replace("https://", "http://")))):
        try:
            html = retry(fn, tries=2)
        except Exception as e:
            print(f">> [재생원료] {how} 실패: {type(e).__name__}: {str(e)[:120]}")
            continue
        rows = _recycle_rows(html)
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        print(f">> [재생원료] {how}: 응답 {len(html):,}자, 제목 {title.group(1).strip()[:60] if title else '-'!r}, 표 {len(rows)}행")
        if rows:
            break
        print(f">> [재생원료] 응답 앞부분: {re.sub(r'\s+', ' ', html[:300])!r}")
    print(f">> [재생원료] 실적월 {sorted({r[0] for r in rows})}")
    if not rows:
        raise ValueError("재생원료 표 없음")
    months = extra.setdefault("recycle_months", {})
    for r in rows:
        ym, name, vals = r[0], r[1], r[2:]
        rec = {REGIONS[i]: _num(v) for i, v in enumerate(vals[:len(REGIONS)])}
        months.setdefault(ym, {})[name] = rec
    latest = max(r[0] for r in rows)
    prev_ym = _prev_month(latest)
    out = {}
    for key, site_name, label in RECYCLE_ITEMS:
        cur = months.get(latest, {}).get(site_name)
        if not cur or cur.get("전국평균") is None:
            print(f">> [재생원료] {site_name} 값 없음")
            continue
        prev = (months.get(prev_ym) or {}).get(site_name) or {}
        out[key] = {"name": label, "unit": "원/kg", "date": latest.replace(".", "-"), "value": cur["전국평균"],
                    "prev_date": prev_ym.replace(".", "-") if prev.get("전국평균") is not None else None,
                    "prev_value": prev.get("전국평균"), "capital": cur.get("수도권"), "src": "순환자원정보센터"}
    # 너무 오래된 달은 정리(최근 36개월만 보관)
    for k in sorted(months)[:-36]:
        months.pop(k, None)
    return out


def sina_daily(sym):
    url = f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/InnerFuturesNewService.getDailyKLine?symbol={sym}"
    txt = retry(lambda: get(url, headers={"Referer": "https://finance.sina.com.cn/"}), tries=3)
    m = re.search(r"\(\[(.*)\]\)", txt, re.S)
    if not m:
        raise ValueError(f"Sina {sym} 응답 형식 이상: {txt[:120]!r}")
    rows = json.loads("[" + m.group(1) + "]")
    return [(r["d"], float(r["c"])) for r in rows if float(r.get("c") or 0) > 0]


def fetch_futures(items, extra):
    out = {}
    for key, sym, name, ex in FUTURES:
        try:
            s = sina_daily(sym)
            (d, v), (pd, pv) = s[-1], (s[-2] if len(s) > 1 else (None, None))
            out[key] = {"name": name, "item": f"{ex} 연속물", "unit": "위안/톤", "date": d, "value": v,
                        "prev_date": pd, "prev_value": pv, "src": "Sina Finance",
                        "spark": [round(x[1]) for x in s[-30:]]}
        except Exception as e:
            print(f">> [중국선물] {name}({sym}) 실패: {type(e).__name__}: {str(e)[:120]}")
    if not out:
        raise ValueError("중국 선물 자료 없음")
    return out


def fetch_fx_step(items, extra):
    rows, src = fetch_fx()
    return fx_items(rows, src)


def add_krw(items):
    """중국 선물 위안/톤 → 원/kg (원/위안 환율 × 위안/톤 ÷ 1000). 환율은 수집된 최신 값."""
    fx = items.get("fx_cny")
    if not fx:
        return
    for key, *_ in FUTURES:
        it = items.get(key)
        if it:
            it["krw_kg"] = round(it["value"] * fx["value"] / 1000, 1)
            it["fx_used"] = fx["value"]


if __name__ == "__main__":
    def futures_with_krw(items, extra):
        got = fetch_futures(items, extra)
        tmp = dict(items)
        tmp.update(got)
        add_krw(tmp)
        return {k: tmp[k] for k in got}

    # 환율을 먼저 받아야 선물 원화 환산에 최신 환율이 쓰인다
    run_all("plastic", [("환율", fetch_fx_step), ("국내 재생원료", fetch_recycle),
                        ("중국 선물", futures_with_krw), ("국제유가", fetch_oil)])
