"""Reconnaissance 5 (lot 1, compléments) : décisions de la Banque du Canada, offres d'achat SEC (TO-T, 13E3),
documents présidentiels du Registre fédéral (60 jours) pour recouper avec la Maison-Blanche.

Roule seulement sur la branche « labo ». Résultat : labo/resultats5/.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reconnaissance2 as r2  # noqa: E402

r2.SORTIE = Path("labo/resultats5")
get, sauver = r2.get, r2.sauver


def banque_canada():
    flux = (get("https://www.bankofcanada.ca/content_type/press-releases/feed/") or b"").decode("utf-8", "replace")
    for lien in re.findall(r"<link>(https://www\.bankofcanada\.ca/\d{4}/\d\d/fad-press-release-[^<]+)</link>", flux)[:3]:
        sauver(f"bdc/{lien.rstrip('/').rsplit('/', 1)[-1]}.html", get(lien))
    sauver("bdc/V39079_2024_2025.json",
           get("https://www.bankofcanada.ca/valet/observations/V39079/json?start_date=2024-05-01&end_date=2025-12-31"))
    # Décisions connues de 2024-2025 (pages officielles) : pour voir le titre et la phrase d'une BAISSE
    for d in ("2025-03-12", "2024-06-05", "2025-10-29"):
        a, m, j = d.split("-")
        sauver(f"bdc/fad-press-release-{d}.html", get(f"https://www.bankofcanada.ca/{a}/{m}/fad-press-release-{d}/"))


def sec_offres():
    d, gardes = date.today(), []
    for _ in range(30):
        d -= timedelta(days=1)
        if d.weekday() >= 5:
            continue
        idx = get(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{(d.month - 1) // 3 + 1}/master.{d:%Y%m%d}.idx")
        for ligne in (idx or b"").decode("latin-1").splitlines():
            p = ligne.split("|")
            if len(p) == 5 and p[2] in ("SC TO-T", "SC 13E3", "SC 14D9"):
                gardes.append(p)
    vus = set()
    for cik, nom, forme, depose, fichier in gardes:
        acc = fichier.rsplit("/", 1)[-1].replace(".txt", "")
        if acc in vus or len(vus) >= 12:
            continue
        vus.add(acc)
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        sauver(f"sec/{acc}.{forme.replace(' ', '_')}.headers.html", get(f"{dossier}/{acc}-index-headers.html"))


def registre_presidentiel():
    depuis = (date.today() - timedelta(days=60)).isoformat()
    champs = "&".join(f"fields[]={c}" for c in ("title", "type", "subtype", "document_number", "html_url",
                                                  "publication_date", "signing_date", "executive_order_number"))
    sauver("registre/presidentiels_60j.json",
           get(f"https://www.federalregister.gov/api/v1/documents.json?per_page=200&order=newest&{champs}"
               f"&conditions[publication_date][gte]={depuis}&conditions[type][]=PRESDOCU"))
    sauver("mb/flux_page3.xml", get("https://www.whitehouse.gov/presidential-actions/feed/?paged=3"))


if __name__ == "__main__":
    r2.SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (banque_canada, sec_offres, registre_presidentiel):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            sauver(f"erreur_{etape.__name__}.txt", f"{type(e).__name__}: {e}")
    sauver("journal.json", json.dumps(r2.journal, indent=1, ensure_ascii=False))
    for j in r2.journal:
        print(j.get("statut"), j.get("octets", j.get("erreur", "")), j["url"][:120])
