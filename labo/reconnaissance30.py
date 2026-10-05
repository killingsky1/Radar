"""Reconnaissance 30 : les formats exacts des fichiers de la SEC avant le rejeu d'un an de Radar."""
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/recon30")
SORTIE.mkdir(parents=True, exist_ok=True)
robots, dernier, resume = {}, {}, []


def dire(t=""):
    print(t, flush=True)
    resume.append(t)
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers={"User-Agent": ua(hote)}, timeout=(20, 40))
            robots[hote] = {"statut": r.status_code, "texte": r.text[:4000]}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(ua(hote)) if robots[hote].get("statut") == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
    return robots[hote]["rp"]


def permis(url):
    hote = urlparse(url).hostname
    return regles(hote).can_fetch(ua(hote), url)


def lire(url, max_octets=20_000_000):
    """(statut, octets) ; (None, None) si robots.txt ne permet pas. Redirections suivies à la main (robots de chaque site)."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not permis(url):
            return None, None
        reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
        if reste > 0:
            time.sleep(reste)
        try:
            r = requests.get(url, headers={"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"},
                             timeout=(20, 180), stream=True, allow_redirects=False)
        except Exception as exc:  # noqa: BLE001
            dernier[hote] = time.monotonic()
            return f"erreur {type(exc).__name__}", b""
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            dernier[hote] = time.monotonic()
            r.close()
            url = urljoin(url, r.headers["location"])
            continue
        morceaux, taille = [], 0
        for m in r.iter_content(1 << 16):
            morceaux.append(m)
            taille += len(m)
            if taille > max_octets:
                break
        r.close()
        dernier[hote] = time.monotonic()
        return r.status_code, b"".join(morceaux)
    return "trop de redirections", b""

import io
import json
import re
import zipfile
from collections import Counter

sys.path.insert(0, str(Path("principal/robot").resolve()))
from radar.collecteurs import sec  # noqa: E402


def contenu(url, maxi=300_000_000):
    statut, b = lire(url, maxi)
    if statut != 200:
        raise RuntimeError(f"{url} : {statut}")
    return b


dire("# Reconnaissance 30 : formats des fichiers pour le rejeu d'un an\n")
PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
page = contenu(PAGE).decode("utf-8", "replace")
liens = {f"{m.group(2)}q{m.group(3)}": urljoin(PAGE, m.group(1))
         for m in re.finditer(r"""href=["']([^"']*?(\d{4})q([1-4])_form345\.zip)["']""", page, re.I)}
dire(f"- jeux de données : {sorted(liens)[:2]} … {sorted(liens)[-3:]}")
z = zipfile.ZipFile(io.BytesIO(contenu(liens["2025q4"])))
dire(f"- fichiers de 2025q4 : {z.namelist()}")


def table(nom):
    vrai = next(n for n in z.namelist() if n.upper().endswith(nom))
    lignes = z.read(vrai).decode("utf-8", "replace").replace("\r", "").split("\n")
    entete = lignes[0].split("\t")
    return entete, [l.split("\t") for l in lignes[1:] if l]


h, sub = table("SUBMISSION.TSV")
c = {k: i for i, k in enumerate(h)}
dire(f"- SUBMISSION : {len(sub):,} lignes · colonnes {h}")
dire(f"  DOCUMENT_TYPE : {Counter(l[c['DOCUMENT_TYPE']] for l in sub).most_common(8)}")
dire(f"  AFF10B5ONE : {Counter(l[c['AFF10B5ONE']] for l in sub if len(l) > c['AFF10B5ONE']).most_common(6)}")
dire(f"  FILING_DATE (exemples) : {[l[c['FILING_DATE']] for l in sub[:3]]} · ISSUERTRADINGSYMBOL : "
     f"{Counter(l[c['ISSUERTRADINGSYMBOL']] for l in sub).most_common(5)}")
h, own = table("REPORTINGOWNER.TSV")
c = {k: i for i, k in enumerate(h)}
dire(f"- REPORTINGOWNER : colonnes {h}")
dire(f"  RPTOWNER_RELATIONSHIP : {Counter(l[c['RPTOWNER_RELATIONSHIP']] for l in own).most_common(12)}")
dire(f"  RPTOWNER_TITLE (exemples) : {Counter(l[c['RPTOWNER_TITLE']] for l in own).most_common(8)}")
h, tr = table("NONDERIV_TRANS.TSV")
c = {k: i for i, k in enumerate(h)}
dire(f"- NONDERIV_TRANS : colonnes {h}")
p = [l for l in tr if len(l) > c["TRANS_CODE"] and l[c["TRANS_CODE"]] == "P"][:3]
dire(f"  exemples P : {[[l[c[k]] for k in ('TRANS_DATE', 'TRANS_SHARES', 'TRANS_PRICEPERSHARE', 'TRANS_ACQUIRED_DISP_CD', 'SECURITY_TITLE_FN', 'TRANS_DATE_FN', 'EQUITY_SWAP_TRANS_CD_FN', 'TRANS_SHARES_FN', 'TRANS_PRICEPERSHARE_FN', 'TRANS_ACQUIRED_DISP_CD_FN')] for l in p]}")
fn = Counter(l[c["TRANS_PRICEPERSHARE_FN"]] for l in tr if len(l) > c["TRANS_PRICEPERSHARE_FN"] and l[c["TRANS_PRICEPERSHARE_FN"]])
dire(f"  notes sur le prix (exemples) : {fn.most_common(5)}")
h, fo = table("FOOTNOTES.TSV")
dire(f"- FOOTNOTES : colonnes {h} · exemple {fo[0][:3] if fo else None}")

# 13D : index trimestriel de la SEC
idx = contenu("https://www.sec.gov/Archives/edgar/full-index/2025/QTR4/master.idx").decode("latin-1").splitlines()
formes = Counter(l.split("|")[2] for l in idx if l.count("|") == 4 and "13D" in l.split("|")[2])
dire(f"- index 2025 T4 : formes avec 13D {formes.most_common()}")
un = next(l for l in idx if l.count("|") == 4 and l.split("|")[2] == "SCHEDULE 13D")
texte = contenu("https://www.sec.gov/Archives/" + un.split("|")[4]).decode("utf-8", "replace")
f = sec.lire_13dg(texte)
dire(f"- un 13D lu par le robot : {un} → {{type: {f['type']}, types: {f['types_declarants']}, sous-évalué: {f['but_sous_evalue']}, émetteur: {f['cik_emetteur']} {f['nom_emetteur']}}} · {len(texte):,} caractères")

# Prix : liste des fichiers d'échecs de livraison
PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
ftd = sorted(re.findall(r"cnsfails(\d{6}[ab])\.zip", contenu(PAGE_FTD).decode("utf-8", "replace"), re.I))
dire(f"- fichiers d'échecs de livraison : {len(set(ftd))} · du {min(ftd)} au {max(ftd)} · 2025 : {sorted({x for x in ftd if x.startswith('2025')})}")

# Actions : un dossier companyconcept (champ « filed » présent ?)
cc = json.loads(contenu("https://data.sec.gov/api/xbrl/companyconcept/CIK0001326380/dei/EntityCommonStockSharesOutstanding.json"))
dire(f"- companyconcept GME : {cc['units']['shares'][-1]}")
sub_gme = json.loads(contenu("https://data.sec.gov/submissions/CIK0001326380.json"))
dire(f"- fiche GME : clés {sorted(sub_gme)} · exchanges {sub_gme.get('exchanges')} · formes récentes {Counter(sub_gme['filings']['recent']['form']).most_common(6)}")
dire("\nVERDICT : sonde faite")
