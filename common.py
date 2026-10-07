# -*- coding: utf-8 -*-
"""수집 스크립트 공통 함수 (Python 기본 라이브러리만 사용)"""
import os, json, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko,en;q=0.8"}


def now_kst():
    return datetime.now(KST)


def retry(fn, tries=3, wait=4):
    last = None
    for i in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"   [재시도 {i}/{tries}] {type(e).__name__}: {str(e)[:120]}")
            time.sleep(wait * i)
    raise last


def get(url, headers=None, data=None, timeout=40, raw=False):
    """GET(또는 data가 있으면 POST). raw=True면 bytes, 아니면 문자열(utf-8 → cp949 순서로 해석)"""
    h = dict(UA)
    h.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if isinstance(data, (dict, list)) else data
    req = urllib.request.Request(url, data=body, headers=h)
    b = urllib.request.urlopen(req, timeout=timeout).read()
    if raw:
        return b
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "ignore")


def get_json(url, headers=None, timeout=40):
    return json.loads(get(url, headers=headers, timeout=timeout))


def load(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f">> [경고] {path} 읽기 실패: {e}")
    return default if default is not None else {}


def save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def save_with_history(name, obj):
    """data/<name>.json 저장 + history/<name>_YYYYMMDD.json 보관(같은 날은 마지막 실행 값)"""
    save(f"data/{name}.json", obj)
    day = now_kst().strftime("%Y%m%d")
    save(f"history/{name}_{day}.json", obj)
    print(f">> data/{name}.json, history/{name}_{day}.json 저장")


def carry_prev(old, date, value):
    """값이 하루에 한 번 바뀌는 지표의 '이전 값'을 저장된 직전 값에서 이어받는다.
    old: 이전에 저장된 같은 지표 dict"""
    old = old or {}
    if old.get("date") == date:
        return old.get("prev_date"), old.get("prev_value")
    if old.get("date") and old.get("value") is not None and old["date"] < date:
        return old["date"], old["value"]
    return old.get("prev_date"), old.get("prev_value")


def run_all(name, steps, post=None):
    """steps: [(이름, 함수(items, extra) -> {key: item})]. 실패한 항목은 이전 값을 그대로 둔다.
    post(items, extra): 저장 직전에 환산값 등을 계산"""
    store = load(f"data/{name}.json", {})
    items = dict(store.get("items", {}))
    extra = dict(store.get("extra", {}))
    ok = 0
    for label, fn in steps:
        try:
            got = fn(items, extra)
            items.update(got)
            ok += 1
            for k, v in got.items():
                print(f">> [수집 성공] {k}: {v.get('date')} {v.get('value')} (이전 {v.get('prev_date')} {v.get('prev_value')})")
        except Exception as e:
            print(f">> [수집 실패] {label}: {type(e).__name__}: {str(e)[:200]} → 이전 값 유지")
    if ok == 0 and not items:
        raise SystemExit(1)
    if post:
        try:
            post(items, extra)
        except Exception as e:
            print(f">> [후처리 실패] {type(e).__name__}: {str(e)[:200]}")
    save_with_history(name, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "items": items, "extra": extra})
    return ok
