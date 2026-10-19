# -*- coding: utf-8 -*-
"""태평양(BKL) '환경 주요 정책 동향' 뉴스레터 접근·본문 추출 점검"""
import re, subprocess, urllib.request
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def get(u, n=6_000_000):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40)
    return r.status, r.headers.get("Content-Type", ""), r.geturl(), r.read(n)


for u in ["https://www.bkl.co.kr/law/insight/newsletter/6820", "https://www.bkl.co.kr/newsLetter/itemUrl.do?itemNo=6820",
          "https://www.bkl.co.kr/law/insight/newsletterList.do", "https://www.bkl.co.kr/law/insight/newsletter"]:
    try:
        st, ct, final, b = get(u)
        print(f"\n== {u}\n   {st} {ct} → {final} {len(b)} bytes, head {b[:8]!r}")
        if b[:4] == b"%PDF":
            t = subprocess.run(["pdftotext", "-layout", "-", "-"], input=b, capture_output=True).stdout.decode("utf8", "ignore")
            print("   PDF 본문", len(t), "자")
            for l in [l for l in t.splitlines() if re.search(r"폐기물|플라스틱|재활용|재생원료|바이오|유기성|음식물|순환", l)][:25]:
                print("   |", l.strip()[:150])
        else:
            h = b.decode("utf8", "ignore")
            print("   title:", (re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1].strip()[:80])
            links = sorted(set(re.findall(r"(?:newsletter/|itemNo=|goPrevNext\(')(\d{4,5})", h)))
            print("   item 번호들:", links[:40])
            print("   '환경' 포함 제목:", re.findall(r"[^<>\"]{0,30}환경 주요 정책 동향[^<>\"]{0,10}", h)[:10])
    except Exception as e:
        print(f"\n== {u}\n   실패 {type(e).__name__}: {str(e)[:150]}")
