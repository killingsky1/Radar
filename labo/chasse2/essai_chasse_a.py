"""Essai hors ligne de la chasse A sur un faux jeu (aucune donnée réelle).
Chaque compagnie dépose un 10-K par année (similarité au hasard). Contrôle positif : un 10-K dans les 20 % les plus hauts
(similarité ≥ 0,9) est suivi d'une hausse cachée de 20 % de plus que le marché en 252 jours : la chasse doit réussir.
Contrôle négatif : sans la hausse, elle ne doit pas réussir. Aucune fuite : le seuil d'un 10-K ne dépend que des 10-K
d'avant. Lancement : python labo/chasse2/essai_chasse_a.py"""
import gzip
import json
import math
import random
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import essai_chasse_b as eb  # noqa: E402  le faux jeu de la chasse B (prix, symboles, actions)


def fabriquer(dossier, effet, graine=9):
    eb.fabriquer(dossier, effet=False, graine=graine)
    rnd = random.Random(graine)
    with gzip.open(dossier / "prix.jsonl.gz", "rt") as f:
        prix = [json.loads(l) for l in f]
    sims = []
    for x in prix:
        if not (len(x["s"]) == 4 and x["s"][0] == "S" and x["s"][1:].isdigit()):
            continue
        k = int(x["s"][1:])
        cik = str(1000 + k)
        jours = x["d"]
        p = x["p"]
        mult = [1.0] * len(jours)
        for an in range(2009, 2027):
            depot = date(an, 2, 1 + (k % 25))
            if depot > date(2026, 6, 30):
                continue
            s = round(rnd.uniform(0.5, 1.0), 6) if an > 2009 else None
            sims.append({"cik": cik, "depot": depot.isoformat(), "acc": f"{cik}-{an}", "mots": 1000, "similarite": s})
            if effet and s is not None and s >= 0.9:
                i0 = next((i for i, d in enumerate(jours) if d > int(depot.strftime("%Y%m%d"))), None)
                if i0 is None:
                    continue
                for i in range(i0, len(jours)):
                    mult[i] *= math.exp(math.log(1.2) * min(i - i0 + 1, 252) / 252)
        x["p"] = [round(v * m, 4) for v, m in zip(p, mult)]
    with gzip.open(dossier / "prix.jsonl.gz", "wt") as f:
        f.writelines(json.dumps(x) + "\n" for x in prix)
    (dossier / "similarites.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sims))


def lancer(effet):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fabriquer(t / "base", effet)
        subprocess.run([sys.executable, str(ICI / "chasse_a.py"), "--base", str(t / "base"), "--similarites",
                        str(t / "base" / "similarites.jsonl"), "--sortie", str(t / "s")], check=True, stdout=subprocess.DEVNULL)
        return json.loads((t / "s" / "resultats.json").read_text())


def main():
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    import chasse_a
    # Aucune fuite : changer les similarités FUTURES ne change pas le seuil d'un 10-K
    fins = [20150130, 20150227, 20150331, 20160129, 20160226, 20160331, 20170131, 20170228]
    univers = {m: {str(i): (f"S{i}", 5000.0) for i in range(80)} for m in fins}
    sims = [{"cik": str(i), "depot": f"{an}-02-{10 + i % 15:02d}", "similarite": random.Random(i + an).random()}
            for i in range(80) for an in (2015, 2016, 2017)]
    a = {(x["cik"], x["jour"]): x["seuil"] for x in chasse_a.signaux(sims, univers, fins)}
    sims2 = [dict(s, similarite=0.0) if s["depot"] >= "2017-01-01" else s for s in sims]
    b = {(x["cik"], x["jour"]): x["seuil"] for x in chasse_a.signaux(sims2, univers, fins)}
    avant_2017 = [k for k in a if k[1] < 20170101]
    verifier("aucune fuite : seuils d'avant 2017 identiques quand on change les similarités de 2017",
             avant_2017 and all(a[k] == b[k] for k in avant_2017) and any(a[k] is not None for k in avant_2017),
             len(avant_2017))
    r = lancer(True)
    pc = r["pour_comprendre"]
    mieux = [an for an, d in pc.items() if d.get("signal", {}).get("moyenne") is not None and d.get("autres", {}).get("moyenne")
             is not None and d["signal"]["moyenne"] > d["autres"]["moyenne"]]
    verifier("signaux : environ 20 % des 10-K de l'univers", 0.12 < r["signaux"] / r["dix_k_de_l_univers"] < 0.28,
             (r["signaux"], r["dix_k_de_l_univers"]))
    verifier("pour comprendre : les signaux font mieux que les autres chaque année mesurée", len(mieux) == len(pc) and len(pc) >= 12,
             {an: (d.get("signal", {}).get("moyenne"), d.get("autres", {}).get("moyenne")) for an, d in pc.items()})
    verifier("avec la hausse cachée : le critère du plan est réussi (10 $)", r["10 $"]["reussi"],
             {k: r["10 $"][k] for k in ("total", "examen_2012_2017", "annees_gagnees", "t_mensuel", "criteres", "ordres")})
    r0 = lancer(False)
    verifier("sans hausse : le critère n'est PAS réussi (10 $ et 0 $)", not r0["10 $"]["reussi"] and not r0["0 $"]["reussi"],
             {k: r0["0 $"][k] for k in ("total", "annees_gagnees", "t_mensuel")})
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
