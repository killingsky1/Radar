"""Essai hors ligne de rapports_a.py avec une fausse SEC (aucune requête réelle) : en-tête XBRL caché retiré,
similarité cosinus, fenêtre de 300 à 430 jours, reprise après arrêt, arrêt sur 403, robots.txt.
Lancement : python labo/chasse2/essai_rapports_a.py"""
import gzip
import json
import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ICI = Path(__file__).resolve().parent
os.environ.setdefault("TOURNOI_ROBOT", str((ICI.parent.parent / "principal" / "robot").resolve()))
sys.path.insert(0, str(ICI))


class Rep:
    def __init__(self, c):
        self.contenu = c


def main():
    import rapports_a as r
    from radar.http import ErreurSource
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    doc = lambda corps, cache="": f"<html><body>{cache}<p>{corps}</p></body></html>".encode()
    xbrl = "<ix:header><ix:hidden>us-gaap:Assets 123 contexte unite</ix:hidden></ix:header>"
    pages = {"https://www.sec.gov/robots.txt": b"User-agent: *\nAllow: /Archives/edgar/data\nDisallow: /cgi-bin\n"}
    textes = {("1", "a1"): "risque vente risque client", ("1", "a2"): "risque vente risque client",
              ("1", "a3"): "litige nouveau dirigeant depart", ("2", "b1"): "alpha beta", ("2", "b2"): "alpha gamma"}
    dix_k = {"1": [["2015-02-01", "a1", "x.htm", ""], ["2016-02-03", "a2", "x.htm", ""], ["2017-02-01", "a3", "x.htm", ""]],
             "2": [["2015-03-01", "b1", "y.htm", ""], ["2017-03-01", "b2", "y.htm", ""], ["2017-04-01", "b3", "", ""]]}
    for cik, liste in dix_k.items():
        for depot, acc, d, _ in liste:
            if d:
                pages[f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{d}"] = doc(textes[(cik, acc)], xbrl if acc == "a2" else "")
    demandes = []

    class Client:
        def get(self, url):
            demandes.append(url)
            v = pages.get(url)
            if v is None:
                raise ErreurSource(f"{url} : HTTP 404")
            if isinstance(v, int):
                raise ErreurSource(f"{url} : HTTP {v}")
            return Rep(v)
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "base").mkdir()
        with gzip.open(t / "base" / "cies.jsonl.gz", "wt") as f:
            for cik, liste in dix_k.items():
                f.write(json.dumps({"cik": cik, "dix_k": liste}) + "\n")
        (t / "a").mkdir()
        (t / "a" / "compagnies.json").write_text(json.dumps(["1", "2"]))
        r.CLIENT = Client()
        sys.argv = ["x", "--base", str(t / "base"), "--dossier", str(t / "a")]
        r.main()
        res = [json.loads(l) for l in (t / "a" / "similarites.jsonl").read_text().splitlines()]
        par = {(x["cik"], x["acc"]): x for x in res}
        verifier("1er 10-K : pas de précédent", par[("1", "a1")]["similarite"] is None, par[("1", "a1")])
        verifier("même texte un an plus tard (en-tête XBRL caché retiré) : similarité 1", par[("1", "a2")]["similarite"] == 1.0,
                 par[("1", "a2")])
        verifier("texte tout changé : similarité 0", par[("1", "a3")]["similarite"] == 0.0, par[("1", "a3")])
        verifier("précédent 730 jours avant (hors 300-430) : pas de similarité", par[("2", "b2")]["similarite"] is None,
                 par[("2", "b2")])
        verifier("10-K sans document principal : sauté", ("2", "b3") not in par, sorted(par))
        verifier("le mot caché du XBRL (contexte) n'est pas compté", par[("1", "a2")]["mots"] == 4, par[("1", "a2")]["mots"])
        n = len(demandes)
        sys.argv = ["x", "--base", str(t / "base"), "--dossier", str(t / "a")]
        r.main()
        verifier("reprise : rien n'est relu (seulement robots.txt)", len(demandes) == n + 1, demandes[n:])
        # 403 : arrêt immédiat
        (t / "a2").mkdir()
        (t / "a2" / "compagnies.json").write_text(json.dumps(["1", "2"]))
        pages["https://www.sec.gov/Archives/edgar/data/1/a2/x.htm"] = 403
        sys.argv = ["x", "--base", str(t / "base"), "--dossier", str(t / "a2")]
        try:
            r.main()
            arret = False
        except SystemExit as exc:
            arret = "INTERDIT" in str(exc)
        verifier("403 : arrêt immédiat sans contourner", arret, arret)
        # robots.txt qui interdit EDGAR : arrêt avant toute lecture
        pages["https://www.sec.gov/robots.txt"] = b"User-agent: *\nDisallow: /Archives/\n"
        (t / "a3").mkdir()
        (t / "a3" / "compagnies.json").write_text(json.dumps(["1"]))
        avant = len(demandes)
        sys.argv = ["x", "--base", str(t / "base"), "--dossier", str(t / "a3")]
        try:
            r.main()
            arret = False
        except SystemExit:
            arret = True
        verifier("robots.txt interdit EDGAR : arrêt, aucun document lu", arret and demandes[avant:] == ["https://www.sec.gov/robots.txt"],
                 demandes[avant:])
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
