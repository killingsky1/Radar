"""Lot 3c (Canada), 2e passage : ce qui manquait au 1er (mêmes règles : robots.txt d'abord, 401/403 = interdit,
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
SORTIE = Path("labo/resultats-lot3c2")
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




def sql(nom, requete_sql):
    visiter(nom, CKAN + "datastore_search_sql?sql=" + quote(requete_sql))


# ---------- Santé Canada : la liste complète une fois, puis 3 fiches ----------
visiter("noc_main_fr", NOC + "noticeofcompliancemain/?lang=fr&type=json", garde=MAX_LU)
complet = SORTIE / "noc_main_fr.bin"
if resultats["noc_main_fr"].get("statut") == 200 and resultats["noc_main_fr"].get("complet"):
    tous = json.loads(complet.read_text(encoding="utf-8-sig"))
    an = sorted((x for x in tous if x["noc_date"] >= "2026-01-01"), key=lambda x: (x["noc_date"], x["noc_number"]))
    par_annee = {}
    for x in tous:
        a = x["noc_date"][:4]
        mn, mx = par_annee.get(a, (10**9, 0))
        par_annee[a] = (min(mn, x["noc_number"]), max(mx, x["noc_number"]))
    stats = {"total": len(tous), "max_numero": max(x["noc_number"] for x in tous),
             "date_max": max(x["noc_date"] for x in tous), "numeros_par_annee": par_annee,
             "classes": {}, "types": {}}
    for x in tous:
        stats["classes"][x["noc_submission_class"]] = stats["classes"].get(x["noc_submission_class"], 0) + 1
        stats["types"][x["noc_product_type"]] = stats["types"].get(x["noc_product_type"], 0) + 1
    (SORTIE / "noc_2026.json").write_text(json.dumps(an, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    (SORTIE / "noc_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    complet.unlink()  # 23 Mo : on ne garde que l'extrait
    nouvelles = [x for x in an if re.search(r"(?i)nouvelle substance|new active substance", x["noc_submission_class"] or "")][-3:]
    for x in nouvelles:
        n = x["noc_number"]
        for res in ("noticeofcompliancemain", "drugproduct", "medicinalingredient"):
            visiter(f"noc_{res}_{n}", NOC + f"{res}/?id={n}&lang=fr&type=json")

# ---------- Contrats de plus de 10 000 $ ----------
visiter("contrats_champs", CKAN + f"datastore_search?resource_id={RESSOURCE}&limit=0")
T = f'"{RESSOURCE}"'
sql("contrats_par_trimestre",
    f"SELECT reporting_period, count(*) AS n, "
    f"sum(CASE WHEN contract_value::numeric >= 1000000 THEN 1 ELSE 0 END) AS un_million, "
    f"sum(CASE WHEN contract_value::numeric >= 10000000 THEN 1 ELSE 0 END) AS dix_millions "
    f"FROM {T} WHERE reporting_period >= '2025-2026-Q1' GROUP BY reporting_period ORDER BY reporting_period DESC")
sql("contrats_gros_recents",
    f"SELECT _id, reference_number, owner_org, owner_org_title, vendor_name, contract_date, contract_value, "
    f"original_value, amendment_value, description_fr, reporting_period, country_of_vendor, solicitation_procedure, "
    f"number_of_bids FROM {T} WHERE reporting_period = '2026-2027-Q1' AND contract_value::numeric >= 10000000 "
    f"ORDER BY contract_value::numeric DESC LIMIT 40")
sql("contrats_doublons",
    f"SELECT count(*) AS lignes, count(DISTINCT owner_org || '|' || reference_number) AS cles FROM {T} "
    f"WHERE reporting_period >= '2025-2026-Q1'")
visiter("recherche_sanctions", CKAN + "package_search?q=" + quote("consolidated autonomous sanctions") + "&rows=3")
visiter("recherche_fusions", CKAN + "package_search?q=" + quote("merger reviews competition bureau") + "&rows=3")

# ---------- CCC : la page des rapports, puis les 2 derniers rapports de transactions signées ----------
visiter("ccc_rapports", "https://www.ccc.ca/en/about/corporate-reports/")
visiter("ccc_conditions", "https://www.ccc.ca/en/terms-of-use/")
page = (SORTIE / "ccc_rapports.bin")
if page.exists():
    t = page.read_text(encoding="utf-8", errors="replace")
    i = t.find('id="transactions"')
    bloc = t[i:i + 40000] if i >= 0 else t
    docs = [urljoin("https://www.ccc.ca/", h) for h in re.findall(r"""href=["']([^"']+)["']""", bloc)
            if re.search(r"(?i)transaction|signed|disclosure", h)]
    resultats["ccc_liens_transactions"] = {"liens": list(dict.fromkeys(docs))[:40]}
    for k, d in enumerate(list(dict.fromkeys(docs))[:2]):
        visiter(f"ccc_rapport_{k}", d)
        f = SORTIE / f"ccc_rapport_{k}.bin"
        if f.exists() and f.read_bytes()[:4] == b"%PDF":
            subprocess.run(["pdftotext", "-layout", str(f), str(SORTIE / f"ccc_rapport_{k}.txt")], check=False)

# ---------- Statistique Canada ----------
for k in ("cal1", "cal3", "cal4"):
    visiter(f"statcan_{k}", f"https://www150.statcan.gc.ca/n1/dai-quo/{k}-eng.htm")
visiter("statcan_conditions", "https://www.statcan.gc.ca/en/terms-conditions")

# ---------- Gazette du Canada : numéros récents ----------
visiter("gazette_p2_0923_fr", "https://gazette.gc.ca/rp-pr/p2/2026/2026-09-23/html/index-fra.html")
visiter("gazette_p1_1003_fr", "https://gazette.gc.ca/rp-pr/p1/2026/2026-10-03/html/index-fra.html")
visiter("gazette_p1_0829_fr", "https://gazette.gc.ca/rp-pr/p1/2026/2026-08-29/html/index-fra.html")
visiter("gazette_p2_extra", "https://gazette.gc.ca/rp-pr/p2/2026/index-fra.html")

# ---------- Bureau de la concurrence (français) ----------
visiter("concurrence_fr", "https://bureau-concurrence.canada.ca/fr/fusions-acquisitions/rapport-examens-fusions-termines")

# ---------- Bureau des grands projets ----------
visiter("bgp_nationaux", BGP + "projects/national.html")
visiter("bgp_autres", BGP + "projects/other.html")
visiter("bgp_west", BGP + "projects/national/west.html")
visiter("bgp_lng", BGP + "projects/national/lng-canada.html")
visiter("bgp_nouvelles", BGP + "news.html")
visiter("bgp_fr", "https://www.canada.ca/fr/conseil-prive/bureau-grands-projets.html")

# ---------- LEGISinfo : une fiche en cours (C-31) ----------
visiter("legisinfo_c31", "https://www.parl.ca/legisinfo/fr/projet-de-loi/45-1/c-31/json")

# ---------- Décret sur la reproduction de la législation fédérale (2e essai) ----------
visiter("decret_reproduction", "https://laws-lois.justice.gc.ca/fra/reglements/TR-97-5/TexteComplet.html")

for h in robots.values():
    h.pop("rp", None)
(SORTIE / "robots.json").write_text(json.dumps(robots, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
