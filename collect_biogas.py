# -*- coding: utf-8 -*-
"""바이오가스 페이지 지표 수집 → data/biogas.json
- 일간: REC 현물 평균가 (전력거래소 홈페이지 → 공공데이터포털)
- 일간: TTF 천연가스 선물 (Yahoo Finance, €/MWh)
- 일간: KCU 상쇄배출권 (한국거래소 배출권시장 정보플랫폼, 최근 거래일 종가)
- 월간: 도시가스용 천연가스 도매요금 평균 (한국가스공사, 원/MJ)
- 분기: 프랑스 바이오가스 원산지보증서(GO) 국가 경매 기준가격 (EEX, €/MWh)
수집에 실패한 항목은 이전 값을 그대로 둔다."""
import os, re, io, json, time, zipfile, http.cookiejar, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from common import UA, get, get_json, retry, run_all, now_kst, carry_prev
from sources import yahoo_series, last_two

DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))


# ---------------------------------------------------------------- REC
def rec_kpx(old):
    """전력거래소 홈페이지 첫 화면 'REC' 카드 (가장 최근 거래일 평균가)"""
    html = retry(lambda: get("https://kpx.or.kr/"), tries=2)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)))
    mm = list(re.finditer(r"거래일\s*(\d{4})\.\s?(\d{2})\.\s?(\d{2})[^\d]{0,6}\s*거래량\s*[\d,]+\s*평균가\s*(\d{1,3}(?:,\d{3})+)", text))
    if not mm:
        raise ValueError("REC(KPX) 카드 없음")
    m = mm[0]
    val = float(m.group(4).replace(",", ""))
    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    while d.weekday() not in (1, 3):  # 현물시장은 화·목 거래
        d -= timedelta(days=1)
    day = d.isoformat()
    if val < 10000 or (old.get("value") and not (0.5 * old["value"] <= val <= 2 * old["value"])):
        raise ValueError(f"REC 값 이상: {val:,.0f}")
    pd, pv = carry_prev(old, day, val)
    return {"name": "REC 현물", "item": "육지 평균가", "unit": "원/REC", "date": day, "value": val,
            "prev_date": pd, "prev_value": pv, "src": "전력거래소"}


def rec_datagokr():
    if not DATA_KEY:
        raise ValueError("DATA_GO_KR_KEY 없음")
    base = "https://apis.data.go.kr/B552115/RecMarketInfo2/getRecMarketInfo2"
    today = now_kst().date()
    found = []
    for back in range(0, 25):
        d = today - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        q = {"serviceKey": DATA_KEY, "pageNo": 1, "numOfRows": 5, "dataType": "json", "bzDd": d.strftime("%Y%m%d")}
        j = retry(lambda: get_json(base + "?" + urllib.parse.urlencode(q)), tries=2)
        body = j.get("response", j).get("body", {})
        its = body.get("items", {}) if isinstance(body, dict) else {}
        its = its.get("item", []) if isinstance(its, dict) else its
        its = [its] if isinstance(its, dict) else its
        rows = [x for x in (its or []) if x.get("landAvgPrc") not in (None, "")]
        if rows:
            found.append((d.isoformat(), float(rows[0]["landAvgPrc"])))
            if len(found) == 2:
                break
    if not found:
        raise ValueError("REC 자료 없음")
    return {"name": "REC 현물", "item": "육지 평균가", "unit": "원/REC", "date": found[0][0], "value": found[0][1],
            "prev_date": found[1][0] if len(found) > 1 else None, "prev_value": found[1][1] if len(found) > 1 else None,
            "src": "공공데이터포털"}


def fetch_rec(items, extra):
    old = items.get("rec") or {}
    try:
        return {"rec": rec_kpx(old)}
    except Exception as e:
        print(f">> [REC] 전력거래소 홈페이지 실패 → 공공데이터포털: {type(e).__name__}: {str(e)[:100]}")
        return {"rec": rec_datagokr()}


# ---------------------------------------------------------------- TTF
def fetch_ttf(items, extra):
    s = yahoo_series("TTF=F")
    (d, v), (pd, pv) = last_two(s)
    return {"ttf": {"name": "TTF 천연가스", "item": "근월물", "unit": "€/MWh", "date": d, "value": round(v, 2),
                    "prev_date": pd, "prev_value": round(pv, 2) if pv else None, "src": "Yahoo Finance (ICE Endex)",
                    "spark": [round(x[1], 1) for x in s[-30:]]}}


# ---------------------------------------------------------------- KCU (한국거래소)
def _krx_session():
    base = "https://ets.krx.co.kr"
    page = base + "/contents/ETS/03/03010000/ETS03010000.jsp"
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    H = {**UA, "Referer": page}
    op.open(urllib.request.Request(page, headers=H), timeout=40).read()
    return base, op, H


def _krx_post(base, op, H, bld, name, form):
    otp = (base + "/contents/COM/GenerateOTP.jspx?bld=" + urllib.parse.quote(bld, safe="") + "&name=" + name
           + "&_=" + str(int(time.time() * 1000)))
    code = op.open(urllib.request.Request(otp, headers=H), timeout=40).read().decode("utf-8", "ignore").strip()
    if len(code) < 20 or "<" in code:
        raise ValueError("KRX 인증값 형식 이상: " + code[:80])
    form = dict(form, code=code)
    req = urllib.request.Request(base + "/contents/ETS/99/ETS99000001.jspx", data=urllib.parse.urlencode(form).encode(),
                                 headers={**H, "X-Requested-With": "XMLHttpRequest"})
    return json.loads(op.open(req, timeout=60).read().decode("utf-8", "ignore"))


def _find_rows(node):
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node) and any("trd_dd" in x for x in node):
            return node
        for x in node:
            r = _find_rows(x)
            if r:
                return r
    elif isinstance(node, dict):
        for v in node.values():
            r = _find_rows(v)
            if r:
                return r
    return []


def _n(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def fetch_kcu(items, extra):
    """KCU(외부사업 감축실적을 전환한 상쇄배출권)는 거래가 드물다.
    ① 최근 1년 일자별 자료에서 실제 거래(거래량>0)가 있었던 마지막 두 거래일 종가
    ② 거래가 없으면 현재가 표의 올해 연도물 가격(기준가)을 '거래 없음'으로 표시"""
    base, op, H = _krx_session()
    now = now_kst()
    yy = now.strftime("%y")
    form = {"isu_cd": "", "fromdate": (now - timedelta(days=365)).strftime("%Y%m%d"), "todate": now.strftime("%Y%m%d"),
            "pagePath": "/contents/ETS/03/03010000/ETS03010000.jsp", "gNo": "98f13708210194c475687be6106a3b84"}
    trades = []
    try:
        j = _krx_post(base, op, H, "ETS/03/03010000/ets03010000_05", "grid", form)
        for x in _find_rows(j):
            nm = str(x.get("isu_eng_abbrv") or x.get("isu_cd") or "")
            if not re.fullmatch(r"KCU\d{2}", nm):  # i-KCU(국제) 제외
                continue
            vol, px = _n(x.get("acc_trdvol")) or 0, _n(x.get("tdd_clsprc"))
            dd = re.sub(r"\D", "", str(x.get("trd_dd", "")))
            if vol > 0 and px and len(dd) == 8:
                trades.append((dd, nm, px, vol))
        print(f">> [KCU] 최근 1년 거래 {len(trades)}건: {sorted(trades)[-3:]}")
    except Exception as e:
        print(f">> [KCU] 일자별 조회 실패: {type(e).__name__}: {str(e)[:100]}")
    ymd = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if trades:
        trades.sort()
        cur = trades[-1]
        prev = next((t for t in reversed(trades[:-1]) if t[0] < cur[0]), None)
        return {"kcu": {"name": "KCU 상쇄배출권", "item": cur[1], "unit": "원/톤", "date": ymd(cur[0]), "value": cur[2],
                        "prev_date": ymd(prev[0]) if prev else None, "prev_value": prev[2] if prev else None,
                        "volume": cur[3], "src": "한국거래소", "basis": "최근 거래일 종가"}}
    j = _krx_post(base, op, H, "ETS/03/03010000/ets03010000_04", "tablesubmit", {"bldcode": "ETS/03/03010000/ets03010000_04"})
    lst = next((v for v in j.values() if isinstance(v, list)), []) if isinstance(j, dict) else []
    row = next((x for x in lst if str(x.get("isu_cd", "")) == "KCU" + yy), None)
    if not row or not _n(row.get("tdd_clsprc")):
        raise ValueError("KCU 자료 없음")
    return {"kcu": {"name": "KCU 상쇄배출권", "item": "KCU" + yy, "unit": "원/톤", "date": now.date().isoformat(),
                    "value": _n(row["tdd_clsprc"]), "prev_date": None, "prev_value": None, "src": "한국거래소",
                    "basis": "최근 1년 거래 없음 (거래소 표시 가격)"}}


# ---------------------------------------------------------------- 천연가스 도매요금
def fetch_gas_tariff(items, extra):
    html = retry(lambda: get("https://www.kogas.or.kr/site/koGas/1040401000000"), tries=2)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)))
    dm = re.search(r"\(\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\s*기준", text)
    am = re.search(r"평균\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", text)
    if not dm or not am:
        raise ValueError("도매요금 표를 찾지 못함")
    date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    fuel, supply, total = (float(am.group(i)) for i in (1, 2, 3))
    hist = extra.setdefault("gas_tariff", {})
    hist[date] = {"total": total, "fuel": fuel, "supply": supply}
    for k in sorted(hist)[:-36]:
        hist.pop(k, None)
    prev_dates = [d for d in sorted(hist) if d < date]
    pd = prev_dates[-1] if prev_dates else None
    print(f">> [도매요금] {date} 평균 {total} (원료비 {fuel} + 공급비 {supply})")
    return {"gas_whole": {"name": "천연가스 도매요금", "item": "도시가스용 평균", "unit": "원/MJ", "date": date[:7], "value": total,
                          "prev_date": pd[:7] if pd else None, "prev_value": hist[pd]["total"] if pd else None,
                          "fuel": fuel, "supply": supply, "src": "한국가스공사"}}


# ---------------------------------------------------------------- 프랑스 바이오가스 GO 경매 (EEX)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _xlsx_sheets(blob):
    """기본 라이브러리로 xlsx 읽기 → {시트명: [[셀값...], ...]}"""
    z = zipfile.ZipFile(io.BytesIO(blob))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            sst.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
        target = rels[sh.get("{%s}id" % NS["r"])].lstrip("/")
        path = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(path)).iter("{%s}row" % NS["m"]):
            vals = {}
            for c in row.findall("m:c", NS):
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                v = c.find("m:v", NS)
                if v is None:
                    is_ = c.find("m:is", NS)
                    val = "".join(t.text or "" for t in is_.iter("{%s}t" % NS["m"])) if is_ is not None else None
                else:
                    val = sst[int(v.text)] if c.get("t") == "s" else v.text
                if val not in (None, ""):
                    vals[col] = val
            if vals:
                rows.append(vals)
        out[sh.get("name").strip()] = rows
    return out


def _auction_ref(rows):
    """'reference price' 글자 바로 위 행의 같은 열 값 = 기준가격(전체 가중평균). 없으면 마지막 숫자 행의 E열."""
    for i, r in enumerate(rows):
        for col, v in r.items():
            if isinstance(v, str) and "reference price" in v.lower() and i > 0:
                try:
                    return float(rows[i - 1][col]), _vol(rows[i - 1])
                except (KeyError, ValueError):
                    pass
    for r in reversed(rows):
        try:
            return float(r["E"]), _vol(r)
        except (KeyError, ValueError):
            continue
    raise ValueError("기준가격 행 없음")


def _vol(r):
    try:
        return float(r.get("D") or r.get("C"))
    except (TypeError, ValueError):
        return None


def fetch_go_auction(items, extra):
    page = "https://www.eex.com/en/markets/energy-certificates/french-auctions-biogas"
    html = retry(lambda: get(page), tries=2)
    links = re.findall(r'href="([^"]*Auction_results[^"]*\.xlsx)"', html, re.I)
    if not links:
        raise ValueError("EEX 경매 결과 파일 링크 없음")
    url = urllib.parse.urljoin(page, links[0])
    print(f">> [GO 경매] 결과 파일: {url}")
    sheets = _xlsx_sheets(retry(lambda: get(url, raw=True), tries=2))
    dated = []
    for name, rows in sheets.items():
        m = re.fullmatch(r"(\d{4})\s+(\d{2})\s+(\d{2})", name)
        if m:
            try:
                p, v = _auction_ref(rows)
                dated.append((f"{m.group(1)}-{m.group(2)}-{m.group(3)}", p, v))
            except ValueError as e:
                print(f">> [GO 경매] 시트 {name}: {e}")
    if not dated:
        raise ValueError("경매 회차 시트 없음")
    dated.sort()
    cur, prev = dated[-1], (dated[-2] if len(dated) > 1 else None)
    print(f">> [GO 경매] 회차 {len(dated)}개, 최근 {cur}, 직전 {prev}")
    return {"go_fr": {"name": "프랑스 바이오가스 GO 경매", "item": "기준가격(가중평균)", "unit": "€/MWh", "date": cur[0],
                      "value": round(cur[1], 2), "prev_date": prev[0] if prev else None,
                      "prev_value": round(prev[1], 2) if prev else None, "volume_mwh": cur[2], "src": "EEX",
                      "history": [[d, round(p, 2)] for d, p, _ in dated]}}


if __name__ == "__main__":
    run_all("biogas", [("REC", fetch_rec), ("TTF", fetch_ttf), ("KCU", fetch_kcu),
                       ("천연가스 도매요금", fetch_gas_tariff), ("프랑스 GO 경매", fetch_go_auction)])
