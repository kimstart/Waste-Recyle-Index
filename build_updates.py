# -*- coding: utf-8 -*-
"""'최근 업데이트' 상자용 자료 변동 소식 → data/data_updates.json
수집이 끝난 뒤 실행해, 직전 상태(state)와 비교해 새로 반영된 자료만 소식으로 남긴다.
매일 바뀌는 시세(TTF·REC·중국 선물·환율)는 소식으로 만들지 않는다. 기능 변경 이력은 data/changelog.json 에 따로 적는다."""
from datetime import timedelta
from common import load, save, now_kst

OUT = "data/data_updates.json"


def pct(it):
    p, v = it.get("prev_value"), it.get("value")
    if p in (None, 0) or v is None:
        return ""
    d = (v - p) / p * 100
    return f", 전월 대비 {'+' if d >= 0 else ''}{d:.1f}%"


def mon(d):
    return f"{int(d[5:7])}월" if d and len(d) >= 7 else ""


def n(v, dec=0):
    return "-" if v is None else f"{v:,.{dec}f}"


def main():
    st = load(OUT, {}) or {}
    state, first = st.get("state", {}), not st.get("state")
    today = now_kst().strftime("%Y-%m-%d")
    events = []

    def ev(page, text):
        events.append({"date": today, "page": page, "kind": "자료", "text": text})

    def changed(key, val):
        old = state.get(key)
        state[key] = val
        return (not first) and val is not None and old != val

    P = (load("data/plastic.json", {}) or {}).get("items", {})
    B = (load("data/biogas.json", {}) or {}).get("items", {})

    # 폐플라스틱: 월간 재활용 단가(수도권)
    rec = {k: v for k, v in P.items() if k.startswith("r_")}
    if rec:
        d = max(v.get("date") or "" for v in rec.values())
        if changed("recycle", d):
            pet = P.get("r_comp_pet") or next(iter(rec.values()))
            ev("plastic", f"{mon(d)} 수도권 재활용 단가 반영 — {pet['name']} {n(pet['value'], 1)}원/kg{pct(pet)}")
    cus = {k: v for k, v in P.items() if k.startswith(("imp_", "exp_scrap"))}
    if cus:
        d = max(v.get("date") or "" for v in cus.values())
        if changed("customs", d):
            ev("plastic", f"관세청 {mon(d)} 신재 수입단가·폐플라스틱 수출 반영")
    it = P.get("uk_prn_plastic")
    if it and changed("prn", it.get("date")):
        ev("plastic", f"영국 플라스틱 PRN {mon(it['date'])} £{n(it['value'])}/톤{pct(it)}")
    it = P.get("ref_bvse")
    if it and changed("bvse", it.get("date")):
        ev("plastic", f"독일 bvse 플라스틱 시황 {mon(it['date'])}호 공개")
    for k in ("rpet_eu_fgp", "rpet_eu_prem", "rpet_asia_fgp", "rpet_kr"):
        it = P.get(k)
        if it and changed(k, f"{it.get('date')}|{it.get('value')}"):
            ev("plastic", f"rPET 기사 가격 추가 — {it['name']} {n(it['value'])} {it.get('unit', '')} ({it.get('src', '')})")

    # 매각입찰 (수도권)
    bids = [b for b in (load("data/bids.json", {}) or {}).get("bids", []) if b.get("region") in ("중점", "수도권")]
    ids = {b["id"]: b.get("status") for b in bids}
    old_ids = state.get("bid_ids", {})
    if not first and old_ids:
        new = [b for b in bids if b["id"] not in old_ids]
        won = [b for b in bids if b.get("status") == "낙찰" and old_ids.get(b["id"]) not in (None, "낙찰")]
        if new:
            ev("plastic", f"수도권 매각입찰 신규 {len(new)}건 — {new[0].get('org', '')} {new[0].get('cat', '')}" + (" 외" if len(new) > 1 else ""))
        if won:
            ups = [b["win_unit_price"] for b in won if b.get("win_unit_price")]
            avg = f", 평균 낙찰단가 {n(sum(ups) / len(ups))}원/kg" if ups else ""
            ev("plastic", f"수도권 매각입찰 낙찰 결과 {len(won)}건{avg}")
    if ids:
        state["bid_ids"] = ids

    # 선별·처리 대행 용역 (수도권)
    svc = (load("data/services.json", {}) or {}).get("items", [])
    sids = {b["id"]: b.get("status") for b in svc}
    old_s = state.get("svc_ids", {})
    if not first and old_s:
        new = [b for b in svc if b["id"] not in old_s]
        won = [b for b in svc if b.get("status") == "낙찰" and old_s.get(b["id"]) not in (None, "낙찰")]
        if new:
            ev("plastic", f"선별·처리 대행 용역 신규 {len(new)}건 — {new[0].get('org', '')} {new[0].get('title', '')[:30]}" + (" 외" if len(new) > 1 else ""))
        if won:
            ev("plastic", f"선별·처리 대행 용역 낙찰 {len(won)}건 — {won[0].get('org', '')} {won[0].get('winner', '')}")
    if sids:
        state["svc_ids"] = sids

    # 제도 변경
    pol = (load("data/policy.json", {}) or {}).get("events", [])
    seen = set(state.get("policy_seen", []))
    for e in pol:
        k = f"{e.get('type')}|{e.get('title')}"
        if k not in seen and not first and seen:
            ev("plastic", f"제도 변경 감지 — {e.get('title', '')[:60]}")
        seen.add(k)
    if pol:
        state["policy_seen"] = sorted(seen)[-300:]

    # 바이오가스
    it = B.get("gas_whole")
    if it and changed("gas_whole", it.get("date")):
        extra = f" (≈{n(it['krw_m3'])}원/㎥)" if it.get("krw_m3") else ""
        ev("biogas", f"{mon(it['date'])} 천연가스 도매요금 반영 — {n(it['value'], 3)}원/MJ{extra}")
    it = B.get("go_fr")
    if it and changed("go_fr", it.get("date")):
        ev("biogas", f"프랑스 바이오가스 GO 경매 결과 반영 — €{n(it['value'], 2)}/MWh")
    it = B.get("kcu")
    if it and changed("kcu", it.get("date")):
        ev("biogas", f"KCU 신규 거래 ({it['date'][5:].replace('-', '.')}) — {n(it['value'])}원/톤")

    cut = (now_kst() - timedelta(days=60)).strftime("%Y-%m-%d")
    allev = (events + [e for e in st.get("events", []) if e.get("date", "") >= cut])[:60]
    save(OUT, {"updated": now_kst().strftime("%Y-%m-%d %H:%M"), "state": state, "events": allev})
    print(f">> 최근 업데이트: 새 소식 {len(events)}건" + (" (첫 실행: 현재 상태만 기록)" if first else ""))
    for e in events:
        print(f"   - [{e['page']}] {e['text']}")


if __name__ == "__main__":
    main()
