"""Reconnaissance du lot 2 : vrais documents + conditions d'utilisation, AVANT d'écrire les lecteurs.

FDA (approbations), SEC 13F (gros fonds), S&P (entrées/sorties d'indices), CanadaBuys (contrats),
OCRI/CIRO (arrêts de négociation). Tout est sauvé dans labo/resultats-lot2/ ; résumé dans resume.md.
Le courriel ne part qu'à la SEC (comme le robot).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

SORTIE = Path("labo/resultats-lot2")
UA = {"User-Agent": "Radar projet personnel"}
UA_SEC = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}
session = requests.Session()
resume: list[str] = ["# Reconnaissance du lot 2", ""]


def get(url: str, max_octets: int | None = None, **kw) -> requests.Response | None:
    hote = (urlparse(url).hostname or "").lower()
    sec = hote == "sec.gov" or hote.endswith(".sec.gov")
    time.sleep(0.25 if sec else 0.6)
    try:
        r = session.get(url, headers={**(UA_SEC if sec else UA), "Accept-Encoding": "gzip, deflate"},
                        timeout=60, stream=max_octets is not None, **kw)
        if max_octets is not None:
            morceaux, total = [], 0
            for m in r.iter_content(65536):
                morceaux.append(m)
                total += len(m)
                if total >= max_octets:
                    break
            r._content = b"".join(morceaux)[:max_octets]
            r.close()
        resume.append(f"- {r.status_code} · {len(r.content)} octets · {url}")
        return r
    except Exception as e:  # noqa: BLE001
        resume.append(f"- ERREUR {type(e).__name__}: {e} · {url}")
        return None


def sauver(nom: str, r: requests.Response | None) -> None:
    if r is not None:
        (SORTIE / nom).write_bytes(r.content)


def liens(html: str, base: str, motif: str) -> list[str]:
    vus = []
    for href, texte in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        t = " ".join(re.sub(r"<[^>]+>", " ", texte).split())
        if re.search(motif, href + " " + t, re.I):
            u = urljoin(base, href)
            if (u, t) not in vus:
                vus.append((u, t))
    return [f"{t[:80]} → {u}" for u, t in vus[:40]]


# ---------- A. FDA ----------


def fda() -> None:
    resume.append("\n## FDA")
    q = ("https://api.fda.gov/drug/drugsfda.json?search=submissions.submission_type:%22ORIG%22"
         "+AND+submissions.submission_status:%22AP%22+AND+submissions.submission_status_date:[20260815+TO+20261003]"
         "&limit=100")
    r = get(q)
    sauver("fda_drugsfda.json", r)
    if r is not None and r.ok:
        d = r.json()
        resume.append(f"  - meta : {json.dumps(d.get('meta', {}))[:400]}")
        for x in d.get("results", [])[:100]:
            subs = [s for s in x.get("submissions", []) if s.get("submission_type") == "ORIG"]
            prods = ", ".join(sorted({p.get("brand_name", "") for p in x.get("products", [])}))[:60]
            resume.append(f"  - {x.get('application_number')} · {x.get('sponsor_name')} · {prods} · "
                          f"ORIG {[(s.get('submission_status'), s.get('submission_status_date')) for s in subs]}")
    for nom, url in [("fda_terms.html", "https://open.fda.gov/terms/"),
                     ("fda_license.html", "https://open.fda.gov/license/"),
                     ("fda_auth.html", "https://open.fda.gov/apis/authentication/"),
                     ("fda_novel_2026.html", "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026"),
                     ("fda_press_rss.xml", "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"),
                     ("fda_robots.txt", "https://www.fda.gov/robots.txt"),
                     ("fda_api_robots.txt", "https://api.fda.gov/robots.txt"),
                     ("fda_website_policies.html", "https://www.fda.gov/about-fda/about-website/website-policies"),
                     ("fda_cber_par_annee.html", "https://www.fda.gov/vaccines-blood-biologics/development-approval-process-cber/biological-approvals-year")]:
        sauver(nom, get(url))
    p = SORTIE / "fda_novel_2026.html"
    if p.exists():
        t = p.read_text("utf-8", "replace")
        lignes = re.findall(r"<tr>(.*?)</tr>", t, re.S)
        resume.append(f"  - approbations « novel » 2026 : {len(lignes)} lignes de tableau")
        for l in lignes[:6] + lignes[-3:]:
            resume.append("    - " + " | ".join(" ".join(re.sub(r"<[^>]+>", " ", c).split())[:70]
                                               for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", l, re.S)))


# ---------- B. SEC 13F ----------

GROS_FONDS = ["BERKSHIRE HATHAWAY", "BRIDGEWATER", "PERSHING SQUARE", "SCION ASSET", "RENAISSANCE TECH",
              "CITADEL ADVISORS", "SOROS FUND", "APPALOOSA", "THIRD POINT", "TIGER GLOBAL", "BAUPOST", "GREENLIGHT",
              "ICAHN", "ARK INVESTMENT", "DUQUESNE", "ELLIOTT", "COATUE", "VIKING GLOBAL", "LONE PINE",
              "GATES FOUNDATION", "NORGES BANK", "CAISSE DE DEPOT", "CANADA PENSION PLAN", "ONTARIO TEACHERS",
              "PUBLIC SECTOR PENSION", "BRITISH COLUMBIA INVESTMENT", "OMERS", "ALBERTA INVESTMENT",
              "HEALTHCARE OF ONTARIO", "ROYAL BANK OF CANADA", "TORONTO DOMINION", "BANK OF MONTREAL",
              "CANADIAN IMPERIAL", "BANK OF NOVA SCOTIA", "FAIRFAX", "BROOKFIELD"]


def sec_13f() -> None:
    resume.append("\n## SEC 13F")
    trouves: dict[str, set] = {}
    total_13f = 0
    for jour in ["20260803", "20260804", "20260805", "20260806", "20260807", "20260810", "20260811", "20260812",
                 "20260813", "20260814"]:
        r = get(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.{jour}.idx")
        if r is None or not r.ok:
            continue
        for ligne in r.content.decode("latin-1").splitlines():
            parties = ligne.split("|")
            if len(parties) == 5 and parties[2] == "13F-HR":
                total_13f += 1
                nom = parties[1].upper()
                for g in GROS_FONDS:
                    if g in nom:
                        trouves.setdefault(g, set()).add((parties[0], parties[1], jour, parties[4]))
    resume.append(f"  - 13F-HR déposés du 3 au 14 août 2026 : {total_13f}")
    for g in GROS_FONDS:
        for cik, nom, jour, fichier in sorted(trouves.get(g, [])):
            resume.append(f"  - {g} → CIK {cik} · {nom} · {jour} · {fichier}")
        if g not in trouves:
            resume.append(f"  - {g} → aucun 13F-HR trouvé du 3 au 14 août")
    (SORTIE / "sec_13f_trouves.json").write_text(json.dumps({g: sorted(v) for g, v in trouves.items()}, indent=1),
                                                  encoding="utf-8")
    # Berkshire : les 2 derniers 13F-HR, leurs fichiers, et la table des positions
    r = get("https://data.sec.gov/submissions/CIK0001067983.json")
    if r is None or not r.ok:
        return
    rec = r.json()["filings"]["recent"]
    resume.append(f"  - Berkshire (submissions) : nom officiel « {r.json().get('name')} »")
    vus = 0
    for form, acc, date_dep, rapport in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec["reportDate"]):
        if form != "13F-HR" or vus >= 2:
            continue
        vus += 1
        dossier = f"https://www.sec.gov/Archives/edgar/data/1067983/{acc.replace('-', '')}"
        idx = get(f"{dossier}/index.json")
        if idx is None or not idx.ok:
            continue
        fichiers = [f["name"] for f in idx.json()["directory"]["item"]]
        resume.append(f"  - 13F-HR {acc} · déposé {date_dep} · trimestre {rapport} · fichiers {fichiers}")
        for f in fichiers:
            if f.endswith(".xml"):
                sauver(f"berkshire_{rapport}_{f}", get(f"{dossier}/{f}"))
        sauver(f"berkshire_{rapport}_index-headers.html", get(f"{dossier}/{acc}-index-headers.html"))


# ---------- C. S&P ----------


def sp() -> None:
    resume.append("\n## S&P Dow Jones Indices")
    for nom, url in [("sp_robots_www.txt", "https://www.spglobal.com/robots.txt"),
                     ("sp_robots_press.txt", "https://press.spglobal.com/robots.txt"),
                     ("sp_press.html", "https://press.spglobal.com/"),
                     ("sp_terms.html", "https://www.spglobal.com/en/terms-of-use"),
                     ("sp_dji_terms.html", "https://www.spglobal.com/spdji/en/terms-of-use/"),
                     ("sp_dji_annonces.html", "https://www.spglobal.com/spdji/en/media-center/news-announcements/"),
                     ("sp_500.html", "https://www.spglobal.com/spdji/en/indices/equity/sp-500/")]:
        r = get(url)
        sauver(nom, r)
        if r is not None and r.ok and nom.endswith(".html"):
            t = r.content.decode("utf-8", "replace")
            for l in liens(t, url, r"terms|legal|rss|S&amp;P 500|S&P 500|set to join|index change"):
                resume.append(f"    - {l}")


# ---------- D. CanadaBuys ----------


def canadabuys() -> None:
    resume.append("\n## CanadaBuys")
    r = get("https://open.canada.ca/data/api/action/package_search?q=CanadaBuys&rows=20")
    sauver("canadabuys_ckan.json", r)
    urls_csv = []
    if r is not None and r.ok:
        for p in r.json().get("result", {}).get("results", []):
            resume.append(f"  - jeu : {p.get('title')} · {p.get('id')} · licence {p.get('license_id')}")
            for res in p.get("resources", []):
                resume.append(f"    - {res.get('name')} · {res.get('format')} · {res.get('last_modified') or res.get('created')}"
                              f" · {res.get('url')}")
                u = res.get("url") or ""
                if u.lower().endswith(".csv") and ("award" in u.lower() or "attribution" in u.lower()
                                                   or "contract" in u.lower() or "contrat" in u.lower()):
                    urls_csv.append(u)
    for i, u in enumerate(urls_csv[:6]):
        sauver(f"canadabuys_csv_{i}.csv", get(u, max_octets=400_000))
    for nom, url in [("canadabuys_robots.txt", "https://canadabuys.canada.ca/robots.txt"),
                     ("canadabuys_accueil.html", "https://canadabuys.canada.ca/en"),
                     ("ogl_canada.html", "https://open.canada.ca/en/open-government-licence-canada")]:
        r = get(url)
        sauver(nom, r)
        if r is not None and r.ok and nom == "canadabuys_accueil.html":
            for l in liens(r.content.decode("utf-8", "replace"), url, r"terms|conditions|open data|données ouvertes|award"):
                resume.append(f"    - {l}")


# ---------- E. OCRI / CIRO ----------


def ciro() -> None:
    resume.append("\n## OCRI / CIRO")
    pages = []
    for nom, url in [("ciro_robots.txt", "https://www.ciro.ca/robots.txt"),
                     ("ciro_accueil.html", "https://www.ciro.ca/"),
                     ("ciro_sitemap.xml", "https://www.ciro.ca/sitemap.xml")]:
        r = get(url)
        sauver(nom, r)
        if r is not None and r.ok and nom == "ciro_accueil.html":
            t = r.content.decode("utf-8", "replace")
            for l in liens(t, url, r"halt|trading|terms|conditions|legal|rss|feed"):
                resume.append(f"    - {l}")
                if re.search(r"halt", l, re.I):
                    pages.append(l.split(" → ")[-1])
        if r is not None and r.ok and nom == "ciro_sitemap.xml":
            for u in re.findall(r"<loc>([^<]+)</loc>", r.content.decode("utf-8", "replace")):
                if re.search(r"halt|terms|legal", u, re.I):
                    resume.append(f"    - plan du site : {u}")
                    if "halt" in u.lower():
                        pages.append(u)
    for i, u in enumerate(dict.fromkeys(pages)):
        if i >= 5:
            break
        r = get(u)
        sauver(f"ciro_arrets_{i}.html", r)
        if r is not None and r.ok:
            t = r.content.decode("utf-8", "replace")
            for l in liens(t, u, r"halt|resum|rss|feed|csv|json|api"):
                resume.append(f"      - {l}")


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (fda, sec_13f, sp, canadabuys, ciro):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            resume.append(f"- ÉTAPE {etape.__name__} PLANTÉE : {type(e).__name__}: {e}")
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
