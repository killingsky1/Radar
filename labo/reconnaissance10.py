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

SORTIE = Path("labo/resultats-lot3a2")
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
    section("FTC : 3 avis de fin anticipée (structure, date)")
    for n in ("20262162", "20262268", "20262326"):
        r = get(f"https://www.ftc.gov/legal-library/browse/early-termination-notices/{n}", f"ftc_{n}.html")
        if r is not None and r.ok:
            t = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)).split())
            i = t.find(n)
            resume.append(f"    - texte : …{t[max(0, i - 200):i + 900]}…")
    r = get("https://www.ftc.gov/news-events/stay-connected/ftc-rss-feeds", "ftc_rss.html")
    liens(r, "https://www.ftc.gov/", r"rss|feed|\.xml")

    section("DOJ : flux antitrust (adresse officielle de la page)")
    get("https://www.justice.gov/news/rss?type%5B0%5D=image_gallery&type%5B1%5D=press_release&type%5B2%5D=speech&type%5B3%5D=youtube_video&field_component=376&search_api_language=en&show_public_archived=0&require_all=0", "doj_atr_rss.xml")
    get("https://www.justice.gov/api/v1/press_releases.json?pagesize=20&parameters%5Bcomponent%5D=376", "doj_atr_api.json")

    section("SEC : suspensions de cotation et procédures administratives")
    get("https://www.sec.gov/enforcement-litigation/trading-suspensions/rss", "sec_susp_rss.xml")
    get("https://www.sec.gov/enforcement-litigation/administrative-proceedings/rss", "sec_ap_rss.xml")

    section("OFAC : pages d'actions récentes")
    for n in ("20261002", "20261001", "20260930"):
        r = get(f"https://ofac.treasury.gov/recent-actions/{n}", f"ofac_{n}.html")
        if r is not None and r.ok:
            t = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)).split())
            i = t.find("Designations")
            resume.append(f"    - texte : …{t[max(0, i - 300):i + 1500]}…")

    section("NHTSA : rappels (portail de données du ministère des Transports)")
    r = get("https://datahub.transportation.gov/resource/6axg-epim.json?$limit=50&$order=report_received_date%20DESC", "nhtsa_50.json")
    get("https://datahub.transportation.gov/api/views/6axg-epim.json", "nhtsa_meta.json")
    if r is not None and r.ok:
        d = r.json()
        resume.append(f"    - champs : {sorted(d[0].keys()) if d else []}")
        for x in d[:8]:
            resume.append(f"    - {x.get('report_received_date')} · {x.get('nhtsa_id')} · {x.get('manufacturer')} · {x.get('potentially_affected')} · {str(x.get('subject'))[:80]}")
    get("https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V000-0001.PDF")  # seulement pour lire le robots.txt de static.nhtsa.gov

    section("SEC : plus de prospectus 424B4 (septembre 2026)")
    trouves = []
    for jour in ("20260915", "20260916", "20260917", "20260918", "20260922", "20260923", "20260924", "20260925"):
        r = get(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.{jour}.idx")
        if r is not None and r.ok:
            trouves += [l.split("|") for l in r.content.decode("latin-1").splitlines() if l.count("|") == 4 and l.split("|")[2] == "424B4"]
    resume.append(f"  - 424B4 du 15 au 25 sept. : {len(trouves)}")
    for p in trouves[:10]:
        acc = p[4].rsplit("/", 1)[1].removesuffix(".txt")
        dossier = f"https://www.sec.gov/Archives/edgar/data/{p[0]}/{acc.replace('-', '')}"
        idx = get(f"{dossier}/index.json")
        if idx is None or not idx.ok:
            continue
        items = idx.json()["directory"]["item"]
        doc = max((i for i in items if i["name"].endswith((".htm", ".html")) and "index" not in i["name"]),
                  key=lambda i: int(i.get("size") or 0), default=None)
        if doc:
            get(f"{dossier}/{doc['name']}", f"424b4_{acc}.htm")
            resume.append(f"    - {p[1]} · {p[3]} · {acc}")

    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
