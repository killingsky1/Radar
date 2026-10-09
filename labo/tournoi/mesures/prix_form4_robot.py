"""Mesure 4 (9 octobre 2026), étape 2 : le prix du formulaire 4 du VRAI code du robot, rejoué sur les vrais fichiers.

Pour chaque achat de dirigeant du jeu (découverte 2023-2026 ou coffre-fort 2016-2023), on refait ce que le robot aurait
su le jour du dépôt (comme regroupements2.py) :
- fichiers d'échecs de livraison publiés avant ce jour ; le prix = le plus récent des 2 derniers (comme le robot) ;
- historique des CUSIP = les fichiers publiés des 400 derniers jours (le départ du robot) ;
- nombre d'actions = le fait dei:EntityCommonStockSharesOutstanding DÉPOSÉ au plus tard ce jour-là, le plus récent ;
- formes des rapports de la compagnie (10-K, 10-Q ou étrangères) ; seuils du NYSE du mois d'avant ;
- formulaires 4 du jeu déposés au plus tard ce jour-là, comme le robot les garde : achats de 25 000 $ et plus, ventes
  de 1 M$ et plus (sec.SEUIL_ACHAT, SEUIL_VENTE) ; « À vérifier » (jamais un prix) si le prix moyen dépasse 2 000 $
  (sauf les actions qui valent vraiment autant), si le montant dépasse 5 G$, s'il manque un prix ou si la transaction
  est datée après le dépôt (contrôles du robot).
Puis le VRAI code du robot (branche travail) : taille.classer sans prix de secours (« 0.27.1 », comme aujourd'hui), et
avec taille.prix_formulaires_4 (« 0.27.2 »), pour chaque garde-fou taille.SAUT_F4_MAX (aucun, 2, 3, 5, 10).

Limites du jeu (comptées dans le résultat) : il n'a pas les notes des déposants (émission, hors bourse, automatique : le
robot en écarte en plus, donc moins de prix de secours, jamais plus) ni le jour de chaque transaction d'un formulaire de
plusieurs jours (toutes prises au dernier jour, au prix moyen du formulaire ; le robot prend celles du dernier jour).

La « vraie » valeur, pour juger seulement (jamais pour décider) : la 1re clôture de la SEC après le dépôt (30 jours ou
moins) × le 1er nombre d'actions déclaré à une date entre le dépôt et 120 jours plus tard (déposé n'importe quand), si
aucun autre CUSIP n'est vu entre ces deux dates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regroupements2 import decision, fusion, lire, seuils_par_mois, symbole  # noqa: E402

TROP_PETITE = 100  # M$, comme score.py
GARDE_FOUS = (None, 2, 3, 5, 10)


def iso8(j):
    j = str(j).replace("-", "")
    return date(int(j[:4]), int(j[4:6]), int(j[6:8]))


def evenement_du_robot(e, sec, titres_vides):
    """L'info du robot faite avec un formulaire 4 du jeu (None : le robot ne la garde pas)."""
    achat = e["sens"] == "achat"
    montant, prix = e.get("montant") or 0, e.get("prix_moyen")
    if not prix or prix <= 0 or not e.get("jour_dernier") or montant < (sec.SEUIL_ACHAT if achat else sec.SEUIL_VENTE):
        return None
    avec_prix = montant / prix  # actions des lignes avec un prix
    s = e["symbole"]
    a_verifier = ((prix > sec.PRIX_MAX and s not in sec.PRIX_ELEVES) or montant > sec.VALEUR_MAX
                  or abs((e.get("actions") or 0) - avec_prix) > max(0.5, 0.001 * avec_prix)
                  or e["jour_dernier"] > e["depot"])
    titres = e.get("titres") or [""]
    if titres == [""]:
        titres_vides[0] += 1
    return {"source": "sec_form4", "kind": "achat_initie" if achat else "vente_initie", "tickers": [s],
            "badge": "a_verifier" if a_verifier else "officiel", "published_on": e["depot"],
            "data": {"hors_bourse": None, "automatique": None, "plusieurs_jours": e.get("jour_premier") != e["jour_dernier"],
                     "transactions": [{"code": "P" if achat else "S", "acquis_cede": "A" if achat else "D",
                                       "date": e["jour_dernier"], "actions": avec_prix / len(titres), "prix": prix,
                                       "titre_valeur": t} for t in titres]}}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--donnees", required=True)
    a.add_argument("--ftd", required=True)
    a.add_argument("--robot", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    sys.path.insert(0, str(Path(x.robot).resolve()))
    from radar.collecteurs import prix_sec as ps
    from radar.collecteurs import sec
    from radar.collecteurs import taille as ta
    defaut = getattr(ta, "SAUT_F4_MAX", None)

    d = Path(x.donnees)
    periode = json.loads((d / "periode.json").read_text())
    evs = [e for e in lire(d / "evenements.jsonl.gz") if e.get("cik") and e.get("symbole")]
    achats = [e for e in evs if e["sens"] == "achat" and periode["debut"] <= e["depot"] <= periode["fin"]]
    voulus = {e["symbole"] for e in achats}
    seuils = seuils_par_mois(Path(x.robot) / "tests" / "fixtures" / "lotL" / "ME_Breakpoints_CSV.zip")

    # Les formulaires 4 tels que le robot les garde, par symbole, rangés par jour de dépôt
    titres_vides = [0]
    f4 = defaultdict(list)
    for e in evs:
        if e["symbole"] in voulus:
            r = evenement_du_robot(e, sec, titres_vides)
            if r:
                f4[e["symbole"]].append(r)
    for v in f4.values():
        v.sort(key=lambda r: r["published_on"])
    depots_f4 = {s: [r["published_on"] for r in v] for s, v in f4.items()}

    # Fichiers d'échecs de livraison (comme regroupements2.py)
    debut_h = (date.fromisoformat(periode["debut"]) - timedelta(days=ta.HISTOIRE_JOURS + 31)).strftime("%Y%m%d")
    cles = sorted(p.stem for p in Path(x.ftd).glob("*.zip") if re.fullmatch(r"\d{6}[ab]", p.stem))
    cles = [c for c in cles if ps.periode(c)[1] >= debut_h]
    resume, prix_f, lignes = {}, {}, defaultdict(list)
    for c in cles:
        rangs = []
        for jour, cusip, s, p in ta.lire_lignes((Path(x.ftd) / f"{c}.zip").read_bytes()):
            s = symbole(s)
            if s in voulus:
                rangs.append((jour, cusip, s, p))
                lignes[s].append((jour, cusip, p))
        r = {}
        ta.ajouter_lignes(r, rangs)  # le vrai code du robot
        resume[c] = r
        pf = {}
        for jour, cusip, s, p in rangs:
            if p is not None and (s not in pf or jour > pf[s][0]):
                pf[s] = [jour, p, cusip]
        prix_f[c] = pf
    for s in lignes:
        lignes[s].sort(key=lambda l: (l[0], l[1]))
    jours_de = {s: [l[0] for l in ls] for s, ls in lignes.items()}
    pub = {c: ps.mise_en_ligne_prevue(ps.periode(c)[0]) for c in cles}
    par_pub = sorted(cles, key=lambda c: (pub[c], c))
    dates_pub = [pub[c] for c in par_pub]

    faits, formes = {}, defaultdict(set)
    for r in lire(d / "finances.jsonl.gz"):
        fs = (r.get("actions") or {}).get("EntityCommonStockSharesOutstanding") or []
        faits[r["cik"]] = [(f[1], f[2], f[4]) for f in fs if f[1] and f[2] and f[4] and f[2] > 0]  # (fin, actions, dépôt)
        for f in fs:
            if len(f) > 5 and f[5]:
                formes[r["cik"]].add(f[5])

    n, ex = Counter(), defaultdict(list)
    juge = defaultdict(Counter)
    ecarts = Counter()
    for e in achats:
        s, cik, X = e["symbole"], e["cik"], date.fromisoformat(e["depot"])
        k = bisect_left(dates_pub, X)  # fichiers publiés AVANT le jour du dépôt
        publies = sorted(par_pub[:k])
        if len(publies) < 2:
            n["pas assez de fichiers publiés"] += 1
            continue
        prix = None
        for c in publies[-2:]:
            p = prix_f[c].get(s)
            if p and (prix is None or p[0] > prix[0]):
                prix = p
        connus = [f for f in faits.get(cik, []) if f[2] <= e["depot"]]
        fin_val = max(connus, key=lambda f: (f[0], f[2])) if connus else None  # (fin, actions, dépôt)
        actions = [fin_val[1], fin_val[0]] if fin_val else None  # comme le robot : [actions, date]
        mois = (X.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        p30, p70 = seuils.get(mois) or seuils[max(m for m in seuils if m <= mois)]
        t = {"seuils": {"mois": mois, "p30": p30, "p70": p70}, "actions": {str(cik): actions} if actions else {},
             "prix": {s: prix} if prix else {}}
        fiche = {"cik": cik, "rapports": sorted(formes.get(cik, set()))}
        limite = (X - timedelta(days=ta.HISTOIRE_JOURS)).strftime("%Y%m%d")
        dans = [c for c in publies if ps.periode(c)[1] >= limite]
        h = fusion(resume[c].get(s, {}) for c in dans)
        cus = {"debut": min(ps.periode(c)[0] for c in dans), "symboles": {s: h} if h else {}}
        r0 = ta.classer(fiche, t, s, X, cus)  # 0.27.1 : comme aujourd'hui
        i = bisect_right(depots_f4.get(s, []), e["depot"])
        j0 = bisect_left(depots_f4.get(s, []), (X - timedelta(days=ta.PRIX_MAX_JOURS + 5)).isoformat())
        candidats = f4.get(s, [])[j0:i]  # déposés au plus tard ce jour-là (le robot filtre lui-même les dates)
        pf4 = ta.prix_formulaires_4(candidats, X)
        r_defaut = ta.classer(fiche, t, s, X, cus, pf4)  # le réglage du robot tel quel (SAUT_F4_MAX du code)
        resultats = {}
        for g in GARDE_FOUS:
            ta.SAUT_F4_MAX = g
            resultats[g] = ta.classer(fiche, t, s, X, cus, pf4)
        ta.SAUT_F4_MAX = defaut
        if defaut in resultats and decision(r_defaut) != decision(resultats[defaut]):
            n["ERREUR : le réglage du robot ne donne pas la même décision que sa variante"] += 1
        sans_prix_sec = (r0.get("raison") or "").startswith("pas de prix de la SEC")
        if not sans_prix_sec:
            n["achats avec un prix de la SEC de 60 jours ou moins, ou inconnus pour une autre raison"] += 1
            # le prix de secours ne doit RIEN changer ici (sauf le texte de la raison « ni de formulaire 4 »)
            if any({k: v for k, v in r.items() if k != "raison"} != {k: v for k, v in r0.items() if k != "raison"}
                   for r in [r_defaut, *resultats.values()]):
                n["ERREUR : résultat changé alors qu'il y avait un prix de la SEC"] += 1
            continue
        n["achats SANS prix de la SEC de 60 jours ou moins (taille inconnue en 0.27.1)"] += 1
        f = pf4.get(s)
        if not f:
            n["  … sans prix de formulaire 4 (reste inconnue)"] += 1
            continue
        n["  … avec un prix de formulaire 4"] += 1
        present = bool(h)
        n[f"  … symbole {'présent' if present else 'ABSENT'} de l'historique des CUSIP (400 jours)"] += 1
        plusieurs = any(r["data"]["plusieurs_jours"] and r["data"]["transactions"][0]["date"].replace("-", "") == f[0]
                        for r in candidats)
        n["  … prix venant d'un formulaire de plusieurs jours (approximé au dernier jour)"] += plusieurs
        r1 = resultats[None]
        if not r1.get("taille"):
            n["  … taille inconnue : changement de CUSIP (époque)"] += 1
        for g in GARDE_FOUS[1:]:
            if r1.get("taille") and not resultats[g].get("taille"):
                n[f"  … écartées par le garde-fou ×{g}"] += 1
        # la « vraie » valeur
        ls = lignes.get(s, [])
        jj = bisect_right(jours_de.get(s, []), X.strftime("%Y%m%d"))
        while jj < len(ls) and ls[jj][2] is None:
            jj += 1
        apres = sorted((fx for fx in faits.get(cik, []) if e["depot"] <= fx[0] <= (X + timedelta(days=120)).isoformat()),
                       key=lambda fx: (fx[0], fx[2]))
        vraie = None
        if apres and jj < len(ls) and iso8(ls[jj][0]) <= X + timedelta(days=30):
            jv, cv, pv = ls[jj]
            fin_v = apres[0][0].replace("-", "")
            a_, b_ = min(jv, fin_v), max(jv, fin_v)
            if not [l for l in ls if a_ <= l[0] <= b_ and l[1] != cv]:
                vraie = apres[0][1] * pv / 1e6
                q = f[1] / pv
                ecarts["prix du formulaire 4 à 25 % ou moins de la vraie clôture" if 0.8 <= q <= 1.25
                       else "prix du formulaire 4 à plus de 25 % de la vraie clôture"] += 1
        if vraie is None:
            n["  … vraie valeur inconnue (pas de clôture de la SEC dans les 30 jours, ou CUSIP changé)"] += 1
            continue
        n["  … vraie valeur connue (jugés)"] += 1
        vrai = (vraie < TROP_PETITE, vraie < p30, "petite" if vraie < p30 else "grande" if vraie >= p70 else "moyenne")
        cle_h = "présent" if present else "absent"
        regles = {"0.27.1 (aujourd'hui)": r0, f"0.27.2 réglage du robot (garde-fou {defaut})": r_defaut}
        for g in GARDE_FOUS:
            nom = f"0.27.2 garde-fou {'aucun' if g is None else '×' + str(g)}"
            regles[nom] = resultats[g]
            regles[nom + ", symbole absent = inconnue"] = resultats[g] if present else r0
        for nom, r in regles.items():
            ecartee, bonus, taille = decision(r)
            for cle in ("tous", f"historique {cle_h}"):
                c = juge[f"{nom} | {cle}"]
                c["achats jugés"] += 1
                c["taille inconnue"] += taille is None
                c["taille juste"] += taille == vrai[2]
                c["taille fausse"] += taille is not None and taille != vrai[2]
                c["gardée à tort (vraie valeur sous 100 M$)"] += vrai[0] and not ecartee
                c["écartée à tort (vraie valeur de 100 M$ ou plus)"] += ecartee and not vrai[0]
                c["bonus petite à tort"] += bonus and not vrai[1]
                c["bonus petite manqué"] += vrai[1] and not bonus
            if nom == "0.27.2 garde-fou aucun":
                for err, oui in (("écartée à tort", ecartee and not vrai[0]), ("bonus à tort", bonus and not vrai[1]),
                                 ("taille fausse", taille and taille != vrai[2])):
                    if oui and len(ex[f"erreur 0.27.2 : {err}"]) < 25:
                        ex[f"erreur 0.27.2 : {err}"].append({
                            "symbole": s, "depot": e["depot"], "actions": actions, "prix_f4": f, "historique": h,
                            "dernier_prix_sec": prix, "classe": {k: r.get(k) for k in ("taille", "valeur_m", "note")},
                            "vraie_cloture": list(ls[jj][:3]), "vraie_valeur_m": round(vraie, 1), "vraie_taille": vrai[2],
                            "garde_fous": {str(g): bool(resultats[g].get("taille")) for g in GARDE_FOUS[1:]}})
        if r1.get("taille") and len(ex["exemples 0.27.2 justes"]) < 10 and r1["taille"] == vrai[2]:
            ex["exemples 0.27.2 justes"].append({"symbole": s, "depot": e["depot"], "prix_f4": f, "valeur_m": r1["valeur_m"],
                                                 "vraie_valeur_m": round(vraie, 1), "taille": vrai[2]})
    n["formulaires du jeu sans nom de titre (aucun prix de secours)"] = titres_vides[0]
    sortie = {"periode": periode, "garde_fou_du_robot": defaut,
              "fichiers_lus": [cles[0], cles[-1], len(cles)] if cles else [], "compte": dict(n),
              "ecarts_de_prix": dict(ecarts), "juge": {k: dict(v) for k, v in sorted(juge.items())}, "exemples": ex}
    Path(x.sortie).write_text(json.dumps(sortie, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"compte": dict(n), "ecarts_de_prix": dict(ecarts),
                      "juge": {k: dict(v) for k, v in sorted(juge.items()) if k.endswith("| tous")}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
