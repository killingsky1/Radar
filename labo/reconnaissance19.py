"""Lot 3c (Canada), 4e passage : les contrats d'un trimestre complet (mesure du seuil) : ce qui manquait au 1er (mêmes règles : robots.txt d'abord, 401/403 = interdit,
Crawl-delay respecté, sinon 1,5 s par site ; rien n'est contourné).

- Santé Canada : la liste complète (une fois) → extrait compact des avis de 2026 + 3 fiches détaillées (?id=) ;
- Contrats : types des champs et comptes par trimestre (API du portail ouvert, 20 s entre deux requêtes) ;
- CCC : la page des rapports et le dernier rapport des transactions signées ;
- Statistique Canada, Gazette, Bureau de la concurrence (FR), Bureau des grands projets, LEGISinfo (une fiche).
"""
import json
import re
import subprocess
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-lot3c4")
SORTIE.mkdir(parents=True, exist_ok=True)
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"
CKAN = "https://open.canada.ca/data/api/action/"
NOC = "https://health-products.canada.ca/api/notice-of-compliance/"
BGP = "https://www.canada.ca/en/privy-council/major-projects-office/"
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






# ---------- Contrats : tout le trimestre 2026-2027-Q1, par pages de 1000 (20 s entre deux requêtes) ----------
CHAMPS = ("_id,reference_number,owner_org,owner_org_title,vendor_name,contract_date,contract_value,original_value,"
          "amendment_value,description_fr,country_of_vendor,solicitation_procedure,number_of_bids,instrument_type")
FILTRE = quote(json.dumps({"reporting_period": "2026-2027-Q1"}))
lignes, debut_t = [], time.monotonic()
for page in range(40):
    nom = f"contrats_page_{page}"
    visiter(nom, CKAN + f"datastore_search?resource_id={RESSOURCE}&filters={FILTRE}&sort=" + quote("_id asc")
            + f"&limit=1000&offset={page * 1000}&fields={CHAMPS}")
    f = SORTIE / f"{nom}.bin"
    if resultats[nom].get("statut") != 200 or not f.exists():
        break
    recs = json.loads(f.read_text(encoding="utf-8"))["result"]["records"]
    f.unlink()
    lignes += recs
    if len(recs) < 1000:
        break
duree = time.monotonic() - debut_t


def valeur(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


vals = [valeur(r["contract_value"]) for r in lignes]
stats = {"lignes": len(lignes), "duree_s": round(duree), "sans_valeur": sum(1 for v in vals if v is None),
         "cles_uniques": len({(r["owner_org"], r["reference_number"]) for r in lignes})}
for seuil in (1e5, 1e6, 5e6, 1e7, 5e7, 1e8):
    stats[f">={int(seuil):,}"] = sum(1 for v in vals if v is not None and v >= seuil)
dates = sorted(r["contract_date"] or "" for r in lignes)
stats["dates"] = [dates[0], dates[len(dates) // 2], dates[-1]] if dates else []
gros = sorted((r for r in lignes if (valeur(r["contract_value"]) or 0) >= 1e6), key=lambda r: -valeur(r["contract_value"]))
(SORTIE / "contrats_1M.json").write_text(json.dumps(gros, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
(SORTIE / "contrats_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(stats)

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
