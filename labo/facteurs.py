"""LE point qui fait la différence ? Pour chaque entrée « hausse » du rejeu de 3 ans : ce qui était connu au moment de
l'achat (rien du futur), puis le résultat 1, 3 et 12 mois plus tard contre le S&P 500 aux mêmes dates.

Méthode anti-chance, décidée AVANT de regarder les résultats :
- Découverte : 2023-2024 et 2024-2025. Confirmation : 2025-2026, sans rien changer.
- Un point compte seulement si, CHAQUE année de découverte (au moins 25 compagnies) : écart médian avec le S&P 500
  positif, au moins 52 % des compagnies battent le S&P 500, et l'écart médian dépasse celui des autres compagnies de
  3 points ou plus. Puis, en confirmation : écart médian positif et au moins 50 % qui battent le S&P 500.
- « À éviter » : l'inverse, chaque année (médiane 3 points sous les autres, 45 % ou moins qui battent le S&P 500).
- Test de permutation (2 000 tirages, dans chaque année) : la chance d'obtenir un tel écart par hasard.
- Rendements : prix officiels de la SEC ; nouveau CUSIP (regroupement d'actions) estimé par le saut de prix au changement.
Les catégories (coupures) sont fixées d'avance, en chiffres ronds.

Sortie : labo/rejeu3/facteurs.md et facteurs.json ; rejeu/facteurs_entrees.json (pour verif_facteurs.py).
"""
import json
import random
import re
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

SORTIE = Path("labo/rejeu3")
TRAVAIL = Path("rejeu")
ANNEES = {"2023-2024": ("2023-07", "2024-06"), "2024-2025": ("2024-07", "2025-06"), "2025-2026": ("2025-07", "2026-06")}
DECOUVERTE, CONFIRMATION = ("2023-2024", "2024-2025"), "2025-2026"
DUREES = (1, 3, 12)
N_MIN, BAT_MIN, BAT_CONF, MARGE, BAT_EVITER = 25, 0.52, 0.50, 0.03, 0.45
TIRAGES = 2000
# Rôles : mêmes mots que la règle « PDG, directeur financier ou président du conseil » du score
PRINCIPAL = re.compile(r"\b(CEO|CFO|PEO|PFO|COB)\b|CHIEF EXECUTIVE|CHIEF FINANCIAL|(?<!VICE )(?<!VICE-)\bCHAIR", re.I)
FINANCIER = re.compile(r"\b(CFO|PFO)\b|CHIEF FINANCIAL|PRINCIPAL FINANCIAL", re.I)

entrees = json.loads((SORTIE / "entrees.json").read_text(encoding="utf-8"))
evs = {e["id"]: e for e in json.loads((TRAVAIL / "evenements.json").read_text(encoding="utf-8"))}
P = json.loads((TRAVAIL / "prix.json").read_text(encoding="utf-8"))
prix = P["prix"]
jours_prix = {s: sorted(p) for s, p in prix.items()}
positions = {h: json.loads((TRAVAIL / f"positions_strict_{h}.json").read_text(encoding="utf-8")) for h in DUREES}
achats = defaultdict(list)
for e in evs.values():
    if e["source"] == "sec_form4" and e["kind"] == "achat_initie":
        achats[e["tickers"][0]].append(e)


def j8(iso):
    return iso.replace("-", "")


def moins(jour8, n):
    return (date(int(jour8[:4]), int(jour8[4:6]), int(jour8[6:])) - timedelta(days=n)).strftime("%Y%m%d")


def prix_au(sym, jour8, tolerance=10):
    """Dernier prix de la SEC à cette date ou avant (au plus `tolerance` jours avant) : [prix, CUSIP]."""
    d = jours_prix.get(sym, [])
    i = bisect_right(d, jour8)
    return prix[sym][d[i - 1]] if i and d[i - 1] >= moins(jour8, tolerance) else None


def ouvrables(a, b):
    a, b = date.fromisoformat(a), date.fromisoformat(b)
    return sum(1 for k in range((b - a).days) if (a + timedelta(days=k + 1)).weekday() < 5)


def classe(x, coupures, noms):
    for c, n in zip(coupures, noms):
        if x < c:
            return n
    return noms[-1]


def mesures(idx, e):
    sym, jour8 = e["symbole"], j8(e["jour"])
    infos = e.get("infos") or []
    m = {"13D activiste": "oui" if any(r == "activiste_13d" for _, r, _ in infos) else "non",
         "Note de Radar": "10" if e["note10"] >= 10 else "9 à 9,9" if e["note10"] >= 9 else "7 à 8,9",
         "Taille selon Radar": e.get("taille") or "inconnue"}
    v = e.get("valeur_m")
    m["Valeur en bourse"] = "inconnue" if v is None else classe(v, (100, 500, 2000), (
        "moins de 100 M$", "100 à 500 M$", "500 M$ à 2 G$", "2 G$ et plus"))
    p0 = prix_au(sym, jour8)
    m["Prix de l'action"] = "inconnu" if not p0 else classe(p0[0], (1, 5, 20), (
        "moins de 1 $", "1 à 5 $", "5 à 20 $", "20 $ et plus"))
    for jours, nom in ((30, "Cours sur 30 jours avant"), (90, "Cours sur 90 jours avant")):
        a = prix_au(sym, moins(jour8, jours))
        if not p0 or not a or a[1] != p0[1]:
            m[nom] = "inconnu ou nouveau CUSIP"
        else:
            m[nom] = classe(p0[0] / a[0] - 1, (-0.30, -0.10, 0.10), (
                "baisse de 30 % et plus", "baisse de 10 à 30 %", "stable (±10 %)", "hausse de 10 % et plus"))
    annee = [prix[sym][d][1] for d in jours_prix.get(sym, []) if moins(jour8, 365) <= d <= jour8]
    m["Nouveau CUSIP dans l'année avant"] = "oui" if len(set(annee)) > 1 else "non" if annee else "inconnu"
    achat = next((evs.get(i) for i, r, compte in infos if r == "achat_dirigeant" and compte), None)
    if achat is None:
        for nom in ("Part que le dirigeant ajoute", "Rôle de l'acheteur", "Montant acheté", "Délai de déclaration",
                    "Jours entre son achat et le nôtre", "Notre prix contre le sien", "Dirigeants qui achètent (30 jours)"):
            m[nom] = "pas d'achat de dirigeant"
        return m
    d = achat["data"]
    lignes = d.get("transactions") or []
    achete = sum(t.get("actions") or 0 for t in lignes)
    apres = lignes[-1].get("apres") if lignes else None
    if apres is None or not achete:
        m["Part que le dirigeant ajoute"] = "inconnue"
    elif apres - achete <= 0:
        m["Part que le dirigeant ajoute"] = "nouvelle position"
    else:
        m["Part que le dirigeant ajoute"] = classe(achete / (apres - achete), (0.05, 0.25, 1.0), (
            "moins de 5 %", "5 à 25 %", "25 à 100 %", "double ou plus"))
    roles = d.get("roles") or []
    m["Rôle de l'acheteur"] = ("directeur financier" if any(FINANCIER.search(r) for r in roles) else
                               "PDG ou président du conseil" if any(PRINCIPAL.search(r) for r in roles) else
                               "actionnaire de 10 % seulement" if roles and set(roles) == {"actionnaire de 10 %"} else
                               "administrateur seulement" if roles and set(roles) == {"administrateur"} else
                               "autre dirigeant")
    m["Montant acheté"] = classe(achat.get("amount_min") or 0, (50_000, 200_000, 1_000_000), (
        "moins de 50 k$", "50 à 200 k$", "200 k$ à 1 M$", "1 M$ et plus"))
    m["Délai de déclaration"] = classe(ouvrables(achat["occurred_on"], achat["published_on"]), (3, 11), (
        "0 à 2 jours ouvrables", "3 à 10 jours ouvrables", "plus de 10 jours ouvrables"))
    m["Jours entre son achat et le nôtre"] = classe((date.fromisoformat(e["jour"]) -
                                                    date.fromisoformat(achat["occurred_on"])).days, (8, 31), (
        "0 à 7 jours", "8 à 30 jours", "plus de 30 jours"))
    pos = positions[1][idx]
    if pos["statut"] != "achetée" or not d.get("prix_moyen"):
        m["Notre prix contre le sien"] = "pas acheté ou inconnu"
    else:
        m["Notre prix contre le sien"] = classe(pos["prix_achat"] / d["prix_moyen"] - 1, (-0.10, 0.10, 0.30), (
            "10 % et plus sous le sien", "proche (±10 %)", "10 à 30 % au-dessus", "30 % et plus au-dessus"))
    debut = (date.fromisoformat(e["jour"]) - timedelta(days=30)).isoformat()
    qui = set()
    for x in achats.get(sym, []):
        if debut <= x["published_on"] <= e["jour"]:
            qui |= set(x["data"].get("proprietaires_cik") or []) or {n.upper() for n in x["entities"][:-1]}
    m["Dirigeants qui achètent (30 jours)"] = "1" if len(qui) <= 1 else "2" if len(qui) == 2 else "3 et plus"
    return m


def annee_de(e):
    return next(a for a, (d, f) in ANNEES.items() if d <= e["mois"] <= f)


lignes_sortie = []
for idx, e in enumerate(entrees):
    r = {"symbole": e["symbole"], "jour": e["jour"], "annee": annee_de(e), "mesures": mesures(idx, e), "resultats": {}}
    for h in DUREES:
        p = positions[h][idx]
        if p["statut"] == "achetée" and p["marche"] is not None:
            r["resultats"][str(h)] = {"ecart": round(p["rendement_estime"] - p["marche"], 4),
                                      "bat": p["rendement_estime"] > p["marche"]}
    lignes_sortie.append(r)
(TRAVAIL / "facteurs_entrees.json").write_text(json.dumps(lignes_sortie, ensure_ascii=False), encoding="utf-8")
FACTEURS = list(lignes_sortie[0]["mesures"])


def stats(groupe, h):
    res = [x["resultats"][str(h)] for x in groupe if str(h) in x["resultats"]]
    if not res:
        return None
    ec = [x["ecart"] for x in res]
    return {"n": len(res), "mediane": round(median(ec), 4), "moyenne": round(mean(ec), 4),
            "bat": round(sum(x["bat"] for x in res) / len(res), 4)}


tableau = {}
for f in FACTEURS:
    for cat in sorted({x["mesures"][f] for x in lignes_sortie}):
        for an in ANNEES:
            for h in DUREES:
                dedans = [x for x in lignes_sortie if x["annee"] == an and x["mesures"][f] == cat]
                dehors = [x for x in lignes_sortie if x["annee"] == an and x["mesures"][f] != cat]
                s1, s2 = stats(dedans, h), stats(dehors, h)
                if s1:
                    tableau[(f, cat, an, h)] = {**s1, "reste": s2}


def permutation(f, cat, h, annees):
    """Part des tirages au hasard (catégories mélangées dans chaque année) où l'écart de « % qui bat le S&P » est au
    moins aussi grand que l'écart observé."""
    rnd = random.Random(2026)
    blocs = []
    for an in annees:
        g = [(x["mesures"][f] == cat, x["resultats"][str(h)]["bat"]) for x in lignes_sortie
             if x["annee"] == an and str(h) in x["resultats"]]
        blocs.append(g)

    def ecart(bl):
        tot = 0.0
        for g in bl:
            d = [b for c, b in g if c]
            r = [b for c, b in g if not c]
            tot += (sum(d) / len(d) - sum(r) / len(r)) if d and r else 0
        return tot

    obs = ecart(blocs)
    plus = 0
    for _ in range(TIRAGES):
        melange = []
        for g in blocs:
            etiquettes = [c for c, _ in g]
            rnd.shuffle(etiquettes)
            melange.append([(c, b) for c, (_, b) in zip(etiquettes, g)])
        plus += abs(ecart(melange)) >= abs(obs)
    return round(plus / TIRAGES, 4)


points, eviter = [], []
for (f, cat, an, h), s in tableau.items():
    if an != DECOUVERTE[0]:
        continue
    decouv = [tableau.get((f, cat, a, h)) for a in DECOUVERTE]
    if any(x is None or x["n"] < N_MIN or x["reste"] is None for x in decouv):
        continue
    conf = tableau.get((f, cat, CONFIRMATION, h))
    bon = all(x["mediane"] > 0 and x["bat"] >= BAT_MIN and x["mediane"] - x["reste"]["mediane"] >= MARGE for x in decouv)
    mauvais = all(x["mediane"] - x["reste"]["mediane"] <= -MARGE and x["bat"] <= BAT_EVITER for x in decouv)
    if bon or mauvais:
        confirme = None
        if conf and conf["n"] >= N_MIN and conf["reste"]:
            confirme = (conf["mediane"] > 0 and conf["bat"] >= BAT_CONF) if bon else \
                       (conf["mediane"] < conf["reste"]["mediane"])
        fiche = {"facteur": f, "categorie": cat, "duree": h, "annees": {a: tableau.get((f, cat, a, h)) for a in ANNEES},
                 "confirme": confirme, "hasard": permutation(f, cat, h, DECOUVERTE)}
        (points if bon else eviter).append(fiche)

json.dump({"points": points, "a_eviter": eviter,
           "tableau": [{"facteur": f, "categorie": c, "annee": a, "duree": h, **s} for (f, c, a, h), s in tableau.items()]},
          open(SORTIE / "facteurs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def pc(x):
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def cellule(s):
    return "—" if not s else f"{pc(s['mediane'])} · {s['bat'] * 100:.0f} % ({s['n']})"


l = ["# LE point qui fait la différence ? (rejeu de 3 ans, juillet 2023 → juin 2026)", "",
     f"Entrées « hausse » : {len(entrees)}. Cellules : écart MÉDIAN avec le S&P 500 aux mêmes dates · part des compagnies "
     "qui battent le S&P 500 (nombre). Découverte : 2023-2024 et 2024-2025 ; confirmation : 2025-2026.", "",
     "## Points qui passent les critères (fixés d'avance)", ""]
for titre, liste in (("Points", points), ("À éviter", eviter)):
    if titre == "À éviter":
        l += ["", "## Catégories à éviter (mauvaises chaque année de découverte)", ""]
    if not liste:
        l.append("- aucun")
    for x in sorted(liste, key=lambda x: x["hasard"]):
        l.append(f"- {x['facteur']} = {x['categorie']} · {x['duree']} mois · " + " · ".join(
            f"{a} {cellule(x['annees'][a])} (autres {cellule((x['annees'][a] or {}).get('reste'))})" for a in ANNEES) +
            f" · confirmé en 2025-2026 : {x['confirme']} · chance que ce soit le hasard : {x['hasard'] * 100:.1f} %")
for h in DUREES:
    l += ["", f"## Tous les facteurs, vendre après {h} mois", "",
          "| Facteur | Catégorie | " + " | ".join(ANNEES) + " |", "|---|---|" + "---|" * len(ANNEES)]
    for f in FACTEURS:
        for cat in sorted({x["mesures"][f] for x in lignes_sortie}):
            l.append(f"| {f} | {cat} | " + " | ".join(cellule(tableau.get((f, cat, a, h))) for a in ANNEES) + " |")
l += ["", "VERDICT : analyse des facteurs faite"]
(SORTIE / "facteurs.md").write_text("\n".join(l) + "\n", encoding="utf-8")
print("\n".join(l[:30]))
