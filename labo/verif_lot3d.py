"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot 3d, livraison 1, publié par le robot.

Mêmes règles : robots.txt lu d'abord avec notre identification (401/403 = interdit), Crawl-delay respecté, sinon 1,5 s
par site ; « Radar projet personnel ».
- Trésor : chaque adjudication relue dans le fichier XML OFFICIEL du résultat (un autre document que l'API JSON lue par
  le robot) : montant, taux, demande/offre, les 3 catégories d'acheteurs, CUSIP, date, heure de publication du jour ;
  la moyenne « des précédentes » recalculée depuis les XML officiels de chacune. État mensuel : 1re lecture silencieuse
  (aucune info) et le mois noté = le dernier mois publié selon l'API (requête différente).
- Douane : chaque message relu sur sa PAGE officielle (pas le flux RSS lu par le robot) : numéro, titre, date et heure
  d'envoi, proclamations et numéros du tarif cités, extrait présent mot pour mot.
- Les 6 sources laissées de côté : statut et raison dans le fichier des sources de l'app.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lot3d.txt")
UA = "Radar projet personnel"
NY = ZoneInfo("America/New_York")
RESULTATS = "https://fiscaldata.treasury.gov/static-data/published-reports/auctions-query/results/"
MTS = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_1"
ECARTEES = ("war_contrats", "gao_contestations", "nbim", "communiques", "prix_yahoo", "sec_ftd")
ROBOTS, DERNIER = {}, {}
ecarts, lignes = [], []


def dire(t):
    print(t, flush=True)
    lignes.append(t)


def lire(url):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if site not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with urllib.request.urlopen(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": UA}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(UA, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = max(1.5, float(ROBOTS[site].crawl_delay(UA) or 0)) - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
        contenu = r.read()
    DERNIER[site] = time.monotonic()
    return contenu


def xml_resultat(document_pdf):
    racine_xml = ET.fromstring(lire(RESULTATS + document_pdf[:-4] + ".xml"))
    return {e.tag: (e.text or "").strip() for e in racine_xml.iter()}


def num(x):
    return float(x) if x not in (None, "") else None


# ---------- Les infos publiées ----------
evs = []
for f in sorted((racine / "evenements").glob("*.jsonl"))[-3:]:
    for ligne in f.read_text(encoding="utf-8").splitlines():
        if '"tresor"' in ligne or '"tarifs"' in ligne:
            d = json.loads(ligne)
            if d["source"] in ("tresor", "tarifs"):
                evs.append(d)
adj = [e for e in evs if e["source"] == "tresor" and e["kind"] == "adjudication"]
mois = [e for e in evs if e["source"] == "tresor" and e["kind"] == "solde_mensuel"]
csms = [e for e in evs if e["source"] == "tarifs"]
dire(f"Infos publiées : adjudications {len(adj)}, soldes mensuels {len(mois)}, messages de la douane {len(csms)}")
if not adj or not csms:
    ecarts.append("aucune adjudication ou aucun message de la douane publié")

# ---------- Trésor : chaque adjudication relue dans le XML officiel ----------
ok = 0
for e in adj:
    d = e["data"]
    x = xml_resultat(d["document"])
    frn = x.get("FloatingRate") == "Y"
    taux = num(x.get("HighDiscountMargin") if frn else x.get("HighYield"))
    acceptees = {"indirect_bidder": num(x.get("IndirectBidderAccepted")), "direct_bidder": num(x.get("DirectBidderAccepted")),
                 "primary_dealer": num(x.get("PrimaryDealerAccepted"))}
    pb = []
    if x.get("CUSIP") != d["cusip"] or x.get("AuctionDate") != e["occurred_on"] or e["published_on"] != e["occurred_on"]:
        pb.append(f"CUSIP ou date ({x.get('CUSIP')}, {x.get('AuctionDate')})")
    if not x.get("ReleaseTime"):
        pb.append("heure de publication absente")
    if abs(num(x["OfferingAmount"]) * 1e9 - e["amount_min"]) > 1:
        pb.append(f"montant {x['OfferingAmount']} G$ ≠ {e['amount_min']}")
    if taux is None or abs(taux - d["taux"]) > 0.0005:
        pb.append(f"taux {taux} ≠ {d['taux']}")
    if abs(num(x["BidToCoverRatio"]) - d["demande_offre"]) > 0.005:
        pb.append(f"demande/offre {x['BidToCoverRatio']} ≠ {d['demande_offre']}")
    if acceptees != d["acceptees"] or num(x["CompetitiveAccepted"]) != d["offres_competitives_acceptees"]:
        pb.append(f"acheteurs {acceptees} ≠ {d['acceptees']}")
    # La moyenne des précédentes, recalculée depuis leurs propres XML officiels
    vals = []
    for p in d["precedentes"]:
        y = xml_resultat(p["document"])
        if y.get("CUSIP") != p["cusip"] or y.get("AuctionDate") != p["adjudication"]:
            pb.append(f"précédente {p['adjudication']} : CUSIP ou date ≠ XML")
        vals.append((num(y["BidToCoverRatio"]), num(y["IndirectBidderAccepted"]) / num(y["CompetitiveAccepted"]) * 100))
    if vals:
        btc, ind = sum(v[0] for v in vals) / len(vals), sum(v[1] for v in vals) / len(vals)
        if abs(btc - d["demande_offre_moyenne"]) > 0.005 or abs(ind - d["part_indirecte_moyenne"]) > 0.05:
            pb.append(f"moyennes recalculées {btc:.3f} / {ind:.2f} % ≠ {d['demande_offre_moyenne']:.3f} / "
                      f"{d['part_indirecte_moyenne']:.2f} %")
    if pb:
        ecarts.append(f"adjudication {e['official_id']} : " + " ; ".join(pb))
    else:
        ok += 1
    dire(f"Trésor {e['official_id']} : « {e['title']} » · XML officiel publié à {x.get('ReleaseTime')} (heure de "
         f"l'Est) · {len(vals)} précédentes relues · {'conforme' if not pb else 'ÉCART'}")
dire(f"Trésor : {ok}/{len(adj)} adjudications = résultat XML officiel (montant, taux, demande/offre, acheteurs, "
     "moyennes des précédentes)")

# ---------- Trésor : état mensuel (1re lecture silencieuse) ----------
etat = json.loads((racine / "tresor" / "etat.json").read_text(encoding="utf-8"))
dernier = json.loads(lire(MTS + "?fields=record_date&sort=-record_date&page[size]=1"))["data"][0]["record_date"]
dire(f"État mensuel : mois noté par le robot {etat.get('etat_mensuel')} · dernier mois publié selon l'API {dernier} · "
     f"infos de solde mensuel publiées : {len(mois)}")
if etat.get("etat_mensuel") != dernier:
    ecarts.append(f"état mensuel : le robot a noté {etat.get('etat_mensuel')}, l'API dit {dernier}")

# ---------- Douane : chaque message relu sur sa page officielle ----------
ok = 0
for e in csms:
    d = e["data"]
    page = lire(e["official_url"]).decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", page)
    page = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", page)
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", "", page)).replace("\xa0", " ").split())
    envoi = re.search(r"sent this bulletin at (\d\d)/(\d\d)/(\d{4}) (\d\d):(\d\d) (AM|PM)", t)
    pb = []
    if f"CSMS # {d['numero']} - {d['titre_officiel']}" not in t:
        pb.append("numéro ou titre absent de la page")
    if not envoi:
        pb.append("date d'envoi absente de la page")
    else:
        h = int(envoi.group(4)) % 12 + (12 if envoi.group(6) == "PM" else 0)
        page_ny = f"{envoi.group(3)}-{envoi.group(1)}-{envoi.group(2)} {h:02d}:{envoi.group(5)}"
        robot_ny = datetime.fromisoformat(d["envoye_le"]).astimezone(NY).strftime("%Y-%m-%d %H:%M")
        if page_ny != robot_ny or e["published_on"] != page_ny[:10]:
            pb.append(f"envoi {page_ny} ≠ {robot_ny}")
    procs = []
    for m in re.finditer(r"\bProc(?:lamation)?s?\.?\s+((?:No\.\s*)?\d{5}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)\d{5})*)", t):
        procs += [n for n in re.findall(r"\d{5}", m.group(1)) if n not in procs]
    if procs != d["proclamations"]:
        pb.append(f"proclamations {procs} ≠ {d['proclamations']}")
    if sorted(set(re.findall(r"\b9903\.\d\d\.\d\d\b", t))) != d["codes_9903"]:
        pb.append("numéros du tarif ≠ page")
    if d.get("extrait") and d["extrait"].replace(" […]", "")[:150] not in t:
        pb.append("extrait absent mot pour mot")
    if pb:
        ecarts.append(f"douane {e['official_id']} : " + " ; ".join(pb))
    else:
        ok += 1
    dire(f"Douane {e['official_id']} : « {e['title'][:110]} » · {'conforme' if not pb else 'ÉCART'}")
dire(f"Douane : {ok}/{len(csms)} messages = page officielle (numéro, titre, envoi, proclamations, numéros du tarif, extrait)")

# ---------- Les 6 sources laissées de côté ----------
sources = {s["id"]: s for s in json.loads((racine / "app" / "sources.json").read_text(encoding="utf-8"))}
for s in ECARTEES:
    x = sources.get(s, {})
    dire(f"Source « {x.get('nom')} » : {x.get('libelle')} · {x.get('explication')}")
    if x.get("statut") != "ecartee" or not x.get("explication"):
        ecarts.append(f"source {s} : statut {x.get('statut')} (attendu : laissée de côté, avec la raison)")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque info relue à sa source officielle.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
