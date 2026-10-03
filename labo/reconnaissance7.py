"""Reconnaissance 2 du lot 2 : ce qui manque pour écrire les lecteurs sans rien deviner.

FDA : liens officiels accessibles au robot ? liste complète des nouvelles molécules récentes.
13F : historique des dépôts de chaque gros fonds ; table CUSIP -> symbole (données « fails-to-deliver » de la SEC).
CanadaBuys : tailles des fichiers, colonnes des avis d'attribution, fréquence de mise à jour, conditions.
Résultats : labo/resultats-lot2b/ (résumé dans resume.md). Le courriel ne part qu'à la SEC.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

SORTIE = Path("labo/resultats-lot2b")
UA = {"User-Agent": "Radar projet personnel"}
UA_SEC = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}
session = requests.Session()
resume: list[str] = ["# Reconnaissance 2 du lot 2", ""]

FONDS = {  # CIK trouvés dans les index officiels de la SEC (3-14 août 2026)
    1067983: "BERKSHIRE HATHAWAY INC", 1350694: "Bridgewater Associates, LP", 2026053: "PERSHING SQUARE INC.",
    1037389: "RENAISSANCE TECHNOLOGIES LLC", 1423053: "CITADEL ADVISORS LLC", 1029160: "SOROS FUND MANAGEMENT LLC",
    1656456: "Appaloosa LP", 1040273: "Third Point LLC", 1167483: "TIGER GLOBAL MANAGEMENT LLC",
    1061768: "BAUPOST GROUP LLC/MA", 921669: "ICAHN CARL C", 1697748: "ARK Investment Management LLC",
    1536411: "Duquesne Family Office LLC", 1791786: "Elliott Investment Management L.P.",
    1135730: "COATUE MANAGEMENT LLC", 1103804: "VIKING GLOBAL INVESTORS LP", 1061165: "LONE PINE CAPITAL LLC",
    1166559: "GATES FOUNDATION TRUST", 1374170: "NORGES BANK", 898286: "CAISSE DE DEPOT ET PLACEMENT DU QUEBEC",
    1283718: "CANADA PENSION PLAN INVESTMENT BOARD", 937567: "ONTARIO TEACHERS PENSION PLAN BOARD",
    1396318: "PUBLIC SECTOR PENSION INVESTMENT BOARD", 1228242: "BRITISH COLUMBIA INVESTMENT MANAGEMENT Corp",
    1053321: "OMERS ADMINISTRATION Corp", 1463559: "Alberta Investment Management Corp",
    1535845: "HEALTHCARE OF ONTARIO PENSION PLAN TRUST FUND", 915191: "FAIRFAX FINANCIAL HOLDINGS LTD/ CAN",
    1336528: "Pershing Square Capital Management (ancien CIK ?)", 1079114: "Greenlight (CIK à vérifier)",
    1649339: "Scion (CIK à vérifier)",
}


def get(url: str, max_octets: int | None = None, methode: str = "get") -> requests.Response | None:
    hote = (urlparse(url).hostname or "").lower()
    sec = hote == "sec.gov" or hote.endswith(".sec.gov")
    time.sleep(0.25 if sec else 0.6)
    try:
        h = {**(UA_SEC if sec else UA), "Accept-Encoding": "gzip, deflate"}
        if methode == "head":
            r = session.head(url, headers=h, timeout=60, allow_redirects=True)
            resume.append(f"- HEAD {r.status_code} · taille {r.headers.get('Content-Length')} · modifié "
                          f"{r.headers.get('Last-Modified')} · {url}")
            return r
        r = session.get(url, headers=h, timeout=120, stream=max_octets is not None)
        if max_octets is not None:
            morceaux, total = [], 0
            for m in r.iter_content(65536):
                morceaux.append(m)
                total += len(m)
                if total >= max_octets:
                    break
            r._content = b"".join(morceaux)[:max_octets]
            r.close()
        resume.append(f"- {r.status_code} · {len(r.content)} octets · {r.headers.get('Content-Type')} · {url}")
        return r
    except Exception as e:  # noqa: BLE001
        resume.append(f"- ERREUR {type(e).__name__}: {e} · {url}")
        return None


def sauver(nom: str, r: requests.Response | None) -> None:
    if r is not None:
        (SORTIE / nom).write_bytes(r.content)


def texte(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


# ---------- FDA ----------


def fda() -> None:
    resume.append("\n## FDA")
    sauver("fda_lettre.pdf", get("https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220605Orig1s000ltr.pdf"))
    r = get("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=220605")
    sauver("fda_drugsatfda_220605.html", r)
    if r is not None and r.ok:
        resume.append("  - extrait : " + texte(r.content.decode("utf-8", "replace"))[:600])
    tous = []
    for skip in range(0, 1000, 100):
        r = get("https://api.fda.gov/drug/drugsfda.json?search=submissions.submission_class_code:%22TYPE+1%22"
                f"+AND+submissions.submission_status_date:[20260601+TO+20261003]&limit=100&skip={skip}")
        if r is None or not r.ok:
            break
        d = r.json()
        tous += d.get("results", [])
        if skip + 100 >= d["meta"]["results"]["total"]:
            break
    (SORTIE / "fda_type1.json").write_text(json.dumps(tous), encoding="utf-8")
    nouveaux = []
    for x in tous:
        for s in x.get("submissions", []):
            if (s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
                    and (s.get("submission_class_code") or "").startswith("TYPE 1")
                    and s.get("submission_status_date", "") >= "20260601"):
                nouveaux.append((s["submission_status_date"], x["application_number"], x.get("sponsor_name"),
                                 sorted({p.get("brand_name") for p in x.get("products", [])}),
                                 (x.get("openfda") or {}).get("manufacturer_name"), s.get("review_priority"),
                                 [p.get("code") for p in s.get("submission_property_type", [])],
                                 [a.get("type") for a in s.get("application_docs", [])]))
    resume.append(f"  - applications reçues : {len(tous)} ; nouvelles molécules approuvées depuis le 1er juin : {len(nouveaux)}")
    for n in sorted(nouveaux, reverse=True):
        resume.append(f"    - {n}")


# ---------- 13F ----------


def sec_13f() -> None:
    resume.append("\n## SEC 13F : historique des dépôts par fonds")
    for cik, nom in FONDS.items():
        r = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        if r is None or not r.ok:
            continue
        d = r.json()
        rec = d["filings"]["recent"]
        depots = [(f, a, fd, rd) for f, a, fd, rd in zip(rec["form"], rec["accessionNumber"], rec["filingDate"],
                                                          rec["reportDate"]) if f.startswith("13F")]
        resume.append(f"  - {cik} · nom officiel « {d.get('name')} » (attendu « {nom} ») · 13F récents : {depots[:4]}")
    resume.append("\n## SEC : données « fails-to-deliver » (CUSIP -> symbole)")
    r = get("https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data")
    sauver("ftd_page.html", r)
    zips = []
    if r is not None and r.ok:
        zips = sorted(set(urljoin("https://www.sec.gov/", z) for z in
                          re.findall(r'href="([^"]+cnsfails\d+[ab]\.zip)"', r.content.decode("utf-8", "replace"))))
        resume.append(f"  - fichiers trouvés : {len(zips)} · derniers : {zips[-4:]}")
    for z in zips[-2:]:
        rz = get(z)
        if rz is None or not rz.ok:
            continue
        with zipfile.ZipFile(io.BytesIO(rz.content)) as f:
            nom = f.namelist()[0]
            t = f.read(nom).decode("latin-1")
        lignes = t.splitlines()
        resume.append(f"  - {z} : {nom} · {len(lignes)} lignes · en-tête « {lignes[0]} »")
        for l in lignes[1:4]:
            resume.append(f"    - {l}")
        (SORTIE / f"ftd_{nom}.head.txt").write_text("\n".join(lignes[:200]), encoding="utf-8")
        # Couverture : combien de positions de Berkshire trouvent un symbole ?
        symb = {}
        for l in lignes[1:]:
            p = l.split("|")
            if len(p) >= 5:
                symb[p[1]] = (p[2], p[4])
        resume.append(f"  - CUSIP distincts dans ce fichier : {len(symb)}")
        (SORTIE / f"ftd_{nom}.cusips.json").write_text(json.dumps(symb), encoding="utf-8")


# ---------- CanadaBuys ----------

FICHIERS_CB = {
    "contrats_2026_2027": "https://canadabuys.canada.ca/opendata/pub/2026-2027-contractHistory-contratsOctroyes.csv",
    "attributions_2026_2027": "https://canadabuys.canada.ca/opendata/pub/2026-2027-awardNotice-avisAttribution.csv",
    "attributions_toutes": "https://canadabuys.canada.ca/opendata/pub/awardNoticeComplete-avisAttributionComplet.csv",
    "contrats_tous": "https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv",
}


def canadabuys() -> None:
    resume.append("\n## CanadaBuys")
    for nom, url in FICHIERS_CB.items():
        get(url, methode="head")
    # Fichier complet de l'année (contrats) : on le lit au complet pour voir les montants et le volume
    r = get(FICHIERS_CB["contrats_2026_2027"])
    if r is not None and r.ok:
        lignes = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace"))))
        resume.append(f"  - contrats 2026-2027 : {len(lignes)} lignes")
        cle_val = "totalContractValue-valeurTotaleContrat"
        par_pub = {}
        gros = []
        for l in lignes:
            par_pub[l.get("publicationDate-datePublication", "")] = par_pub.get(l.get("publicationDate-datePublication", ""), 0) + 1
            try:
                v = float(l.get(cle_val) or 0)
            except ValueError:
                v = -1
            if v >= 10_000_000 and l.get("amendmentType-typeModification-eng") == "Original":
                gros.append((l.get("publicationDate-datePublication"), round(v / 1e6, 1), l.get("supplierLegalName-nomLegalFournisseur-eng"),
                             l.get("title-titre-fra"), l.get("endUserEntitiesName-nomEntitesUtilisateurFinal-fra"),
                             l.get("noticeType-avisType-fra"), l.get("referenceNumber-numeroReference"),
                             l.get("amendmentNumber-numeroModification")))
        resume.append(f"  - lignes par date de publication (10 dernières) : {sorted(par_pub.items())[-10:]}")
        resume.append(f"  - contrats originaux de 10 M$ et plus : {len(gros)}")
        for g in sorted(gros, reverse=True)[:40]:
            resume.append(f"    - {g}")
        types = {}
        for l in lignes:
            k = (l.get("amendmentType-typeModification-eng"), l.get("noticeType-avisType-eng"))
            types[k] = types.get(k, 0) + 1
        resume.append(f"  - types : {sorted(types.items(), key=lambda x: -x[1])[:15]}")
        (SORTIE / "cb_contrats_2026_2027.head.csv").write_bytes(r.content[:300_000])
    r = get(FICHIERS_CB["attributions_2026_2027"], max_octets=300_000)
    if r is not None and r.ok:
        t = r.content.decode("utf-8-sig", "replace")
        t = t[:t.rfind("\n")]
        rangs = list(csv.reader(io.StringIO(t)))
        resume.append(f"  - avis d'attribution : colonnes {rangs[0]}")
        for rg in rangs[1:3]:
            resume.append("    - " + json.dumps({k: v[:100] for k, v in zip(rangs[0], rg) if v and "contact" not in k.lower()},
                                                 ensure_ascii=False)[:2500])
    for nom, url in [("cb_soutien_contrats.html", "https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/COsoutien-CHsupport-eng.html"),
                     ("cb_soutien_avis.html", "https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/soutien-support-eng.html"),
                     ("canada_ca_terms.html", "https://www.canada.ca/en/transparency/terms.html")]:
        r = get(url)
        sauver(nom, r)
        if r is not None and r.ok:
            t = texte(r.content.decode("utf-8", "replace"))
            for mot in ("updated", "daily", "frequency", "refresh", "robot", "automated", "Open Government Licence",
                        "reproduc", "commercial"):
                for m in re.finditer(mot, t, re.I):
                    resume.append(f"    - [{nom}] …{t[max(0, m.start() - 200):m.start() + 250]}…")
                    break


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    for etape in (fda, sec_13f, canadabuys):
        try:
            etape()
        except Exception as e:  # noqa: BLE001
            resume.append(f"- ÉTAPE {etape.__name__} PLANTÉE : {type(e).__name__}: {e}")
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
