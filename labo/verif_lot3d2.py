"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot 3d, livraison 2.

Mêmes règles : robots.txt lu d'abord avec notre identification (401/403 = interdit), Crawl-delay respecté, sinon 1,5 s
par site ; « Radar projet personnel », courriel seulement pour la SEC.
- USAspending : la liste des contrats notés par le robot (1re lecture silencieuse) = une relecture de l'API triée
  autrement (par date de signature) ; chaque info publiée (s'il y en a) = sa fiche officielle (montant, fournisseur,
  date de signature, ministère, lien public).
- Participations du gouvernement : chaque info publiée : chaque extrait présent mot pour mot dans le document officiel
  relu ; les points de l'en-tête officiel ; le symbole = fichier officiel des symboles de la SEC pour ce CIK.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import acces  # labo/acces.py : un site qui ne répond pas = « non vérifiable », jamais un plantage

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lot3d2.txt")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
API = "https://api.usaspending.gov/api/v2/"
POINTS = {"entry into a material definitive agreement": "1.01", "unregistered sales of equity securities": "3.02",
          "other events": "8.01"}
ROBOTS, DERNIER = {}, {}
ecarts, lignes = [], []
acces.installer(lignes, SORTIE)


def dire(t):
    print(t, flush=True)
    lignes.append(t)


def lire(url, corps=None):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    ua = UA_SEC if urlparse(url).netloc.endswith("sec.gov") else UA
    if site not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with acces.ouvrir(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": ua}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(ua, url):
        raise acces.NonVerifiable(f"robots.txt ne permet pas {url}")
    attente = max(1.5, float(ROBOTS[site].crawl_delay(ua) or 0)) - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Content-Type": "application/json"},
                                 data=json.dumps(corps).encode() if corps is not None else None)
    with acces.ouvrir(req, timeout=120) as r:
        contenu = r.read()
    DERNIER[site] = time.monotonic()
    return contenu


def texte(contenu):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", contenu.decode("utf-8", "replace"))
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", t)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").split())


evs = []
for f in sorted((racine / "evenements").glob("*.jsonl"))[-3:]:
    for ligne in f.read_text(encoding="utf-8").splitlines():
        if '"usaspending"' in ligne or '"participations_gouv"' in ligne:
            d = json.loads(ligne)
            if d["source"] in ("usaspending", "participations_gouv"):
                evs.append(d)
contrats = [e for e in evs if e["source"] == "usaspending"]
parts = [e for e in evs if e["source"] == "participations_gouv"]
dire(f"Infos publiées : contrats USAspending {len(contrats)}, participations du gouvernement {len(parts)}")
etat_sources = json.loads((racine / "etat_sources.json").read_text(encoding="utf-8"))
for s in ("usaspending", "participations_gouv"):
    x = etat_sources.get(s, {})
    dire(f"État du robot, {s} : dernière lecture réussie {x.get('dernier_succes')}, erreur : {x.get('derniere_erreur')}")
    if not x.get("dernier_succes") or x.get("derniere_erreur"):
        ecarts.append(f"{s} : pas de lecture réussie, ou une erreur")

# ---------- USAspending : relecture indépendante (autre tri) ----------
with acces.section("USAspending (contrats relus à l'API)"):
    etat = json.loads((racine / "usaspending" / "vus.json").read_text(encoding="utf-8"))
    lu_le = date.fromisoformat(etat["lu_le"])
    debut = (lu_le - timedelta(days=150)).isoformat()
    ids, page = {}, 1
    while page <= 12:
        r = json.loads(lire(API + "search/spending_by_award/", {
            "filters": {"award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": debut, "end_date": lu_le.isoformat(), "date_type": "new_awards_only"}],
                        "award_amounts": [{"lower_bound": 100000000}]},
            "fields": ["Award ID", "Award Amount", "Base Obligation Date", "generated_internal_id"],
            "sort": "Base Obligation Date", "order": "desc", "limit": 100, "page": page}))
        for x in r.get("results") or []:
            ids[x["generated_internal_id"]] = x.get("Base Obligation Date")
        if not (r.get("page_metadata") or {}).get("hasNext"):
            break
        page += 1
    robot = set(etat["vus"])
    dire(f"USAspending : le robot a noté {len(robot)} contrats (lu le {etat['lu_le']}, depuis le {etat['depuis']}) ; relecture "
         f"triée par date de signature : {len(ids)} contrats · en commun {len(robot & set(ids))} · seulement chez le robot "
         f"{len(robot - set(ids))} · seulement dans la relecture {len(set(ids) - robot)}")
    if robot - set(ids):
        ecarts.append(f"USAspending : {len(robot - set(ids))} contrat(s) noté(s) par le robot absent(s) de la relecture : "
                      f"{sorted(robot - set(ids))[:3]}")
    for e in contrats:
        d = e["data"]
        f = json.loads(lire(API + f"awards/{e['official_id']}/"))
        pb = []
        if abs((f.get("total_obligation") or 0) - (e["amount_min"] or 0)) > 1:
            pb.append(f"montant {f.get('total_obligation')} ≠ {e['amount_min']}")
        if " ".join(((f.get("recipient") or {}).get("recipient_name") or "").split()) != d["fournisseur"]:
            pb.append("fournisseur ≠ fiche")
        if f.get("date_signed") != e["occurred_on"]:
            pb.append(f"signé le {f.get('date_signed')} ≠ {e['occurred_on']}")
        if ((f.get("awarding_agency") or {}).get("toptier_agency") or {}).get("name") != d["agence"]:
            pb.append("ministère ≠ fiche")
        if e["official_url"] != f"https://www.usaspending.gov/award/{e['official_id']}":
            pb.append("lien public")
        if pb:
            ecarts.append(f"contrat {e['official_id']} : " + " ; ".join(pb))
        dire(f"USAspending {e['official_id']} : « {e['title']} » · {'conforme' if not pb else 'ÉCART'}")

# ---------- Participations : chaque extrait relu dans son document officiel ----------
with acces.section('Participations (documents relus à la SEC)'):
    symboles = json.loads(lire("https://www.sec.gov/files/company_tickers_exchange.json"))
    par_cik = {}
    for cik, nom, symbole, bourse in symboles["data"]:
        par_cik.setdefault(str(cik), []).append(symbole)
    for e in parts:
        d, pb = e["data"], []
        entete = html.unescape(lire(e["official_url"].replace("-index.htm", "-index-headers.html")).decode("utf-8", "replace"))
        points = sorted({POINTS[p.strip().lower()] for p in re.findall(r"ITEM INFORMATION:[ \t]*([^\n<]+)", entete)
                         if p.strip().lower() in POINTS})  # une ligne par point dans l'en-tête brut
        if points != sorted(d["points"]):
            pb.append(f"points de l'en-tête {points} ≠ {d['points']}")
        if re.search(r"\([^()]*\(", e["title"]):
            pb.append("titre avec des parenthèses dans des parenthèses")
        if not set(e["tickers"]) & set(par_cik.get(str(int(d["cik"])), [])):
            pb.append(f"symbole {e['tickers']} ≠ fichier de la SEC pour le CIK {d['cik']}")
        for doc in d["documents"]:
            t = texte(lire(doc["url"]))
            for x in doc["extraits"]:
                coeur = x.removeprefix("… ").removesuffix(" …")
                i = t.find(coeur)
                if i < 0:
                    pb.append(f"extrait absent du document {doc['url'].rsplit('/', 1)[-1]} : « {coeur[:80]}… »")
                elif (i > 0 and t[i - 1] != " ") or (i + len(coeur) < len(t) and t[i + len(coeur)] != " "):
                    pb.append(f"extrait coupé au milieu d'un mot : « {coeur[:40]}… {coeur[-25:]} »")
        if pb:
            ecarts.append(f"participation {e['official_id']} : " + " ; ".join(pb))
        dire(f"Participation {e['official_id']} : « {e['title'][:120]} » · {'conforme' if not pb else 'ÉCART'}")

dire("\n".join(ecarts) if ecarts else ("AUCUN ÉCART dans ce qui a pu être relu." if acces.NON_VERIFIABLES
                                       else "AUCUN ÉCART : chaque info relue à sa source officielle."))
for ligne in acces.lignes_non_verifiables():
    dire(ligne)
dire(acces.verdict(ecarts))
SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
