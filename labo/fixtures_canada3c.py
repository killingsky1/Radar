"""Vrais fichiers pour les tests du lot 3c, livraison 1 (concurrence, sanctions, Gazette, grands projets, StatCan,
LEGISinfo). Mêmes règles : robots.txt d'abord (401/403 = interdit), Crawl-delay respecté, sinon 1,5 s par site.

Tout est enregistré compressé (gzip) dans labo/fixtures-canada3c, avec pages.json : adresse -> fichier.
"""
import gzip
import json
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/fixtures-canada3c")
SORTIE.mkdir(parents=True, exist_ok=True)
AUJOURDHUI = date.today()
LOIS = re.compile(r"^(Tarif des douanes|Mesures économiques spéciales|Licences d’exportation et d’importation"
                  r"|Mesures spéciales d’importation|Investir au Canada|Douanes \(Loi|Taxe d’accise"
                  r"|Tribunal canadien du commerce extérieur|Accord |Protocole d’adhésion|Exécution du budget|Libre-échange"
                  r"|Bâtir le Canada)")
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000  # au-delà, on arrête de lire (la taille exacte n'est alors pas connue)
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|export|download|telecharg|terms|conditions|avis|notice"
                          r"|licen|disclosure|divulgation|transaction|feed", re.I)
robots, resultats, dernier = {}, {}, {}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
            robots[hote] = {"statut": r.status_code, "texte": r.text[:4000]}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(UA) if robots[hote]["statut"] == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, tete):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(UA, url):
            return None, url
        attendre(hote)
        r = (requests.head if tete else requests.get)(url, headers=H, timeout=(20, 180), stream=not tete,
                                                      allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, tete=False, garde=MAX_GARDE):
    res = {"url": url}
    try:
        r, finale = requete(url, tete)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None and tete:
            res.update({"statut": r.status_code, "entetes": dict(r.headers)})
        elif r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            corps = b"".join(morceaux)[:garde]
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"),
                        "taille": taille, "complet": taille <= garde, "lecture_arretee": taille > MAX_LU,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control",
                                                     "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding")},
                        "debut": corps[:500].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(corps)
            if "html" in (r.headers.get("content-type") or ""):
                texte = corps.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:150]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)






pages = {}


def garder(nom, url):
    """Télécharge (robots.txt respecté) et garde le contenu complet, compressé."""
    visiter(nom, url, garde=MAX_LU)
    f = SORTIE / f"{nom}.bin"
    if resultats[nom].get("statut") == 200 and f.exists():
        (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(f.read_bytes(), mtime=0))
        pages[resultats[nom]["url"]] = f"{nom}.gz"
    if f.exists():
        f.unlink()
    return resultats[nom].get("statut") == 200


def contenu(nom):
    return gzip.decompress((SORTIE / f"{nom}.gz").read_bytes())


def date_du_lien(lien):
    m = re.search(r"/(\d{4}-\d\d-\d\d)", lien)
    return date.fromisoformat(m.group(1)) if m else None


# ---------- Gazette : les 2 fils RSS, puis chaque numéro des 90 derniers jours ----------
for partie in ("p1", "p2"):
    garder(f"rss_{partie}", f"https://gazette.gc.ca/rss/{partie}-fra.xml")
    canal = ET.fromstring(contenu(f"rss_{partie}")).find("channel")
    for it in canal.findall("item"):
        lien = (it.findtext("link") or "").strip()
        d = date_du_lien(lien)
        if not d or d < AUJOURDHUI - timedelta(days=90) or re.search(r"-c\d/index", lien):
            continue
        nom = f"{partie}_" + re.sub(r"[^0-9a-z]+", "_", lien.split("/rp-pr/")[1].lower()).strip("_")
        if not garder(nom, lien) or partie != "p2" or not lien.endswith("/html/index-fra.html"):
            continue
        # Partie II : la page de chaque règlement retenu (lois liées à l'argent, Loi visant à bâtir le Canada)
        t = contenu(nom).decode("utf-8", "replace")
        for li in re.findall(r"<li>(.*?)</li>", t[t.find("<main"):t.find("</main>")], re.S):
            m = re.search(r'<a href="([^"]+)">(.*?)</a>(.*)', li, re.S)
            if not m or "erratum" in m.group(3):
                continue
            morceaux = [" ".join(re.sub(r"<[^>]+>", " ", p).replace("&nbsp;", " ").split())
                        for p in re.split(r"<br\s*/?>", m.group(2))]
            if LOIS.search(morceaux[-1]):
                garder(nom + "_" + m.group(1).replace("-fra.html", "").replace("-", "_"), urljoin(lien, m.group(1)))

# Partie I : les pages d'avis de la Loi visant à bâtir le Canada (1er août et 29 août 2026)
garder("p1_avis_0801", "https://gazette.gc.ca/rp-pr/p1/2026/2026-08-01/html/sup1-fra.html")
garder("p1_avis_0829", "https://gazette.gc.ca/rp-pr/p1/2026/2026-08-29/html/notice-avis-fra.html")
# Partie II : un exemple d'édition spéciale qui pointe directement vers un texte
garder("p2_extra_exemple", "https://gazette.gc.ca/rp-pr/p2/2026/2026-06-08-x1/html/si-tr29-fra.html")

# ---------- Bureau des grands projets (français) ----------
garder("bgp_national", "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/projets/national.html")

# ---------- Bureau de la concurrence (français) ----------
garder("concurrence", "https://bureau-concurrence.canada.ca/fr/fusions-acquisitions/rapport-examens-fusions-termines")

# ---------- Sanctions ----------
garder("sanctions", "https://www.international.gc.ca/world-monde/assets/office_docs/international_relations-"
                    "relations_internationales/sanctions/sema-lmes.xml")

# ---------- Statistique Canada ----------
garder("statcan_quotidien", "https://www150.statcan.gc.ca/n1/fr/rss/dai-quo/0-fra.atom")
garder("statcan_principaux", "https://www150.statcan.gc.ca/n1/dai-quo/cal1-fra.htm")

# ---------- LEGISinfo ----------
garder("legisinfo", "https://www.parl.ca/legisinfo/fr/projets-de-loi/json?parlsession=45-1")

(SORTIE / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
