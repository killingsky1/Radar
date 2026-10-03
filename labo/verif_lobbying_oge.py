"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lobbying et des rapports 278-T de l'OGE publiés.

OGE : relit l'adresse de données publique (les 2 filtres de la page officielle). Chaque rapport publié doit y être avec
un lien direct (sans formulaire 201), même nom, même date, poste permis ; chaque rapport à lien direct des 90 derniers
jours (avant le passage du robot) doit être publié ; chaque lien PDF doit répondre (requête HEAD).
Lobbying : relit LDA.gov (4,5 s entre deux requêtes) avec la recherche du robot ET une 2e recherche (1er mot du nom) ;
rapports au nom exact et total recalculés à la main (guide du LDA : dépenses de la compagnie si elle a ses propres
lobbyistes, sinon la somme des firmes). Les noms de clients proches non comptés sont listés pour relecture.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

racine, sortie = Path(sys.argv[1]), Path(sys.argv[2])
UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
ATTENTE = {"lda.gov": 4.5}
robots, dernier, lignes, ecarts = {}, {}, [], []


def dire(t):
    print(t)
    lignes.append(t)


def lire(url, methode="GET"):
    hote = urlparse(url).hostname
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
        if r.status_code in (401, 403) or r.status_code >= 500:
            rp.disallow_all = True
        elif r.status_code >= 400:
            rp.allow_all = True
        else:
            rp.parse(r.text.splitlines())
        robots[hote] = rp
        dernier[hote] = time.monotonic()
    if not robots[hote].can_fetch(UA, url):
        raise SystemExit(f"robots.txt interdit {url}")
    reste = ATTENTE.get(hote, 1.5) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)
    r = requests.request(methode, url, headers=H, timeout=(20, 90))
    dernier[hote] = time.monotonic()
    return r


# ---------- OGE ----------
evs = {}
for f in sorted((racine / "evenements").glob("*.jsonl")):
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            e = json.loads(l)
            if e["source"] == "oge_278t":
                evs[e["id"]] = e
etat = json.loads((racine / "etat_sources.json").read_text(encoding="utf-8")).get("oge_278t", {})
passage = (etat.get("dernier_succes") or "")[:10]
API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest?draw=1&order%5B0%5D%5Bcolumn%5D=0&order%5B0%5D%5Bdir%5D=desc"
for i, c in enumerate(("docDate", "title", "type", "name", "agency", "level")):
    API += f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true&columns%5B{i}%5D%5Borderable%5D=true"
API += "&search%5Bvalue%5D=&columns%5B2%5D%5Bsearch%5D%5Bvalue%5D=Transaction"
directs, exigent_201 = {}, set()
for filtre in ("&columns%5B5%5D%5Bsearch%5D%5Bvalue%5D=Level", "&columns%5B1%5D%5Bsearch%5D%5Bvalue%5D=President"):
    for r in lire(API + filtre + "&start=0&length=100").json()["data"]:
        m = re.search(r"href='(https://extapps2\.oge\.gov/201/Presiden\.nsf/PAS\+Index/[0-9A-F]{32}/\$FILE/[^']+\.pdf)'>278 Transaction</a>", r["type"])
        if m:
            directs[m.group(1).replace("&amp;", "&")] = r
        else:
            exigent_201.add(r["name"])
permis = lambda r: r["title"] in ("President", "Vice President") or r["level"] in ("Level I", "Level II")  # noqa: E731
dire(f"OGE : {len(evs)} rapports publiés · passage du robot : {passage or '?'} · {len(directs)} lignes à lien direct relues")
for e in evs.values():
    r = directs.get(e["official_url"])
    if r is None:
        ecarts.append(f"OGE : {e['title']} : lien absent des lignes à lien direct de l'OGE")
        continue
    famille, _, prenoms = r["name"].partition(",")
    nom = " ".join(f"{prenoms.strip()} {famille.strip()}".split())
    if not (e["title"].startswith(nom + " (") and e["published_on"] == r["docDate"][:10] and permis(r)):
        ecarts.append(f"OGE : {e['title']} ≠ ligne officielle {r['name']} / {r['title']} / {r['level']} / {r['docDate']}")
    if e["badge"] != "officiel":
        ecarts.append(f"OGE : {e['title']} : badge {e['badge']}")
limite = (date.fromisoformat(passage) - timedelta(days=90)).isoformat() if passage else "9999"
publies = {e["official_url"] for e in evs.values()}
manquants = [u for u, r in directs.items() if permis(r) and limite <= r["docDate"][:10] < passage and u not in publies]
for u in manquants:
    ecarts.append(f"OGE : rapport à lien direct non publié : {directs[u]['name']} {directs[u]['docDate']}")
pdf_ok = 0
for u in sorted(publies):
    h = lire(u, "HEAD")
    if h.status_code == 200 and "pdf" in (h.headers.get("content-type") or ""):
        pdf_ok += 1
    else:
        ecarts.append(f"OGE : lien PDF {u} : HTTP {h.status_code} {h.headers.get('content-type')}")
dire(f"OGE : rapports manquants : {len(manquants)} · liens PDF qui répondent : {pdf_ok}/{len(publies)}")

# ---------- Lobbying ----------
lob = json.loads((racine / "app" / "lobbying.json").read_text(encoding="utf-8"))
SUF = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LLC", "LP", "LLP", "PLC", "SA",
       "NV", "AG", "SE", "THE"}


def mots(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().upper().replace("&", " AND ")
    m = re.findall(r"[A-Z0-9]+", n.replace("'", ""))
    while m and m[-1] in SUF:
        m.pop()
    while m and m[0] == "THE":
        m.pop(0)
    return m


jour = date.fromisoformat(passage) if passage else date.today()
a, t = jour.year, (jour.month - 1) // 3 + 1
while True:  # dernier trimestre dont la date limite (le 20 du mois suivant) est passée
    t -= 1
    if t == 0:
        a, t = a - 1, 4
    if jour > date(a + (t == 4), (t * 3) % 12 + 1, 20):
        break
if (lob["trimestre"]["annee"], lob["trimestre"]["numero"]) != (a, t):
    ecarts.append(f"lobbying : trimestre publié {lob['trimestre']} ≠ recalculé {a}-T{t}")
if lob.get("avertissement") != ("Senate Office of Public Records cannot vouch for the data or analyses derived from "
                                "these data after the data have been retrieved from LDA.gov."):
    ecarts.append("lobbying : phrase obligatoire du Sénat absente ou modifiée")
periode = {1: "first_quarter", 2: "second_quarter", 3: "third_quarter", 4: "fourth_quarter"}[t]
TYPES = {f"Q{t}", f"Q{t}Y", f"{t}T", f"{t}TY", f"{t}A", f"{t}AY", f"{t}@", f"{t}@Y"}
dire(f"Lobbying : {len(lob['par_symbole'])} compagnies · {lob['trimestre']['libelle']}")
for sym, x in sorted(lob["par_symbole"].items()):
    m = mots(x["nom"])
    recherches = [x["recherche"]] + ([m[0]] if m and len(m[0]) >= 4 and m[0] != x["recherche"] else [])
    resultats, proches = {}, set()
    for mot in recherches:
        url = f"https://lda.gov/api/v1/filings/?filing_year={a}&filing_period={periode}&page_size=25&client_name={quote(mot)}"
        pages = 0
        while url and pages < 6:
            d = lire(url).json()
            pages += 1
            for f in d["results"]:
                if sorted(mots(f["client"]["name"])) == sorted(m):
                    resultats[f["filing_uuid"]] = f
                elif len(set(mots(f["client"]["name"])) & set(m)) >= max(1, min(2, len(m))):
                    proches.add(f["client"]["name"])
            url = d.get("next")
    derniers = {}
    for f in sorted((f for f in resultats.values() if f["filing_type"] in TYPES), key=lambda f: (f["dt_posted"], f["filing_uuid"])):
        derniers[(f["registrant"]["id"], f["client"]["id"])] = f
    actifs = [f for f in derniers.values() if not f["filing_type"].endswith("Y")]
    soi = [f for f in actifs if f["client"].get("client_self_select") is True
           or sorted(mots(f["registrant"]["name"])) == sorted(mots(f["client"]["name"]))]
    montant = lambda f: float(f["expenses"] if f["expenses"] is not None else (f["income"] or 0))  # noqa: E731
    total = sum(map(montant, soi)) if soi else (sum(montant(f) for f in actifs) if actifs else None)
    publies_uuid = {r["uuid"] for r in x["rapports"]}
    if x["complet"] and (publies_uuid != {f["filing_uuid"] for f in derniers.values()} or x["total"] != total):
        ecarts.append(f"lobbying {sym} : publié {x['total']} ({len(publies_uuid)} rapports) ≠ recalculé {total} "
                      f"({len(derniers)} rapports)")
    dire(f"{sym} {x['nom']} : recherches {recherches} · rapports au nom exact {len(derniers)} · total {total} · "
         f"publié {x['total']} · noms proches non comptés : {sorted(proches)[:6]}")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : OGE et lobbying = sources officielles relues.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
sortie.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
