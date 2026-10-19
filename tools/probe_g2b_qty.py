# -*- coding: utf-8 -*-
"""처리 대행 용역의 예상 처리물량을 어디서 얻을 수 있는지 점검 (키는 출력하지 않는다)
1) 나라장터 용역 공고 응답의 전체 필드  2) 공고 규격서(첨부파일) 내려받기·본문 추출 → '톤' 문맥"""
import os, re, io, sys, json, zlib, zipfile, urllib.parse, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get, retry
from datetime import datetime, timedelta

KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
U = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"


def fetch(kw, s, e):
    q = {"serviceKey": KEY, "pageNo": 1, "numOfRows": 200, "type": "json", "inqryDiv": 1,
         "inqryBgnDt": s.strftime("%Y%m%d0000"), "inqryEndDt": e.strftime("%Y%m%d2359"), "bidNtceNm": kw}
    its = json.loads(retry(lambda: get(U + "?" + urllib.parse.urlencode(q), timeout=40), tries=2))["response"]["body"].get("items") or []
    return its if isinstance(its, list) else its.get("item", [])


def raw(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Disposition", ""), r.headers.get("Content-Type", "")


def text_of(b, name):
    n = name.lower()
    try:
        if b[:4] == b"PK\x03\x04":
            z = zipfile.ZipFile(io.BytesIO(b))
            xs = [f for f in z.namelist() if re.search(r"(section\d+\.xml|document\.xml)$", f, re.I)]
            return re.sub(r"<[^>]+>", " ", " ".join(z.read(f).decode("utf8", "ignore") for f in xs))
        if b[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            import olefile
            o = olefile.OleFileIO(io.BytesIO(b))
            hdr = o.openstream("FileHeader").read()
            comp = hdr[36] & 1
            out = []
            for st in sorted(s for s in o.listdir() if s[0] == "BodyText"):
                d = o.openstream(st).read()
                if comp:
                    d = zlib.decompress(d, -15)
                i = 0
                while i < len(d):
                    h = int.from_bytes(d[i:i + 4], "little"); tag, size = h & 0x3FF, (h >> 20) & 0xFFF
                    i += 4
                    if size == 0xFFF:
                        size = int.from_bytes(d[i:i + 4], "little"); i += 4
                    if tag == 67:
                        out.append(d[i:i + size].decode("utf-16le", "ignore"))
                    i += size
            return " ".join(out)
        if b[:4] == b"%PDF":
            p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=b, capture_output=True, timeout=60)
            return p.stdout.decode("utf8", "ignore")
    except Exception as ex:
        return f"[추출 실패 {type(ex).__name__}: {ex}]"
    return f"[알 수 없는 형식 {b[:8]!r}]"


def main():
    now = datetime.utcnow() + timedelta(hours=9)
    its = []
    for kw in ("음식물", "슬러지"):
        for k in range(0, 300, 30):
            try:
                its += fetch(kw, now - timedelta(days=k + 30), now - timedelta(days=k))
            except Exception as ex:
                print("fetch fail", kw, k, type(ex).__name__)
    print("총", len(its))
    if its:
        x = its[0]
        print("== 필드 목록")
        for k, v in x.items():
            print(f"  {k} = {str(v)[:80]}")
    from collections import Counter
    print("ntceKindNm", Counter(x.get("ntceKindNm") for x in its))
    cap = re.compile(r"서울|인천|경기|수원|화성|평택|오산|고양|성남|용인|부천|안산|안양|남양주|의정부|파주|김포|광명|시흥|군포|하남|구리|양주|포천|여주|이천|가평|양평|과천|의왕|동두천|연천|안성|광주시")
    sel = [x for x in its if re.search(r"처리", x.get("bidNtceNm", "")) and re.search(r"대행|위탁", x.get("bidNtceNm", ""))
           and cap.search((x.get("bidNtceNm") or "") + (x.get("dminsttNm") or "") + (x.get("ntceInsttNm") or ""))]
    print("수도권 처리 대행/위탁 후보", len(sel))
    seen = set()
    for x in sel[:14]:
        if x["bidNtceNo"] in seen:
            continue
        seen.add(x["bidNtceNo"])
        print(f"\n### {x['bidNtceNo']} {x.get('ntceKindNm')} | {x.get('dminsttNm')} | {x['bidNtceNm']} | 추정 {x.get('presmptPrce')}")
        for i in range(1, 11):
            u, nm = x.get(f"ntceSpecDocUrl{i}"), x.get(f"ntceSpecFileNm{i}")
            if not u:
                continue
            print(f"  첨부{i}: {nm}")
            try:
                b, cd, ct = raw(u)
                t = re.sub(r"\s+", " ", text_of(b, nm or ""))
                print(f"    {len(b)} bytes {ct[:30]} → 본문 {len(t)}자")
                hits = re.findall(r".{0,40}(?:\d[\d,\.]*\s*(?:톤|ton|t/일|톤/일|톤/년|㎥|m3)).{0,30}", t)
                for h in hits[:8]:
                    print("     ·", h.strip())
                if not hits:
                    print("     (톤 표기 없음) 앞부분:", t[:200])
            except Exception as ex:
                print(f"    내려받기 실패 {type(ex).__name__}: {str(ex)[:120]}")


if __name__ == "__main__":
    main()
