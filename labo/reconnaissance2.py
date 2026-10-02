"""Reconnaissance 2 : vrais documents pour les politiciens, le gouvernement, le Canada et le militaire.

Roule seulement sur la branche « labo ». Résultat : labo/resultats2/. Rien n'est publié dans l'app.
"""

from __future__ import annotations

import gzip
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import io
from datetime import date, timedelta
from pathlib import Path

UA = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/resultats2")
journal: list[dict] = []
pots = http.cookiejar.CookieJar()
ouvreur = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(pots))


def get(url, donnees=None, entetes=None, max_octets=8_000_000):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    h.update(entetes or {})
    req = urllib.request.Request(url, data=donnees, headers=h)
    t0 = time.time()
    try:
        with ouvreur.open(req, timeout=60) as r:
            brut = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                brut = gzip.decompress(brut)
            journal.append({"url": url, "statut": r.status, "octets": len(brut), "secondes": round(time.time() - t0, 2)})
            return brut[:max_octets]
    except urllib.error.HTTPError as e:
        journal.append({"url": url, "statut": e.code, "erreur": str(e)[:200]})
    except Exception as e:  # noqa: BLE001
        journal.append({"url": url, "statut": None, "erreur": f"{type(e).__name__}: {e}"[:200]})
    finally:
        time.sleep(0.4)
    return None


def sauver(chemin, contenu):
    if contenu is None:
        return
    f = SORTIE / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode("utf-8"))


def chambre():
    z = get("https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026FD.zip")
    if not z:
        return
    x = zipfile.ZipFile(io.BytesIO(z)).read("2026FD.xml").decode("utf-8", "replace")
    ptr = [m for m in re.findall(r"<Member>(.*?)</Member>", x, re.S) if "<FilingType>P</FilingType>" in m]

    def cle(m):
        mo, jo, an = re.search(r"<FilingDate>(.*?)</FilingDate>", m).group(1).split("/")
        return (an, mo.zfill(2), jo.zfill(2))

    import pdfplumber  # installé par le workflow

    for m in sorted(ptr, key=cle)[-14:]:
        doc = re.search(r"<DocID>(.*?)</DocID>", m).group(1)
        pdf = get(f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/{doc}.pdf")
        if not pdf:
            continue
        sauver(f"chambre/{doc}.pdf", pdf)
        sauver(f"chambre/{doc}.membre.xml", m)
        try:
            with pdfplumber.open(io.BytesIO(pdf)) as p:
                texte = "\n\n=== PAGE ===\n\n".join((page.extract_text() or "") for page in p.pages)
                tables = [page.extract_tables() for page in p.pages]
            sauver(f"chambre/{doc}.txt", texte)
            sauver(f"chambre/{doc}.tables.json", json.dumps(tables, ensure_ascii=False, indent=1))
        except Exception as e:  # noqa: BLE001
            sauver(f"chambre/{doc}.erreur.txt", f"{type(e).__name__}: {e}")


def senat():
    accueil = get("https://efdsearch.senate.gov/search/home/")
    if not accueil:
        return
    jeton = next((c.value for c in pots if c.name == "csrftoken"), None)
    m = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', accueil)
    if not (jeton and m):
        sauver("senat/note.txt", "pas de jeton CSRF")
        return
    get("https://efdsearch.senate.gov/search/home/",
        donnees=urllib.parse.urlencode({"prohibition_agreement": "1", "csrfmiddlewaretoken": m.group(1).decode()}).encode(),
        entetes={"Referer": "https://efdsearch.senate.gov/search/home/"})
    jeton = next((c.value for c in pots if c.name == "csrftoken"), jeton)
    debut = (date.today() - timedelta(days=30)).strftime("%m/%d/%Y 00:00:00")
    corps = urllib.parse.urlencode({
        "start": "0", "length": "25", "report_types": "[11]", "filer_types": "[]",
        "submitted_start_date": debut, "submitted_end_date": "", "candidate_state": "", "senator_state": "",
        "office_id": "", "first_name": "", "last_name": "",
    }).encode()
    rep = get("https://efdsearch.senate.gov/search/report/data/", donnees=corps,
              entetes={"X-CSRFToken": jeton, "Referer": "https://efdsearch.senate.gov/search/"})
    sauver("senat/recherche.json", rep)
    if rep:
        try:
            lignes = json.loads(rep).get("data", [])
        except ValueError:
            return
        for ligne in lignes[:4]:
            lien = re.search(r'href="([^"]+)"', " ".join(map(str, ligne)))
            if lien:
                url = urllib.parse.urljoin("https://efdsearch.senate.gov/", lien.group(1))
                page = get(url)
                if page:
                    sauver(f"senat/{url.rstrip('/').rsplit('/', 1)[-1]}.html", page)


def registre_federal():
    champs = ["title", "type", "subtype", "abstract", "document_number", "html_url", "pdf_url", "publication_date",
              "signing_date", "agencies", "executive_order_number", "significant", "action", "excerpts"]
    f = "&".join(f"fields[]={c}" for c in champs)
    depuis = (date.today() - timedelta(days=7)).isoformat()
    base = "https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest"
    sauver("registre/presidentiels.json", get(f"{base}&{f}&conditions[publication_date][gte]={depuis}&conditions[type][]=PRESDOCU"))
    agences = ["foreign-assets-control-office", "industry-and-security-bureau", "trade-representative-office-of-united-states",
               "food-and-drug-administration", "defense-department", "securities-and-exchange-commission"]
    a = "&".join(f"conditions[agencies][]={x}" for x in agences)
    sauver("registre/agences.json", get(f"{base}&{f}&conditions[publication_date][gte]={depuis}&{a}"))
    depuis60 = (date.today() - timedelta(days=60)).isoformat()
    sauver("registre/ventes_armes.json", get(f"{base}&{f}&conditions[publication_date][gte]={depuis60}&conditions[term]=%22Arms+Sales+Notification%22"))
    sauver("registre/veille.json", get("https://www.federalregister.gov/api/v1/public-inspection-documents/current.json"))
    sauver("registre/agences_liste.json", get("https://www.federalregister.gov/api/v1/agencies"))


def canada():
    for langue in ("fr", "en"):
        sauver(f"canada/nouvelles_{langue}.atom",
               get(f"https://api.io.canada.ca/io-server/gc/news/{langue}/v2?sort=publishedDate&orderBy=desc&pick=200&format=atom"))


def usaspending():
    debut = (date.today() - timedelta(days=150)).isoformat()
    corps = json.dumps({
        "filters": {"agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
                    "award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": debut, "end_date": date.today().isoformat()}],
                    "award_amounts": [{"lower_bound": 500000000}]},
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Start Date", "Awarding Sub Agency", "Description",
                   "generated_internal_id", "recipient_id"],
        "sort": "Award Amount", "order": "desc", "limit": 20, "page": 1,
    }).encode()
    sauver("militaire/usaspending_dod.json", get("https://api.usaspending.gov/api/v2/search/spending_by_award/", donnees=corps,
                                                 entetes={"Content-Type": "application/json"}))
    sauver("militaire/gao.html.statut", str(bool(get("https://www.gao.gov/legal/bid-protests/search"))))


if __name__ == "__main__":
    SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (registre_federal, canada, chambre, senat, usaspending):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            sauver(f"erreur_{etape.__name__}.txt", f"{type(e).__name__}: {e}")
    sauver("journal.json", json.dumps(journal, indent=1, ensure_ascii=False))
    for j in journal:
        print(j.get("statut"), j.get("octets", j.get("erreur", "")), j["url"][:120])
