"""Recherche avant le plan de match (fins de blocage, prix, rachats d'actions, FINRA) : vérifié EN DIRECT, avec les
règles du robot (robots.txt lu d'abord avec notre identification ; 401/403 ou robots.txt illisible = interdit ;
Crawl-delay respecté, sinon au moins 1,5 s entre deux requêtes au même site ; une seule requête à la fois ; rien n'est
contourné ; courriel seulement pour la SEC ; aucun formulaire, aucun compte, aucun courriel envoyé).

A. robots.txt et conditions d'utilisation : FINRA (ventes à découvert), IEX (prix HIST), Nasdaq Trader, data.sec.gov.
   Aucune donnée de FINRA n'est téléchargée (seulement robots.txt et la page des conditions).
B. Prix publiés par la SEC dans les fichiers d'échecs de livraison : quelle part de nos compagnies y a un prix, et
   combien de jours.
C. API officielle data.sec.gov (frames) : combien de compagnies déclarent des rachats d'actions en XBRL.
D. Fins de blocage : TOUS les prospectus 424B4 de juillet à septembre 2026, règle stricte mesurée.
E. Rachats d'actions annoncés : tous les 8-K du 1er et du 2 octobre 2026 (points 2.02, 7.01, 8.01), phrases trouvées.
"""
import csv
import gzip
import html
import io
import json
import re
import sys
import time
import urllib.robotparser
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/resultats-plan-fgh")
SORTIE.mkdir(parents=True, exist_ok=True)
DONNEES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("principal/data")
DEBUT = time.monotonic()
LIMITE_S = 70 * 60  # le travail E s'arrête proprement avant la fin du temps permis
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


BLOC = re.compile(r"</?(?:p|div|td|th|tr|br|li|h\d|table|center|font\s+size)\b[^>]*>", re.I)


def texte_html(raw: str) -> str:
    raw = BLOC.sub(" ", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return " ".join(html.unescape(raw).replace("​", " ").replace("\xa0", " ").split())


def phrases_cles(texte, mots, n=30):
    out = []
    for p in re.split(r"(?<=[.!?;])\s+", texte):
        if any(re.search(m, p, re.I) for m in mots) and len(p) < 1500:
            out.append(p.strip())
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- A. robots.txt et conditions
dire("# Recherche avant le plan de match — vérifiée en direct par le labo (GitHub), avec les règles du robot")
dire(f"Date : {datetime.utcnow():%Y-%m-%d %H:%M} UTC")
dire()
dire("## A. robots.txt et conditions d'utilisation")
CIBLES = {
    "FINRA ventes à découvert (page des fichiers)": "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files",
    "FINRA fichier de ventes à découvert (CDN)": "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260915.csv",
    "FINRA API": "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest",
    "FINRA conditions": "https://www.finra.org/terms-of-use",
    "IEX HIST (liste des fichiers)": "https://iextrading.com/api/1.0/hist?date=20261002",
    "IEX page des données": "https://iextrading.com/trading/market-data/",
    "IEX conditions HIST": "https://www.iexexchange.io/legal/hist-data-terms",
    "Nasdaq Trader conditions": "https://www.nasdaqtrader.com/Trader.aspx?id=CopyDisclaimMain",
    "Nasdaq Trader liste des symboles": "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt",
    "SEC API data.sec.gov (frames)": "https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025.json",
}
for nom, url in CIBLES.items():
    ok = permis(url)
    h = urlparse(url).hostname
    dire(f"- {nom} : robots.txt de {h} → statut {robots[h].get('statut')}"
         f"{' (' + robots[h]['erreur'] + ')' if robots[h].get('erreur') else ''} · délai {robots[h]['delai']} · "
         f"{'PERMIS' if ok else 'INTERDIT'} · {url}")
(SORTIE / "robots.json").write_text(json.dumps({h: {k: v for k, v in r.items() if k != "rp"} for h, r in robots.items()},
                                               ensure_ascii=False, indent=1), encoding="utf-8")

MOTS_CONDITIONS = [r"robot", r"scrap", r"crawl", r"spider", r"automat", r"data mining", r"harvest", r"commercial",
                   r"redistribut", r"resell|resale", r"attribut|cite IEX|provided for free", r"written consent",
                   r"personal", r"bulk"]
for nom in ("FINRA conditions", "IEX conditions HIST", "Nasdaq Trader conditions"):
    url = CIBLES[nom]
    statut, contenu = lire(url, 5_000_000)
    if statut is None:
        dire(f"### {nom} : non lue (robots.txt ne le permet pas)")
        continue
    t = texte_html(contenu.decode("utf-8", "replace"))
    (SORTIE / f"conditions_{nom.split()[0].lower()}.txt").write_text(t[:400000], encoding="utf-8")
    dire(f"### {nom} : HTTP {statut}, {len(t)} caractères · {url}")
    for p in phrases_cles(t, MOTS_CONDITIONS, 25):
        dire(f"  > {p[:700]}")

# IEX : la liste officielle des fichiers HIST (aucun gros fichier téléchargé)
statut, contenu = lire(CIBLES["IEX HIST (liste des fichiers)"], 2_000_000)
if statut is None:
    dire("### IEX HIST : liste non lue (robots.txt ne le permet pas)")
else:
    dire(f"### IEX HIST : HTTP {statut}")
    try:
        for f in json.loads(contenu)[:6]:
            dire(f"  - {f.get('feed')} {f.get('protocol')} {f.get('version')} · {int(f.get('size', 0)) / 1e9:.1f} Go · "
                 f"{f.get('date')} · {urlparse(f.get('link', '')).hostname}")
    except Exception as exc:  # noqa: BLE001
        dire(f"  - réponse non lisible en JSON : {contenu[:200]!r} ({exc})")

# FINRA : la page des fichiers (liens seulement, aucun fichier de données téléchargé)
statut, contenu = lire(CIBLES["FINRA ventes à découvert (page des fichiers)"], 5_000_000)
if statut is not None:
    t = contenu.decode("utf-8", "replace")
    liens = sorted(set(re.findall(r"""href=["']([^"']*(?:shrt|short)[^"']*)["']""", t, re.I)))[:15]
    dire(f"### FINRA page des fichiers : HTTP {statut} · liens : {liens}")

# ---------------------------------------------------------------- B. prix des fichiers d'échecs de livraison (SEC)
dire()
dire("## B. Prix publiés par la SEC (fichiers d'échecs de livraison)")
PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
statut, contenu = lire(PAGE_FTD, 5_000_000)
fichiers = []
if statut is not None and contenu:
    fichiers = sorted({urljoin(PAGE_FTD, h) for h in re.findall(r"""href=["']([^"']*cnsfails\d{6}[ab]\.zip)["']""",
                                                                 contenu.decode("utf-8", "replace"), re.I)})
dire(f"- page {PAGE_FTD} : HTTP {statut} · {len(fichiers)} fichiers · derniers : {[f.rsplit('/', 1)[1] for f in fichiers[-3:]]}")
prix = {}  # symbole -> {jour: prix}
for f in fichiers[-2:]:
    statut, contenu = lire(f, 40_000_000)
    if statut != 200:
        dire(f"- {f} : HTTP {statut}")
        continue
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        brut = z.read(z.namelist()[0]).decode("latin-1")
    lignes = [l.split("|") for l in brut.splitlines()[1:] if l.count("|") >= 5]
    jours = sorted({l[0] for l in lignes})
    for l in lignes:
        try:
            p = float(l[5])
        except ValueError:
            continue
        prix.setdefault(l[2].strip(), {})[l[0]] = p
    dire(f"- {f.rsplit('/', 1)[1]} : {len(lignes)} lignes · {len({l[2] for l in lignes})} symboles · "
         f"{len(jours)} jours ({jours[0] if jours else '?'} → {jours[-1] if jours else '?'})")
tous_jours = sorted({j for d in prix.values() for j in d})
auj = json.loads((DONNEES / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
argent = json.loads((DONNEES / "app" / "argent.json").read_text(encoding="utf-8"))
groupes = {
    "listes du jour (hausse et baisse)": sorted({x["symbole"] for x in auj["hausse"] + auj["baisse"]}),
    "section Argent (30 jours)": sorted({l["symbole"] for l in argent["lignes"] if l.get("symbole")}),
}
for nom, syms in groupes.items():
    if not tous_jours:
        break
    avec = [s for s in syms if s in prix]
    part_jours = [len(prix[s]) / len(tous_jours) for s in avec]
    dire(f"- {nom} : {len(avec)}/{len(syms)} symboles ont au moins un prix · en moyenne "
         f"{(sum(part_jours) / len(part_jours) * 100 if part_jours else 0):.0f} % des {len(tous_jours)} jours")
    if nom.startswith("listes"):
        dire("  " + " · ".join(f"{s} {len(prix.get(s, {}))}/{len(tous_jours)}" for s in syms))

# ---------------------------------------------------------------- C. rachats en XBRL (frames de data.sec.gov)
dire()
dire("## C. Rachats d'actions déclarés en XBRL (API officielle data.sec.gov, « frames »)")
for chemin in ("us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2025", "us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2026Q1",
               "us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY2026Q2", "us-gaap/StockRepurchasedDuringPeriodValue/USD/CY2026Q2",
               "us-gaap/StockRepurchaseProgramAuthorizedAmount1/USD/CY2026Q2I",
               "srt/StockRepurchaseProgramAuthorizedAmount1/USD/CY2026Q2I"):
    url = f"https://data.sec.gov/api/xbrl/frames/{chemin}.json"
    statut, contenu = lire(url, 60_000_000)
    if statut != 200:
        dire(f"- {chemin} : HTTP {statut}")
        continue
    d = json.loads(contenu)
    donnees = sorted(d.get("data", []), key=lambda x: -x.get("val", 0))
    dire(f"- {chemin} : {len(donnees)} compagnies · plus gros : "
         + " · ".join(f"{x.get('entityName', '')[:28]} {x.get('val', 0) / 1e9:.1f} G$" for x in donnees[:3]))

# ---------------------------------------------------------------- D. fins de blocage : tous les 424B4 de juillet à septembre
dire()
dire("## D. Fins de blocage : tous les prospectus 424B4 de juillet à septembre 2026 (règle stricte)")
MOIS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
N = r"(?:[a-z][a-z -]*\((\d{2,3})\)|(\d{2,3}))"
ANTICIPEE = re.compile(
    r"(?:closing|last reported sale) price[^.]{0,250}(?:exceed|at least|greater than|equal to or greater)[^.]{0,150}"
    r"(?:initial public )?offering price|(?:release|announcement) of (?:our |its )?(?:earnings|quarterly|financial "
    r"results)[^.]{0,200}(?:lock-?up|restricted period)|(?:lock-?up|restricted period)[^.]{0,200}(?:release|"
    r"announcement) of (?:our |its )?(?:earnings|quarterly|financial results)|early release|earlier of[^.]{0,200}"
    r"(?:lock-?up|restricted period|trading day)", re.I)


def jour(s):
    return datetime.strptime(" ".join(s.split()), "%B %d, %Y").date()


def documents(txt: str):
    """(type, texte) de chaque document du dépôt complet (.txt)."""
    for m in re.finditer(r"<DOCUMENT>\s*<TYPE>([^\n<]+)(.*?)</DOCUMENT>", txt, re.S):
        yield m.group(1).strip(), m.group(2)


def jours_ouvrables(a: date, b: date) -> int:
    n, j = 0, a
    while j < b:
        j += timedelta(days=1)
        n += j.weekday() < 5
    return n


def analyser_424b4(principal: str, depose: date) -> dict:
    t = texte_html(principal)
    debut = t[:40000]
    r = {"ipo": bool(re.search(r"this is (?:an|the|our) initial public offering|prior to this offering,? there (?:has|have) "
                               r"been no (?:established )?public market", debut, re.I))}
    r["exclu"] = [w for w in ("blank check company", "direct listing", "special purpose acquisition") if w in debut.lower()]
    couv = {jour(m.group(1)) for m in re.finditer(r"(?:The date of this prospectus is|Prospectus dated)\s+(" + MOIS + ")",
                                                  t[:120000])}
    j25 = {jour(m.group(1)) - timedelta(days=25) for m in re.finditer(
        r"Through and including (" + MOIS + r")\s*\((?:the )?25(?:th)? days? after the (?:date of this prospectus|"
        r"commencement of this offering)", t)}
    r["dates"] = sorted(str(d) for d in couv | j25)
    r["deux_preuves"] = bool(couv and j25)
    durees, phrases = set(), []
    for s in re.split(r"(?<=[.;])\s", t):
        if not re.search(r"lock-?up|restricted period", s, re.I) or re.search(
                r"Rule 144|Rule 701|effective date of the registration|25 days|underwriter(?:s'|'s)? warrants|FINRA Rule 5110",
                s, re.I):
            continue
        for m in re.finditer(N + r"[ -]days? (?:after|from|following) the date of (?:this|the final) prospectus", s, re.I):
            durees.add(int(m.group(1) or m.group(2)))
            phrases.append(s[:400])
        for m in re.finditer(N + r"-day (?:lock-?up|restricted) period", s, re.I):
            durees.add(int(m.group(1) or m.group(2)))
            phrases.append(s[:400])
    r["durees"] = sorted(durees)
    r["anticipee"] = bool(ANTICIPEE.search(t))
    dates = couv | j25
    d0 = next(iter(dates)) if len(dates) == 1 else None
    r["ecart_ouvrables"] = jours_ouvrables(d0, depose) if d0 and d0 <= depose else None
    raisons = []
    if not r["ipo"]:
        raisons.append("pas une entrée en bourse")
    if r["exclu"]:
        raisons.append("exclu : " + ", ".join(r["exclu"]))
    if len(dates) != 1:
        raisons.append("date du prospectus absente" if not dates else "dates différentes")
    elif r["ecart_ouvrables"] is None or r["ecart_ouvrables"] > 2:
        raisons.append("date du prospectus loin du dépôt")
    if len(durees) != 1:
        raisons.append("aucune durée" if not durees else "plusieurs durées")
    if r["anticipee"]:
        raisons.append("clause de levée anticipée")
    r["raisons"] = raisons
    r["publiable"] = not raisons
    if r["publiable"]:
        r["fin"] = str(d0 + timedelta(days=next(iter(durees))))
        r["phrase"] = phrases[0]
    return r


def index_trimestre(annee, trim):
    statut, contenu = lire(f"https://www.sec.gov/Archives/edgar/full-index/{annee}/QTR{trim}/master.idx", 80_000_000)
    if statut != 200:
        dire(f"- index {annee} T{trim} : HTTP {statut}")
        return []
    lignes = [l.split("|") for l in contenu.decode("latin-1").splitlines() if l.count("|") == 4]
    return [l for l in lignes if l[2] == "424B4"]


t2 = index_trimestre(2026, 2)
t3 = index_trimestre(2026, 3)
dire(f"- 424B4 déposés : avril à juin {len(t2)} · juillet à septembre {len(t3)} (index officiels de la SEC)")
resultats_d = []
for cik, nom, forme, depose, fichier in t3[:400]:
    statut, contenu = lire(f"https://www.sec.gov/Archives/{fichier}", 25_000_000)
    if statut != 200:
        resultats_d.append({"acc": fichier, "nom": nom, "erreur": statut})
        continue
    txt = contenu.decode("latin-1")
    principal = next((corps for typ, corps in documents(txt) if typ.upper().startswith("424B4")), txt)
    r = analyser_424b4(principal, date.fromisoformat(depose[:10]))
    resultats_d.append({"acc": fichier.rsplit("/", 1)[1][:-4], "cik": cik, "nom": nom, "depose": depose, **r})
(SORTIE / "blocage.json").write_text(json.dumps(resultats_d, ensure_ascii=False, indent=1), encoding="utf-8")
ipos = [r for r in resultats_d if r.get("ipo") and not r.get("exclu")]
pub = [r for r in ipos if r.get("publiable")]
dire(f"- lus : {len(resultats_d)} · vraies entrées en bourse (sans SPAC ni inscription directe) : {len(ipos)} · "
     f"PUBLIABLES avec la règle stricte : {len(pub)}")
raisons = {}
for r in ipos:
    for x in r.get("raisons", []):
        raisons[x] = raisons.get(x, 0) + 1
dire(f"- raisons d'écarter une vraie entrée en bourse : {raisons}")
dire(f"- durées des publiables : { {d: sum(1 for r in pub if r['durees'] == [d]) for d in sorted({r['durees'][0] for r in pub})} }")
dire(f"- deux preuves de la date (couverture + « 25 jours ») qui concordent : {sum(1 for r in pub if r['deux_preuves'])}/{len(pub)}")
for r in pub[:40]:
    dire(f"  - {r['nom'][:40]} · prospectus {r['dates'][0]} · {r['durees'][0]} jours → fin {r['fin']} · {r['acc']}")

# ---------------------------------------------------------------- E. rachats d'actions annoncés dans les 8-K
dire()
dire("## E. Rachats d'actions annoncés : 8-K du 1er et du 2 octobre 2026 (points 2.02, 7.01, 8.01 ; document et EX-99)")
POINTS = ("results of operations and financial condition", "regulation fd disclosure", "other events")
RACHAT = re.compile(r"repurchase|buy-?back|buy back", re.I)
AUTORISE = re.compile(r"authoriz|approv", re.I)
MONTANT = re.compile(r"\$\s?[\d.,]+\s*(?:million|billion)|\b[\d,.]+\s*(?:million\s+)?shares", re.I)
EXCLURE = re.compile(r"\bnotes?\b|debenture|bonds?\b|repurchase agreement|preferred|warrant|redemption|trust account|"
                     r"convertible", re.I)
NOUVEAU = re.compile(r"\bnew\b[^.]{0,80}(?:program|authorization|plan)|authoriz\w+ (?:the )?(?:repurchase|buyback)s? of up to|"
                     r"(?:approved|authorized) a (?:share |stock )?(?:repurchase|buyback) (?:program|plan|authorization)", re.I)
HAUSSE = re.compile(r"increase|additional|expan|upsiz|replenish", re.I)
RESTE = re.compile(r"remain|available|as of|previously (?:announced|authorized)|existing", re.I)
lus_e, retenus, candidats = 0, 0, []
for jour_idx in ("20261001", "20261002"):
    statut, contenu = lire(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.{jour_idx}.idx", 20_000_000)
    if statut != 200:
        dire(f"- index du {jour_idx} : HTTP {statut}")
        continue
    huit = [l.split("|") for l in contenu.decode("latin-1").splitlines() if l.count("|") == 4 and l.split("|")[2] == "8-K"]
    dire(f"- {jour_idx} : {len(huit)} 8-K")
    for cik, nom, forme, depose, fichier in huit:
        if time.monotonic() - DEBUT > LIMITE_S:
            dire(f"  (arrêt : temps permis atteint après {lus_e} 8-K)")
            break
        statut, contenu = lire(f"https://www.sec.gov/Archives/{fichier}", 25_000_000)
        lus_e += 1
        if statut != 200:
            continue
        txt = contenu.decode("latin-1")
        entete = txt[:20000]
        items = [i.strip().lower() for i in re.findall(r"ITEM INFORMATION:\s*([^\n]+)", entete)]
        if not any(i.startswith(POINTS) for i in items):
            continue
        retenus += 1
        for typ, corps in documents(txt):
            if not (typ.upper().startswith("8-K") or typ.upper().startswith("EX-99")):
                continue
            t = texte_html(corps)
            for p in re.split(r"(?<=[.;])\s+", t):
                if len(p) > 1200 or not (RACHAT.search(p) and AUTORISE.search(p) and MONTANT.search(p)):
                    continue
                if EXCLURE.search(p):
                    classe = "exclu (dette, actions privilégiées, bons, SPAC…)"
                elif NOUVEAU.search(p):
                    classe = "nouveau programme"
                elif HAUSSE.search(p):
                    classe = "hausse d'un programme"
                elif RESTE.search(p):
                    classe = "reste d'un ancien programme"
                else:
                    classe = "à lire"
                candidats.append({"acc": fichier.rsplit("/", 1)[1][:-4], "nom": nom, "doc": typ, "items": items,
                                  "classe": classe, "phrase": p[:900]})
    else:
        continue
    break
(SORTIE / "rachats.json").write_text(json.dumps(candidats, ensure_ascii=False, indent=1), encoding="utf-8")
classes = {}
for c in candidats:
    classes[c["classe"]] = classes.get(c["classe"], 0) + 1
dire(f"- 8-K lus : {lus_e} · avec 2.02, 7.01 ou 8.01 : {retenus} · phrases candidates : {len(candidats)} · {classes}")
vus = set()
for c in candidats:
    if c["classe"] in ("nouveau programme", "hausse d'un programme", "à lire") and (c["acc"], c["phrase"][:80]) not in vus:
        vus.add((c["acc"], c["phrase"][:80]))
        dire(f"  - [{c['classe']}] {c['nom'][:35]} ({c['doc']}, {c['acc']}) : {c['phrase'][:420]}")
dire()
dire(f"Durée totale : {(time.monotonic() - DEBUT) / 60:.0f} min")
