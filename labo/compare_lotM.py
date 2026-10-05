"""Lot M : le rejeu de 3 ans AVANT (score-8) et APRÈS (score-9 : les compagnies de moins de 100 M$ en bourse n'entrent
plus dans la liste « hausse »), avec le même code d'analyse (strategies.py) et les mêmes prix de la SEC.

Usage : python labo/compare_lotM.py <dossier d'avant> <dossier d'après>
Lit entrees.json et strategies.json des deux rejeux, et rejeu/positions_strict_{1,3}.json (celles d'après, dans l'ordre
de entrees.json) pour mesurer les compagnies qui entrent à la place des écartées.
Sortie : <après>/comparaison_lotM.md et comparaison_lotM.json
"""
import json
import sys
from datetime import date
from pathlib import Path
from statistics import median

avant, apres = Path(sys.argv[1]), Path(sys.argv[2])
TRAVAIL = Path("rejeu")
ANNEES = ["2023-2024", "2024-2025", "2025-2026"]


def lire(d, nom):
    return json.loads((d / nom).read_text(encoding="utf-8"))


def annee(jour):
    j = date.fromisoformat(jour)
    return f"{j.year}-{j.year + 1}" if j.month >= 7 else f"{j.year - 1}-{j.year}"


def cle(e):
    return e["symbole"], e["entree"][:10]


def case(cases, an, h, sel="toutes"):
    return next(c for c in cases if c["annee"] == an and c["selection"] == sel and c["duree"] == h
                and c["depart"] == "strict")


def pc(x):
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",").replace("-", "−")


def part(c):
    return f"{c['battent_le_marche'] * 100 // c['achetees']} %" if c.get("achetees") else "—"


def argent(c, couts):
    a = (c.get("argent") or {}).get(couts) or {}
    x, s = a.get("833_par_mois"), a.get("833_par_mois_spy_memes_dates")
    return "—" if x is None else f"{x:,.0f} $ (S&P {s:,.0f} $)".replace(",", " ")


ea, ep = lire(avant, "entrees.json"), lire(apres, "entrees.json")
ca, cp = lire(avant, "strategies.json"), lire(apres, "strategies.json")
cles_a, cles_p = {cle(e) for e in ea}, {cle(e) for e in ep}
retirees = [e for e in ea if cle(e) not in cles_p]
ajoutees = [(i, e) for i, e in enumerate(ep) if cle(e) not in cles_a]
pos = {h: lire(TRAVAIL, f"positions_strict_{h}.json") for h in (1, 3)}
assert all(len(pos[h]) == len(ep) for h in pos), "positions et entrées pas alignées"

l = ["# Lot M : rejeu de 3 ans avant et après la règle des 100 M$", "",
     "Avant : score-8 (rejeu du labo, labo/rejeu3). Après : score-9, le robot de la branche travail appelé tel quel. "
     "Mêmes jours, mêmes infos, mêmes prix de la SEC, même analyse (strategies.py). Écart = rendement (CUSIP estimé) "
     "moins le S&P 500 aux mêmes dates, sans frais ; « bat » = part des achetées qui battent le S&P 500.", ""]
sortie = {"annees": {}}
l += ["## Entrées dans la liste « hausse »", "", "| Année | Avant | Après | Retirées | dont moins de 100 M$ | Ajoutées |",
      "|---|---|---|---|---|---|"]
for an in ANNEES:
    r = [e for e in retirees if annee(e["entree"][:10]) == an]
    petites = [e for e in r if e.get("valeur_m") is not None and e["valeur_m"] < 100]
    a = [e for _, e in ajoutees if annee(e["entree"][:10]) == an]
    n_a = sum(annee(e["entree"][:10]) == an for e in ea)
    n_p = sum(annee(e["entree"][:10]) == an for e in ep)
    l.append(f"| {an} | {n_a} | {n_p} | {len(r)} | {len(petites)} | {len(a)} |")
    sortie["annees"][an] = {"avant": n_a, "apres": n_p, "retirees": len(r), "retirees_moins_de_100": len(petites),
                            "ajoutees": len(a)}
restent = [e for e in ep if e.get("valeur_m") is not None and e["valeur_m"] < 100]
l += ["", f"Entrées d'après sous 100 M$ (devrait être 0) : {len(restent)}"
      + (" — " + ", ".join(f"{e['symbole']} {e['entree'][:10]} {e['valeur_m']}" for e in restent[:10]) if restent else ""),
      ""]
sortie["apres_sous_100"] = len(restent)

for h in (1, 3):
    l += [f"## Garder {h} mois (départ strict, sans frais)", "",
          "| Année | Achetées avant → après | Écart moyen avant → après | Écart médian avant → après | Bat le S&P avant → après |",
          "|---|---|---|---|---|"]
    for an in ANNEES:
        x, y = case(ca, an, h), case(cp, an, h)
        if not x.get("mesurable") or not y.get("mesurable"):
            l.append(f"| {an} | pas encore mesurable | | | |")
            continue
        l.append(f"| {an} | {x['achetees']} → {y['achetees']} | {pc(x['ecart_moyen_estime'])} → "
                 f"{pc(y['ecart_moyen_estime'])} | {pc(x['ecart_median_estime'])} → {pc(y['ecart_median_estime'])} | "
                 f"{part(x)} → {part(y)} |")
        sortie["annees"][an][f"{h}_mois"] = {
            k: [x.get(k), y.get(k)] for k in ("achetees", "ecart_moyen_estime", "ecart_median_estime", "battent_le_marche")}
    l.append("")

l += ["## Argent : 833 $ par mois répartis sur les nouvelles entrées du mois, garder 1 mois", "",
      "| Année | Sans frais avant → après | 10 $ par transaction avant → après |", "|---|---|---|"]
for an in ANNEES:
    x, y = case(ca, an, 1), case(cp, an, 1)
    l.append(f"| {an} | {argent(x, 'aucun')} → {argent(y, 'aucun')} | {argent(x, '10 $')} → {argent(y, '10 $')} |")
l.append("")

l += ["## Les compagnies qui entrent à la place des écartées", "",
      "| Année | Garder 1 mois : n · écart médian · bat le S&P | Garder 3 mois : n · écart médian · bat le S&P |",
      "|---|---|---|"]
for an in ANNEES:
    morceaux = []
    for h in (1, 3):
        ec = [round(pos[h][i]["rendement_estime"] - pos[h][i]["marche"], 4) for i, e in ajoutees
              if annee(e["entree"][:10]) == an and pos[h][i]["statut"] == "achetée" and pos[h][i]["marche"] is not None]
        morceaux.append(f"{len(ec)} · {pc(median(ec))} · {sum(v > 0 for v in ec) * 100 // len(ec)} %" if ec else "—")
        sortie["annees"][an][f"ajoutees_{h}_mois"] = ec
    l.append(f"| {an} | {morceaux[0]} | {morceaux[1]} |")
l += ["", "Les écartées elles-mêmes (moins de 100 M$) sont mesurées dans facteurs.md du rejeu d'avant "
      "(« Valeur en bourse = moins de 100 M$ »)."]

(apres / "comparaison_lotM.md").write_text("\n".join(l) + "\n", encoding="utf-8")
(apres / "comparaison_lotM.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("\n".join(l))
