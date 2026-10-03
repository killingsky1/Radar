"""Lot 3b, D et E (essai réel) : le lobbying des 23 compagnies des listes, les filtres de l'OGE, l'étude sur le lobbying.

LDA.gov : 4,5 secondes entre deux requêtes (robots.txt : Crawl-delay 4 ; 15 par minute sans compte).
OGE : seulement l'adresse de données publique de la page « Officials' Individual Disclosures » (robots.txt absent).
"""
import json
import re
import time
import unicodedata
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
SORTIE = Path("labo/resultats-lobbying-essai")
SORTIE.mkdir(parents=True, exist_ok=True)
ATTENTE = {"lda.gov": 4.5}
robots, dernier, journal = {}, {}, []


def permis(url):
    hote = urlparse(url).hostname
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
            robots[hote] = (rp, r.status_code)
        except Exception as exc:  # noqa: BLE001
            rp.disallow_all = True
            robots[hote] = (rp, str(exc)[:100])
        dernier[hote] = time.monotonic()
    return robots[hote][0].can_fetch(UA, url)


def lire(url, methode="GET"):
    hote = urlparse(url).hostname
    if not permis(url):
        journal.append({"url": url, "refus": "robots.txt"})
        return None
    reste = ATTENTE.get(hote, 1.5) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)
    try:
        r = requests.request(methode, url, headers=H, timeout=(20, 60), allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        journal.append({"url": url, "erreur": str(exc)[:200]})
        return None
    dernier[hote] = time.monotonic()
    journal.append({"url": url, "methode": methode, "statut": r.status_code, "taille": len(r.content),
                    "type": r.headers.get("content-type"), "longueur": r.headers.get("content-length")})
    return r


# ---------- A. OGE : filtres ----------
API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest?draw=1&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
for i, c in enumerate(("docDate", "title", "type", "name", "agency", "level")):
    API += f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true&columns%5B{i}%5D%5Borderable%5D=true"
API += "&search%5Bvalue%5D=&columns%5B2%5D%5Bsearch%5D%5Bvalue%5D=Transaction"
oge = {}
for nom, filtre in (("niveaux", "&columns%5B5%5D%5Bsearch%5D%5Bvalue%5D=Level"),
                    ("president", "&columns%5B1%5D%5Bsearch%5D%5Bvalue%5D=President")):
    r = lire(API + filtre + "&start=0&length=100")
    if r is not None and r.status_code == 200:
        d = r.json()
        (SORTIE / f"oge_{nom}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        oge[nom] = {"total": d.get("recordsFiltered"), "lignes": len(d.get("data", []))}
pdf = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/B157175D415FEC4685258E82002DBEBE/$FILE/Scott-A-Kupor-07.31.2026-278T.pdf"
r = lire(pdf, "HEAD")
oge["head_pdf"] = None if r is None else {"statut": r.status_code, "type": r.headers.get("content-type"),
                                          "longueur": r.headers.get("content-length")}

# ---------- B. Lobbying : essai réel sur les compagnies des listes ----------
SUFFIXES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LLC", "LP", "LLP",
            "PLC", "SA", "NV", "AG", "SE", "THE"}
COMMUNS = {"FIRST", "CAPITAL", "GROUP", "HOLDING", "HOLDINGS", "BANCORP", "BANCSHARES", "FINANCIAL", "INTERNATIONAL",
           "AMERICAN", "NATIONAL", "TECHNOLOGIES", "TECHNOLOGY", "THERAPEUTICS", "PHARMACEUTICALS", "ENERGY",
           "SYSTEMS", "SERVICES", "INDUSTRIES", "PARTNERS", "TRUST", "BANK", "GLOBAL", "RESOURCES", "SOLUTIONS",
           "MANAGEMENT", "ASSET", "INVESTMENT", "DATA", "HEALTH", "MEDICAL", "BIOSCIENCES", "SCIENCES"}


def mots(nom):
    n = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper().replace("&", " AND ")
    m = re.findall(r"[A-Z0-9]+", n.replace("'", ""))
    while m and m[-1] in SUFFIXES:
        m.pop()
    while m and m[0] == "THE":
        m.pop(0)
    return m


def mot_de_recherche(m):
    candidats = [x for x in m if len(x) >= 4 and x not in COMMUNS] or [x for x in m if len(x) >= 4] or m
    return max(candidats, key=len)


trimestre = "filing_year=2026&filing_period=second_quarter"
compagnies = json.loads(Path("principal/data/app/aujourdhui.json").read_text(encoding="utf-8"))
liste = [(x["symbole"], x["nom"]) for l in ("hausse", "baisse") for x in compagnies[l]] + [("LMT", "LOCKHEED MARTIN CORP")]
essai = {}
for sym, nom in liste:
    m = mots(nom)
    cle = mot_de_recherche(m)
    url = f"https://lda.gov/api/v1/filings/?{trimestre}&page_size=25&client_name={quote(cle)}"
    pages, vus, gardes, proches = 0, 0, [], set()
    while url and pages < 4:
        r = lire(url)
        pages += 1
        if r is None or r.status_code != 200:
            essai[sym] = {"erreur": r.status_code if r is not None else "pas lu"}
            break
        d = r.json()
        for f in d["results"]:
            vus += 1
            if sorted(mots(f["client"]["name"])) == sorted(m):
                gardes.append({"type": f["filing_type"], "registrant": f["registrant"]["name"], "client": f["client"]["name"],
                               "soi_meme": f["client"].get("client_self_select"), "revenus": f["income"],
                               "depenses": f["expenses"], "poste": f["dt_posted"][:10],
                               "sujets": sorted({a["general_issue_code"] for a in f["lobbying_activities"]})})
            elif m and m[0] in mots(f["client"]["name"]):
                proches.add(f["client"]["name"])
        url = d.get("next")
    essai.setdefault(sym, {}).update({"nom": nom, "mots": m, "recherche": cle, "pages": pages, "reste": bool(url),
                                       "resultats_vus": vus, "gardes": gardes, "noms_proches": sorted(proches)[:10]})
    print(sym, nom, "→", cle, "| pages", pages, "| vus", vus, "| gardés", len(gardes), "| reste", bool(url))

# ---------- C. L'étude sur le lobbying (résumé) ----------
r = lire("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1014264")
if r is not None:
    (SORTIE / "ssrn_chen_parsley_yang.html").write_bytes(r.content[:2_000_000])

(SORTIE / "oge.json").write_text(json.dumps(oge, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "lobbying.json").write_text(json.dumps(essai, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(SORTIE / "journal.json").write_text(json.dumps({"robots": {h: str(v[1]) for h, v in robots.items()}, "requetes": journal},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("requêtes :", len(journal))
