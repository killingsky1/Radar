"""Recalcul INDÉPENDANT du score (n'importe rien du robot) à partir des règles publiées dans l'app.

Entrées : les infos du robot (data/evenements/*.jsonl, 3 derniers mois) et le score publié (data/app/aujourdhui.json).
Vérifie : mêmes compagnies dans le même ordre, mêmes points (±0,01), mêmes infos comptées, bonus, contexte,
et que chaque info citée existe, est « officiel »/« confirmé », et pointe vers un domaine officiel.
Lot B : note sur 10 = 5 + points × 5/6 (0 à 10, au dixième, 5 vers le haut) ; listes à 7/10 et plus, 3/10 et moins ;
« Récent » = l'info comptée la plus récente du sens de la liste, déposée il y a moins de 3 jours de bourse.
Lot L : un achat ou une vente d'un initié routinier (classement gardé par le robot, refait aux fichiers de la SEC par
verif_lotL.py) ne compte pas ; un achat de dirigeant dans une petite compagnie compte ×1,5 (taille refaite ici avec les
chiffres gardés par le robot, et aux sources officielles par verif_lotL.py).
Lot M (score-9 et plus) : une compagnie dont la valeur en bourse (refaite ici) est connue et sous 100 M$ n'entre pas dans
la liste « hausse » : elle va dans « écartées » (mêmes vérifications que la liste). Taille inconnue : jamais écartée.
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
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
    """PDG, directeur financier ou président du conseil (pas un vice-président). Les mots sont séparés par TOUT signe
    qui n'est pas une lettre ou un chiffre (« CEO/President », « Pres. & CEO ») ; avant le lot M, seulement par - , & ( )."""
    t = " " + " ".join(re.findall(r"[A-Z0-9]+", titre.upper())) + " "
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


# Lot L : initiés routiniers (règle publiée : même CIK, ou même nom en lettres et chiffres, dans la même compagnie ;
# classement de l'année de la transaction)
fichier_r = racine / "sec" / "inities_routiniers.json"
ROUTINIERS = json.loads(fichier_r.read_text(encoding="utf-8")).get("annees", {}) if fichier_r.exists() else {}


def nom_simple(n):
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", (n or "").upper()).split())


def routinier(e):
    c, d = ROUTINIERS.get(e["occurred_on"][:4]), e["data"]
    cik = str(d.get("cik_emetteur") or "").strip()
    if not c or not cik.isdigit():
        return False
    em = str(int(cik))
    return any(str(o).isdigit() and str(int(o)) in c["cik"].get(em, {}) for o in d.get("proprietaires_cik") or []) or \
        any(nom_simple(n) in c["noms"].get(em, {}) for n in e["entities"][:-1])


def regle_de(e):
    s, d = e["source"], e.get("data") or {}
    if s == "sec_form4":
        if d.get("plan_10b5_1") or d.get("hors_bourse") or d.get("automatique"):
            return None
        if e["kind"] == "achat_initie" and any((e["tickers"][0], l["date"], l["prix"]) in EMISSIONS
                                               for l in d.get("transactions", [])):
            return None
        if e["kind"] in ("achat_initie", "vente_initie") and routinier(e):
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

# Lot L : la taille en bourse (règles publiées : étrangère, actions de plus de 200 jours ou moins de 500 000, prix de plus
# de 60 jours = inconnue ; petite sous le 30e centile du NYSE, grande au 70e et plus)
fichier_t = racine / "prix" / "taille.json"
TAILLE = json.loads(fichier_t.read_text(encoding="utf-8")) if fichier_t.exists() else {}
FICHES = json.loads(fiches.read_text(encoding="utf-8")) if fiches.exists() else {}


def taille_de(t):
    v, s = valeur_de(t), TAILLE.get("seuils")
    if v is None:
        return None
    return "petite" if v < s["p30"] else "grande" if v >= s["p70"] else "moyenne"


def valeur_de(t):
    """Valeur en bourse en M$ (actions déclarées × prix de la SEC), None si la taille est inconnue."""
    f, s = FICHES.get(t), TAILLE.get("seuils")
    if f is None or not s or "rapports" not in f or f.get("cik") is None:
        return None
    r = set(f["rapports"])
    if r & {"20-F", "40-F", "6-K"} or not r & {"10-K", "10-Q", "10-KT", "10-QT"}:
        return None
    # le fait le plus récent : fichiers frames ou dossier companyconcept (même date : les frames)
    faits = [x for x in ((TAILLE.get("actions") or {}).get(str(f["cik"])),
                         (TAILLE.get("actions_concept") or {}).get(str(f["cik"]))) if x]
    a = max(faits, key=lambda x: x[1], default=None)
    if not a or (jour - date.fromisoformat(a[1])).days > 200 or a[0] < 500_000:
        return None
    p = (TAILLE.get("prix") or {}).get(t)
    if not p or (jour - date(int(p[0][:4]), int(p[0][4:6]), int(p[0][6:]))).days > 60:
        return None
    return a[0] * p[1] / 1e6

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

def principal_avant(titre):  # découpage d'avant le lot M, gardé pour montrer les désaccords
    t = " " + titre.upper().replace("-", " ").replace(",", " ").replace("&", " ").replace("(", " ").replace(")", " ") + " "
    for vice in (" VICE PRESIDENT", " VICE CHAIRMAN", " VICE CHAIRPERSON", " VICE CHAIRWOMAN", " VICE CHAIR"):
        t = t.replace(vice, " ")
    mots = t.split()
    return (any(m in ("CEO", "CFO", "PEO", "PFO", "COB") for m in mots) or "CHIEF EXECUTIVE" in t
            or "CHIEF FINANCIAL" in t or any(m.startswith("CHAIR") for m in mots))


desaccords = sorted({(t, x) for t, liste in notes.items() for r, _, e in liste if r == "achat_dirigeant"
                     for x in e["data"].get("roles") or [] if principal(x) != principal_avant(x)})
for t, x in desaccords:
    print(f"Découpage du titre : {t} « {x} » → PDG, directeur financier ou président du conseil : "
          f"{'oui' if principal(x) else 'non'} (avant le lot M : {'oui' if principal_avant(x) else 'non'})")

calcule = {}
for t, liste in notes.items():
    achats = [x for x in liste if x[0] == "achat_dirigeant"]
    lignes = []
    for r, age, e in liste:
        m, petite = 1.0, False
        if r == "achat_dirigeant" and taille_de(t) == "petite":
            m, petite = 1.5, True
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
        lignes.append((FAMILLE[r], POINTS[r] * m * 2 ** (-age / demi), e["id"], e["published_on"], petite))
    meilleurs, sans_taille = {}, {}
    for fam, p, i, d, petite in lignes:
        cle = (fam, 1 if p > 0 else -1)
        q = p / 1.5 if petite else p
        sans_taille[cle] = max(sans_taille.get(cle, 0.0), q, key=abs)
    for fam, p, i, d, _ in lignes:
        cle = (fam, 1 if p > 0 else -1)
        if cle not in meilleurs or (abs(p), d, i) > (abs(meilleurs[cle][0]), meilleurs[cle][2], meilleurs[cle][1]):
            meilleurs[cle] = (p, i, d)
    total = 0.0
    for sens in (1, -1):
        groupe = [v[0] for k, v in meilleurs.items() if k[1] == sens]
        if groupe:
            total += sum(groupe) * (1 + 0.25 * (len(groupe) - 1))
    frais = {sens: max((v[2] for k, v in meilleurs.items() if k[1] == sens), default=None) for sens in (1, -1)}
    sans_bonus = sum(v[0] for v in meilleurs.values())
    total_st = sum(sum(v for k, v in sans_taille.items() if k[1] == sens) * (1 + 0.25 * (sum(1 for k in sans_taille if k[1] == sens) - 1))
                   for sens in (1, -1) if any(k[1] == sens for k in sans_taille))
    calcule[t] = (total, {k: v[1] for k, v in meilleurs.items()}, frais, sans_bonus, total_st)


def sur_10(points):
    n = Decimal(str(round(points, 2))) * 5 / 6 + 5
    return float(min(max(n, Decimal(0)), Decimal(10)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


candidates = sorted((t for t in calcule if sur_10(calcule[t][0]) >= 7.0), key=lambda t: (-calcule[t][0], t))
LOT_M = int(pub["version"].split("-")[1]) >= 9  # score-9 : règle des 100 M$


def trop_petite(t):
    return LOT_M and valeur_de(t) is not None and valeur_de(t) < 100


hausse = [t for t in candidates if not trop_petite(t)][:20]
ecartees = [t for t in candidates if trop_petite(t)][:20]
baisse = sorted((t for t in calcule if sur_10(calcule[t][0]) <= 3.0), key=lambda t: (calcule[t][0], t))[:20]

ecarts = []
if not LOT_M and pub.get("ecartees"):
    ecarts.append(f"écartées publiées avec {pub['version']} (la règle des 100 M$ arrive avec score-9)")
for nom, attendu in (("hausse", hausse), ("baisse", baisse), ("ecartees", ecartees)):
    publie = [x["symbole"] for x in pub.get(nom, [])]
    if publie != attendu:
        ecarts.append(f"{nom} : publié {publie} ≠ recalculé {attendu}")
    for x in pub.get(nom, []):
        t = x["symbole"]
        if t not in calcule:
            continue
        v = valeur_de(t)
        if nom == "ecartees" and (v is None or abs((x.get("taille") or {}).get("valeur_m", -1) - round(v, 1)) > 0.05):
            ecarts.append(f"{t} : valeur publiée {(x.get('taille') or {}).get('valeur_m')} ≠ recalculée {v}")
        if abs(x["score"] - calcule[t][0]) > 0.01:
            ecarts.append(f"{t} : score publié {x['score']} ≠ recalculé {calcule[t][0]:.4f} ; achats de dirigeants : "
                          + "; ".join(f"{e['id']} {e['occurred_on']} {e.get('amount_min')} {e['data'].get('roles')}"
                                      for r, _, e in notes.get(t, []) if r == "achat_dirigeant"))
        if x.get("note10") != sur_10(calcule[t][0]):
            ecarts.append(f"{t} : note publiée {x.get('note10')} ≠ recalculée {sur_10(calcule[t][0])}")
        depot = calcule[t][2][-1 if nom == "baisse" else 1]
        recent = bool(depot) and ouvrables(date.fromisoformat(depot), jour) < 3
        if x.get("depot_recent") != depot or x.get("recent") is not recent:
            ecarts.append(f"{t} : « Récent » publié {x.get('recent')} ({x.get('depot_recent')}) ≠ recalculé {recent} ({depot})")
        if (x.get("taille") or {}).get("taille") != taille_de(t):
            ecarts.append(f"{t} : taille publiée {(x.get('taille') or {}).get('taille')} ≠ recalculée {taille_de(t)}")
        if x.get("note10_sans_bonus") != sur_10(calcule[t][3]) or x.get("note10_sans_taille") != sur_10(calcule[t][4]):
            ecarts.append(f"{t} : notes sans bonus / sans taille publiées {x.get('note10_sans_bonus')} / "
                          f"{x.get('note10_sans_taille')} ≠ recalculées {sur_10(calcule[t][3])} / {sur_10(calcule[t][4])}")
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
print(f"Hausse (7/10 et plus) : {len(hausse)} · Baisse (3/10 et moins) : {len(baisse)}"
      + (f" · Écartées (moins de 100 M$) : {', '.join(f'{t} {valeur_de(t):.1f} M$' for t in ecartees) or 'aucune'}"
         if LOT_M else ""))
for nom, liste in (("Hausse", hausse), ("Baisse", baisse)):
    print(f"{nom} : " + ", ".join(f"{t} {str(sur_10(calcule[t][0])).replace('.', ',')}/10" + (" (récent)" if
          ouvrables(date.fromisoformat(calcule[t][2][1 if nom == 'Hausse' else -1]), jour) < 3 else "") for t in liste))
if not pub["methode"].get("seuil", "").startswith("Une compagnie entre dans la liste à partir de 7/10"):
    ecarts.append("méthode publiée : le seuil n'est pas 7/10")
transactions_chefs = {e["id"] for e in infos if e["source"] in ("chambre_ptr", "senat_ptr") and est_chef(e)}
print(f"Chefs du Congrès dans la liste officielle : {len(CHEFS)} · leurs transactions (3 mois) : {len(transactions_chefs)}")
routinieres = [e["id"] for e in infos if e["source"] == "sec_form4" and e["badge"] in ("officiel", "confirme")
               and (jour - date.fromisoformat(e["published_on"])).days <= 90 and routinier(e)]
print(f"Lot L : formulaires 4 d'initiés routiniers (0 point) : {len(routinieres)} · listes : "
      + ", ".join(f"{x['symbole']} {taille_de(x['symbole']) or 'inconnue'}" for n in ("hausse", "baisse") for x in pub[n]))
publiees = {r["code"]: r["points"] for r in pub["methode"]["regles"]}
if publiees != POINTS:
    ecarts.append(f"règles publiées {publiees} ≠ règles du recalcul {POINTS}")
if pub["compagnies_notees"] != len(calcule):
    ecarts.append("nombre de compagnies notées différent")
print("\n".join(ecarts) if ecarts else "AUCUN ÉCART : le recalcul indépendant donne exactement le score publié.")
sys.exit(1 if ecarts else 0)
