"""Essai hors ligne de reconnaissance.py avec une fausse SEC (aucune requête réelle) : robots.txt, prix, 13F, rapports,
et l'arrêt quand robots.txt interdit une adresse. Lancement : python labo/chasse2/essai_reconnaissance.py"""
import importlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
os.environ.setdefault("TOURNOI_ROBOT", str((ICI.parent.parent / "principal" / "robot").resolve()))


def zip_de(nom, texte):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(nom, texte)
    return b.getvalue()


ENTETE = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"


def ftd(jour, symboles):
    return zip_de("x.txt", "\n".join([ENTETE] + [f"{jour}|C{s}|{s}|100|NOM {s}|10.5" for s in symboles]))


def submissions():
    principal = {"cik": "1", "filings": {"recent": {
        "accessionNumber": ["0000000001-09-000001", "0000000001-09-000002", "0000000001-24-000003", "0000000001-24-000004"],
        "filingDate": ["2009-03-01", "2009-05-01", "2024-03-01", "2024-05-01"],
        "form": ["10-K", "10-Q", "10-K", "10-Q"], "size": [1000, 500, 2000, 700],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"]}, "files": []}}
    page2 = {"accessionNumber": ["0000000001-09-000009"], "filingDate": ["2009-08-01"], "form": ["10-K/A"], "size": [9],
             "primaryDocument": ["e.htm"]}
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("CIK0000000001.json", json.dumps(principal))
        z.writestr("CIK0000000001-submissions-001.json", json.dumps(page2))
    return b.getvalue()


DOC = "<html><p>Item 7. Management&#8217;s Discussion and Analysis</p><p>MANAGEMENT'S DISCUSSION AND ANALYSIS of results</p></html>"


class Rep:
    def __init__(self, contenu):
        self.contenu = contenu


def faux_client(pages, demandes):
    from radar.http import ErreurSource

    class C:
        def get(self, url):
            demandes.append(url)
            if url not in pages:
                raise ErreurSource(f"{url} : HTTP 404")
            v = pages[url]
            if isinstance(v, int):
                raise ErreurSource(f"{url} : HTTP {v}")
            return Rep(v)
    return C()


def lancer(robots, pages_en_plus=None):
    sys.path.insert(0, str(ICI))
    import reconnaissance as r
    r = importlib.reload(r)
    from radar.collecteurs import prix_sec
    pages = {r.ROBOTS: robots.encode(),
             prix_sec.PAGE: ('<a href="/files/data/fails-deliver-data/cnsfails200403a.zip">x</a>'
                             "<a href='/files/data/fails-deliver-data/cnsfails200901a.zip'>y</a>"
                             '<a href="/files/data/fails-deliver-data/cnsfails201201a.zip">z</a>'
                             '<a href="/files/data/fails-deliver-data/cnsfails202609a_0.zip">w</a>').encode(),
             "https://www.sec.gov/files/data/fails-deliver-data/cnsfails200403a.zip": ftd("20040315", ["AAA"]),
             "https://www.sec.gov/files/data/fails-deliver-data/cnsfails200901a.zip": ftd("20090105", ["AAA", "SPY"]),
             "https://www.sec.gov/files/data/fails-deliver-data/cnsfails201201a.zip": ftd("20120103", ["SPY", "BBB", "CCC"]),
             r.PAGE_13F: b'<a href="/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip">a</a>',
             r.SUBMISSIONS: submissions()}
    for acc, doc in (("000000000109000001", "a.htm"), ("000000000109000002", "b.htm"), ("000000000124000003", "c.htm"),
                     ("000000000124000004", "d.htm")):
        pages[f"https://www.sec.gov/Archives/edgar/data/1/{acc}/{doc}"] = DOC.encode()
    pages.update(pages_en_plus or {})
    demandes = []
    with tempfile.TemporaryDirectory() as t:
        r.CACHE, r.SORTIE = Path(t) / "cache", Path(t) / "sortie"
        r.CLIENT = faux_client(pages, demandes)
        r.main()
        return json.loads((r.SORTIE / "reconnaissance.json").read_text()), demandes


def main():
    ok = []

    def verifier(nom, v, detail):
        ok.append(bool(v))
        print(f"{'OK ' if v else 'NON'} {nom} : {detail}")

    res, demandes = lancer("User-agent: *\nDisallow: /cgi-bin\n")
    p = res["prix"]
    verifier("prix : 4 fichiers, du plus ancien au plus récent (nom en « _0 » compris)",
             p["fichiers"] == 4 and p["premier"] == "200403a" and p["dernier"] == "202609a", p)
    verifier("prix : symboles comptés (3e champ) et SPY trouvé en 2012", p["temoins"]["201201a"]["symboles"] == 3
             and p["temoins"]["201201a"]["SPY"] and p["temoins"]["200403a"]["entete_comme_aujourdhui"], p["temoins"]["201201a"])
    rp = res["rapports"]
    verifier("rapports : 10-K et 10-Q originaux par année (10-K/A laissé de côté)",
             rp["par_annee"]["2009"] == {"10-K": 1, "10-Q": 1, "compagnies": 1, "taille_declaree_go": 0.0}
             and rp["par_annee"]["2024"]["10-K"] == 1, rp["par_annee"])
    t = rp["temoins"]
    verifier("rapports : 6 témoins lus (3 de 2009, 3 de 2024 ; avec une seule compagnie, certains se répètent), "
             "section gestion trouvée", len(t) == 6 and all(x.get("mentions_gestion") == 2 for x in t), t[:2])
    verifier("13F : lien zip lu", res["fonds_13f"]["liens_zip"] == 1, res["fonds_13f"])
    verifier("robots.txt noté dans le résultat", res["robots_txt"]["lignes"] == 2, res["robots_txt"])
    verifier("le courriel n'est jamais dans une adresse demandée", not any("@" in d for d in demandes), len(demandes))
    # robots.txt qui interdit les rapports : arrêt, aucune lecture de submissions.zip, le reste est gardé
    res2, demandes2 = lancer("User-agent: *\nDisallow: /Archives/\n")
    verifier("robots.txt interdit /Archives/ : arrêt avant toute lecture des rapports, prix et 13F gardés",
             "arret" in res2["rapports"] and not any("/Archives/" in d for d in demandes2) and res2["prix"]["fichiers"] == 4,
             res2["rapports"])
    # robots.txt illisible (panne autre que 404) : rien n'est lu
    res3, demandes3 = lancer("", {"https://www.sec.gov/robots.txt": 500})
    verifier("robots.txt illisible : arrêt, aucune autre adresse lue",
             "illisible" in res3["prix"].get("arret", "") and demandes3 == ["https://www.sec.gov/robots.txt"]
             and list(res3) == ["prix"], (res3, demandes3))
    # 403 sur un fichier : arrêt (on ne contourne pas)
    res4, demandes4 = lancer("User-agent: *\nDisallow: /cgi-bin\n",
                             {"https://www.sec.gov/files/data/fails-deliver-data/cnsfails200901a.zip": 403})
    verifier("403 sur un fichier de prix : arrêt de toute lecture (ni 13F ni rapports)",
             "arret" in res4["prix"] and "fonds_13f" not in res4 and "rapports" not in res4, list(res4))
    print(f"{sum(ok)}/{len(ok)} réussis")
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
