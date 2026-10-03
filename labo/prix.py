"""Source de prix pour mesurer le score : robots.txt et conditions de Stooq (et FRED pour l'indice S&P 500)."""
import re, time, urllib.robotparser
from pathlib import Path
import requests
S = Path("labo/resultats-prix"); S.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Radar projet personnel"}
out = []
def get(u, nom=None):
    time.sleep(1.5)
    r = requests.get(u, headers=UA, timeout=60)
    out.append(f"- {r.status_code} · {len(r.content)} octets · {r.headers.get('Content-Type')} · {u}")
    if nom: (S / nom).write_bytes(r.content)
    return r
r = get("https://stooq.com/robots.txt", "stooq_robots.txt")
out.append("```\n" + r.text[:1500] + "\n```")
rp = urllib.robotparser.RobotFileParser(); rp.parse(r.text.splitlines())
for u in ("https://stooq.com/q/d/l/?s=aapl.us&i=d", "https://stooq.com/q/l/?s=aapl.us&f=sd2t2ohlcv&h&e=csv"):
    out.append(f"- robots.txt : {'PERMIS' if rp.can_fetch('Radar projet personnel', u) else 'INTERDIT'} · {u}")
p = get("https://stooq.com/", "stooq_accueil.html")
liens = sorted(set(re.findall(r'href="([^"]*(?:regulamin|terms|rules|warunki|polityka|privacy)[^"]*)"', p.text, re.I)))
out.append(f"- liens conditions sur l'accueil : {liens}")
for l in liens[:3]:
    u = l if l.startswith("http") else "https://stooq.com" + ("" if l.startswith("/") else "/") + l
    t = get(u, "stooq_conditions_" + str(liens.index(l)) + ".html")
    txt = " ".join(re.sub(r"<[^>]+>", " ", t.text).split())
    for mot in ("robot", "automat", "pobier", "download", "commercial", "komercyj", "kopiow", "copy"):
        for m in list(re.finditer(mot, txt, re.I))[:2]:
            out.append(f"    - [{mot}] …{txt[max(0, m.start() - 250):m.start() + 300]}…")
f = get("https://fred.stlouisfed.org/robots.txt", "fred_robots.txt")
rp2 = urllib.robotparser.RobotFileParser(); rp2.parse(f.text.splitlines())
u = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"
out.append(f"- FRED robots.txt : {'PERMIS' if rp2.can_fetch('Radar projet personnel', u) else 'INTERDIT'} · {u}")
(S / "resume.md").write_text("\n".join(out) + "\n", encoding="utf-8"); print("\n".join(out))
