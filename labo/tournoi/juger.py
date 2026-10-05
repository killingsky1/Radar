"""Tournoi : chaque règle au banc d'essai, ses 2 programmations comparées, et les 3 critères de regles_du_jeu.md.

- labo/tournoi/regles/<id>.py         : la règle programmée par son testeur
- labo/tournoi/regles_verif/<id>.py   : la même règle, reprogrammée sans voir la première (vérificateur)
Les deux doivent donner les MÊMES achats et ventes (id, date d'achat, date de vente). Sinon : « différentes », avec les
premiers écarts, et la règle ne peut pas passer tant que ce n'est pas expliqué et corrigé selon le texte de la règle.

Critères (découverte, juillet 2023 à juin 2026) :
1. portefeuille après frais meilleur que le S&P 500 gardé, chacune des 3 années (juillet à juin) ;
2. écart mensuel avec le S&P 500 : t de 3 ou plus, sur les mois de la période seulement (fins de mois jusqu'au 30 juin) ;
3. au moins 30 achats sur les 3 ans, dont au moins 5 chaque année (une position encore ouverte compte).

Aussi publié (demandé par le critique, AVANT les tests ; ne change pas les critères) : le résultat sur toute la période
contre le S&P 500 (SPY) et contre les petites compagnies (IWM), le nombre d'années gagnées, et ce que sont devenus les
signaux (dont ceux perdus faute de prix de la SEC : un biais possible, les prix n'existant que les jours d'échecs).

Usage : python labo/tournoi/juger.py [--donnees labo/tournoi/donnees] [--sortie labo/tournoi/resultats] [id ...]
"""
import argparse
import json
import math
import sys
import traceback
from bisect import bisect_right
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import banc  # noqa: E402

T_MIN, ACHATS_MIN, ACHATS_ANNEE_MIN = 3.0, 30, 5


def t_mensuel(valeur_jour, d, fin):
    """Écart mensuel portefeuille − SPY (fin de mois à fin de mois), jusqu'à `fin` : (mois, moyenne, t)."""
    spy = d.prix["SPY"]

    def spy_au(jour):
        return spy[1][bisect_right(spy[0], jour) - 1]
    fins = {}
    for j, v in valeur_jour:
        if j <= fin:
            fins[j[:7]] = (j, v)
    points = [valeur_jour[0]] + [fins[m] for m in sorted(fins)]  # le 1er mois compte depuis le 1er jour
    if len(points) > 1 and points[1][0] == points[0][0]:  # 1er jour = fin de son mois : pas de doublon
        points.pop(0)
    e = [(b[1] / a[1] - 1) - (spy_au(b[0]) / spy_au(a[0]) - 1) for a, b in zip(points, points[1:])]
    if len(e) < 3:
        return len(e), None, None
    moy = sum(e) / len(e)
    sd = math.sqrt(sum((x - moy) ** 2 for x in e) / (len(e) - 1))
    return len(e), round(moy, 5), (round(moy / (sd / math.sqrt(len(e))), 2) if sd else None)


def annees_de(periode):
    a, b = int(periode["debut"][:4]), int(periode["fin"][:4])
    return [f"{x}-{x + 1}" for x in range(a, b)]


def rendement(serie, a, b):
    """Rendement d'une série de clôtures (dates, prix) entre les dernières clôtures connues à `a` et à `b`."""
    i, j = bisect_right(serie[0], a) - 1, bisect_right(serie[0], b) - 1
    return round(serie[1][j] / serie[1][i] - 1, 4) if i >= 0 and j >= 0 else None


def passer(regle, d):
    journal = {}
    transactions, valeur_jour, ouvertes = banc.simuler(regle, d, journal=journal)
    s = banc.statistiques(transactions, valeur_jour, d, ouvertes)
    periode = d.periode or {"debut": valeur_jour[0][0], "fin": valeur_jour[-1][0]}
    annees = annees_de(periode)
    mois, moy, t = t_mensuel(valeur_jour, d, periode["fin"])
    par_an = {a: s["annees"].get(a, {}) for a in annees}
    c1 = all(x.get("portefeuille") is not None and x.get("spy_garde") is not None and x["portefeuille"] > x["spy_garde"]
             for x in par_an.values())
    achats = sum(x.get("achats", 0) for x in par_an.values())
    c3 = achats >= ACHATS_MIN and all(x.get("achats", 0) >= ACHATS_ANNEE_MIN for x in par_an.values())
    c2 = t is not None and t >= T_MIN
    dans = [x for x in valeur_jour if x[0] <= periode["fin"]]
    total = {"portefeuille": round(dans[-1][1] / dans[0][1] - 1, 4) if len(dans) > 1 else None,
             "spy": rendement(d.prix["SPY"], dans[0][0], dans[-1][0]) if dans else None,
             "iwm": rendement(d.prix["IWM"], dans[0][0], dans[-1][0]) if dans and "IWM" in d.prix else None,
             "annees_gagnees": sum(1 for x in par_an.values() if x.get("portefeuille") is not None
                                   and x.get("spy_garde") is not None and x["portefeuille"] > x["spy_garde"])}
    return {"stats": s, "mois": mois, "ecart_mensuel_moyen": moy, "t_periode": t, "achats": achats,
            "periode_entiere": total, "signaux": journal,
            "criteres": {"1_bat_spy_chaque_annee": c1, "2_t_3_ou_plus": c2, "3_achats": c3},
            "par_annee": {a: {k: x.get(k) for k in ("achats", "portefeuille", "spy_garde", "ecart_moyen", "t")}
                          for a, x in par_an.items()}}, transactions


def cle(t):
    return (t["id"], t["achat"], t["vente"])


def main():
    a = argparse.ArgumentParser()
    a.add_argument("ids", nargs="*")
    a.add_argument("--donnees", default=str(ICI / "donnees"))
    a.add_argument("--sortie", default=str(ICI / "resultats"))
    a.add_argument("--regles", default=str(ICI / "regles"))
    a.add_argument("--verif", default=str(ICI / "regles_verif"))
    x = a.parse_args()
    d = banc.Donnees(x.donnees)
    sortie = Path(x.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    fichiers = sorted(Path(x.regles).glob("*.py"))
    if x.ids:
        fichiers = [f for f in fichiers if f.stem in x.ids]
    lignes, tous = [], {}
    for f in fichiers:
        r = {"fichier": f.name}
        try:
            regle = banc.charger_regle(f)
            r["id"] = regle.ID
            if getattr(regle, "IMPOSSIBLE", None):  # écartée : impossible sans information du futur ou sans données
                r.update(ecartee=regle.IMPOSSIBLE, passe=False)
                tous[f.stem] = r
                (sortie / f"{f.stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                lignes.append(f"| {f.stem} | ÉCARTÉE : {r['ecartee'][:150]} | | | | | | | | | | non |")
                continue
            res, trans = passer(regle, d)
            r.update(res)
            verif = Path(x.verif) / f.name
            if verif.exists():
                _, trans_v = passer(banc.charger_regle(verif), d)
                a_, b_ = {cle(t) for t in trans}, {cle(t) for t in trans_v}
                r["deux_programmations"] = "identiques" if a_ == b_ else "différentes"
                r["ecarts"] = {"seulement_testeur": sorted(a_ - b_)[:10], "seulement_verificateur": sorted(b_ - a_)[:10],
                               "nombres": [len(a_), len(b_), len(a_ & b_)]}
            else:
                r["deux_programmations"] = "vérificateur absent"
            r["temoin"] = bool(getattr(regle, "TEMOIN", False))  # un témoin sert à comparer : il ne peut pas passer
            r["passe"] = all(r["criteres"].values()) and r["deux_programmations"] == "identiques" and not r["temoin"]
            (sortie / f"{f.stem}.transactions.json").write_text(json.dumps(trans, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — une règle qui plante est notée, les autres continuent
            r.update(erreur=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1500:], passe=False)
        tous[f.stem] = r
        (sortie / f"{f.stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if "erreur" in r:
            lignes.append(f"| {f.stem} | ERREUR : {r['erreur'][:120]} | | | | | | | | | | non |")
            continue
        pa = " · ".join(f"{(v['portefeuille'] or 0) * 100:+.1f} / {(v['spy_garde'] or 0) * 100:+.1f} ({v['achats'] or 0})"
                        for v in r["par_annee"].values())
        c, pe, sg = r["criteres"], r["periode_entiere"], r["signaux"]
        pct = lambda v: "—" if v is None else f"{v * 100:+.1f}"  # noqa: E731
        lignes.append(f"| {f.stem} | {pa} | {pct(pe['portefeuille'])} / {pct(pe['spy'])} / {pct(pe['iwm'])} | "
                      f"{pe['annees_gagnees']} | {sg.get('sans_prix', 0)} sur {sg.get('signaux', 0)} | "
                      f"{r['t_periode']} | {r['achats']} | {'oui' if c['1_bat_spy_chaque_annee'] else 'non'} | "
                      f"{'oui' if c['2_t_3_ou_plus'] else 'non'} | {'oui' if c['3_achats'] else 'non'} | "
                      f"{r['deux_programmations']} | {'témoin' if r.get('temoin') else '**OUI**' if r['passe'] else 'non'} |")
    entete = ["# Tournoi : découverte (juillet 2023 à juin 2026)", "",
              f"Données : `{x.donnees}`. Par année : portefeuille / S&P 500 gardé, en % (achats). Période entière : "
              "portefeuille / S&P 500 / petites compagnies (IWM), en %. t = écart mensuel avec le S&P 500, sur les mois "
              "de la période. Sans prix : signaux jamais achetés faute de prix de la SEC.", "",
              "| Règle | Années | Période entière | Années gagnées | Sans prix | t | Achats | 1. bat le S&P 500 chaque année "
              "| 2. t ≥ 3 | 3. achats | 2 programmations | Passe |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    (sortie / "resume.md").write_text("\n".join(entete + lignes) + "\n", encoding="utf-8")
    (sortie / "tous.json").write_text(json.dumps(tous, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(entete + lignes))


if __name__ == "__main__":
    main()
