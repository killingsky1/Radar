"""Recalcul INDÉPENDANT du score (n'importe rien du robot) à partir des règles publiées dans l'app.

Entrées : les infos du robot (data/evenements/*.jsonl, 3 derniers mois) et le score publié (data/app/aujourdhui.json).
Vérifie : mêmes compagnies dans le même ordre, mêmes points (±0,01), mêmes infos comptées, bonus, contexte,
et que chaque info citée existe, est « officiel »/« confirmé », et pointe vers un domaine officiel.
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

racine = Path(sys.argv[1])
pub = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
fichiers = sorted((racine / "evenements").glob("*.jsonl"))[-3:]
infos = [json.loads(l) for f in fichiers for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
infos = [e for e in infos if not e.get("data", {}).get("meme_acte_que")]

# Règles écrites à la main d'après la page « Comment le score est calculé »
POINTS = {"achat_dirigeant": 2, "vente_dirigeant": -0.5, "activiste_13d": 5, "fonds_13f": 1, "achat_elu": 1,
          "achat_chef": 2, "vente_chef": -1, "fda": 0.5,
          "rappel": -0.5, "sec_suspension": -5, "sec_procedure": -2, "faillite": -5, "etats_financiers": -5}
FAMILLE = {"achat_dirigeant": "inities", "vente_dirigeant": "inities", "activiste_13d": "activistes", "fonds_13f": "fonds",
           "achat_elu": "elus", "achat_chef": "elus", "vente_chef": "elus", "fda": "fda", "rappel": "rappels",
           "sec_suspension": "sec", "sec_procedure": "sec", "faillite": "compagnie", "etats_financiers": "compagnie"}
DOMAINES = {"sec.gov", "accessdata.fda.gov", "fda.gov", "nhtsa.gov", "house.gov", "senate.gov", "ftc.gov",
            "transportation.gov", "justice.gov", "efdsearch.senate.gov"}


def principal(titre):
    t = " " + titre.upper().replace("-", " ").replace(",", " ").replace("&", " ").replace("(", " ").replace(")", " ") + " "
    for vice in (" VICE PRESIDENT", " VICE CHAIRMAN", " VICE CHAIRPERSON", " VICE CHAIRWOMAN", " VICE CHAIR"):
        t = t.replace(vice, " ")
    mots = t.split()
    return (any(m in ("CEO", "CFO", "PEO", "PFO", "COB") for m in mots) or "CHIEF EXECUTIVE" in t
            or "CHIEF FINANCIAL" in t or any(m.startswith("CHAIR") for m in mots))


# Achats que le déposant dit faits lors d'une émission ou hors bourse : (symbole, date, prix) de chaque ligne marquée
EMISSIONS = set()
for e in infos:
    if e["source"] == "sec_form4" and e["kind"] == "achat_initie" and e["badge"] in ("officiel", "confirme") \
            and e["tickers"] and e["data"].get("hors_bourse"):
        for ligne in e["data"]["transactions"]:
            if ligne.get("hors_bourse"):
                EMISSIONS.add((e["tickers"][0], ligne["date"], ligne["prix"]))


# Chefs du Congrès : la liste officielle gardée par le robot (data/elus/congres.json ; contre-vérifiée aux pages
# officielles par verif_congres.py). Le lien avec le nom écrit dans chaque rapport est refait ici à la main.
def mots(nom):
    n = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper()
    return [m for m in re.findall(r"[A-Z]+", n) if m not in {"JR", "SR", "II", "III", "IV"}]


fichier_congres = racine / "elus" / "congres.json"
CONGRES = json.loads(fichier_congres.read_text(encoding="utf-8")) if fichier_congres.exists() else {}
CHEFS = {c["cle"] for c in CONGRES.get("chefs", [])}


def est_chef(e):
    d = e["data"]
    if e["source"] == "chambre_ptr":
        m = CONGRES.get("chambre", {}).get(d.get("circonscription") or "")
        return f"chambre:{d.get('circonscription')}" in CHEFS and bool(m) and mots(m["nom_famille"])[-1] in mots(d["elu"])
    nom = mots(d["elu"])
    for cle in CHEFS:
        if cle.startswith("senat:"):
            famille, etat = cle.split(":")[1], cle.split(":")[2]
            homonymes = [k for k in CONGRES["senat"] if k.split(":")[0] == famille]
            s = CONGRES["senat"][f"{famille}:{etat}"]
            if nom[-1:] == famille.split()[-1:] and (len(homonymes) == 1 or any(
                    a.startswith(b) or b.startswith(a) for a in nom[:-1] for b in mots(s["prenom"]))):
                return True
    return False


def regle_de(e):
    s, d = e["source"], e.get("data") or {}
    if s == "sec_form4":
        if d.get("plan_10b5_1") or d.get("hors_bourse") or d.get("automatique"):
            return None
        if e["kind"] == "achat_initie" and any((e["tickers"][0], l["date"], l["prix"]) in EMISSIONS
                                               for l in d.get("transactions", [])):
            return None
        return {"achat_initie": "achat_dirigeant", "vente_initie": "vente_dirigeant"}.get(e["kind"])
    if s == "sec_13dg":
        ok = (d.get("type") == "SCHEDULE 13D" and e["kind"] == "plus_5_pourcent"
              and "IA" in (d.get("types_declarants") or []) and d.get("but_sous_evalue") is True)
        return "activiste_13d" if ok else None
    if s == "sec_13f":
        return "fonds_13f" if e["direction"] == 1 else None
    if s in ("chambre_ptr", "senat_ptr"):
        chef = est_chef(e)
        if e["direction"] == 1:
            return "achat_chef" if chef else "achat_elu"
        return "vente_chef" if chef and e["kind"] == "vente_elu" else None
    if s == "fda":
        return "fda"
    if s == "nhtsa":
        return "rappel"
    if s == "sec_poursuites":
        return "sec_suspension" if d.get("sorte") == "suspension" else "sec_procedure"
    if s == "sec_8k":
        items = [i["item"] for i in d.get("items", [])]
        return "faillite" if "1.03" in items else ("etats_financiers" if "4.02" in items else None)
    return None


def ouvrables(a, b):
    if a > b:
        a, b = b, a
    semaines, reste = divmod((b - a).days, 7)
    n = semaines * 5
    for i in range(reste):
        if (a + timedelta(days=semaines * 7 + i)).weekday() < 5:
            n += 1
    return n


# Fonds enregistrés selon leur fiche SEC (rapports de fonds trouvés) : mis à part du score
fiches = racine / "sec" / "emetteurs.json"
FONDS = {s for s, f in json.loads(fiches.read_text(encoding="utf-8")).items() if f.get("formulaires_fonds")} \
    if fiches.exists() else set()

genere = datetime.fromisoformat(pub["genere_a"])
jour = genere.astimezone(ZoneInfo("America/Toronto")).date()
assert jour.isoformat() == pub["jour"], (jour, pub["jour"])

notes = {}  # symbole -> liste de (regle, points, info)
contexte = {}
for e in infos:
    if e["badge"] not in ("officiel", "confirme") or not e["tickers"]:
        continue
    age = (jour - date.fromisoformat(e["published_on"])).days
    if age > 90:
        continue
    r = regle_de(e)
    cibles = e["tickers"] if (r is None or e["source"] == "sec_poursuites") else e["tickers"][:1]
    for t in cibles:
        if r is None or t in FONDS:
            contexte.setdefault(t, []).append(e)
        else:
            notes.setdefault(t, []).append([r, max(age, 0), e])

calcule = {}
for t, liste in notes.items():
    achats = [x for x in liste if x[0] == "achat_dirigeant"]
    lignes = []
    for r, age, e in liste:
        m = 1.0
        if r == "achat_dirigeant":
            roles = e["data"].get("roles") or []
            if any(principal(x) for x in roles):
                m *= 1.5
            elif roles and set(roles) == {"actionnaire de 10 %"}:
                m *= 0.5
            gens = {n.strip().upper() for n in e["entities"][:-1]}
            for _, _, f in achats:
                if f is e or gens & {n.strip().upper() for n in f["entities"][:-1]}:
                    continue
                if f["occurred_on"] == e["occurred_on"] and round(f["amount_min"] or 0) == round(e["amount_min"] or 0):
                    continue
                if ouvrables(date.fromisoformat(e["occurred_on"]), date.fromisoformat(f["occurred_on"])) <= 2:
                    m *= 1.75
                    break
        demi = 60 if r == "fonds_13f" else 30
        lignes.append((FAMILLE[r], POINTS[r] * m * 2 ** (-age / demi), e["id"], e["published_on"]))
    meilleurs = {}
    for fam, p, i, d in lignes:
        cle = (fam, 1 if p > 0 else -1)
        if cle not in meilleurs or (abs(p), d, i) > (abs(meilleurs[cle][0]), meilleurs[cle][2], meilleurs[cle][1]):
            meilleurs[cle] = (p, i, d)
    total = 0.0
    for sens in (1, -1):
        groupe = [v[0] for k, v in meilleurs.items() if k[1] == sens]
        if groupe:
            total += sum(groupe) * (1 + 0.25 * (len(groupe) - 1))
    calcule[t] = (total, {k: v[1] for k, v in meilleurs.items()})

hausse = sorted((t for t in calcule if calcule[t][0] >= 1.5), key=lambda t: (-calcule[t][0], t))[:20]
baisse = sorted((t for t in calcule if calcule[t][0] <= -1.5), key=lambda t: (calcule[t][0], t))[:20]

ecarts = []
for nom, attendu in (("hausse", hausse), ("baisse", baisse)):
    publie = [x["symbole"] for x in pub[nom]]
    if publie != attendu:
        ecarts.append(f"{nom} : publié {publie} ≠ recalculé {attendu}")
    for x in pub[nom]:
        t = x["symbole"]
        if t not in calcule:
            continue
        if abs(x["score"] - calcule[t][0]) > 0.01:
            ecarts.append(f"{t} : score publié {x['score']} ≠ recalculé {calcule[t][0]:.4f}")
        comptees = {(g["famille"], g["sens"]): next(i["id"] for i in g["infos"] if i["compte"]) for g in x["groupes"]}
        if comptees != calcule[t][1]:
            ecarts.append(f"{t} : infos comptées {comptees} ≠ {calcule[t][1]}")
        attendu_ctx = sorted(contexte.get(t, []), key=lambda e: (e["published_on"], e["id"]), reverse=True)[:5]
        if [c["id"] for c in x["contexte"]] != [e["id"] for e in attendu_ctx]:
            ecarts.append(f"{t} : contexte différent")
        for i in [i["id"] for g in x["groupes"] for i in g["infos"]] + [c["id"] for c in x["contexte"]]:
            ev = pub["evenements"].get(i)
            if ev is None:
                ecarts.append(f"{t} : info {i} absente du fichier")
                continue
            dom = urlparse(ev["official_url"]).hostname or ""
            if ev["badge"] not in ("officiel", "confirme") or not any(dom == d or dom.endswith("." + d) for d in DOMAINES):
                ecarts.append(f"{t} : info {i} badge {ev['badge']} ou domaine {dom} non officiel")

print(f"Jour du calcul : {jour} · infos lues : {len(infos)} · compagnies notées : {len(calcule)} "
      f"(publié : {pub['compagnies_notees']}) · fonds mis à part : {len(FONDS)}")
print(f"Hausse : {len(hausse)} · Baisse : {len(baisse)}")
transactions_chefs = {e["id"] for e in infos if e["source"] in ("chambre_ptr", "senat_ptr") and est_chef(e)}
print(f"Chefs du Congrès dans la liste officielle : {len(CHEFS)} · leurs transactions (3 mois) : {len(transactions_chefs)}")
publiees = {r["code"]: r["points"] for r in pub["methode"]["regles"]}
if publiees != POINTS:
    ecarts.append(f"règles publiées {publiees} ≠ règles du recalcul {POINTS}")
if pub["compagnies_notees"] != len(calcule):
    ecarts.append("nombre de compagnies notées différent")
print("\n".join(ecarts) if ecarts else "AUCUN ÉCART : le recalcul indépendant donne exactement le score publié.")
sys.exit(1 if ecarts else 0)
