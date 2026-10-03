"""Mesure du VRAI code du robot (branche d'essai, module radar.collecteurs.participations) avant sa mise en ligne.

Mêmes règles : robots.txt d'abord (identification avec courriel, seulement pour la SEC) ; 1,5 s entre deux requêtes.
- les 8 cas réels de 2025-2026 : chaque 8-K des périodes connues (points lus par le robot, extraits trouvés) ;
- tous les 8-K de 3 jours ouvrables (100 au plus par jour, dans l'ordre de l'index officiel) : chaque extrait signalé
  est écrit en entier pour être relu à la main (vrai cas ou fausse alerte).
"""
import sys  # noqa: E402
sys.path.insert(0, "code/robot")
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
SORTIE = Path("labo/resultats-participations")
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




from radar.collecteurs import participations as pa  # noqa: E402


def page(nom, url):
    r = visiter(nom, url)
    f = SORTIE / f"{nom}.bin"
    contenu = f.read_bytes() if r.get("statut") == 200 and f.exists() else None
    f.unlink(missing_ok=True)
    return contenu


def analyser(cik, acc):
    """Comme le robot : points de l'en-tête, puis document principal et EX-99 si un point 1.01, 3.02 ou 8.01."""
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    entete = (page(f"h_{acc}", f"{base}/{acc}-index-headers.html") or b"").decode("utf-8", "replace")
    points = [p["item"] for p in pa.points(entete)]
    if not points:
        return {"acc": acc, "points": [], "documents": []}
    index = (page(f"i_{acc}", f"{base}/{acc}-index.htm") or b"").decode("utf-8", "replace")
    docs = []
    for url, sorte in pa.documents_du_depot(index):
        c = page(f"d_{acc}", url)
        ts = pa.passages(pa.texte_doc(c)) if c else []
        docs.append({"url": url, "type": sorte, "extraits": [t["extrait"] for t in ts]})
    return {"acc": acc, "points": points, "documents": docs}


CAS = {"INTC": ("2025-08-20", "2025-09-05"), "MP": ("2025-07-08", "2025-07-20"), "QBTS": ("2026-09-01", "2026-09-20"),
       "LAC": ("2025-09-25", "2025-10-20"), "TMQ": ("2025-10-01", "2025-10-20"), "USAR": ("2026-01-20", "2026-02-10"),
       "LHX": ("2026-01-10", "2026-04-30"), "RGTI": ("2026-09-01", "2026-09-20")}
table = json.loads(page("symboles", "https://www.sec.gov/files/company_tickers_exchange.json") or b'{"data": []}')
cik_de = {x[2]: x[0] for x in table["data"]}
mesure = {"cas": {}, "jours": {}}
for symbole, (de, a) in CAS.items():
    cik = cik_de.get(symbole)
    rec = json.loads(page(f"s_{symbole}", f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json") or b"{}")
    rec = (rec.get("filings") or {}).get("recent") or {"form": []}
    accs = [rec["accessionNumber"][i] for i in range(len(rec["form"])) if rec["form"][i] == "8-K"
            and de <= rec["filingDate"][i] <= a]
    mesure["cas"][symbole] = [analyser(cik, acc) for acc in accs]
    print("cas", symbole, [(x["points"], sum(len(d["extraits"]) for d in x["documents"])) for x in mesure["cas"][symbole]],
          flush=True)

for jour in ("20260930", "20261001", "20261002"):
    t = (page(f"idx_{jour}", f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/form.{jour}.idx"
              if jour < "20261001" else f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/form.{jour}.idx")
         or b"").decode("latin-1")
    lignes = [l for l in t.splitlines() if l.startswith("8-K ")][:100]
    lus, avec_points, signales = 0, 0, []
    for l in lignes:
        chemin = l.split()[-1]
        r = analyser(chemin.split("/")[2], chemin.split("/")[-1][:-4])
        lus += 1
        avec_points += bool(r["points"])
        if any(d["extraits"] for d in r["documents"]):
            signales.append(r)
    mesure["jours"][jour] = {"8k": len(lignes), "lus": lus, "avec_points_1_01_3_02_8_01": avec_points,
                             "signales": signales}
    print("jour", jour, len(lignes), "avec points", avec_points, "signalés", len(signales), flush=True)

(SORTIE / "mesure.json").write_text(json.dumps(mesure, ensure_ascii=False, indent=1), encoding="utf-8")
print("fini")
