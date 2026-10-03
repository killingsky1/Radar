"""Reconnaissance du lot 3a : robots.txt et pages d'accueil des données, AVANT toute lecture.

Poursuites SEC, fins de blocage (424B4), sanctions OFAC, fusions FTC, rappels NHTSA, antitrust DOJ.
Règle : une adresse n'est téléchargée que si le robots.txt de son site le permet.
"""

import json
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

SORTIE = Path("labo/resultats-lot3a3")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
session = requests.Session()
resume = ["# Reconnaissance 2 du lot 3a", ""]
robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def ua_pour(url):
    h = (urlparse(url).hostname or "").lower()
    return UA_SEC if h == "sec.gov" or h.endswith(".sec.gov") else UA


def permis(url):
    p = urlparse(url)
    hote = f"{p.scheme}://{p.netloc}"
    if hote not in robots:
        time.sleep(0.5)
        try:
            r = session.get(f"{hote}/robots.txt", headers={"User-Agent": ua_pour(url)}, timeout=30)
            (SORTIE / f"robots_{p.netloc}.txt").write_text(f"HTTP {r.status_code}\n{r.text}", encoding="utf-8")
            if r.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
                robots[hote] = rp
            elif r.status_code in (404, 410):
                robots[hote] = None  # pas de robots.txt : permis
            else:
                robots[hote] = "illisible"
            resume.append(f"- robots.txt {p.netloc} : HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            robots[hote] = "illisible"
            resume.append(f"- robots.txt {p.netloc} : ERREUR {e}")
    rp = robots[hote]
    if rp == "illisible":
        return False
    return rp is None or rp.can_fetch(ua_pour(url), url)


def get(url, nom=None, max_octets=None):
    if not permis(url):
        resume.append(f"- INTERDIT par robots.txt (pas téléchargé) · {url}")
        return None
    time.sleep(0.6)
    try:
        r = session.get(url, headers={"User-Agent": ua_pour(url), "Accept-Encoding": "gzip, deflate"}, timeout=90,
                        stream=max_octets is not None)
        if max_octets:
            morceaux, total = [], 0
            for m in r.iter_content(65536):
                morceaux.append(m)
                total += len(m)
                if total >= max_octets:
                    break
            r._content = b"".join(morceaux)[:max_octets]
            r.close()
        resume.append(f"- {r.status_code} · {len(r.content)} octets · {r.headers.get('Content-Type')} · {url}")
        if nom and r.ok:
            (SORTIE / nom).write_bytes(r.content)
        return r
    except Exception as e:  # noqa: BLE001
        resume.append(f"- ERREUR {type(e).__name__}: {e} · {url}")
        return None


def liens(r, base, motif, n=30):
    if r is None or not r.ok:
        return []
    t = r.content.decode("utf-8", "replace")
    vus = []
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S | re.I):
        u = urljoin(base, href.replace("&amp;", "&"))
        txt = " ".join(re.sub(r"<[^>]+>", " ", txt).split())
        if re.search(motif, u + " " + txt, re.I) and u not in [v[0] for v in vus]:
            vus.append((u, txt))
    for u, txt in vus[:n]:
        resume.append(f"    - {txt[:90]} → {u}")
    return [u for u, _ in vus]


def section(titre):
    resume.append(f"\n## {titre}")


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    section("FTC : flux RSS des avis de fin anticipée")
    r = get("https://www.ftc.gov/feeds/hsr-early-termination-notices.xml", "ftc_et_rss.xml")
    if r is not None and r.ok:
        items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
        resume.append(f"  - {len(items)} items ; 2 premiers bruts :")
        for it in items[:2]:
            resume.append("    " + it[:1500].replace("\n", " "))
    section("SEC : 2 documents officiels (suspension, procédure)")
    get("https://www.sec.gov/files/litigation/suspensions/2026/34-105675.pdf", "sec_susp_34-105675.pdf")
    get("https://www.sec.gov/files/litigation/admin/2026/33-11450.pdf", "sec_ap_33-11450.pdf")
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
