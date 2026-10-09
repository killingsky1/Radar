"""Essai hors ligne de la chasse B sur un faux jeu (aucune donnée réelle).
Contrôle positif : chaque mois, ~1 compagnie sur 10 a un achat d'initié (PDG) ; son action fait +2 % de plus que le marché
par mois pendant les 3 mois suivants (caché) : le modèle doit le trouver (corrélation positive chaque année) et le
portefeuille doit réussir le critère du plan. Un fractionnement 4 pour 1 (même code du titre, actions × 4) doit être
repéré. Contrôle négatif : le même jeu sans l'effet : pas de réussite, corrélation moyenne près de 0 (aucune fuite).
Lancement : python labo/chasse2/essai_chasse_b.py"""
import gzip
import json
import math
import random
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ICI = Path(__file__).resolve().parent
N = 160


def ecrire(chemin, lignes):
    with gzip.open(chemin, "wt") as f:
        f.writelines(json.dumps(l) + "\n" for l in lignes)


def fabriquer(dossier, effet, graine=3):
    rnd = random.Random(graine)
    jours, j = [], date(2009, 6, 30)
    while j <= date(2026, 9, 15):
        if j.weekday() < 5:
            jours.append(j)
        j += timedelta(days=1)
    n = len(jours)
    mois = sorted({(x.year, x.month) for x in jours})
    fin_de = {}
    for i, x in enumerate(jours):
        fin_de[(x.year, x.month)] = i
    # les achats d'initiés (dépôt 5 à 15 jours avant une fin de mois) et l'effet caché des 3 mois suivants
    bonus = [[0.0] * n for _ in range(N)]
    inities = []
    for (a, m) in mois:
        i_fin = fin_de[(a, m)]
        for k in range(N):
            if rnd.random() < 0.035:
                depot = jours[max(i_fin - rnd.randint(5, 15), 0)]
                inities.append([depot.isoformat(), str(1000 + k), f"S{k:03d}", "achat", 50000.0, 1000.0, 1, 1, 0, 0, 1, 0,
                                0.2, None])
                if effet:
                    for t in range(i_fin + 1, min(i_fin + 1 + 63, n)):
                        bonus[k][t] += math.log(1.02) / 21
            if rnd.random() < 0.15:
                depot = jours[max(i_fin - rnd.randint(1, 20), 0)]
                inities.append([depot.isoformat(), str(1000 + k), f"S{k:03d}", "vente", 80000.0, 2000.0, 1, 0, 0, 1, 0, 0,
                                None, None])
    inities.sort()
    marche = [100.0]
    for _ in range(n - 1):
        marche.append(marche[-1] * math.exp(0.0003 + 0.01 * rnd.gauss(0, 1)))
    prix = []
    for k in range(N):
        p, serie = rnd.uniform(20, 200), []
        for t in range(n):
            if t:
                p *= (marche[t] / marche[t - 1]) * math.exp(0.017 * rnd.gauss(0, 1) + bonus[k][t])
            serie.append(p)
        if k == 7:  # fractionnement 4 pour 1 le 10 juin 2024, même code du titre
            coupe = jours.index(date(2024, 6, 10))
            serie = serie[:coupe] + [x / 4 for x in serie[coupe:]]
        prix.append({"s": f"S{k:03d}", "d": [int(x.strftime("%Y%m%d")) for x in jours], "p": [round(x, 4) for x in serie],
                     "q": [rnd.randint(0, 5000) for _ in jours], "c": [f"C{k:03d}"] * n})
    for s, mult in (("SPY", 1.0), ("IWM", 0.8)):
        prix.append({"s": s, "d": [int(x.strftime("%Y%m%d")) for x in jours], "p": [round(x * mult, 4) for x in marche],
                     "q": [1] * n, "c": [s] * n})
    dossier.mkdir(parents=True)
    (dossier / "calendrier.json").write_text(json.dumps([x.strftime("%Y%m%d") for x in jours]))
    ecrire(dossier / "prix.jsonl.gz", prix)
    ecrire(dossier / "inities.jsonl.gz", inities)
    ecrire(dossier / "symboles_f4.jsonl.gz", [[str(1000 + k), f"S{k:03d}", f"{a}-{m:02d}", 1] for k in range(N)
                                              for a, m in mois])
    faits = []
    for k in range(N):
        actions = []
        for a in range(2009, 2027):
            for fin_t, depot in (("03-31", "05-10"), ("06-30", "08-10"), ("09-30", "11-10"), ("12-31", "02-20")):
                an_dep = a + 1 if fin_t == "12-31" else a
                nb = 50e6 * (4 if k == 7 and f"{a}-{fin_t}" >= "2024-06-30" else 1)
                actions.append([f"{a}-{fin_t}", nb, f"{an_dep}-{depot}"])
        faits.append({"cik": str(1000 + k), "actions": actions, "finances": {}})
    ecrire(dossier / "faits.jsonl.gz", faits)
    ecrire(dossier / "treize.jsonl.gz", [["2015-01-05", "13D", ["1001"]]])


def lancer(effet):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fabriquer(t / "base", effet)
        subprocess.run([sys.executable, str(ICI / "chasse_b.py"), "--base", str(t / "base"), "--sortie", str(t / "s")],
                       check=True, stdout=subprocess.DEVNULL)
        return json.loads((t / "s" / "resultats.json").read_text())


def main():
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    r = lancer(True)
    m = r["mesures"]
    corr = [x.get("correlation_rang") for x in m.values()]
    verifier("14 années jugées", len(m) == 14, sorted(m))
    # Le signal touche ~1 action sur 10 : corrélation de toute l'année petite (~0,035, erreur ~0,023 par année)
    verifier("signal caché trouvé : corrélation moyenne > 0,02 et positive au moins 12 années sur 14",
             sum(corr) / len(corr) > 0.02 and sum(1 for x in corr if x > 0) >= 12, corr)
    verifier("les 10 meilleurs scores font mieux que l'univers, chaque année",
             all(x["ecart_moyen_10_meilleurs"] > x["ecart_moyen_univers"] for x in m.values()),
             [(x["ecart_moyen_10_meilleurs"], x["ecart_moyen_univers"]) for x in m.values()])
    verifier("fractionnement 4 pour 1 repéré (S007, 10 juin 2024)",
             any(x[0] == "S007" and x[1] == 20240610 and x[2] == 4.0 for x in r["exemples_fractionnements"]),
             r["exemples_fractionnements"])
    verifier("aucun autre fractionnement inventé", r["fractionnements"] == 1, r["fractionnements"])
    verifier("avec le signal caché : le critère du plan est réussi (10 $)", r["10 $"]["reussi"],
             {k: r["10 $"][k] for k in ("total", "examen_2012_2017", "annees_gagnees", "t_mensuel", "criteres")})
    r0 = lancer(False)
    c0 = [x.get("correlation_rang") for x in r0["mesures"].values()]
    moyenne = sum(c0) / len(c0)
    verifier("sans signal : le critère n'est PAS réussi (10 $ et 0 $)", not r0["10 $"]["reussi"] and not r0["0 $"]["reussi"],
             {k: r0["0 $"][k] for k in ("total", "annees_gagnees", "t_mensuel")})
    verifier("sans signal : aucune fuite du futur (corrélation moyenne entre -0,03 et 0,03)", abs(moyenne) < 0.03,
             f"{moyenne:.4f} {c0}")
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
