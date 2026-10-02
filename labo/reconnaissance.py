"""Reconnaissance : télécharge de VRAIS documents officiels pour bâtir et tester les lecteurs du robot.

Roule seulement sur la branche « labo » (GitHub Actions). Rien de ceci n'est publié dans l'app.
Résultat : labo/resultats/ (journal des requêtes, échantillons de documents).
"""

from __future__ import annotations

import gzip
import json
import random
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

UA = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/resultats")
journal: list[dict] = []
random.seed(20261002)


def get(url: str, max_octets: int = 3_000_000, entetes: dict | None = None, donnees: bytes | None = None) -> bytes | None:
    h = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
    h.update(entetes or {})
    req = urllib.request.Request(url, headers=h, data=donnees)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            brut = r.read(max_octets + 1)
            if r.headers.get("Content-Encoding") == "gzip":
                brut = gzip.decompress(brut)
            journal.append({"url": url, "statut": r.status, "octets": len(brut), "tronque": len(brut) > max_octets,
                            "secondes": round(time.time() - t0, 2), "type": r.headers.get("Content-Type")})
            return brut[:max_octets]
    except urllib.error.HTTPError as e:
        journal.append({"url": url, "statut": e.code, "erreur": str(e)[:200]})
    except Exception as e:  # noqa: BLE001 - on note toute erreur réseau
        journal.append({"url": url, "statut": None, "erreur": f"{type(e).__name__}: {e}"[:200]})
    finally:
        time.sleep(0.3)  # moins de 4 requêtes par seconde
    return None


def sauver(chemin: str, contenu: bytes | None) -> None:
    if contenu is None:
        return
    f = SORTIE / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(contenu)


def sec() -> None:
    # 1) Index officiel des dépôts : on recule jusqu'au dernier jour ouvrable disponible
    index, jour = None, date.today()
    for _ in range(7):
        jour -= timedelta(days=1)
        if jour.weekday() >= 5:
            continue
        trimestre = (jour.month - 1) // 3 + 1
        index = get(f"https://www.sec.gov/Archives/edgar/daily-index/{jour.year}/QTR{trimestre}/master.{jour:%Y%m%d}.idx", 20_000_000)
        if index:
            break
    if not index:
        return
    sauver(f"sec/master.{jour:%Y%m%d}.idx.gz", gzip.compress(index))

    lignes = [l.split("|") for l in index.decode("latin-1").splitlines() if l.count("|") == 4]
    lignes = [l for l in lignes if l[0].strip().isdigit()]
    par_type: dict[str, dict[str, list]] = {}
    for cik, nom, forme, depose, fichier in lignes:
        acc = fichier.rsplit("/", 1)[-1].removesuffix(".txt")
        par_type.setdefault(forme, {}).setdefault(acc, []).append({"cik": cik, "nom": nom, "depose": depose, "fichier": fichier})
    comptes = {f: len(a) for f, a in sorted(par_type.items(), key=lambda kv: -len(kv[1]))}
    sauver("sec/comptes_par_type.json", json.dumps({"jour": str(jour), "comptes": comptes}, indent=1, ensure_ascii=False).encode())

    def echantillon(forme: str, n: int) -> list[tuple[str, list]]:
        items = list(par_type.get(forme, {}).items())
        return random.sample(items, min(n, len(items)))

    # 2) Documents complets (.txt) : formulaire 4, 13D/13G, 144
    for forme, n, dossier in [("4", 60, "form4"), ("SCHEDULE 13D", 5, "13d"), ("SCHEDULE 13D/A", 4, "13d"),
                              ("SCHEDULE 13G", 4, "13g"), ("144", 4, "form144"), ("SC TO-T", 2, "offres")]:
        for acc, filers in echantillon(forme, n):
            sauver(f"sec/{dossier}/{acc}.txt", get(f"https://www.sec.gov/Archives/{filers[0]['fichier']}", 2_000_000))
            sauver(f"sec/{dossier}/{acc}.filers.json", json.dumps(filers, ensure_ascii=False).encode())

    # 3) 8-K : seulement l'en-tête (les pièces jointes peuvent être énormes)
    for acc, filers in echantillon("8-K", 15):
        cik = filers[0]["cik"]
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        sauver(f"sec/8k/{acc}-index-headers.html", get(f"{dossier}/{acc}-index-headers.html"))
        sauver(f"sec/8k/{acc}.filers.json", json.dumps(filers, ensure_ascii=False).encode())
    for acc, filers in echantillon("8-K", 2):
        cik = filers[0]["cik"]
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        sauver(f"sec/8k/{acc}-index.htm", get(f"{dossier}/{acc}-index.htm"))
        sauver(f"sec/8k/{acc}.hdr.sgml", get(f"{dossier}/{acc}.hdr.sgml"))

    # 4) 13F : un rapport complet (positions des gros fonds)
    for acc, filers in echantillon("13F-HR", 1):
        sauver(f"sec/13f/{acc}.txt", get(f"https://www.sec.gov/Archives/{filers[0]['fichier']}", 15_000_000))

    # 5) Fichiers de référence et fils
    for nom, url in [
        ("company_tickers.json", "https://www.sec.gov/files/company_tickers.json"),
        ("company_tickers_exchange.json", "https://www.sec.gov/files/company_tickers_exchange.json"),
        ("submissions_apple.json", "https://data.sec.gov/submissions/CIK0000320193.json"),
    ]:
        contenu = get(url, 30_000_000)
        sauver(f"sec/{nom}.gz", gzip.compress(contenu) if contenu else None)
    sauver("sec/fil_form4.atom", get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&start=0&count=40&output=atom"))


AUTRES = {
    # Phase 2 : militaire
    "war_rss.xml": "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=10",
    "war_contrats.html": "https://www.war.gov/News/Contracts/",
    "state_ventes_armes.html": "https://www.state.gov/arms-sales-congressional-notifications",
    "usaspending_agences.json": "https://api.usaspending.gov/api/v2/references/toptier_agencies/",
    "canadabuys_liste.html": "https://canadabuys.canada.ca/opendata/pub/",
    "canada_contrats_10k.json": "https://open.canada.ca/data/api/3/action/package_show?id=d8f85d91-7dec-4fd1-8055-483b77225d8b",
    "canada_nouvelles.atom": "https://api.io.canada.ca/io-server/gc/news/en/v2?sort=publishedDate&orderBy=desc&pick=5&format=atom",
    # Phase 3 : politiciens
    "chambre_2026FD.zip": "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip",
    "senat_accueil.html": "https://efdsearch.senate.gov/search/home/",
    "oge_accueil.html": "https://www.oge.gov/",
    "lda_depots.json": "https://lda.gov/api/v1/filings/?filing_year=2026&page_size=2",
    "comites_actuels.json": "https://unitedstates.github.io/congress-legislators/committee-membership-current.json",
    "chambre_vote.xml": "https://clerk.house.gov/evs/2026/roll001.xml",
    # Phase 4 : gouvernement
    "registre_federal.json": "https://www.federalregister.gov/api/v1/documents.json?per_page=3&order=newest",
    "registre_federal_veille.json": "https://www.federalregister.gov/api/v1/public-inspection-documents/current.json",
    "maison_blanche.rss": "https://www.whitehouse.gov/presidential-actions/feed/",
    "openfda.json": "https://api.fda.gov/drug/drugsfda.json?limit=1",
    "ftc_hsr.json": "https://api.ftc.gov/v0/hsr-early-termination-notices?api_key=DEMO_KEY&page[limit]=2",
    "fed.rss": "https://www.federalreserve.gov/feeds/press_all.xml",
    "tresor.json": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance?page[size]=1",
    "cftc_cot.json": "https://publicreporting.cftc.gov/resource/6dca-aqww.json?$limit=1",
    "nhtsa.json": "https://api.nhtsa.gov/recalls/recallsByVehicle?make=ford&model=f-150&modelYear=2024",
    "banque_canada.json": "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1",
    "gazette_canada.xml": "https://gazette.gc.ca/rss/p2-eng.xml",
    "sp_communiques.html": "https://press.spglobal.com/",
    "nbim.html": "https://www.nbim.no/en/investments/all-investments/",
    "globenewswire.html": "https://www.globenewswire.com/rss/list",
}


def autres() -> None:
    for nom, url in AUTRES.items():
        contenu = get(url, 6_000_000)
        # Les pages web de tiers peuvent contenir leurs propres clés (ex. cartes) : on garde seulement le code de réponse.
        if not nom.endswith(".html"):
            sauver(f"autres/{nom}", contenu)


if __name__ == "__main__":
    SORTIE.mkdir(parents=True, exist_ok=True)
    sec()
    autres()
    sauver("journal.json", json.dumps(journal, indent=1, ensure_ascii=False).encode())
    ok = sum(1 for j in journal if j.get("statut") == 200)
    print(f"{ok}/{len(journal)} requêtes réussies")
    for j in journal:  # visible dans le journal de GitHub même si l'enregistrement échoue
        if "sec.gov/Archives/edgar/data" not in j["url"]:
            print(j.get("statut"), j.get("octets", j.get("erreur", "")), j["url"][:110])
