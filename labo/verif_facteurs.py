"""Vérification INDÉPENDANTE de facteurs.py (n'importe rien de facteurs.py, du rejeu ni du robot).

1. Chaque mesure de chaque entrée refaite à partir des données brutes du rejeu (entrées, infos de la SEC, prix, positions).
2. Les chiffres des points trouvés (et des catégories à éviter) refaits : nombre, écart médian, part qui bat le S&P 500.
Sortie : labo/rejeu3/verification_facteurs.md
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path
from statistics import median

SORTIE, TRAVAIL = Path("labo/rejeu3"), Path("rejeu")
lignes, ecarts = [], []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "verification_facteurs.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


entrees = json.loads((SORTIE / "entrees.json").read_text(encoding="utf-8"))
leurs = json.loads((TRAVAIL / "facteurs_entrees.json").read_text(encoding="utf-8"))
resultat = json.loads((SORTIE / "facteurs.json").read_text(encoding="utf-8"))
infos = {e["id"]: e for e in json.loads((TRAVAIL / "evenements.json").read_text(encoding="utf-8"))}
prix = json.loads((TRAVAIL / "prix.json").read_text(encoding="utf-8"))["prix"]
pos = {h: json.loads((TRAVAIL / f"positions_strict_{h}.json").read_text(encoding="utf-8")) for h in (1, 3, 12)}
par_symbole = {}
for x in infos.values():
    if x["source"] == "sec_form4" and x["kind"] == "achat_initie":
        par_symbole.setdefault(x["tickers"][0], []).append(x)
dire("# Vérification indépendante des facteurs\n")


def jour_moins(j, n):
    return (date(int(j[:4]), int(j[4:6]), int(j[6:])) - timedelta(days=n)).strftime("%Y%m%d")


def dernier_prix(s, j, tol=10):
    dates = [d for d in prix.get(s, {}) if jour_moins(j, tol) <= d <= j]
    return prix[s][max(dates)] if dates else None


def jours_ouvrables(a, b):
    a, b = date.fromisoformat(a), date.fromisoformat(b)
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return n


def tranche(x, bornes):
    """Indice de la tranche : 0 si x < bornes[0], 1 si x < bornes[1]…"""
    return next((i for i, b in enumerate(bornes) if x < b), len(bornes))


def mes_mesures(i, e):
    s, j = e["symbole"], e["jour"].replace("-", "")
    m = {}
    les_infos = e.get("infos") or []
    m["13D activiste"] = "oui" if [1 for x in les_infos if x[1] == "activiste_13d"] else "non"
    m["Note de Radar"] = ["7 à 8,9", "9 à 9,9", "10"][tranche(e["note10"], (9, 10))]
    m["Taille selon Radar"] = e.get("taille") or "inconnue"
    v = e.get("valeur_m")
    m["Valeur en bourse"] = "inconnue" if v is None else \
        ["moins de 100 M$", "100 à 500 M$", "500 M$ à 2 G$", "2 G$ et plus"][tranche(v, (100, 500, 2000))]
    p0 = dernier_prix(s, j)
    m["Prix de l'action"] = "inconnu" if p0 is None else \
        ["moins de 1 $", "1 à 5 $", "5 à 20 $", "20 $ et plus"][tranche(p0[0], (1, 5, 20))]
    for n, nom in ((30, "Cours sur 30 jours avant"), (90, "Cours sur 90 jours avant")):
        a = dernier_prix(s, jour_moins(j, n))
        m[nom] = "inconnu ou nouveau CUSIP" if p0 is None or a is None or a[1] != p0[1] else \
            ["baisse de 30 % et plus", "baisse de 10 à 30 %", "stable (±10 %)", "hausse de 10 % et plus"][
                tranche(p0[0] / a[0] - 1, (-0.30, -0.10, 0.10))]
    cusips = {v[1] for d, v in prix.get(s, {}).items() if jour_moins(j, 365) <= d <= j}
    m["Nouveau CUSIP dans l'année avant"] = "inconnu" if not cusips else ("oui" if len(cusips) > 1 else "non")
    compte = [x[0] for x in les_infos if x[1] == "achat_dirigeant" and x[2]]
    a = infos.get(compte[0]) if compte else None
    noms = ("Part que le dirigeant ajoute", "Rôle de l'acheteur", "Montant acheté", "Délai de déclaration",
            "Jours entre son achat et le nôtre", "Notre prix contre le sien", "Dirigeants qui achètent (30 jours)")
    if a is None:
        m.update({n: "pas d'achat de dirigeant" for n in noms})
        return m
    tr = a["data"].get("transactions") or []
    total = sum(t.get("actions") or 0 for t in tr)
    fin = tr[-1].get("apres") if tr else None
    if fin is None or not total:
        m[noms[0]] = "inconnue"
    elif fin - total <= 0:
        m[noms[0]] = "nouvelle position"
    else:
        m[noms[0]] = ["moins de 5 %", "5 à 25 %", "25 à 100 %", "double ou plus"][tranche(total / (fin - total),
                                                                                           (0.05, 0.25, 1.0))]
    roles = a["data"].get("roles") or []
    texte = " | ".join(roles).upper()
    if re.search(r"\bCFO\b|\bPFO\b|CHIEF FINANCIAL|PRINCIPAL FINANCIAL", texte):
        m[noms[1]] = "directeur financier"
    elif any(re.search(r"\b(CEO|CFO|PEO|PFO|COB)\b|CHIEF EXECUTIVE|CHIEF FINANCIAL|(?<!VICE )(?<!VICE-)\bCHAIR", r.upper())
             for r in roles):
        m[noms[1]] = "PDG ou président du conseil"
    elif roles and all(r == "actionnaire de 10 %" for r in roles):
        m[noms[1]] = "actionnaire de 10 % seulement"
    elif roles and all(r == "administrateur" for r in roles):
        m[noms[1]] = "administrateur seulement"
    else:
        m[noms[1]] = "autre dirigeant"
    m[noms[2]] = ["moins de 50 k$", "50 à 200 k$", "200 k$ à 1 M$", "1 M$ et plus"][
        tranche(a.get("amount_min") or 0, (50_000, 200_000, 1_000_000))]
    m[noms[3]] = ["0 à 2 jours ouvrables", "3 à 10 jours ouvrables", "plus de 10 jours ouvrables"][
        tranche(jours_ouvrables(a["occurred_on"], a["published_on"]), (3, 11))]
    m[noms[4]] = ["0 à 7 jours", "8 à 30 jours", "plus de 30 jours"][
        tranche((date.fromisoformat(e["jour"]) - date.fromisoformat(a["occurred_on"])).days, (8, 31))]
    p = pos[1][i]
    pm = a["data"].get("prix_moyen")
    m[noms[5]] = "pas acheté ou inconnu" if p["statut"] != "achetée" or not pm else \
        ["10 % et plus sous le sien", "proche (±10 %)", "10 à 30 % au-dessus", "30 % et plus au-dessus"][
            tranche(p["prix_achat"] / pm - 1, (-0.10, 0.10, 0.30))]
    debut = (date.fromisoformat(e["jour"]) - timedelta(days=30)).isoformat()
    gens = set()
    for x in par_symbole.get(s, []):
        if debut <= x["published_on"] <= e["jour"]:
            gens |= set(x["data"].get("proprietaires_cik") or []) or {n.upper() for n in x["entities"][:-1]}
    m[noms[6]] = "1" if len(gens) <= 1 else ("2" if len(gens) == 2 else "3 et plus")
    return m


# 1. Mesures
dire("## 1. Mesures refaites pour chaque entrée")
pareilles, total = 0, 0
for i, (e, x) in enumerate(zip(entrees, leurs)):
    mien = mes_mesures(i, e)
    for f, v in x["mesures"].items():
        total += 1
        if mien.get(f) == v:
            pareilles += 1
        elif len(ecarts) < 30:
            ecarts.append(f"{e['symbole']} {e['jour']} · {f} : {v} ≠ {mien.get(f)}")
            dire(f"- ÉCART : {ecarts[-1]}")
        else:
            ecarts.append("…")
dire(f"- mesures comparées : {total:,} · identiques : {pareilles:,}")

# 2. Les chiffres des points trouvés
dire("\n## 2. Chiffres des points trouvés et des catégories à éviter, refaits")
for genre in ("points", "a_eviter"):
    for c in resultat[genre]:
        for an, s in c["annees"].items():
            if not s:
                continue
            res = []
            for i, x in enumerate(leurs):
                if x["annee"] == an and x["mesures"][c["facteur"]] == c["categorie"]:
                    p = pos[c["duree"]][i]
                    if p["statut"] == "achetée" and p["marche"] is not None:
                        res.append(round(p["rendement_estime"] - p["marche"], 4))  # même définition : écart arrondi
            ok = len(res) == s["n"] and abs(round(median(res), 4) - s["mediane"]) < 1e-4 and \
                abs(round(sum(r > 0 for r in res) / len(res), 4) - s["bat"]) < 1e-4
            dire(f"- {genre} · {c['facteur']} = {c['categorie']} · {c['duree']} mois · {an} : "
                 f"{'identique' if ok else 'DIFFÉRENT'} (n {len(res)} / {s['n']})")
            if not ok:
                ecarts.append(f"{c['facteur']} {c['categorie']} {an}")
dire(f"\nVERDICT : {'tout concorde' if not ecarts else f'{len(ecarts)} écart(s)'}")
