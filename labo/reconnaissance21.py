"""Lot 3d, 2e passage (mêmes règles que le 1er : robots.txt d'abord, lu avec notre identification ; 401/403 = interdit ;
Crawl-delay respecté, sinon 1,5 s par site ; clés d'accès des pages masquées ; rien n'est contourné).

- USAspending et GlobeNewswire : leur robots.txt n'a pas répondu au 1er passage (relu jusqu'à 3 fois, 30 s d'écart) ;
- SEC : la liste COMPLÈTE des fichiers d'échecs de livraison (le 1er passage l'avait tronquée à 200 liens) ;
- adresses trouvées dans la documentation officielle (à compléter).
"""
import json
import re
import time
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/resultats-lot3d2")
SORTIE.mkdir(parents=True, exist_ok=True)
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|rss|feed|api|export|download|terms|conditions"
                          r"|legal|copyright|policy|polic|exclu|holding|investments|press|news|bulletin|fails", re.I)
robots, resultats, dernier = {}, {}, {}
AUJ = date.today()
# Des pages publiques contiennent parfois des clés d'accès (ex. une clé Mapbox dans la page de NBIM) : on ne les garde
# jamais. Elles sont masquées avant tout enregistrement.
CLES = [re.compile(rb"\b(?:pk|sk|tk)\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"), re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
        re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        re.compile(rb"(?i)((?:access_?token|api_?key|apikey|secret|token)[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._~+/-]{16,}")]


def masquer(contenu, type_contenu):
    if not re.search(r"html|json|xml|javascript|text", type_contenu or ""):
        return contenu, 0
    n = 0
    for motif in CLES:
        contenu, k = motif.subn(lambda m: (m.group(1) if m.groups() else b"") + b"[cle masquee]", contenu)
        n += k
    return contenu, n


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def entetes(hote):
    return {"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=entetes(hote), timeout=(20, 40), allow_redirects=True)
            robots[hote] = {"statut": r.status_code, "texte": r.text[:6000], "url_finale": r.url}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(ua(hote)) if robots[hote].get("statut") == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
        print("robots.txt", hote, robots[hote].get("statut"), "délai", robots[hote]["delai"], flush=True)
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, corps=None):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(ua(hote), url):
            return None, url
        attendre(hote)
        if corps is None:
            r = requests.get(url, headers=entetes(hote), timeout=(20, 180), stream=True, allow_redirects=False)
        else:
            r = requests.post(url, headers={**entetes(hote), "Content-Type": "application/json"}, data=json.dumps(corps),
                              timeout=(20, 180), stream=True, allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            corps = None
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, corps=None, garde=MAX_GARDE):
    res = {"url": url, "post": corps}
    try:
        r, finale = requete(url, corps)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            contenu, masquees = masquer(b"".join(morceaux)[:garde], r.headers.get("content-type"))
            res["cles_masquees"] = masquees
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": taille,
                        "complet": taille <= garde,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control", "retry-after",
                                                     "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding",
                                                     "server")},
                        "debut": contenu[:600].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(contenu)
            if "html" in (r.headers.get("content-type") or ""):
                texte = contenu.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:200]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)
    return res



def relire_robots(hote, essais=3):
    """robots.txt qui n'a pas répondu : jusqu'à 3 essais, 30 s d'écart, 90 s d'attente chacun. Échec = interdit."""
    for i in range(essais):
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=entetes(hote), timeout=(30, 90), allow_redirects=True)
            rp = urllib.robotparser.RobotFileParser()
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
            delai = rp.crawl_delay(ua(hote)) if r.status_code == 200 else None
            robots[hote] = {"statut": r.status_code, "texte": r.text[:6000], "url_finale": r.url, "essai": i + 1,
                            "delai": float(delai) if delai else None, "rp": rp}
            dernier[hote] = time.monotonic()
            print("robots.txt (relu)", hote, r.status_code, "essai", i + 1, flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            print("robots.txt (relu)", hote, "échec", i + 1, str(exc)[:120], flush=True)
            time.sleep(30)
    rp = urllib.robotparser.RobotFileParser()
    rp.disallow_all = True
    robots[hote] = {"statut": None, "erreur": f"{essais} essais sans réponse", "delai": None, "rp": rp}
    dernier[hote] = time.monotonic()


for hote in ("api.usaspending.gov", "www.globenewswire.com"):
    relire_robots(hote)

# ---------- SEC : échecs de livraison, la liste complète ----------
page = visiter("sec_ftd_page", "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data")
f = SORTIE / "sec_ftd_page.bin"
if f.exists():
    zips = sorted({urljoin(page["url_finale"], h) for h in LIENS.findall(f.read_text(encoding="utf-8", errors="replace"))
                   if h.endswith(".zip")})
    resultats["sec_ftd_page"]["zips"] = zips[-6:]
    resultats["sec_ftd_page"]["nombre_de_fichiers"] = len(zips)
    if zips:
        visiter("sec_ftd_dernier", zips[-1])

# ---------- USAspending : l'API, si son robots.txt la permet ----------
US = "https://api.usaspending.gov/api/v2/"
CHAMPS = ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Awarding Agency", "Awarding Sub Agency",
          "Start Date", "Base Obligation Date", "Last Modified Date", "Description", "generated_internal_id"]
for nom, type_date, jours in (("us_modifies_7j", "last_modified_date", 7), ("us_nouveaux_30j", "new_awards_only", 30)):
    visiter(nom, US + "search/spending_by_award/", corps={
        "filters": {"award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": (AUJ - timedelta(days=jours)).isoformat(), "end_date": AUJ.isoformat(),
                                     "date_type": type_date}],
                    "award_amounts": [{"lower_bound": 100_000_000}]},
        "fields": CHAMPS, "sort": "Award Amount", "order": "desc", "limit": 100, "page": 1})
visiter("us_mise_a_jour", US + "awards/last_updated/")
try:
    premier = json.loads((SORTIE / "us_nouveaux_30j.bin").read_bytes())["results"][0]["generated_internal_id"]
    visiter("us_fiche_contrat", US + f"awards/{premier}/")
except Exception as exc:  # noqa: BLE001
    resultats["us_fiche_contrat"] = {"erreur": str(exc)[:200]}

# ---------- Conditions d'utilisation : les vraies pages, avec notre identification ----------
for nom, url in (("conditions_nbim", "https://www.nbim.no/en/disclaimer/"),
                 ("conditions_prnewswire", "https://www.prnewswire.com/terms-of-use/"),
                 ("conditions_newswire_ca", "https://www.newswire.ca/privacy-terms-of-use/"),
                 ("conditions_newsfile", "https://www.newsfilecorp.com/TermsOfUse.php"),
                 ("conditions_globenewswire", "https://portal.notified.com/terms-conditions/en"),
                 ("conditions_yahoo", "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html"),
                 ("conditions_cbp", "https://www.cbp.gov/site-policy-notices/privacy"),
                 ("licence_fiscal_data", "https://fiscaldata.treasury.gov/api-documentation/")):
    visiter(nom, url)

# ---------- Trésor : calendrier officiel des publications ----------
visiter("fd_calendrier", "https://api.fiscaldata.treasury.gov/services/calendar/release")

# ---------- Tarifs : messages CSMS de la douane (RSS GovDelivery) et RSS de l'USTR ----------
visiter("csms_rss", "https://content.govdelivery.com/accounts/USDHSCBP/widgets/USDHSCBP_WIDGET_2.rss")
visiter("ustr_rss", "https://ustr.gov/rss.xml")

# ---------- Participations du gouvernement : mesure d'une détection dans le texte des 8-K ----------
# Une phrase qui nomme un ministère fédéral (ou le gouvernement des États-Unis) ET un titre de propriété.
GOUV = re.compile(r"(?:U\.S\.|United States)\s+Department\s+of\s+(?:Commerce|War|Defense|Energy)"
                  r"|Department\s+of\s+(?:Commerce|War|Defense|Energy)|United\s+States\s+of\s+America"
                  r"|(?:U\.S\.|United States)\s+Government", re.I)
TITRE = re.compile(r"\bwarrants?\b|preferred\s+stock|common\s+stock|common\s+shares|equity\s+(?:stake|interest)", re.I)
VERBE = re.compile(r"\b(?:issue[sd]?|issuance|sell|sold|sale|purchase[sd]?|acquire[sd]?|grant(?:ed)?|receive[sd]?|hold|own)\b",
                   re.I)


def texte_html(contenu):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", contenu.decode("utf-8", "replace"))
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</td>|</tr>", ". ", t)
    return " ".join(html_unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ").split())


def html_unescape(t):
    import html
    return html.unescape(t)


def phrases_gouv(texte):
    return [p.strip()[:600] for p in re.split(r"(?<=[.;])\s+(?=[A-Z(])", texte)
            if GOUV.search(p) and TITRE.search(p) and VERBE.search(p)][:6]


def documents_8k(cik, depuis, jusqua):
    """Les 8-K d'une compagnie (fichier officiel des dépôts de data.sec.gov), avec leurs points."""
    r = visiter(f"soumissions_{cik}", f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
    f = SORTIE / f"soumissions_{cik}.bin"
    if r.get("statut") != 200 or not f.exists():
        return []
    d = json.loads(f.read_bytes())
    f.unlink()
    rec = d["filings"]["recent"]
    return [(rec["accessionNumber"][i], rec["filingDate"][i], rec["items"][i], rec["primaryDocument"][i])
            for i in range(len(rec["form"])) if rec["form"][i] == "8-K" and depuis <= rec["filingDate"][i] <= jusqua]


CAS = {"INTC": ("2025-08-20", "2025-09-05"), "MP": ("2025-07-08", "2025-07-20"), "QBTS": ("2026-09-01", "2026-09-20"),
       "LAC": ("2025-09-25", "2025-10-20"), "TMQ": ("2025-10-01", "2025-10-20"), "USAR": ("2026-01-20", "2026-02-10"),
       "LHX": ("2026-01-10", "2026-04-30"), "RGTI": ("2026-09-01", "2026-09-20")}
sym = visiter("sec_symboles", "https://www.sec.gov/files/company_tickers_exchange.json")
table = json.loads((SORTIE / "sec_symboles.bin").read_bytes()) if sym.get("statut") == 200 else {"data": []}
(SORTIE / "sec_symboles.bin").unlink(missing_ok=True)
cik_de = {x[2]: x[0] for x in table["data"]}
mesure = {"cas": {}, "echantillon": {}}
for symbole, (depuis, jusqua) in CAS.items():
    cik = cik_de.get(symbole)
    trouves = []
    for acc, jour, items, doc in (documents_8k(cik, depuis, jusqua) if cik else []):
        nom = f"8k_{symbole}_{acc}"
        r = visiter(nom, f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}")
        f = SORTIE / f"{nom}.bin"
        if f.exists():
            trouves.append({"acc": acc, "jour": jour, "items": items, "phrases": phrases_gouv(texte_html(f.read_bytes()))})
            f.unlink()
    mesure["cas"][symbole] = {"cik": cik, "8k": trouves}
    print("cas", symbole, cik, [(x["jour"], x["items"], len(x["phrases"])) for x in trouves], flush=True)

# Échantillon : tous les 8-K de 2 jours ouvrables récents (fausses alertes ?)
for jour in ("20261001", "20261002"):
    r = visiter(f"index_{jour}", f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.{jour}.idx")
    f = SORTIE / f"index_{jour}.bin"
    if not f.exists():
        continue
    lignes = [l for l in f.read_text(encoding="latin-1").splitlines() if l.startswith("8-K ")][:100]  # 100 par jour
    f.unlink()
    marques, lus = [], 0
    for l in lignes:
        chemin = l.split()[-1]  # edgar/data/CIK/0000000000-26-000000.txt
        cik, acc = chemin.split("/")[2], chemin.split("/")[-1][:-4]
        nom = f"idx_{acc}"
        r = visiter(nom, f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm")
        g = SORTIE / f"{nom}.bin"
        if not g.exists():
            continue
        page = g.read_text(encoding="utf-8", errors="replace")
        g.unlink()
        doc = re.search(r'href="(?:/ix\?doc=)?(/Archives/edgar/data/[^"]+\.htm)"', page)  # 1re ligne = document principal
        if not doc:
            continue
        nom = f"doc_{acc}"
        visiter(nom, "https://www.sec.gov" + doc.group(1))
        h = SORTIE / f"{nom}.bin"
        if h.exists():
            lus += 1
            ph = phrases_gouv(texte_html(h.read_bytes()))
            h.unlink()
            if ph:
                marques.append({"acc": acc, "cik": cik, "phrases": ph})
    mesure["echantillon"][jour] = {"8k": len(lignes), "lus": lus, "marques": marques}
    print("échantillon", jour, len(lignes), "lus", lus, "marqués", len(marques), flush=True)
(SORTIE / "participations_mesure.json").write_text(json.dumps(mesure, ensure_ascii=False, indent=1), encoding="utf-8")

(SORTIE / "resultats.json").write_text(json.dumps(
    {"pages": resultats, "robots": {h: {k: v for k, v in r.items() if k != "rp"} for h, r in robots.items()}},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("fini")
