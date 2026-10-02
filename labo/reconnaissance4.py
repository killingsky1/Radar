"""Reconnaissance 4 (lot 1) : Fed, Banque du Canada, offres d'achat SEC, CFTC, Maison-Blanche.

Roule seulement sur la branche « labo ». Résultat : labo/resultats4/. Rien n'est publié dans l'app.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reconnaissance2 as r2  # noqa: E402

r2.SORTIE = Path("labo/resultats4")
get, sauver = r2.get, r2.sauver


def fed():
    for nom in ("press_monetary", "press_all"):
        sauver(f"fed/{nom}.xml", get(f"https://www.federalreserve.gov/feeds/{nom}.xml"))
    flux = (get("https://www.federalreserve.gov/feeds/press_monetary.xml") or b"").decode("utf-8", "replace")
    liens = re.findall(r"<link>(?:<!\[CDATA\[)?(https://www\.federalreserve\.gov/newsevents/pressreleases/monetary\d+\w\.htm)", flux)
    for lien in liens[:8]:
        sauver(f"fed/{lien.rsplit('/', 1)[-1]}", get(lien))


def banque_canada():
    sauver("bdc/series.json", get("https://www.bankofcanada.ca/valet/lists/series/json"))
    for candidat in ("V39079", "V122530", "STATIC_ATABLE_V39079"):
        sauver(f"bdc/obs_{candidat}.json", get(f"https://www.bankofcanada.ca/valet/observations/{candidat}/json?recent=12"))
    for i, url in enumerate(("https://www.bankofcanada.ca/feed/", "https://www.bankofcanada.ca/content_type/press-releases/feed/",
                             "https://www.bankofcanada.ca/rss-feeds/", "https://www.bankofcanada.ca/content_type/announcements/feed/",
                             "https://www.bankofcanada.ca/fr/feed/")):
        sauver(f"bdc/flux_{i}.xml", get(url))


def sec_offres():
    trouves, comptes = [], {}
    d = date.today()
    for _ in range(14):
        d -= timedelta(days=1)
        if d.weekday() >= 5:
            continue
        idx = get(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{(d.month - 1) // 3 + 1}/master.{d:%Y%m%d}.idx")
        if not idx:
            continue
        for ligne in idx.decode("latin-1").splitlines():
            p = ligne.split("|")
            if len(p) == 5 and re.search(r"TO-T|TO-I|14D9|13E3|TO-C", p[2]):
                comptes[p[2]] = comptes.get(p[2], 0) + 1
                trouves.append(p)
    sauver("sec/formes_offres.json", json.dumps(comptes, indent=1))
    vus = set()
    for cik, nom, forme, depose, fichier in trouves:
        acc = fichier.rsplit("/", 1)[-1].replace(".txt", "")
        if acc in vus or "/A" in forme or len(vus) >= 8:
            continue
        vus.add(acc)
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        sauver(f"sec/{acc}.{forme.replace(' ', '_').replace('/', '_')}.headers.html", get(f"{dossier}/{acc}-index-headers.html"))
        if len(vus) <= 3:
            sauver(f"sec/{acc}.index.html", get(f"{dossier}/{acc}-index.htm"))


def cftc():
    base = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
    dernier = get(f"{base}?$select=max(report_date_as_yyyy_mm_dd)")
    sauver("cftc/dernier.json", dernier)
    try:
        jour = json.loads(dernier)[0]["max_report_date_as_yyyy_mm_dd"][:10]
    except Exception:  # noqa: BLE001
        return
    sauver("cftc/marches.json", get(f"{base}?$select=market_and_exchange_names,cftc_contract_market_code,open_interest_all"
                                    f"&$where=report_date_as_yyyy_mm_dd='{jour}T00:00:00.000'&$limit=2000"))
    debut = (date.fromisoformat(jour) - timedelta(days=35)).isoformat()
    sauver("cftc/semaines.json", get(f"{base}?$where=report_date_as_yyyy_mm_dd>='{debut}T00:00:00.000'"
                                     "%20AND%20cftc_contract_market_code%20in('088691','13874A','209742','067651','090741',"
                                     "'133741','043602','085692')&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=100"))


def maison_blanche():
    flux = get("https://www.whitehouse.gov/presidential-actions/feed/")
    sauver("mb/flux.xml", flux)
    sauver("mb/flux_page2.xml", get("https://www.whitehouse.gov/presidential-actions/feed/?paged=2"))


if __name__ == "__main__":
    r2.SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (fed, banque_canada, sec_offres, cftc, maison_blanche):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            sauver(f"erreur_{etape.__name__}.txt", f"{type(e).__name__}: {e}")
    sauver("journal.json", json.dumps(r2.journal, indent=1, ensure_ascii=False))
    for j in r2.journal:
        print(j.get("statut"), j.get("octets", j.get("erreur", "")), j["url"][:120])
