"""Essai hors ligne de donnees2.py : faux caches (tournoi et chasse 2) + fausse SEC, aucune requête réelle.
Lancement : python labo/chasse2/essai_donnees2.py"""
import gzip
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
os.environ.setdefault("TOURNOI_ROBOT", str((ICI.parent.parent / "principal" / "robot").resolve()))
ENTETE = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"


def zip_de(fichiers):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, v in fichiers.items():
            z.writestr(n, v)
    return b.getvalue()


def ftd(lignes):
    return zip_de({"x.txt": "\n".join([ENTETE] + lignes)})


def ecrire(chemin, contenu):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)


def depot(acc, depose, cik, symbole, code, titre, role):
    return {acc: {"s": [depose, cik, symbole, "Cie", None],
                  "l": [[1, code, depose, 100.0, 10.0, "A" if code == "P" else "D", 1000.0, "D", "Common Stock"]],
                  "p": [["9" + cik, "Initié", role, titre]]}}


class Rep:
    def __init__(self, c):
        self.contenu = c


def main():
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    sys.path.insert(0, str(ICI))
    import donnees2 as d2
    t = d2.t
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ct, c2 = tmp / "cache", tmp / "cache2"
        d2.CACHE_T, d2.CACHE2, d2.BASE, d2.SORTIE = ct, c2, c2 / "base", tmp / "sortie"
        d2.INITIES, d2.TREIZE, d2.PRIX_DEBUT = ("2012q3", "2012q4"), ("2012q3", "2015q2"), "201210a"
        # initiés (cache du tournoi) : un PDG qui achète AAA, un administrateur qui vend BBB
        ecrire(ct / "tournoi/ds/2012q3.json.gz", gzip.compress(json.dumps(
            depot("0001-12-000001", "2012-08-01", "11", "AAA", "P", "Chief Executive Officer", "officer")).encode()))
        ecrire(ct / "tournoi/ds/2012q4.json.gz", gzip.compress(json.dumps(
            depot("0001-12-000002", "2012-11-05", "22", "bbb", "S", "", "director")).encode()))
        # finances (companyfacts du tournoi) : 2 compagnies, une sans faits utiles
        faits = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2012-06-30", "val": 1000000, "filed": "2012-08-01"}]}}},
            "us-gaap": {"Assets": {"units": {"USD": [{"end": "2012-06-30", "val": 5e6, "filed": "2012-08-01",
                                                       "form": "10-Q", "accn": "a1"}]}}}}}
        ecrire(ct / "tournoi/companyfacts.zip", zip_de({"CIK0000000011.json": json.dumps(faits),
                                                        "CIK0000000022.json": json.dumps({"facts": {}})}))
        # 13 : 2015q2 dans le cache du tournoi, le reste lu sur la fausse SEC
        ecrire(ct / "tournoi/13/2015q2.json.gz", gzip.compress(json.dumps([["2015-04-02", "13G", ["11"]]]).encode()))
        # submissions (cache de la chasse 2) : 10-K sur 2 pages pour la compagnie 11
        principal = {"name": "Cie 11", "sic": "3571", "tickers": ["AAA"], "exchanges": ["Nasdaq"], "filings": {"recent": {
            "form": ["10-K", "10-Q"], "filingDate": ["2013-02-01", "2013-05-01"], "accessionNumber": ["x1", "x2"],
            "primaryDocument": ["a.htm", "b.htm"], "reportDate": ["2012-12-31", "2013-03-31"]}, "files": []}}
        page2 = {"form": ["10-K"], "filingDate": ["2012-02-01"], "accessionNumber": ["x0"], "primaryDocument": ["z.htm"],
                 "reportDate": ["2011-12-31"]}
        ecrire(c2 / "submissions.zip", zip_de({"CIK0000000011.json": json.dumps(principal),
                                               "CIK0000000011-submissions-001.json": json.dumps(page2),
                                               "CIK0000000033.json": json.dumps({"name": "Sans 10-K", "filings": {
                                                   "recent": {"form": ["8-K"], "filingDate": ["2013-01-01"],
                                                              "accessionNumber": ["y"], "primaryDocument": ["y.htm"]}}})}))
        # prix : 201210b dans le cache du tournoi, 201210a et 201211a sur la fausse SEC (autour de Sandy)
        ecrire(ct / "ftd/201210b.zip", ftd(["20121031|C1|AAA|10|AAA INC|21.0", "20121031|S|SPY|5|SPDR|141.0",
                                            "20121031|I|IWM|5|ISHARES|80.0"]))
        page = ('<a href="/files/data/fails-deliver-data/cnsfails201210a.zip">a</a>'
                '<a href="/files/data/fails-deliver-data/cnsfails201210b.zip">b</a>'
                '<a href="/files/data/fails-deliver-data/cnsfails201211a.zip">c</a>'
                '<a href="/files/data/fails-deliver-data/cnsfails201209b.zip">avant</a>')
        idx = "CIK|Company Name|Form Type|Date Filed|Filename\n----\n11|Cie|SC 13D|2012-09-04|edgar/data/11/0009-12-1.txt\n" \
              "99|Fonds|SC 13D|2012-09-04|edgar/data/11/0009-12-1.txt\n"
        pages = {t.prix_sec.PAGE: page.encode(),
                 "https://www.sec.gov/files/data/fails-deliver-data/cnsfails201210a.zip": ftd(
                     ["20121026|C1|AAA|10|AAA INC|20.0", "20121026|S|SPY|5|SPDR|140.0", "20121026|I|IWM|5|ISHARES|79.0",
                      "20121026|Z|ZZZ|7|ZZZ CORP|3.0"]),
                 "https://www.sec.gov/files/data/fails-deliver-data/cnsfails201211a.zip": ftd(
                     ["20121101|C1|AAA|10|AAA INC|22.0", "20121101|S|SPY|5|SPDR|142.0", "20121101|I|IWM|5|ISHARES|81.0"])}
        for q in ("2012q3", "2012q4", "2013q1", "2013q2", "2013q3", "2013q4", "2014q1", "2014q2", "2014q3", "2014q4",
                  "2015q1"):
            pages[f"https://www.sec.gov/Archives/edgar/full-index/{q[:4]}/QTR{q[5]}/master.idx"] = idx.encode()
        demandes = []

        class Client:
            def get(self, url):
                demandes.append(url)
                if url not in pages:
                    raise t.ErreurSource(f"{url} : HTTP 404")
                return Rep(pages[url])
        t.CLIENT = Client()
        d2.main()
        res = json.loads((d2.SORTIE / "resume.json").read_text())

        def lire(nom):
            with gzip.open(d2.BASE / nom, "rt") as f:
                return [json.loads(x) for x in f]
        px = {x["s"]: x for x in lire("prix.jsonl.gz")}
        verifier("prix : tous les symboles (ZZZ compris, absent de toute liste voulue)", set(px) == {"AAA", "SPY", "IWM", "ZZZ"},
                 sorted(px))
        verifier("prix : fichier d'avant 200907a… (ici 201210a) seulement ; 201209b ignoré", res["prix"]["premier"] == "201210a"
                 and res["prix"]["fichiers"] == 3, res["prix"])
        verifier("Sandy : le règlement du 31 octobre 2012 = clôture du vendredi 26 (bourse fermée les 29 et 30)",
                 res["prix"]["sandy"].get("20121031") == "20121026", res["prix"]["sandy"])
        verifier("prix de AAA aux bonnes dates de clôture", px["AAA"]["d"] == [20121025, 20121026, 20121031]
                 and px["AAA"]["p"] == [20.0, 21.0, 22.0], (px["AAA"]["d"], px["AAA"]["p"]))
        ini = lire("inities.jsonl.gz")
        verifier("initiés : 2 infos, PDG reconnu, symbole normalisé (bbb → BBB)",
                 len(ini) == 2 and ini[0][7] == 1 and ini[0][3] == "achat" and ini[1][2] == "BBB" and ini[1][9] == 1, ini)
        verifier("carte des symboles des formulaires 4", sorted(map(tuple, lire("symboles_f4.jsonl.gz")))
                 == [("11", "AAA", "2012-08", 1), ("22", "BBB", "2012-11", 1)], lire("symboles_f4.jsonl.gz"))
        fa = lire("faits.jsonl.gz")
        verifier("finances : la compagnie avec faits seulement", [x["cik"] for x in fa] == ["11"]
                 and fa[0]["actions"] == [["2012-06-30", 1000000, "2012-08-01"]], fa)
        tr = lire("treize.jsonl.gz")
        verifier("13 : cache du tournoi (2015q2) + index lus (11 trimestres), les 2 CIK du dépôt",
                 len(tr) == 12 and tr[0] == ["2012-09-04", "13D", ["11", "99"]] and tr[-1][0] == "2015-04-02", (len(tr), tr[0], tr[-1]))
        verifier("13 : index bruts jamais gardés dans le cache", not (c2 / "index").exists() and (c2 / "13").exists(),
                 sorted(p.name for p in c2.iterdir()))
        ci = lire("cies.jsonl.gz")
        verifier("compagnies : seulement celles avec un 10-K ; 10-K des 2 pages, triés",
                 [x["cik"] for x in ci] == ["11"] and [k[1] for k in ci[0]["dix_k"]] == ["x0", "x1"]
                 and ci[0]["symboles"] == ["AAA"], ci)
        verifier("le cache du tournoi n'est jamais modifié (rien d'écrit dedans)",
                 sorted(str(p.relative_to(ct)) for p in ct.rglob("*") if p.is_file()) ==
                 ["ftd/201210b.zip", "tournoi/13/2015q2.json.gz", "tournoi/companyfacts.zip", "tournoi/ds/2012q3.json.gz",
                  "tournoi/ds/2012q4.json.gz"], sorted(str(p.relative_to(ct)) for p in ct.rglob("*") if p.is_file()))
        verifier("fichier du tournoi relu dans son cache, pas redemandé", not any("201210b" in x for x in demandes),
                 [x.rsplit("/", 1)[-1] for x in demandes])
        verifier("résumé sans aucun rendement", "rendement" not in json.dumps(res).lower(), list(res))
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
