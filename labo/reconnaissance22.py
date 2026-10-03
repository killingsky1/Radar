"""Lot 3d, livraison 2 : vraies données des tests et MESURES (mêmes règles : robots.txt d'abord, lu avec notre
identification ; 401/403 = interdit ; Crawl-delay respecté, sinon 1,5 s par site ; clés masquées ; rien n'est contourné ;
courriel seulement pour la SEC).

- USAspending : contrats de 100 M$ et plus signés depuis 150 jours (toutes les pages), fiches détaillées, date de mise à
  jour, page publique d'un contrat ;
- Participations du gouvernement : détection AMÉLIORÉE (abréviations définies dans le texte, mot « shares », revente,
  communiqués joints EX-99) mesurée sur 8 cas réels et sur 200 8-K pris au hasard (2 jours).
Tout est gardé compressé (gzip) dans labo/fixtures-lot3d2, avec pages.json : adresse -> fichier.
"""
import json
import re
import time
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/fixtures-lot3d2")
SORTIE.mkdir(parents=True, exist_ok=True)
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|rss|feed|api|export|download|terms|conditions"
                          r"|legal|copyright|policy|polic|exclu|holding|investments|press|news|bulletin|fails", re.I)
robots, resultats, dernier = {}, {}, {}
AUJ = date.today()
# Des pages publiques contiennent parfois des clés d'accès (ex. une clé Mapbox dans la page de NBIM) : on ne les garde
# jamais. Elles sont masquées avant tout enregistrement.
CLES = [re.compile(rb"\b(?:pk|sk|tk)\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"), re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
        re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        re.compile(rb"(?i)((?:access_?token|api_?key|apikey|secret|token)[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._~+/-]{16,}")]


def masquer(contenu, type_contenu):
    if not re.search(r"html|json|xml|javascript|text", type_contenu or ""):
        return contenu, 0
    n = 0
    for motif in CLES:
        contenu, k = motif.subn(lambda m: (m.group(1) if m.groups() else b"") + b"[cle masquee]", contenu)
        n += k
    return contenu, n


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def entetes(hote):
    return {"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=entetes(hote), timeout=(20, 40), allow_redirects=True)
            robots[hote] = {"statut": r.status_code, "texte": r.text[:6000], "url_finale": r.url}
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
        print("robots.txt", hote, robots[hote].get("statut"), "délai", robots[hote]["delai"], flush=True)
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, corps=None):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(ua(hote), url):
            return None, url
        attendre(hote)
        if corps is None:
            r = requests.get(url, headers=entetes(hote), timeout=(20, 180), stream=True, allow_redirects=False)
        else:
            r = requests.post(url, headers={**entetes(hote), "Content-Type": "application/json"}, data=json.dumps(corps),
                              timeout=(20, 180), stream=True, allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            corps = None
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, corps=None, garde=MAX_GARDE):
    res = {"url": url, "post": corps}
    try:
        r, finale = requete(url, corps)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            contenu, masquees = masquer(b"".join(morceaux)[:garde], r.headers.get("content-type"))
            res["cles_masquees"] = masquees
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": taille,
                        "complet": taille <= garde,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control", "retry-after",
                                                     "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding",
                                                     "server")},
                        "debut": contenu[:600].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(contenu)
            if "html" in (r.headers.get("content-type") or ""):
                texte = contenu.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:200]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)
    return res




import gzip  # noqa: E402
import html as html_mod  # noqa: E402

pages = {}


def garder(nom, url, corps=None, cle=None):
    r = visiter(nom, url, corps)
    f = SORTIE / f"{nom}.bin"
    if r.get("statut") == 200 and f.exists():
        (SORTIE / f"{nom}.gz").write_bytes(gzip.compress(f.read_bytes(), 9))
        pages[cle or url] = f"{nom}.gz"
    f.unlink(missing_ok=True)
    return r


def lu(nom):
    f = SORTIE / f"{nom}.gz"
    return gzip.decompress(f.read_bytes()) if f.exists() else None


# ---------- USAspending ----------
US = "https://api.usaspending.gov/api/v2/"
CHAMPS = ["Award ID", "Recipient Name", "Recipient UEI", "Award Amount", "Awarding Agency", "Awarding Sub Agency",
          "Contract Award Type", "Start Date", "Base Obligation Date", "Last Modified Date", "Description",
          "generated_internal_id"]
debut, fin = (AUJ - timedelta(days=150)).isoformat(), AUJ.isoformat()
contrats = []
for page in range(1, 8):
    corps = {"filters": {"award_type_codes": ["A", "B", "C", "D"],
                         "time_period": [{"start_date": debut, "end_date": fin, "date_type": "new_awards_only"}],
                         "award_amounts": [{"lower_bound": 100_000_000}]},
             "fields": CHAMPS, "sort": "Award Amount", "order": "desc", "limit": 100, "page": page}
    garder(f"us_page_{page}", US + "search/spending_by_award/", corps, cle=f"POST {US}search/spending_by_award/ page={page}")
    c = lu(f"us_page_{page}")
    if not c:
        break
    d = json.loads(c)
    contrats += d.get("results") or []
    if not (d.get("page_metadata") or {}).get("hasNext"):
        break
garder("us_mise_a_jour", US + "awards/last_updated/")
for i, x in enumerate(contrats[:8]):
    garder(f"us_fiche_{i}", US + f"awards/{x['generated_internal_id']}/")
if contrats:
    garder("us_page_publique", f"https://www.usaspending.gov/award/{contrats[0]['generated_internal_id']}")
par_agence, par_mois = {}, {}
for x in contrats:
    par_agence[x.get("Awarding Agency")] = par_agence.get(x.get("Awarding Agency"), 0) + 1
    m = (x.get("Base Obligation Date") or "")[:7]
    cle_m = (("Défense" if "Defense" in (x.get("Awarding Agency") or "") or "War" in (x.get("Awarding Agency") or "")
              else "autres"), m)
    par_mois[str(cle_m)] = par_mois.get(str(cle_m), 0) + 1
resultats["mesure_usaspending"] = {"contrats": len(contrats), "par_agence": par_agence, "par_mois_signature": par_mois}
print("USAspending :", len(contrats), "contrats ;", par_agence, flush=True)

# ---------- Participations du gouvernement : détection améliorée ----------
GOUV = (r"(?:U\.S\.|United\s+States)\s+(?:Department|Dept\.)\s+of\s+(?:Commerce|War|Defense|Energy)"
        r"|Department\s+of\s+(?:Commerce|War|Defense|Energy)|United\s+States\s+of\s+America"
        r"|(?:U\.S\.|United\s+States)\s+[Gg]overnment|[Ff]ederal\s+[Gg]overnment")
DEFINITION = re.compile(r"(?:" + GOUV + r")[^()]{0,120}?\(\s*(?:the\s+|each,?\s+a\s+)?[“\"‘']\s*([A-Z][A-Za-z.\- ]{1,24}?)\s*[”\"’']\s*\)")
TITRE = re.compile(r"\bwarrants?\b|preferred\s+stock|common\s+stock|common\s+shares|\bshares\b|equity\s+(?:stake|interest|"
                   r"investment)|ownership\s+interest", re.I)
VERBE = re.compile(r"\b(?:issue[sd]?|issuance|issuing|sell|sold|sale|resale|resell|purchase[sd]?|purchasing|acquire[sd]?|"
                   r"acquisition|grant(?:ed)?|receive[sd]?|hold(?:s|ing)?|own(?:s|ed)?|subscri(?:be|bed|ption)|"
                   r"invest(?:s|ed|ment)?|convert(?:ible|s|ed)?)\b", re.I)
ABREV = re.compile(r"\b(U\.S|Inc|Corp|Co|Ltd|No|Nos|Mr|Ms|Dr|Jr|Sr|St|L\.L\.C|L\.P|N\.A|S\.A)\.")


def texte_doc(contenu):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", contenu.decode("utf-8", "replace"))
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", t)
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").split())


def phrases_gouv(texte):
    alias = sorted({a.strip() for a in DEFINITION.findall(texte) if len(a.strip()) >= 2}, key=len, reverse=True)
    motif = re.compile(GOUV + "".join(r"|\b" + re.escape(a) + r"\b" for a in alias))
    protege = ABREV.sub(lambda m: m.group(0).replace(".", "·"), texte)
    phrases = re.split(r"(?<=[.;])\s+(?=[A-Z(“\"])", protege)
    trouve = [p.replace("·", ".") for p in phrases if motif.search(p.replace("·", ".")) and TITRE.search(p) and VERBE.search(p)]
    return alias, [p[:700] for p in trouve][:8]


def documents(cik, acc):
    """Le document principal et les communiqués joints (EX-99) d'un dépôt, d'après sa page d'index officielle."""
    nom = f"index_{acc}"
    garder(nom, f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm")
    page = (lu(nom) or b"").decode("utf-8", "replace")
    (SORTIE / f"{nom}.gz").unlink(missing_ok=True)
    pages.pop(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm", None)
    docs = []
    for ligne in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        lien = re.search(r'href="(?:/ix\?doc=)?(/Archives/edgar/data/[^"]+\.htm)"', ligne)
        sorte = re.findall(r"<td[^>]*>([^<]*)</td>", ligne)
        if lien and sorte:
            type_doc = sorte[-2].strip() if len(sorte) >= 2 else ""
            if type_doc in ("8-K", "8-K/A") or type_doc.startswith("EX-99"):
                docs.append((type_doc, "https://www.sec.gov" + lien.group(1)))
    return docs[:4]


def analyser(cik, acc, garder_texte):
    res = []
    for i, (type_doc, url) in enumerate(documents(cik, acc)):
        nom = f"doc_{acc}_{i}"
        garder(nom, url)
        c = lu(nom)
        if c is None:
            continue
        alias, ph = phrases_gouv(texte_doc(c))
        if not (garder_texte or ph):
            (SORTIE / f"{nom}.gz").unlink(missing_ok=True)
            pages.pop(url, None)
        res.append({"type": type_doc, "url": url, "alias": alias, "phrases": ph})
    return res


CAS = {"INTC": ("2025-08-20", "2025-09-05"), "MP": ("2025-07-08", "2025-07-20"), "QBTS": ("2026-09-01", "2026-09-20"),
       "LAC": ("2025-09-25", "2025-10-20"), "TMQ": ("2025-10-01", "2025-10-20"), "USAR": ("2026-01-20", "2026-02-10"),
       "LHX": ("2026-01-10", "2026-04-30"), "RGTI": ("2026-09-01", "2026-09-20")}
garder("sec_symboles", "https://www.sec.gov/files/company_tickers_exchange.json")
table = json.loads(lu("sec_symboles") or b'{"data": []}')
(SORTIE / "sec_symboles.gz").unlink(missing_ok=True)
pages.pop("https://www.sec.gov/files/company_tickers_exchange.json", None)
cik_de = {x[2]: x[0] for x in table["data"]}
mesure = {"cas": {}, "echantillon": {}}
for symbole, (de, a) in CAS.items():
    cik = cik_de.get(symbole)
    r = visiter(f"soumissions_{symbole}", f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json") if cik else {}
    f = SORTIE / f"soumissions_{symbole}.bin"
    depots = []
    if f.exists():
        rec = json.loads(f.read_bytes())["filings"]["recent"]
        f.unlink()
        depots = [(rec["accessionNumber"][i], rec["filingDate"][i], rec["items"][i]) for i in range(len(rec["form"]))
                  if rec["form"][i] == "8-K" and de <= rec["filingDate"][i] <= a]
    mesure["cas"][symbole] = [{"acc": acc, "jour": j, "points": it, "documents": analyser(cik, acc, True)}
                              for acc, j, it in depots]
    print("cas", symbole, [(x["jour"], sum(len(d["phrases"]) for d in x["documents"])) for x in mesure["cas"][symbole]],
          flush=True)

for jour in ("20261001", "20261002"):
    garder(f"index_jour_{jour}", f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.{jour}.idx")
    t = (lu(f"index_jour_{jour}") or b"").decode("latin-1")
    (SORTIE / f"index_jour_{jour}.gz").unlink(missing_ok=True)
    pages.pop(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.{jour}.idx", None)
    lignes = [l for l in t.splitlines() if l.startswith("8-K ")][:100]
    marques = []
    for l in lignes:
        chemin = l.split()[-1]
        cik, acc = chemin.split("/")[2], chemin.split("/")[-1][:-4]
        docs = analyser(cik, acc, False)
        if any(d["phrases"] for d in docs):
            marques.append({"acc": acc, "cik": cik, "documents": [d for d in docs if d["phrases"]]})
    mesure["echantillon"][jour] = {"8k": len(lignes), "marques": marques}
    print("échantillon", jour, len(lignes), "marqués", len(marques), flush=True)

(SORTIE / "participations_mesure.json").write_text(json.dumps(mesure, ensure_ascii=False, indent=1), encoding="utf-8")
(SORTIE / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
(SORTIE / "resultats.json").write_text(json.dumps(
    {"pages": resultats, "robots": {h: {k: v for k, v in r.items() if k != "rp"} for h, r in robots.items()}},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("fini")
