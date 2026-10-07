# -*- coding: utf-8 -*-
"""두 페이지가 함께 쓰는 시세 출처 (환율, Yahoo Finance)"""
import os, re, csv, io, http.cookiejar, urllib.request, urllib.parse
from datetime import datetime, timedelta
from common import KST, UA, get, get_json, retry, now_kst

EXIM_KEY = os.environ.get("KOREAEXIM_KEY", "")


def iso(d):
    return d.isoformat() if hasattr(d, "isoformat") else d


def yahoo_series(sym, rng="1mo"):
    """Yahoo Finance 일봉 종가 [(YYYY-MM-DD, 종가)] — 비공식 공개 시세"""
    last = None
    for host in ("query1", "query2"):
        try:
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1d"
            j = retry(lambda: get_json(url), tries=2)
            r = j["chart"]["result"][0]
            gmt = r["meta"].get("gmtoffset", 0)
            out = []
            for t, c in zip(r.get("timestamp", []), r["indicators"]["quote"][0].get("close", [])):
                if c is None:
                    continue
                d = datetime.utcfromtimestamp(t + gmt).date().isoformat()
                if out and out[-1][0] == d:
                    out[-1] = (d, c)
                else:
                    out.append((d, c))
            if out:
                return out
        except Exception as e:
            last = e
    raise last or ValueError(f"Yahoo {sym} 자료 없음")


def last_two(series):
    cur = series[-1]
    prev = series[-2] if len(series) > 1 else (None, None)
    return cur, prev


# ---------------------------------------------------------------- 환율
def fx_exim():
    """한국수출입은행 매매기준율 (Secret KOREAEXIM_KEY 가 있을 때만)"""
    if not EXIM_KEY:
        raise ValueError("KOREAEXIM_KEY 없음")
    found = []
    d = now_kst().date()
    for _ in range(14):
        url = ("https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?"
               + urllib.parse.urlencode({"authkey": EXIM_KEY, "searchdate": d.strftime("%Y%m%d"), "data": "AP01"}))
        rows = retry(lambda: get_json(url), tries=2) or []
        m = {}
        for x in rows if isinstance(rows, list) else []:
            cu = str(x.get("cur_unit", ""))
            try:
                v = float(str(x.get("deal_bas_r", "")).replace(",", ""))
            except ValueError:
                continue
            if cu == "USD":
                m["usd"] = v
            elif cu in ("CNH", "CNY"):
                m["cny"] = v
        if "usd" in m and "cny" in m:
            found.append((d.isoformat(), m))
            if len(found) == 2:
                break
        d -= timedelta(days=1)
    if not found:
        raise ValueError("수출입은행 환율 없음")
    return found, "수출입은행 매매기준율"


def fx_ecb():
    """ECB 기준환율(frankfurter) — 키 없이 사용. 원/위안 = (원/달러) ÷ (위안/달러)"""
    today = now_kst().date()
    q = urllib.parse.urlencode({"base": "USD", "symbols": "KRW,CNY"})
    last = None
    for base in ("https://api.frankfurter.dev/v1/", "https://api.frankfurter.app/"):
        try:
            url = f"{base}{(today - timedelta(days=14)).isoformat()}..{today.isoformat()}?{q}"
            j = retry(lambda: get_json(url), tries=2)
            rates = j.get("rates", {})
            days = sorted(rates)
            out = [(d, {"usd": rates[d]["KRW"], "cny": rates[d]["KRW"] / rates[d]["CNY"]}) for d in days
                   if "KRW" in rates[d] and "CNY" in rates[d]]
            if out:
                return list(reversed(out))[:2], "ECB 기준환율"
        except Exception as e:
            last = e
    raise last or ValueError("ECB 환율 없음")


def fx_yahoo():
    u, c = yahoo_series("KRW=X"), yahoo_series("CNYKRW=X")
    cm = dict(c)
    out = [(d, {"usd": v, "cny": cm[d]}) for d, v in u if d in cm]
    if not out:
        raise ValueError("Yahoo 환율 없음")
    return list(reversed(out))[:2], "Yahoo Finance"


def fetch_fx():
    """[(날짜, {'usd': 원/달러, 'cny': 원/위안})] 최신순 최대 2개, 출처명"""
    for fn in (fx_exim, fx_ecb, fx_yahoo):
        try:
            rows, src = fn()
            print(f">> [환율] {src}: {rows[0]}")
            return rows, src
        except Exception as e:
            print(f">> [환율] {fn.__name__} 실패: {type(e).__name__}: {str(e)[:100]}")
    raise ValueError("환율 자료 없음")


def fx_items(rows, src):
    cur, prev = rows[0], (rows[1] if len(rows) > 1 else (None, {}))
    out = {}
    for key, name, k in (("fx_usd", "원/달러", "usd"), ("fx_cny", "원/위안", "cny")):
        out[key] = {"name": name, "unit": "원", "date": cur[0], "value": round(cur[1][k], 2),
                    "prev_date": prev[0], "prev_value": round(prev[1][k], 2) if prev[1].get(k) else None, "src": src}
    return out


# ---------------------------------------------------------------- 국제유가
def _opinet_csv(text):
    rows = []
    for line in csv.reader(io.StringIO(text)):
        if len(line) < 4:
            continue
        d = line[0].strip()
        m = re.fullmatch(r"(\d{2})\D+(\d{1,2})\D+(\d{1,2})\D*", d)
        if m:
            d = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
        if not re.fullmatch(r"\d{6}", d):
            continue
        try:
            rows.append((d, float(line[1]), float(line[2]), float(line[3])))
        except ValueError:
            pass
    return sorted(rows)


def oil_opinet():
    """한국석유공사 오피넷 국제유가 (두바이·브렌트·WTI, $/bbl)"""
    base = "https://www.opinet.co.kr"
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    H = {**UA, "Referer": base + "/glopcoilSelect.do"}
    op.open(urllib.request.Request(base + "/glopcoilSelect.do", headers=H), timeout=40).read()
    now = now_kst().date()
    s, e = (now - timedelta(days=14)).strftime("%Y%m%d"), now.strftime("%Y%m%d")

    def post(sel, multi):
        data = [("TERM", "D"), ("OILSRTCD1", "001"), ("OILSRTCD2", "002"), ("OILSRTCD3", "003")]
        data += [("OILSRTCD", c) for c in (("001", "002", "003") if multi else ("001",))]
        data += [("STDDATE", s), ("ENDDATE", e), ("SEL_DIV", sel), ("STA_Y", s[:4]), ("STA_M", s[4:6]), ("STA_D", s[6:]),
                 ("END_Y", e[:4]), ("END_M", e[4:6]), ("END_D", e[6:])]
        raw = op.open(urllib.request.Request(base + "/glopcoil_csv.do", data=urllib.parse.urlencode(data).encode(), headers=H),
                      timeout=40).read()
        for enc in ("utf-8", "cp949"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                pass
        return raw.decode("utf-8", "ignore")

    rows = []
    for sel, multi in (("div_dar", False), ("div_dar", True), ("D", False)):
        try:
            r = _opinet_csv(retry(lambda: post(sel, multi), tries=2))
        except Exception as ex:
            print(f">> [오피넷 {sel}/{multi}] 실패 {type(ex).__name__}")
            continue
        if r and all(20 <= v <= 400 for v in r[-1][1:]):
            rows = r
            break
    if not rows:
        raise ValueError("오피넷 자료 없음")
    cur, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    ymd = lambda t: "20" + t[:2] + "-" + t[2:4] + "-" + t[4:]
    out = {}
    for i, (key, name) in enumerate((("dubai", "두바이유"), ("brent", "브렌트유"), ("wti", "WTI")), start=1):
        out[key] = {"name": name, "unit": "$/bbl", "date": ymd(cur[0]), "value": cur[i],
                    "prev_date": ymd(prev[0]) if prev else None, "prev_value": prev[i] if prev else None, "src": "오피넷"}
    return out


def oil_yahoo():
    out = {}
    for key, name, sym in (("brent", "브렌트유", "BZ=F"), ("wti", "WTI", "CL=F")):
        (d, v), (pd, pv) = last_two(yahoo_series(sym))
        out[key] = {"name": name, "unit": "$/bbl", "date": d, "value": round(v, 2), "prev_date": pd,
                    "prev_value": round(pv, 2) if pv else None, "src": "Yahoo Finance"}
    return out


def fetch_oil(items, extra):
    got = {}
    try:
        got.update(oil_opinet())
    except Exception as e:
        print(f">> [유가] 오피넷 실패 → Yahoo로 보충: {type(e).__name__}: {str(e)[:100]}")
    if len(got) < 3:
        try:
            for k, v in oil_yahoo().items():
                got.setdefault(k, v)
        except Exception as e:
            print(f">> [유가] Yahoo 실패: {type(e).__name__}")
    if not got:
        raise ValueError("국제유가 자료 없음")
    return got


# ---------------------------------------------------------------- 원/유로·원/파운드 (환산용)
def fx_krw(cur):
    """원/외화 1단위: 수출입은행(키 있을 때) → ECB → Yahoo. cur 예) 'EUR', 'GBP'"""
    rows, src = None, None
    if EXIM_KEY:
        try:
            d = now_kst().date()
            found = []
            for _ in range(14):
                url = ("https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?"
                       + urllib.parse.urlencode({"authkey": EXIM_KEY, "searchdate": d.strftime("%Y%m%d"), "data": "AP01"}))
                for x in (retry(lambda: get_json(url), tries=2) or []):
                    if str(x.get("cur_unit")) == cur:
                        found.append((d.isoformat(), float(str(x["deal_bas_r"]).replace(",", ""))))
                if len(found) >= 2:
                    break
                d -= timedelta(days=1)
            if found:
                rows, src = found, "수출입은행 매매기준율"
        except Exception as e:
            print(f">> [원/{cur}] 수출입은행 실패: {type(e).__name__}")
    if not rows:
        try:
            today = now_kst().date()
            j = retry(lambda: get_json(f"https://api.frankfurter.dev/v1/{(today - timedelta(days=14)).isoformat()}..{today.isoformat()}?base={cur}&symbols=KRW"), tries=2)
            r = j.get("rates", {})
            rows, src = [(d, r[d]["KRW"]) for d in sorted(r, reverse=True) if "KRW" in r[d]][:2], "ECB 기준환율"
        except Exception as e:
            print(f">> [원/{cur}] ECB 실패: {type(e).__name__}")
    if not rows:
        s_ = yahoo_series(f"{cur}KRW=X")
        rows, src = [(d, v) for d, v in reversed(s_)][:2], "Yahoo Finance"
    return rows, src


def _fx_item(name, rows, src):
    cur, prev = rows[0], (rows[1] if len(rows) > 1 else (None, None))
    return {"name": name, "unit": "원", "date": cur[0], "value": round(cur[1], 2), "prev_date": prev[0],
            "prev_value": round(prev[1], 2) if prev[1] else None, "src": src}


def fetch_eur(items, extra):
    return {"fx_eur": _fx_item("원/유로", *fx_krw("EUR"))}


def fetch_gbp(items, extra):
    return {"fx_gbp": _fx_item("원/파운드", *fx_krw("GBP"))}
