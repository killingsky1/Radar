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

SORTIE = Path("labo/resultats-lot3a")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
session = requests.Session()
resume = ["# Reconnaissance du lot 3a", ""]
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
    section("SEC : poursuites (litigation releases) et communiqués")
    r = get("https://www.sec.gov/enforcement-litigation/litigation-releases", "sec_lit.html")
    liens(r, "https://www.sec.gov/", r"rss|feed|lr-\d|litigation-releases/\d")
    for u, n in [("https://www.sec.gov/rss/litigation/litreleases.xml", "sec_lit_rss.xml"),
                 ("https://www.sec.gov/enforcement-litigation/litigation-releases/rss", "sec_lit_rss2.xml"),
                 ("https://www.sec.gov/news/pressreleases.rss", "sec_pr_rss.xml"),
                 ("https://www.sec.gov/about/rss-feeds", "sec_rss_feeds.html")]:
        r = get(u, n)
    liens(r, "https://www.sec.gov/", r"rss|\.xml")

    section("SEC : prospectus d'entrée en bourse (424B4)")
    trouves = []
    for jour in ("20260928", "20260929", "20260930", "20261001"):
        r = get(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.{jour}.idx") if jour < "20261001" else \
            get(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.{jour}.idx")
        if r is not None and r.ok:
            for l in r.content.decode("latin-1").splitlines():
                p = l.split("|")
                if len(p) == 5 and p[2] == "424B4":
                    trouves.append(p)
    resume.append(f"  - 424B4 du 28 sept. au 1er oct. : {len(trouves)}")
    for p in trouves[:12]:
        resume.append(f"    - {p}")
    for p in trouves[:4]:
        acc = p[4].rsplit("/", 1)[1].removesuffix(".txt")
        dossier = f"https://www.sec.gov/Archives/edgar/data/{p[0]}/{acc.replace('-', '')}"
        idx = get(f"{dossier}/index.json")
        if idx is None or not idx.ok:
            continue
        items = idx.json()["directory"]["item"]
        doc = max((i for i in items if i["name"].endswith((".htm", ".html")) and "index" not in i["name"]),
                  key=lambda i: int(i.get("size") or 0), default=None)
        if doc:
            r = get(f"{dossier}/{doc['name']}", f"424b4_{acc}.htm")
            if r is not None and r.ok:
                t = " ".join(re.sub(r"<[^>]+>", " ", r.content.decode("utf-8", "replace")).split())
                for m in list(re.finditer(r"lock-?up", t, re.I))[:3]:
                    resume.append(f"      - …{t[max(0, m.start() - 250):m.start() + 350]}…")

    section("OFAC : actions récentes (sanctions)")
    r = get("https://ofac.treasury.gov/recent-actions", "ofac_recent.html")
    liens(r, "https://ofac.treasury.gov/", r"rss|feed|xml|recent-actions/\d")
    for u, n in [("https://ofac.treasury.gov/rss.xml", "ofac_rss.xml"),
                 ("https://ofac.treasury.gov/recent-actions/rss.xml", "ofac_rss2.xml"),
                 ("https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV", "ofac_sdn_head.csv")]:
        get(u, n, max_octets=300_000)

    section("FTC : fin anticipée de l'examen des fusions")
    r = get("https://www.ftc.gov/legal-library/browse/early-termination-notices", "ftc_et.html")
    liens(r, "https://www.ftc.gov/", r"early-termination-notices/|rss|feed|\.xml|\.csv")

    section("NHTSA : rappels")
    for u, n in [("https://datahub.transportation.gov/resource/6axg-epim.json?$limit=5&$order=report_received_date%20DESC",
                  "nhtsa_socrata.json"),
                 ("https://www.nhtsa.gov/nhtsa-datasets-and-apis", "nhtsa_apis.html"),
                 ("https://api.nhtsa.gov/recalls/recallsByVehicle?make=ford&model=f-150&modelYear=2024", "nhtsa_api.json")]:
        r = get(u, n)
        if n == "nhtsa_apis.html":
            liens(r, "https://www.nhtsa.gov/", r"recall|rcl|flat|download|socrata|datahub")

    section("DOJ : antitrust")
    r = get("https://www.justice.gov/atr/news-feeds", "doj_feeds.html")
    liens(r, "https://www.justice.gov/", r"rss|feed|xml")
    for u, n in [("https://www.justice.gov/api/v1/press_releases.json?pagesize=5&sort=date&direction=DESC", "doj_api.json"),
                 ("https://www.justice.gov/news/rss?type=press_release&component=376", "doj_rss.xml")]:
        get(u, n)

    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
