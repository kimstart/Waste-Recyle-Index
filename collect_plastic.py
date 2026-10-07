# -*- coding: utf-8 -*-
"""폐플라스틱 페이지 지표 수집 → data/plastic.json
- 월간: 국내 재생원료 단가 (한국환경공단 '재활용가능자원 가격조사', 원/kg, VAT 포함)
  출처 순서: 순환자원정보센터 화면(전국평균) → 공공데이터포털 API(키 필요) → 공공데이터포털 CSV(권역 단순평균)
- 일간: 중국 신재 플라스틱 선물 (정저우·다롄 상품거래소 연속물 종가, Sina Finance, 위안/톤) + 원/kg 환산
- 월간: 영국 플라스틱 PRN(재활용 증명서) 가격 (letsrecycle.com, £/톤, 매월 첫 주에 전월 가격 공개) + 원/kg 환산
- 참고: 독일 bvse 플라스틱 시황 보고서 최신 PDF 링크 (plasticker.de)
- 환율 (수출입은행 → ECB → Yahoo): 원/파운드는 PRN 원화 환산에 사용
수집에 실패한 항목은 이전 값을 그대로 둔다."""
import os, re, io, csv, json, urllib.parse
from common import UA, get, retry, run_all, now_kst
from sources import fetch_fx, fx_items, fetch_gbp

RECYCLE_URL = "https://www.recycling-info.or.kr/sds/marketIndex.do?menuNo=M130301"
RECYCLE_API = "https://apis.data.go.kr/B552584/reutilMrktPrcExmn/getlist"
RECYCLE_FILE_PAGE = "https://www.data.go.kr/data/3076421/fileData.do"
DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
# (키, 정규화한 품목명, 화면 표시명) — 정규화: 공백·괄호·하이픈·'(잡색)' 제거. 예) '압축 (PET)', '압축-PET(잡색)' → '압축PET'
RECYCLE_ITEMS = [
    ("r_comp_pet", "압축PET", "압축 PET"),
    ("r_comp_pe", "압축PE", "압축 PE"),
    ("r_comp_pp", "압축PP", "압축 PP"),
    ("r_flk_pet_clear", "플레이크PET무색", "플레이크 PET(무색)"),
    ("r_flk_pet_color", "플레이크PET유색", "플레이크 PET(유색)"),
    ("r_flk_pe", "플레이크PE", "플레이크 PE"),
    ("r_flk_pp", "플레이크PP", "플레이크 PP"),
    ("r_flk_pvc", "플레이크PVC", "플레이크 PVC"),
    ("r_pel_pe", "펠렛PE", "펠렛 PE"),
    ("r_pel_pp", "펠렛PP", "펠렛 PP"),
]
REGIONS = ["수도권", "강원", "충북", "충남", "전북", "전남", "경북", "경남"]
BASIS_NAT, BASIS_MEAN = "전국평균", "권역 단순평균"

# Sina 연속물 코드, 화면 표시명, 거래소
FUTURES = [
    ("cn_pet", "PR0", "PET 병 칩", "정저우"),
    ("cn_pe", "L0", "PE (LLDPE)", "다롄"),
    ("cn_pp", "PP0", "PP", "다롄"),
    ("cn_pvc", "V0", "PVC", "다롄"),
]

def _num(s):
    s = str(s if s is not None else "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _norm(name):
    name = name.replace("(잡색)", "").replace("청·녹색", "청녹색")
    return re.sub(r"[^0-9A-Za-z가-힣]", "", name)


def _prev_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y:04d}-{m:02d}"


# 각 출처는 {YYYY-MM: {정규화 품목명: {"nat": 전국평균|None, "regions": {권역: 값}}}} 를 돌려준다
def _site_rows(html):
    rows = []
    for tr in re.findall(r'<tr class="rrm">(.*?)</tr>', html, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip() for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 3 and re.fullmatch(r"\d{4}\.\d{2}", cells[0]):
            rows.append(cells)
    return rows


def recycle_site():
    """① 순환자원정보센터 화면 표 (전국평균 포함). 해외 IP는 차단되는 경우가 많다."""
    html = retry(lambda: get(RECYCLE_URL), tries=2)
    rows = _site_rows(html)
    if not rows:
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        raise ValueError(f"표 없음 (응답 제목 {title.group(1).strip()[:40] if title else '-'!r})")
    out = {}
    for r in rows:
        ym = r[0].replace(".", "-")
        vals = [_num(v) for v in r[2:]]
        out.setdefault(ym, {})[_norm(r[1])] = {"nat": vals[8] if len(vals) > 8 else None,
                                              "regions": {REGIONS[i]: v for i, v in enumerate(vals[:8]) if v is not None}}
    return out


def recycle_api():
    """② 공공데이터포털 '한국환경공단_재활용가능자원 가격조사 정보 조회 서비스' (Secret DATA_GO_KR_KEY 필요, 활용신청 후)"""
    if not DATA_KEY:
        raise ValueError("DATA_GO_KR_KEY 없음")
    rows, page = [], 1
    while page <= 30:
        q = {"serviceKey": DATA_KEY, "pageNo": page, "numOfRows": 1000, "returnType": "json", "type": "json", "dataType": "json"}
        txt = retry(lambda: get(RECYCLE_API + "?" + urllib.parse.urlencode(q)), tries=2)
        try:
            j = json.loads(txt)
        except ValueError:
            raise ValueError("API 응답이 JSON이 아님: " + " ".join(txt[:200].split()))
        root = j.get("response", j)
        head, body = root.get("header", {}), root.get("body", {})
        its = body.get("items", []) if isinstance(body, dict) else []
        if isinstance(its, dict):
            its = its.get("item", [])
        flat = []
        for x in its if isinstance(its, list) else [its]:
            flat.append(x.get("item", x) if isinstance(x, dict) else x)
        if page == 1:
            print(f">> [재생원료 API] code={head.get('resultCode')} msg={head.get('resultMsg')} 전체={body.get('totalCount') if isinstance(body, dict) else None}")
            print(f">> [재생원료 API] 예시: {flat[:3]}")
        rows += flat
        total = int(_num(body.get("totalCount")) or 0) if isinstance(body, dict) else 0
        if not flat or len(rows) >= total:
            break
        page += 1
    out = {}
    for x in rows:
        d = re.sub(r"\D", "", str(x.get("exmnYmd", "")))
        price = _num(x.get("mrktPrc"))
        if len(d) < 6 or price is None:
            continue
        ym = f"{d[:4]}-{d[4:6]}"
        rec = out.setdefault(ym, {}).setdefault(_norm(str(x.get("itemNm", ""))), {"nat": None, "regions": {}})
        region = str(x.get("stdgNm", "")).strip()
        if "전국" in region:
            rec["nat"] = price
        else:
            rec["regions"][region] = price
    if not out:
        raise ValueError("API 자료 없음")
    print(f">> [재생원료 API] 월: {sorted(out)[-3:]}, 품목 예: {list(out[max(out)])[:8]}")
    return out


def recycle_csv():
    """③ 공공데이터포털 파일데이터 '한국환경공단_재활용가능자원 가격조사' (키 불필요, 매월 갱신, 최신 1개월, 전국평균 열 없음)"""
    html = retry(lambda: get(RECYCLE_FILE_PAGE), tries=2)
    m = re.search(r"fileDownload\.do\?atchFileId=(FILE_\d+)&(?:amp;)?fileDetailSn=(\d+)", html)
    if not m:
        raise ValueError("파일 다운로드 경로 없음")
    url = f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={m.group(1)}&fileDetailSn={m.group(2)}&insertDataPrcus=N"
    b = retry(lambda: get(url, raw=True, headers={"Referer": RECYCLE_FILE_PAGE}), tries=2)
    txt = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            txt = b.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    rows = list(csv.reader(io.StringIO(txt or "")))
    print(f">> [재생원료 CSV] {m.group(1)} {len(rows)}행, 머리글 {rows[0] if rows else None}")
    if len(rows) < 2:
        raise ValueError("CSV 자료 없음")
    head = [h.strip() for h in rows[0]]
    out = {}
    for r in rows[1:]:
        if len(r) < 3 or not re.match(r"\d{4}-\d{2}", r[0].strip()):
            continue
        ym = r[0].strip()[:7]
        regions = {}
        nat = None
        for i, h in enumerate(head[2:], start=2):
            if i >= len(r):
                break
            v = _num(r[i])
            if h in REGIONS and v is not None:
                regions[h] = v
            elif "전국" in h and v is not None:
                nat = v
        out.setdefault(ym, {})[_norm(r[1])] = {"nat": nat, "regions": regions}
    if not out:
        raise ValueError("CSV 해석 실패")
    return out


def fetch_recycle(items, extra):
    """세 출처를 순서대로 시도. 전국평균이 없으면 8개 권역 단순평균을 쓰고 기준을 표시한다.
    월별 값은 extra.recycle_months 에 쌓아 전월 대비를 계산한다(같은 달은 전국평균 값이 있으면 그것을 우선 보존)."""
    data, src = None, None
    for name, fn in (("순환자원정보센터", recycle_site), ("공공데이터포털 API", recycle_api), ("공공데이터포털 파일", recycle_csv)):
        try:
            data, src = fn(), name
            print(f">> [재생원료] {name}에서 수집: 월 {sorted(data)}")
            break
        except Exception as e:
            print(f">> [재생원료] {name} 실패: {type(e).__name__}: {str(e)[:160]}")
    if not data:
        raise ValueError("재생원료 자료 없음 (세 출처 모두 실패)")
    months = extra.setdefault("recycle_months", {})
    for ym, its in data.items():
        for nm, rec in its.items():
            regs = rec.get("regions") or {}
            if rec.get("nat") is not None:
                val, basis = rec["nat"], BASIS_NAT
            elif regs:
                val, basis = round(sum(regs.values()) / len(regs), 1), BASIS_MEAN
            else:
                continue
            old = months.setdefault(ym, {}).get(nm)
            if old and old.get("basis") == BASIS_NAT and basis != BASIS_NAT:
                continue
            months[ym][nm] = {"value": val, "basis": basis, "capital": regs.get("수도권"), "n": len(regs), "src": src}
    latest = max(data)
    prev_ym = _prev_month(latest)
    out = {}
    for key, nm, label in RECYCLE_ITEMS:
        cur = months.get(latest, {}).get(nm)
        if not cur:
            print(f">> [재생원료] {nm} 값 없음")
            continue
        prev = (months.get(prev_ym) or {}).get(nm) or {}
        out[key] = {"name": label, "unit": "원/kg", "date": latest, "value": cur["value"],
                    "prev_date": prev_ym if prev.get("value") is not None else None, "prev_value": prev.get("value"),
                    "capital": cur.get("capital"), "src": cur.get("src"),
                    "basis": None if cur["basis"] == BASIS_NAT else f"{cur['basis']}, {cur['n']}개 권역 값"}
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


# ---------------------------------------------------------------- 영국 플라스틱 PRN
PRN_URL = "https://www.letsrecycle.com/prices/prns/prn-prices-{y}/"
MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def _cells(row):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]


def prn_year(y):
    """letsrecycle 연도별 PRN 표에서 Plastics 행을 [(YYYY-MM, 하단, 상단)] 로"""
    html = retry(lambda: get(PRN_URL.format(y=y)), tries=2)
    t = re.search(r'<table[^>]*price-graph-table[^>]*>(.*?)</table>', html, re.S)
    if not t:
        raise ValueError(f"{y} PRN 표 없음")
    rows = [_cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S)]
    head = [c.lower() for c in rows[0]]
    plast = next((r for r in rows[1:] if r and re.fullmatch(r"plastics?", r[0].strip(), re.I)), None)
    if not plast:
        raise ValueError(f"{y} Plastics 행 없음")
    out = []
    for i, c in enumerate(plast[1:], start=1):
        mon = head[i] if i < len(head) else ""
        if mon not in MONTHS_EN:
            continue
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", c.replace(",", ""))]
        if not nums:
            continue
        out.append((f"{y:04d}-{MONTHS_EN.index(mon) + 1:02d}", min(nums), max(nums)))
    return out


def fetch_prn(items, extra):
    y = now_kst().year
    series = []
    for yy in (y - 1, y):
        try:
            series += prn_year(yy)
        except Exception as e:
            print(f">> [PRN] {yy}년 표 실패: {type(e).__name__}: {str(e)[:120]}")
    if not series:
        raise ValueError("PRN 자료 없음")
    series.sort()
    mid = lambda r: round((r[1] + r[2]) / 2, 1)
    cur = series[-1]
    prev = series[-2] if len(series) > 1 else None
    rng = lambda r: f"{r[1]:g}~{r[2]:g}"
    return {"uk_prn_plastic": {"name": "영국 플라스틱 PRN", "item": f"범위 {rng(cur)}, 중간값", "unit": "£/톤", "date": cur[0],
                               "value": mid(cur), "low": cur[1], "high": cur[2],
                               "prev_date": prev[0] if prev else None, "prev_value": mid(prev) if prev else None,
                               "spark": [mid(r) for r in series[-12:]], "src": "letsrecycle.com"}}


# ---------------------------------------------------------------- 독일 bvse 시황 (참고 자료 링크)
BVSE_PDF = "https://plasticker.de/docs/preise/bvse_market_report_plastics_{ym}.pdf"


def fetch_bvse(items, extra):
    d = now_kst()
    y, m = d.year, d.month
    for _ in range(7):
        url = BVSE_PDF.format(ym=f"{y:04d}_{m:02d}")
        try:
            b = get(url, raw=True, timeout=30)
            if b[:4] == b"%PDF":
                return {"ref_bvse": {"name": "bvse 플라스틱 시황", "date": f"{y:04d}-{m:02d}", "value": None, "url": url, "src": "bvse·plasticker.de"}}
        except Exception:
            pass
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    raise ValueError("최근 7개월 bvse 보고서 없음")


def plastic_post(items, extra):
    # 화면에서 뺀 중국 선물·환율·유가 항목은 저장 파일에서도 정리
    for k in ("cn_pet", "cn_pe", "cn_pp", "cn_pvc", "fx_usd", "fx_cny", "dubai", "brent", "wti"):
        items.pop(k, None)
    # PRN £/톤 → 원/kg (원/파운드 × £/톤 ÷ 1000)
    p, g = items.get("uk_prn_plastic"), items.get("fx_gbp")
    if p and g:
        p["krw_kg"] = round(p["value"] * g["value"] / 1000, 1)
        p["fx_used"] = g["value"]


if __name__ == "__main__":
    run_all("plastic", [("국내 재생원료", fetch_recycle), ("영국 PRN", fetch_prn), ("원/파운드", fetch_gbp),
                        ("bvse 시황", fetch_bvse)], post=plastic_post)
