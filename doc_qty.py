# -*- coding: utf-8 -*-
"""나라장터 공고 첨부파일(공고문·과업지시서·규격서)에서 예상 처리물량(톤)을 읽는다.
hwpx(zip) · hwp(OLE, olefile 필요) · pdf(pdftotext 필요) 본문을 텍스트로 바꾼 뒤 '예상물량 51,170톤' 같은 문구를 찾는다."""
import io, re, zlib, zipfile, subprocess, urllib.request


def download(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(8_000_000)


def text_of(b):
    try:
        if b[:4] == b"PK\x03\x04":
            z = zipfile.ZipFile(io.BytesIO(b))
            xs = [f for f in z.namelist() if re.search(r"(section\d+\.xml|document\.xml)$", f, re.I)]
            return re.sub(r"<[^>]+>", " ", " ".join(z.read(f).decode("utf8", "ignore") for f in xs))
        if b[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            import olefile
            o = olefile.OleFileIO(io.BytesIO(b))
            comp = o.openstream("FileHeader").read()[36] & 1
            out = []
            for st in sorted(s for s in o.listdir() if s[0] == "BodyText"):
                d = o.openstream(st).read()
                if comp:
                    d = zlib.decompress(d, -15)
                i = 0
                while i + 4 <= len(d):
                    h = int.from_bytes(d[i:i + 4], "little")
                    tag, size = h & 0x3FF, (h >> 20) & 0xFFF
                    i += 4
                    if size == 0xFFF:
                        size = int.from_bytes(d[i:i + 4], "little")
                        i += 4
                    if tag == 67:      # 문단 글자
                        out.append(re.sub(r"[\x00-\x1f]", " ", d[i:i + size].decode("utf-16le", "ignore")))
                    i += size
            return " ".join(out)
        if b[:4] == b"%PDF":
            p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=b, capture_output=True, timeout=60)
            return p.stdout.decode("utf8", "ignore")
    except Exception:
        return ""
    return ""


NUM = r"(\d[\d,]*(?:\.\d+)?)"
# '예상물량 : 51,170 톤', '과업량: 음식물류폐기물 982톤', '처리 예정물량 : 1,700 톤', '대행물량 : 51,170톤', '예상처리량 1,700톤/년'
P1 = re.compile(r"(?:예상|예정|대행|과업|사업|처리|계약|위탁|발생)\s*(?:처리)?\s*(?:예정)?\s*(?:물량|처리량|량|발생량)\s*(?:\(\s*예정\s*\))?[^0-9]{0,40}?" + NUM +
                r"\s*(톤|ton|㎏|kg|Kg|KG)(?!\s*/\s*일|\s*급|\s*이상|\s*이하|\s*미만)")
# '처리량(예정) 음식물류 폐기물(kg) 492,800'
P2 = re.compile(r"(?:처리량|물량|배출량)\s*\(\s*예정\s*\)[^0-9]{0,40}?\(\s*(톤|kg|㎏)\s*\)\s*" + NUM)


# '1,700톤/년' (표 안의 연간 예상처리량)
P3 = re.compile(NUM + r"\s*톤\s*/\s*년")


def find_qty(text):
    """후보 (톤, 문맥) 목록. 일 단위·차량 톤급·허가용량은 뺀다"""
    t = re.sub(r"\s+", " ", text or "")
    t = re.sub(r"(?<=[가-힣])\s(?=[가-힣])", "", t)      # '과 업 량' → '과업량'
    out = []
    for m in P1.finditer(t):
        ctx = t[max(0, m.start() - 20):m.end() + 10]
        if re.search(r"허가|용량|차량|암롤|실적|기준\s*\d|규모", t[max(0, m.start() - 15):m.end()]):
            continue
        v = float(m.group(1).replace(",", ""))
        out.append((v / 1000 if m.group(2).lower() in ("kg", "㎏") else v, ctx))
    for m in P2.finditer(t):
        v = float(m.group(2).replace(",", ""))
        out.append((v / 1000 if m.group(1) in ("kg", "㎏") else v, t[max(0, m.start() - 10):m.end() + 10]))
    for m in P3.finditer(t):
        out.append((float(m.group(1).replace(",", "")), t[max(0, m.start() - 30):m.end() + 5]))
    return [(v, c) for v, c in out if v >= 1]


def doc_rank(name):
    n = name or ""
    for i, k in enumerate(("과업", "규격", "제안", "공고")):
        if k in n:
            return i
    return 9


def qty_from_docs(docs, est=None, max_docs=4):
    """docs: [(파일명, url)]. 추정가격이 있으면 톤당 1만~60만원 범위에 드는 물량만 받아들인다"""
    seen_pdf_pair = set()
    tried = 0
    for name, url in sorted(docs, key=lambda d: (doc_rank(d[0]), (d[0] or "").lower().endswith(".pdf"))):
        stem = re.sub(r"\.\w+$", "", name or "")
        if stem in seen_pdf_pair or not re.search(r"\.(hwpx?|pdf)$", name or "", re.I) or re.search(r"예규|유의서|일반조건|청렴|서약|제출서류", name or ""):
            continue
        seen_pdf_pair.add(stem)
        tried += 1
        if tried > max_docs:
            break
        try:
            cands = find_qty(text_of(download(url)))
        except Exception:
            continue
        for v, ctx in cands:
            if est and not (1e4 <= est / v <= 6e5):
                continue
            return v, f"{name}: {ctx.strip()[:80]}"
    return None, ""
