# -*- coding: utf-8 -*-
"""K-APT '사업자 선정(경쟁입찰) 결과 공개'(bidList.do?type=3) 공개 목록이 일반 조회로 읽히는지 (요청 2~3회)"""
import sys, os, re, time, urllib.parse, urllib.request, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import UA
from datetime import date, timedelta
B = "https://www.k-apt.go.kr"
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
sq = lambda t: re.sub(r"\s+", " ", t)
def get(u):
    time.sleep(3)
    return op.open(urllib.request.Request(u, headers={**UA, "Referer": B + "/bid/bidList.do"}), timeout=60).read().decode("utf8", "ignore")
q = {"type": "3", "bidArea": "11|28|41", "searchBidGb": "bid_gb_1", "bidTitle": "재활용", "searchDateGb": "reg",
     "dateStart": (date.today() - timedelta(days=90)).isoformat(), "dateEnd": date.today().isoformat(), "dateArea": "2", "pageNo": "1",
     "bidState": "", "codeAuth": "", "codeWay": "", "codeAuthSub": "", "codeSucWay": "", "codeClassifyType1": "", "codeClassifyType2": "", "codeClassifyType3": ""}
h = get(B + "/bid/bidList.do?" + urllib.parse.urlencode(q))
i = h.find("<thead"); print("머리:", sq(re.sub(r"<[^>]+>", "|", h[i:i + 1200]))[:300])
tb = h[h.find("<tbody"):h.find("</tbody>")]
trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
print("행:", len(trs))
for tr in trs[:12]:
    print("  ", [sq(re.sub(r"<[^>]+>", " ", x)).strip()[:40] for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)], re.findall(r"goView\('(\d+)'", tr)[:1])
