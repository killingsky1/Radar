"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) des contrats fédéraux de 10 M$ et plus (lot 3c).

Relit EN ENTIER, par un autre chemin que le robot (tri par numéro interne « _id » croissant ; le robot lit en
décroissant), chaque trimestre suivi par le robot sur l'API officielle du portail du gouvernement ouvert (robots.txt
lu d'abord ; son Crawl-delay de 20 secondes est respecté) et compare à l'état du robot (data/contrats/trimestres.json) :
- le plus haut numéro noté par le robot existe, et chaque ligne jusqu'à lui a été comptée ;
- les contrats de 10 M$ et plus (nouveau contrat : sa valeur ; modification : la hausse) jusqu'à ce numéro = ceux
  notés par le robot, ni plus ni moins ;
- les lignes ajoutées depuis la lecture du robot : combien, dont combien de 10 M$ et plus (prochaines infos) ;
- chaque info publiée (s'il y en a) : la ligne officielle (fournisseur, montant) et son lien public ;
- 3 liens publics de contrats (fiche « record » du site de recherche) : la page montre le bon contrat.
Chaque ligne du résultat est écrite tout de suite (un arrêt en cours de route garde ce qui est fait).
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlencode, urlparse

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("contrats.txt")
UA = "Radar projet personnel"
API = "https://open.canada.ca/data/api/action/datastore_search"
RESSOURCE = "fac950c0-00d5-4ec1-a4d3-9cbebf98a305"
CHAMPS = "_id,owner_org,reference_number,vendor_name,contract_value,amendment_value,instrument_type,reporting_period"
FICHE = "https://rechercher.ouvert.canada.ca/contrats/record/"
SEUIL = 10_000_000
ROBOTS, DERNIER = {}, {}
ecarts = []
SORTIE.write_text("", encoding="utf-8")


def dire(t):
    print(t, flush=True)
    with SORTIE.open("a", encoding="utf-8") as f:
        f.write(t + "\n")


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
        DERNIER[site] = time.monotonic()  # robots.txt compte comme une requête
        dire(f"robots.txt de {site} : Crawl-delay {rp.crawl_delay(UA)}")
    if not ROBOTS[site].can_fetch(UA, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    delai = max(1.5, float(ROBOTS[site].crawl_delay(UA) or 0))
    attente = delai - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    finally:
        DERNIER[site] = time.monotonic()


def somme(x):
    """La nouvelle somme engagée : la hausse pour une modification (A), sinon la valeur du contrat."""
    try:
        return float(x["amendment_value"] if x.get("instrument_type") == "A" else x["contract_value"])
    except (TypeError, ValueError, KeyError):
        return None


def cle(x):
    return f"{x['owner_org']}:{x['reference_number']}"


def plat(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


etat = json.loads((racine / "contrats" / "trimestres.json").read_text(encoding="utf-8"))
sources = {s["id"]: s for s in json.loads((racine / "app" / "sources.json").read_text(encoding="utf-8"))}
s = sources.get("contrats_ca_10k", {})
dire(f"Source dans l'app : « {s.get('nom')} » · {s.get('libelle')} · lue le {s.get('dernier_succes')} {s.get('explication') or ''}")
evs = []
for f in sorted((racine / "evenements").glob("*.jsonl"))[-3:]:
    evs += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if '"contrats_ca_10k"' in l]
evs = [e for e in evs if e["source"] == "contrats_ca_10k"]
dire(f"Trimestres suivis par le robot : {sorted(etat)} · infos publiées : {len(evs)}")

officiel = {}
for periode, e in sorted(etat.items()):
    lignes, page, total = [], 0, None
    while True:
        r = json.loads(lire(API + "?" + urlencode({
            "resource_id": RESSOURCE, "filters": json.dumps({"reporting_period": periode}), "sort": "_id asc",
            "limit": 1000, "offset": page * 1000, "fields": CHAMPS})))
        if not r.get("success"):
            raise SystemExit(f"API en erreur pour {periode}")
        recs = r["result"]["records"]
        total = r["result"].get("total", total)
        lignes += recs
        if len(recs) < 1000:
            break
        page += 1
    ids = [x["_id"] for x in lignes]
    if len(ids) != len(set(ids)):
        ecarts.append(f"{periode} : la lecture complète a vu {len(ids) - len(set(ids))} numéro(s) en double")
    officiel[periode] = lignes
    haut = e["max_id"]
    jusqu = [x for x in lignes if x["_id"] <= haut]
    apres = [x for x in lignes if x["_id"] > haut]
    grands = {cle(x) for x in jusqu if (somme(x) or 0) >= SEUIL}
    grands_apres = [x for x in apres if (somme(x) or 0) >= SEUIL]
    vus = set(e["vus"])
    present = haut == 0 and not jusqu or haut in set(ids)
    dire(f"{periode} : {len(lignes)} lignes officielles en {page + 1} page(s) (total annoncé : {total}) · robot (lu le "
         f"{e.get('lu_le')}, depuis le {e.get('depuis')}, complet : {e.get('complet')}) : plus haut numéro {haut} "
         f"({'présent' if present else 'ABSENT'}), {e.get('lignes_lues')} lignes lues, {len(vus)} contrats de 10 M$ et "
         f"plus notés · officiel jusqu'à ce numéro : {len(jusqu)} lignes, {len(grands)} de 10 M$ et plus · ajoutées "
         f"depuis : {len(apres)} ligne(s), dont {len(grands_apres)} de 10 M$ et plus")
    if not e.get("complet"):
        ecarts.append(f"{periode} : lecture du robot incomplète")
    if not present:
        ecarts.append(f"{periode} : le plus haut numéro noté par le robot ({haut}) n'existe pas dans le trimestre")
    if len(jusqu) != e.get("lignes_lues"):
        ecarts.append(f"{periode} : {len(jusqu)} lignes officielles jusqu'au numéro {haut}, le robot en a compté "
                      f"{e.get('lignes_lues')}")
    if grands != vus:
        ecarts.append(f"{periode} : contrats de 10 M$ et plus différents · manquent au robot : {sorted(grands - vus)[:5]}"
                      f" · en trop : {sorted(vus - grands)[:5]}")
    for x in grands_apres[:5]:
        dire(f"   ajouté depuis : {cle(x)} · {x['vendor_name']} · {x['instrument_type']} · {somme(x):,.0f} $")

# Les infos publiées : la ligne officielle et le lien public
par_cle = {cle(x): x for ls in officiel.values() for x in ls}
for ev in evs:
    x = par_cle.get(ev["official_id"])
    lien = FICHE + ev["official_id"].replace(":", ",", 1)
    if x is None or ev["amount_min"] != somme(x) or ev["official_url"] != lien \
            or " ".join(x["vendor_name"].split()) not in ev["title"]:
        ecarts.append(f"info {ev['official_id']} : ligne officielle {x and (x['vendor_name'], somme(x))} ≠ publiée "
                      f"({ev['title']}, {ev['amount_min']}, {ev['official_url']})")
dire(f"Infos publiées vérifiées à la ligne officielle : {len(evs)}")

# 3 liens publics (fiche « record ») de contrats de 10 M$ et plus
grands = sorted((x for ls in officiel.values() for x in ls if (somme(x) or 0) >= SEUIL), key=lambda x: -x["_id"])
for x in grands[:3]:
    lien = FICHE + f"{x['owner_org']},{x['reference_number']}"
    page = lire(lien).decode("utf-8", "replace")
    t = plat(page[page.find("<main"):page.find("</main>")] if "<main" in page else page)
    bon = " ".join(x["vendor_name"].split()) in t and x["reporting_period"] in t
    dire(f"Lien public {lien} : fournisseur « {x['vendor_name']} » et période {x['reporting_period']} sur la page : "
         + ("OUI" if bon else "NON"))
    if not bon:
        ecarts.append(f"la fiche publique {lien} ne montre pas ce contrat")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : l'état du robot = la relecture complète des trimestres suivis.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
sys.exit(1 if ecarts else 0)
