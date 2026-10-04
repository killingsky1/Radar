"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) de la section « Argent » (data/app/argent.json).

Mêmes règles d'accès : robots.txt lu d'abord avec notre identification (401/403 = interdit), au moins 1,5 s entre deux
requêtes au même site ; « Radar projet personnel » et le courriel seulement pour la SEC.
- Dirigeants (formulaire 4) et avis de vente (144) des 30 derniers jours : le dépôt complet est relu à la SEC (fichier
  .txt du dépôt, son XML officiel) ; refaits ici : nombre d'actions, prix moyen, total en dollars (au dollar près), part
  de ses actions (seulement si les lignes se suivent dans un même compte), part des actions de la compagnie (144 : un
  seul titre et un seul total en circulation).
- Élus, contrats et rachats : la ligne = l'info enregistrée (fourchette officielle déjà contrôlée à sa lecture ; chaque
  annonce de rachat est aussi relue à son 8-K par verif_lotH.py).
- Thermomètre (7 jours) refait à partir des lignes ; jamais deux lignes pour la même transaction ; tri par montant.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("argent.txt")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
ROBOTS, DERNIER = {}, {}
ecarts, lignes_sortie = [], []


def dire(t):
    print(t, flush=True)
    lignes_sortie.append(t)


def lire(url):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    ua = UA_SEC if urlparse(url).netloc.endswith("sec.gov") else UA
    if site not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with urllib.request.urlopen(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": ua}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(ua, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = max(1.5, float(ROBOTS[site].crawl_delay(ua) or 0)) - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=120) as r:
        contenu = r.read()
    DERNIER[site] = time.monotonic()
    return contenu.decode("utf-8", "replace")


def xml_officiel(texte, balise):
    """Le bloc <XML> du dépôt dont la racine est `balise`, lu tel quel, puis sans les espaces de noms."""
    for bloc in re.findall(r"<XML>\s*(.*?)\s*</XML>", texte, re.S):
        try:
            r = ET.fromstring(bloc.strip().encode("utf-8"))
        except ET.ParseError:
            continue
        for el in r.iter():
            if isinstance(el.tag, str) and "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]
        if r.tag == balise:
            return r
    raise ValueError(f"pas de <{balise}> dans le dépôt")


def nb(el, chemin):
    t = (el.findtext(chemin) or "").replace(",", "").strip()
    return float(t) if t else None


def txt_du_depot(index):
    """Page d'index officielle -> fichier complet du dépôt (.txt) : une seule requête par dépôt."""
    return index.replace("-index.htm", ".txt")


a = json.loads((racine / "app" / "argent.json").read_text(encoding="utf-8"))
infos = json.loads((racine / "app" / "argent_infos.json").read_text(encoding="utf-8"))
jour = date.fromisoformat(a["jour"])
dire(f"Section Argent du {a['jour']} : {len(a['lignes'])} lignes depuis le {a['depuis']} (dernier jour : {a['dernier_jour']})")

# ---------- Formulaires 4 et 144 : relus à la SEC ----------
relus, ok = 0, 0
for l in a["lignes"]:
    if l["source"] not in ("sec_form4", "sec_form144"):
        continue
    ev = infos[l["id"]]
    texte = lire(txt_du_depot(ev["official_url"]))
    relus += 1
    pb = []
    if l["source"] == "sec_form4":
        doc = xml_officiel(texte, "ownershipDocument")
        code = "P" if l["sens"] > 0 else "S"
        ts = [(nb(t, "transactionAmounts/transactionShares/value"), nb(t, "transactionAmounts/transactionPricePerShare/value"),
               nb(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"))
              for t in doc.findall("nonDerivativeTable/nonDerivativeTransaction")
              if (t.findtext("transactionCoding/transactionCode") or "").strip() == code]
        total_actions = sum(s or 0 for s, _, _ in ts)
        total = sum((s or 0) * (p or 0) for s, p, _ in ts)
        prix = [p for _, p, _ in ts if p]
        multiples = bool(prix) and max(prix) / min(prix) > 2
        if abs(total - l["montant"]) > 1:
            pb.append(f"total {total:.2f} ≠ {l['montant']}")
        if multiples != l["prix_multiples"]:
            pb.append("prix multiples différents")
        if not multiples and (l["actions"] != total_actions or abs((l["prix"] or 0) - round(total / total_actions, 4)) > 0.0001):
            pb.append(f"actions ou prix : {total_actions} à {total / total_actions if total_actions else 0:.4f}")
        # Part de ses actions : seulement si chaque « détenues après » suit le précédent (même compte)
        signe = 1 if code == "P" else -1
        suite = all(x[2] is not None and x[0] for x in ts) and all(
            abs(b[2] - (a_[2] + signe * b[0])) <= 0.5 for a_, b in zip(ts, ts[1:]))
        attendu = None
        if ts and suite:
            avant = ts[0][2] - signe * ts[0][0]
            if code == "P" and avant < 0.5:
                attendu = {"nouvelle": True}
            elif avant >= 0.5:
                attendu = {"pourcentage": round(total_actions / avant * 100, 2)}
        if attendu != l["part"]:
            pb.append(f"part {l['part']} ≠ {attendu}")
    else:
        doc = xml_officiel(texte, "edgarSubmission")
        infos144 = doc.findall("formData/securitiesInformation")
        actions = sum(nb(t, "noOfUnitsSold") or 0 for t in infos144)
        valeur = sum(nb(t, "aggregateMarketValue") or 0 for t in infos144)
        totaux = {nb(t, "noOfUnitsOutstanding") for t in infos144 if nb(t, "noOfUnitsOutstanding")}
        titres = {(t.findtext("securitiesClassTitle") or "").strip().lower() for t in infos144}
        attendu = ({"pourcentage_compagnie": round(actions / next(iter(totaux)) * 100, 3)}
                   if len(totaux) == 1 and len(titres) == 1 and actions else None)
        if abs(valeur - l["montant"]) > 1 or actions != l["actions"]:
            pb.append(f"144 : {actions} actions pour {valeur} ≠ {l['actions']} pour {l['montant']}")
        if attendu != l["part"]:
            pb.append(f"part {l['part']} ≠ {attendu}")
    if pb:
        ecarts.append(f"{l['id']} ({l['symbole']}) : " + " ; ".join(pb))
    else:
        ok += 1
dire(f"Dirigeants et avis 144 : {ok}/{relus} lignes = dépôt officiel relu à la SEC (actions, prix, total, part)")

# ---------- Élus, contrats et rachats : recopie exacte ----------
autres = [l for l in a["lignes"] if l["source"] not in ("sec_form4", "sec_form144")]
for l in autres:
    ev = infos[l["id"]]
    seul = l["famille"] in ("contrats", "rachats")  # un seul montant (contrat signé, plafond de rachat autorisé)
    attendu = (l["montant"] if seul else (l["montant_min"], l["montant_max"]))
    vrai = (ev.get("amount_min") if seul else (ev.get("amount_min"), ev.get("amount_max")))
    if attendu != vrai or l["symbole"] != (ev.get("tickers") or [None])[0]:
        ecarts.append(f"{l['id']} : montant ou symbole ≠ info enregistrée")
n_rachats = sum(1 for l in autres if l["famille"] == "rachats")
dire(f"Élus, cabinet, contrats et rachats : {len(autres)} lignes (dont {n_rachats} rachats) = infos enregistrées "
     f"(fourchettes officielles ; les rachats aussi relus à leur 8-K par verif_lotH.py)")

# ---------- Doublons, tri, période, thermomètre ----------
cles = {}
for l in a["lignes"]:
    ev = infos[l["id"]]
    t = tuple(sorted((x.get("date"), x.get("code"), x.get("actions"), x.get("prix")) for x in ev["data"].get("transactions") or []))
    if l["source"] == "sec_form4":
        cle = (l["symbole"], l["sens"], t)
        if cle in cles:
            ecarts.append(f"même transaction deux fois : {cles[cle]} et {l['id']}")
        cles[cle] = l["id"]
    if ev["published_on"] < a["depuis"] or ev.get("badge") not in ("officiel", "confirme"):
        ecarts.append(f"{l['id']} : hors période ou badge {ev.get('badge')}")
montants = [l["montant"] if l["montant"] is not None else l.get("montant_min") or 0 for l in a["lignes"]]
if montants != sorted(montants, reverse=True):
    ecarts.append("lignes pas triées du plus gros montant au plus petit")
depuis = (jour - timedelta(days=6)).isoformat()
th = {"achats": [0, 0.0], "ventes_libres": [0, 0.0], "ventes_planifiees": [0, 0.0], "intentions": [0, 0.0]}
for l in a["lignes"]:
    if l["publie"] < depuis:
        continue
    cle = ("achats" if l["sens"] > 0 else "ventes_planifiees" if l["plan"] else "ventes_libres") if l["famille"] == "dirigeants" \
        else ("intentions" if l["famille"] == "intentions" else None)
    if cle:
        th[cle][0] += 1
        th[cle][1] += l["montant"]
for k, (n, m) in th.items():
    if a["thermometre"][k]["nombre"] != n or abs(a["thermometre"][k]["montant"] - m) > 1:
        ecarts.append(f"thermomètre {k} : publié {a['thermometre'][k]} ≠ refait {n} / {m:.2f}")
dire(f"Thermomètre (depuis le {depuis}) : achats {th['achats'][0]} pour {th['achats'][1] / 1e6:.1f} M$ · ventes décidées "
     f"sur le moment {th['ventes_libres'][0]} pour {th['ventes_libres'][1] / 1e6:.1f} M$ · ventes planifiées "
     f"{th['ventes_planifiees'][0]} pour {th['ventes_planifiees'][1] / 1e6:.1f} M$")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque ligne relue à son dépôt officiel.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(lignes_sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
