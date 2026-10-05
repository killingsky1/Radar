"""Quelle règle aurait fait le plus d'argent, chaque année ? Rejeu de Radar de juillet 2023 à juin 2026.

Lit labo/rejeu3/entrees.json (les nouvelles entrées « hausse », jour par jour, avec les règles actuelles du robot) et
rejeu/prix.json (prix officiels de la SEC). Pour chaque année (juillet à juin) et chaque règle :
- Sélection, sans regarder le futur : toutes ; les 10, 5 ou 3 premières du mois (ordre d'arrivée dans la liste) ;
  note de 9 et plus ; note de 10 ; petites compagnies ; petites compagnies avec une note de 9 et plus.
- Durée : vendre après 1, 3, 6 ou 12 mois (30, 91, 182 ou 365 jours).
- Achat : règle de la page Résultats (clôture d'un jour de bourse après la suggestion ; 2 dates de plus au plus) ;
  variante : jusqu'à 10 dates de règlement plus tard (beaucoup de petites compagnies n'ont pas de prix de la SEC
  chaque jour).
- Vente : le prix de la SEC à la date voulue (3 jours de plus au plus), sinon le 1er prix suivant (60 jours de plus au
  plus), sinon le dernier prix avant. Nouveau CUSIP (regroupement d'actions, nouveau titre) : 0 %. Prix pas encore
  publiés : position mise de côté (comptée).
- Coûts : aucun ; 10 $ par achat et par vente ; écart achat-vente de 1 % ou de 2 % (hypothèse des études, pas mesurée :
  aucune source gratuite ne donne l'écart) ; 10 $ + écart de 1 %.
- Argent : (a) 833 $ par mois pendant 12 mois, divisés également entre les choix du mois, pas réinvesti ;
  (b) 10 000 $ d'un coup, en autant de tranches que de mois de durée : chaque tranche est placée dans les choix d'un
  mois, puis réinvestie dans ceux du mois où elle revient (1 mois : une seule tranche, réinvestie chaque mois).
- Comparaisons : S&P 500 (SPY, sinon IVV, sinon VOO) aux mêmes dates ; S&P 500 acheté (833 $ par mois ou 10 000 $ d'un
  coup) et gardé jusqu'à la dernière vente.
Sortie : labo/rejeu3/strategies.json et tableau.md ; rejeu/positions_*.json (pour verif_rejeu.py).
"""
import json
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

SORTIE = Path("labo/rejeu3")
TRAVAIL = Path("rejeu")
ANNEES = {"2023-2024": ("2023-07", "2024-06"), "2024-2025": ("2024-07", "2025-06"), "2025-2026": ("2025-07", "2026-06")}
DUREES = {1: 30, 3: 91, 6: 182, 12: 365}
TOLERANCE, SECOURS, SAUT_MAX, PROCHE = 3, 60, 1.8, 5
MARCHE = ("SPY", "IVV", "VOO")
DEPARTS = {"strict": 3, "10 jours": 10}  # nombre de dates de règlement essayées après la 1re
COUTS = {"aucun": (0.0, 0.0), "10 $": (10.0, 0.0), "écart 1 %": (0.0, 0.01), "écart 2 %": (0.0, 0.02),
         "10 $ + écart 1 %": (10.0, 0.01)}
MENSUEL, CAPITAL = 10_000 / 12, 10_000.0
EN_ATTENTE_MAX = 0.05  # plus de 5 % des positions sans prix publié : la case n'est pas mesurable

entrees = json.loads((SORTIE / "entrees.json").read_text(encoding="utf-8"))
P = json.loads((TRAVAIL / "prix.json").read_text(encoding="utf-8"))
cal, couvert, prix = P["calendrier"], P["couvert"], P["prix"]
spy_jours = sorted(prix.get("SPY", {}))


def plus(j, n):
    return (date(int(j[:4]), int(j[4:6]), int(j[6:])) + timedelta(days=n)).strftime("%Y%m%d")


def marche_entre(d1, d2):
    for f in MARCHE:
        if d1 in prix.get(f, {}) and d2 in prix.get(f, {}):
            return f, round(prix[f][d2][0] / prix[f][d1][0] - 1, 4)
    a = [x for x in spy_jours[bisect_left(spy_jours, plus(d1, -PROCHE)):bisect_right(spy_jours, d1)]]
    b = [x for x in spy_jours[bisect_left(spy_jours, plus(d2, -PROCHE)):bisect_right(spy_jours, d2)]]
    if a and b:
        return "SPY~", round(prix["SPY"][b[-1]][0] / prix["SPY"][a[-1]][0] - 1, 4)
    return None, None


def depart(e, essais):
    p = prix.get(e["symbole"], {})
    i = bisect_right(cal, e["jour"].replace("-", ""))
    return next((c for c in cal[i + 1:i + 1 + essais] if c in p), None)


def sortie(p, dep, h):
    """(date de vente, comment) ou None si les prix ne sont pas encore publiés."""
    cible, limite = plus(dep, DUREES[h]), plus(dep, DUREES[h] + TOLERANCE)
    arr = next((c for c in cal[bisect_left(cal, cible):bisect_right(cal, limite)] if c in p), None)
    if arr:
        return arr, "à la date"
    if limite > couvert:
        return None
    fin = plus(cible, SECOURS)
    apres = next((c for c in cal[bisect_right(cal, limite):bisect_right(cal, min(fin, couvert))] if c in p), None)
    if apres:
        return apres, "plus tard (pas de prix à la date)"
    if fin > couvert:
        return None
    avant = [c for c in cal[bisect_right(cal, dep):bisect_left(cal, cible)] if c in p]
    return (avant[-1], "plus tôt (plus aucun prix après)") if avant else (dep, "aucun prix après l'achat")


def position(e, nom_depart, h):
    p = prix.get(e["symbole"], {})
    pos = {"symbole": e["symbole"], "jour": e["jour"], "mois": e["mois"], "note10": e["note10"],
           "taille": e.get("taille"), "duree": h, "depart_regle": nom_depart}
    dep = depart(e, DEPARTS[nom_depart])
    if dep is None:
        return {**pos, "statut": "pas achetée (pas de prix de la SEC)"}
    s = sortie(p, dep, h)
    if s is None:
        return {**pos, "statut": "en attente (prix pas encore publiés)", "depart": dep}
    arr, comment = s
    a, b = p[dep], p[arr]
    r = round(b[0] / a[0] - 1, 4)
    suite = [p[c][0] for c in cal[bisect_left(cal, dep):bisect_right(cal, arr)] if c in p]
    saut = max((max(x / y, y / x) for x, y in zip(suite, suite[1:])), default=1.0)
    f, m = marche_entre(dep, arr)
    nouveau_cusip = a[1] != b[1]
    return {**pos, "statut": "achetée", "depart": dep, "prix_achat": a[0], "sortie": arr, "prix_vente": b[0],
            "comment": comment, "variation": r, "nouveau_cusip": nouveau_cusip, "saut": round(saut, 3),
            "rendement": 0.0 if nouveau_cusip else r, "marche": m, "fonds_marche": f}


positions = {(d, h): [position(e, d, h) for e in entrees] for d in DEPARTS for h in DUREES}
for (d, h), ps in positions.items():
    (TRAVAIL / f"positions_{'strict' if d == 'strict' else 'large'}_{h}.json").write_text(
        json.dumps(ps, ensure_ascii=False), encoding="utf-8")

# Rang de chaque entrée dans son mois (ordre d'arrivée dans la liste « hausse ») : pour « les N premières »
rang = {}
for mo in {e["mois"] for e in entrees}:
    for i, e in enumerate(sorted((e for e in entrees if e["mois"] == mo), key=lambda e: (e["entree"], e["symbole"]))):
        rang[(e["symbole"], e["entree"])] = i
for e in entrees:
    e["rang"] = rang[(e["symbole"], e["entree"])]

SELECTIONS = {
    "toutes": lambda e: True,
    "10 premières du mois": lambda e: e["rang"] < 10,
    "5 premières du mois": lambda e: e["rang"] < 5,
    "3 premières du mois": lambda e: e["rang"] < 3,
    "note de 9 et plus": lambda e: e["note10"] >= 9,
    "note de 10": lambda e: e["note10"] >= 10,
    "petites compagnies": lambda e: e.get("taille") == "petite",
    "petites, note de 9 et plus": lambda e: e.get("taille") == "petite" and e["note10"] >= 9,
}


def mois_de(annee):
    a, b = ANNEES[annee]
    sortie_, m = [], date(int(a[:4]), int(a[5:]), 1)
    while m.isoformat()[:7] <= b:
        sortie_.append(m.isoformat()[:7])
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    return sortie_


def valeur(alloc, r, frais, ecart):
    if not frais and not ecart:
        return alloc * (1 + r)
    return max(0.0, (alloc - frais) * (1 + r) * (1 - ecart) - frais)


def spy_au(jour, apres=True):
    """Le prix du SPY à la 1re date avec un prix à partir de `jour` (ou la dernière avant)."""
    if apres:
        i = bisect_left(spy_jours, jour)
        return spy_jours[i] if i < len(spy_jours) else None
    i = bisect_right(spy_jours, jour)
    return spy_jours[i - 1] if i else None


def case(annee, nom_sel, h, nom_depart):
    mois = mois_de(annee)
    choisies = [(e, p) for e, p in zip(entrees, positions[(nom_depart, h)])
                if e["mois"] in mois and SELECTIONS[nom_sel](e)]
    achetees = [p for _, p in choisies if p["statut"] == "achetée"]
    attente = sum(p["statut"].startswith("en attente") for _, p in choisies)
    nb = len(achetees) + attente
    sortie_ = {"annee": annee, "selection": nom_sel, "duree": h, "depart": nom_depart, "choisies": len(choisies),
               "achetees": len(achetees), "en_attente": attente,
               "pas_achetees": sum(p["statut"].startswith("pas achetée") for _, p in choisies)}
    if nb and attente / nb > EN_ATTENTE_MAX:
        return {**sortie_, "mesurable": False}
    sortie_["mesurable"] = True
    if not achetees:
        return sortie_
    r = [p["rendement"] for p in achetees]
    mk = [p["marche"] for p in achetees if p["marche"] is not None]
    sortie_.update({
        "rendement_moyen": round(mean(r), 4), "rendement_median": round(median(r), 4),
        "marche_moyen": round(mean(mk), 4) if mk else None,
        "ecart_moyen": round(mean(p["rendement"] - p["marche"] for p in achetees if p["marche"] is not None), 4)
        if mk else None,
        "gagnantes": sum(x > 0 for x in r),
        "battent_le_marche": sum(p["marche"] is not None and p["rendement"] > p["marche"] for p in achetees),
        "sans_marche": sum(p["marche"] is None for p in achetees),
        "meilleure": max(((p["symbole"], p["jour"], p["rendement"]) for p in achetees), key=lambda x: x[2]),
        "pire": min(((p["symbole"], p["jour"], p["rendement"]) for p in achetees), key=lambda x: x[2]),
        "rendement_moyen_sans_sauts": round(mean(0.0 if p["saut"] > SAUT_MAX else p["rendement"] for p in achetees), 4),
    })
    cohortes = {mo: [p for p in achetees if p["mois"] == mo] for mo in mois}
    fin = max(p["sortie"] for p in achetees)
    sortie_["derniere_vente"] = fin
    argent = {}
    for nom_cout, (frais, ecart) in COUTS.items():
        etale, etale_spy = 0.0, 0.0
        for mo in mois:
            ps = cohortes[mo]
            if ps:
                etale += sum(valeur(MENSUEL / len(ps), p["rendement"], frais, ecart) for p in ps)
                etale_spy += sum(MENSUEL / len(ps) * (1 + (p["marche"] or 0)) for p in ps)
            else:
                etale += MENSUEL
                etale_spy += MENSUEL
        tranches, tranches_spy = 0.0, 0.0
        for k in range(h):
            v = v_spy = CAPITAL / h
            for i in range(k, len(mois), h):
                ps = cohortes[mois[i]]
                if ps:
                    v = sum(valeur(v / len(ps), p["rendement"], frais, ecart) for p in ps)
                    v_spy = sum(v_spy / len(ps) * (1 + (p["marche"] or 0)) for p in ps)
            tranches += v
            tranches_spy += v_spy
        argent[nom_cout] = {"833_par_mois": round(etale, 2), "833_par_mois_spy_memes_dates": round(etale_spy, 2),
                            "10000_d_un_coup": round(tranches, 2),
                            "10000_d_un_coup_spy_memes_dates": round(tranches_spy, 2)}
    sortie_["argent"] = argent
    return sortie_


def spy_garde(annee, fin, frais):
    """S&P 500 acheté (833 $ au début de chaque mois, ou 10 000 $ au début) et vendu à la date `fin`."""
    mois = mois_de(annee)
    vente = spy_au(fin, apres=False)
    p_fin = prix["SPY"][vente][0]
    parts = 0.0
    for mo in mois:
        achat = spy_au(mo.replace("-", "") + "01")
        parts += (MENSUEL - frais) / prix["SPY"][achat][0]
    achat0 = spy_au(mois[0].replace("-", "") + "01")
    return {"833_par_mois": round(max(0.0, parts * p_fin - frais), 2),
            "10000_d_un_coup": round(max(0.0, (CAPITAL - frais) / prix["SPY"][achat0][0] * p_fin - frais), 2),
            "vente": vente}


cases = []
for annee in ANNEES:
    for h in DUREES:
        for nom_depart in DEPARTS:
            ref = case(annee, "toutes", h, nom_depart)
            fin_commune = ref.get("derniere_vente")
            for nom_sel in SELECTIONS:
                c = case(annee, nom_sel, h, nom_depart)
                if c.get("mesurable") and fin_commune:
                    c["fin_commune"] = fin_commune
                    c["spy_garde"] = {nom: spy_garde(annee, fin_commune, frais) for nom, (frais, _) in COUTS.items()}
                cases.append(c)

(SORTIE / "strategies.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------- Le tableau ----------
def pc(x):
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def argent_txt(x):
    return f"{x:,.0f} $".replace(",", " ")


def trouve(annee, sel, h, dep="strict"):
    return next(c for c in cases if c["annee"] == annee and c["selection"] == sel and c["duree"] == h
                and c["depart"] == dep)


l = ["# Quelle règle aurait fait le plus d'argent ? Rejeu de Radar, juillet 2023 → juin 2026", "",
     f"Entrées « hausse » : {len(entrees)} · prix de la SEC jusqu'au {couvert}. Règles du robot actuel. Dirigeants "
     "(formulaires 4) les 3 années ; 13D seulement depuis décembre 2024 (avant, pas de format XML).", ""]
for titre, cle in (("Rendement moyen par compagnie, moins le S&P 500 aux mêmes dates (sans coûts)", "ecart"),
                   ("Compagnies qui font mieux que le S&P 500 aux mêmes dates", "battent")):
    l += [f"## {titre}", ""]
    for dep in DEPARTS:
        l += [f"### Achat : {'règle de la page Résultats' if dep == 'strict' else 'jusqu’à 10 jours de bourse plus tard'}",
              "", "| Sélection | Durée | " + " | ".join(ANNEES) + " |", "|---|---|" + "---|" * len(ANNEES)]
        for sel in SELECTIONS:
            for h in DUREES:
                cel = []
                for annee in ANNEES:
                    c = trouve(annee, sel, h, dep)
                    if not c.get("mesurable"):
                        cel.append("pas mesurable")
                    elif not c.get("achetees"):
                        cel.append("aucune")
                    elif cle == "ecart":
                        cel.append(f"{pc(c['ecart_moyen'])} ({c['achetees']})")
                    else:
                        cel.append(f"{c['battent_le_marche'] / c['achetees'] * 100:.0f} %")
                l.append(f"| {sel} | {h} mois | " + " | ".join(cel) + " |")
        l.append("")
for nom_cout in ("aucun", "10 $ + écart 1 %"):
    l += [f"## Argent : 833 $ par mois pendant 12 mois (coûts : {nom_cout}) — Radar / S&P 500 acheté et gardé", ""]
    l += ["| Sélection | Durée | " + " | ".join(ANNEES) + " |", "|---|---|" + "---|" * len(ANNEES)]
    for sel in SELECTIONS:
        for h in DUREES:
            cel = []
            for annee in ANNEES:
                c = trouve(annee, sel, h)
                if not c.get("mesurable") or "argent" not in c or "spy_garde" not in c:
                    cel.append("pas mesurable" if not c.get("mesurable") or "argent" in c else "aucune")
                else:
                    cel.append(f"{argent_txt(c['argent'][nom_cout]['833_par_mois'])} / "
                               f"{argent_txt(c['spy_garde'][nom_cout]['833_par_mois'])}")
            l.append(f"| {sel} | {h} mois | " + " | ".join(cel) + " |")
    l.append("")
# Les règles qui font mieux que le S&P 500 aux mêmes dates CHAQUE année mesurable (au moins 2 années)
l += ["## Règles qui font mieux que le S&P 500 aux mêmes dates chaque année mesurable (achat : règle de la page "
      "Résultats ; au moins 2 années)", "", "| Sélection | Durée | Plus faible écart d'une année | Écarts par année |",
      "|---|---|---|---|"]
gagnantes = []
for sel in SELECTIONS:
    for h in DUREES:
        cs = [trouve(annee, sel, h) for annee in ANNEES]
        ok = [c for c in cs if c.get("mesurable") and c.get("achetees") and c.get("ecart_moyen") is not None]
        if len(ok) >= 2 and all(c["ecart_moyen"] > 0 for c in ok):
            gagnantes.append((min(c["ecart_moyen"] for c in ok), sel, h, ok))
for mini, sel, h, ok in sorted(gagnantes, key=lambda x: -x[0]):
    l.append(f"| {sel} | {h} mois | {pc(mini)} | " + " · ".join(f"{c['annee']} {pc(c['ecart_moyen'])} ({c['achetees']})"
                                                                for c in ok) + " |")
if not gagnantes:
    l.append("| aucune | | | |")
l.append("")
l += ["## Comptes", "", f"- Positions (départ strict) par statut et durée : " + str(
    {h: dict(Counter(p["statut"] for p in positions[('strict', h)])) for h in DUREES}),
      f"- Ventes « plus tard » ou « plus tôt » (départ strict) : " + str(
          {h: dict(Counter(p.get("comment") for p in positions[('strict', h)] if p.get("comment"))) for h in DUREES}),
      "", "VERDICT : analyse faite"]
(SORTIE / "tableau.md").write_text("\n".join(l) + "\n", encoding="utf-8")
print("\n".join(l[:40]))
