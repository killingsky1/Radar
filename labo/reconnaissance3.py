"""Reconnaissance 3 : plus d'échantillons pour tester les lecteurs (texte complet des ventes d'armes,
40 rapports de la Chambre, tous les rapports récents du Sénat). Résultat : labo/resultats3/.
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.parse
import zipfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reconnaissance2 as r2  # noqa: E402

r2.SORTIE = Path("labo/resultats3")
get, sauver = r2.get, r2.sauver


def ventes_armes():
    depuis = (date.today() - timedelta(days=120)).isoformat()
    champs = "&".join(f"fields[]={c}" for c in ["document_number", "title", "publication_date", "raw_text_url",
                                                  "body_html_url", "full_text_xml_url", "html_url", "pdf_url"])
    liste = get("https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest&" + champs
                + f"&conditions[publication_date][gte]={depuis}&conditions[term]=%22Arms+Sales+Notification%22")
    sauver("armes/liste.json", liste)
    for d in json.loads(liste)["results"][:12]:
        sauver(f"armes/{d['document_number']}.txt", get(d["raw_text_url"]))
        sauver(f"armes/{d['document_number']}.xml", get(d["full_text_xml_url"]))


def chambre():
    z = get("https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip")
    x = zipfile.ZipFile(io.BytesIO(z)).read("2026FD.xml").decode("utf-8", "replace")
    ptr = [m for m in re.findall(r"<Member>(.*?)</Member>", x, re.S) if "<FilingType>P</FilingType>" in m]
    import pdfplumber

    choisis = [m for m in ptr if re.search(r"<DocID>2\d+</DocID>", m)][-60:-14]  # e-déposés, avant ceux déjà lus
    for m in choisis:
        doc = re.search(r"<DocID>(.*?)</DocID>", m).group(1)
        pdf = get(f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/{doc}.pdf")
        if not pdf:
            continue
        sauver(f"chambre/{doc}.membre.xml", m)
        sauver(f"chambre/{doc}.pdf", pdf)
        with pdfplumber.open(io.BytesIO(pdf)) as p:
            sauver(f"chambre/{doc}.txt", "\n\n=== PAGE ===\n\n".join((pg.extract_text() or "") for pg in p.pages))


def senat():
    accueil = get("https://efdsearch.senate.gov/search/home/")
    m = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', accueil)
    get("https://efdsearch.senate.gov/search/home/",
        donnees=urllib.parse.urlencode({"prohibition_agreement": "1", "csrfmiddlewaretoken": m.group(1).decode()}).encode(),
        entetes={"Referer": "https://efdsearch.senate.gov/search/home/"})
    jeton = next(c.value for c in r2.pots if c.name == "csrftoken")
    debut = (date.today() - timedelta(days=75)).strftime("%m/%d/%Y 00:00:00")
    corps = urllib.parse.urlencode({
        "start": "0", "length": "100", "report_types": "[11]", "filer_types": "[]",
        "submitted_start_date": debut, "submitted_end_date": "", "candidate_state": "", "senator_state": "",
        "office_id": "", "first_name": "", "last_name": "",
    }).encode()
    rep = get("https://efdsearch.senate.gov/search/report/data/", donnees=corps,
              entetes={"X-CSRFToken": jeton, "Referer": "https://efdsearch.senate.gov/search/"})
    sauver("senat/recherche.json", rep)
    for ligne in json.loads(rep).get("data", []):
        lien = re.search(r'href="([^"]+)"', " ".join(map(str, ligne)))
        if lien:
            url = urllib.parse.urljoin("https://efdsearch.senate.gov/", lien.group(1))
            sauver(f"senat/{'papier-' if '/paper/' in url else ''}{url.rstrip('/').rsplit('/', 1)[-1]}.html", get(url))


if __name__ == "__main__":
    r2.SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (ventes_armes, chambre, senat):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            sauver(f"erreur_{etape.__name__}.txt", f"{type(e).__name__}: {e}")
    sauver("journal.json", json.dumps(r2.journal, indent=1, ensure_ascii=False))
    for j in r2.journal:
        print(j.get("statut"), j.get("octets", j.get("erreur", "")), j["url"][:120])
