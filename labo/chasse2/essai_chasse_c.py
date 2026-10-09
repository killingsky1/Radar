"""Essai hors ligne de la chasse C sur un faux jeu (aucune donnée réelle).
Contrôle positif : 9 épisodes d'achats en masse des initiés (2012 à 2025), chacun suivi d'une hausse cachée de SPY
(+25 % en 126 jours) : la chasse doit passer à SSO après chaque épisode et réussir le critère du plan.
Contrôle négatif : les mêmes épisodes, sans hausse après : elle ne doit pas réussir.
Lancement : python labo/chasse2/essai_chasse_c.py"""
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
EPISODES = ["2012-10-01", "2014-03-03", "2015-09-01", "2017-02-01", "2018-12-03", "2020-06-01", "2021-11-01",
            "2023-06-01", "2025-01-06"]


def fabriquer(dossier, hausse, graine=5, fractionner=False):
    rnd = random.Random(graine)
    jours, j = [], date(2006, 1, 2)
    while j <= date(2026, 9, 15):
        if j.weekday() < 5:
            jours.append(j)
        j += timedelta(days=1)
    pos = {x: i for i, x in enumerate(jours)}
    debuts = [pos[date.fromisoformat(e)] for e in EPISODES]
    spy, sso, p, q = [], [], 100.0, 100.0
    for i in range(len(jours)):
        r = rnd.gauss(0.0003, 0.011)
        if hausse and any(d <= i < d + 126 for d in debuts):
            r += math.log(1.25) / 126
        p *= math.exp(r)
        q *= 1 + 2 * (math.exp(r) - 1)
        spy.append(p)
        sso.append(q)
    lignes, cik = [], 0
    for i, x in enumerate(jours):
        en_masse = any(d - 25 <= i < d for d in debuts)
        for _ in range(rnd.randint(25, 35)):  # ventes
            cik += 1
            lignes.append([x.isoformat(), str(cik % 4000), "X", "vente"] + [None] * 10)
        for _ in range(rnd.randint(40, 60) if en_masse else rnd.randint(6, 12)):  # achats
            cik += 1
            lignes.append([x.isoformat(), str(cik % 4000), "X", "achat"] + [None] * 10)
    dossier.mkdir(parents=True)
    with gzip.open(dossier / "inities.jsonl.gz", "wt") as f:
        f.writelines(json.dumps(l) + "\n" for l in lignes)
    cal = [int(x.strftime("%Y%m%d")) for x in jours if x >= date(2009, 6, 30)]
    (dossier / "calendrier.json").write_text(json.dumps([str(x) for x in cal]))
    with gzip.open(dossier / "prix.jsonl.gz", "wt") as f:
        for s, serie in (("SPY", spy), ("SSO", sso)):
            d = [int(x.strftime("%Y%m%d")) for x in jours if x >= date(2009, 6, 30)]
            pr = [round(serie[pos[x]] / (2 if s == "SSO" and fractionner and x >= date(2022, 1, 13) else 1), 4)
                  for x in jours if x >= date(2009, 6, 30)]  # SSO fractionné 2 pour 1 le 13 janvier 2022, même code
            f.write(json.dumps({"s": s, "d": d, "p": pr, "q": [1] * len(d), "c": [s] * len(d)}) + "\n")


def lancer(hausse, fractionner=False):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fabriquer(t / "base", hausse, fractionner=fractionner)
        subprocess.run([sys.executable, str(ICI / "chasse_c.py"), "--base", str(t / "base"), "--sortie", str(t / "s")],
                       check=True, stdout=subprocess.DEVNULL)
        return json.loads((t / "s" / "resultats.json").read_text())


def main():
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    r = lancer(True)
    e = r["10 $"]["episodes"]

    def tenu_le(jour):  # SSO tenu ce jour-là ? (un pari va de son début à sa fin, renouvellements compris)
        return any(x["debut"] <= jour < x.get("fin", "9999") for x in e)
    verifier("chaque hausse cachée commence pendant un pari (SSO tenu le jour de l'épisode)",
             all(tenu_le(ep) for ep in EPISODES), [(ep, tenu_le(ep)) for ep in EPISODES])
    verifier("vraies clôtures de SSO utilisées (couverture complète)", r["10 $"]["sso"]["source"] == "vraies clôtures de SSO",
             r["10 $"]["sso"])
    verifier("avec la hausse cachée : le critère du plan est réussi (10 $)", r["10 $"]["reussi"],
             {k: r["10 $"][k] for k in ("total", "annees_gagnees", "t_mensuel", "criteres")})
    # Aucune fuite du futur : la météo d'un jour est la même si on efface tous les dépôts de ce jour et d'après
    sys.path.insert(0, str(ICI))
    import chasse_c
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fabriquer(t / "base", True)
        complete = chasse_c.meteo(t / "base")
        lignes = gzip.open(t / "base" / "inities.jsonl.gz", "rt").read().splitlines()
        memes = []
        for jour in ("2012-09-17", "2018-11-20", "2024-12-16"):
            (t / jour).mkdir()
            with gzip.open(t / jour / "inities.jsonl.gz", "wt") as f:
                f.writelines(l + "\n" for l in lignes if json.loads(l)[0] < jour)
            memes.append(chasse_c.meteo(t / jour, jusqu_a=jour)[jour] == complete[jour])
    verifier("aucune fuite du futur : météo identique sans les dépôts du jour et d'après (3 jours testés)", all(memes), memes)
    rf = lancer(True, fractionner=True)
    verifier("SSO fractionné 2 pour 1 (même code) : repéré, et le résultat est identique au même jeu sans fractionnement",
             [x[1:] for x in rf["fractionnements_sso"]] == [[20220113, 2.0]]
             and abs(rf["10 $"]["total"]["portefeuille"] - r["10 $"]["total"]["portefeuille"]) < 1e-3,
             (rf["fractionnements_sso"], rf["10 $"]["total"], r["10 $"]["total"]))
    r0 = lancer(False)
    verifier("sans hausse après les épisodes : le critère n'est PAS réussi", not r0["10 $"]["reussi"] and not r0["0 $"]["reussi"],
             {k: r0["10 $"][k] for k in ("total", "annees_gagnees", "t_mensuel")})
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
