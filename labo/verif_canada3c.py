"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) des infos du lot 3c, livraison 1, publiées par le robot.

Relit chaque source officielle elle-même (robots.txt vérifié pour chaque site, au moins 1,5 s entre deux requêtes
au même site, Crawl-delay respecté ; « Radar projet personnel », courriel seulement pour la SEC) et compare à
data/evenements :
- concurrence_ca : la ligne du rapport officiel (parties, dates, résultat) ; chaque symbole : le nom officiel à la
  SEC est exactement le nom d'une des parties (formes juridiques à part) ;
- sanctions_ca : recompte des inscriptions du jour et du régime dans le XML officiel, noms compris ;
- statcan : l'entrée du Quotidien (titre, date à Ottawa) et le nom dans la liste officielle des grands indicateurs ;
- gazette_ca et décrets des grands projets : la page officielle du texte (titre, numéro, date d'enregistrement) et
  sa ligne dans l'index du numéro (même numéro, même loi) ;
- avis des grands projets : la page officielle de l'avis (nom du projet, date, phrase « afin d'inscrire ») ;
- legisinfo : la fiche JSON du projet de loi : la date de l'étape dans les étapes de la chambre (à la seconde près).
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("canada3c.txt")
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SOURCES = ("concurrence_ca", "sanctions_ca", "statcan", "gazette_ca", "grands_projets_ca", "legisinfo")
TORONTO = ZoneInfo("America/Toronto")
ROBOTS, DERNIER = {}, {}
ecarts, lignes = [], []


def dire(t):
    print(t)
    lignes.append(t)


def lire(url):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    ua = UA_SEC if urlparse(url).netloc.endswith("sec.gov") else UA
    if site not in ROBOTS:
        # robots.txt lu avec NOTRE identification (la SEC refuse les robots anonymes) : 401/403 = interdit, 404 = permis
        rp = urllib.robotparser.RobotFileParser()
        try:
            with urllib.request.urlopen(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": ua}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(ua, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    delai = max(1.5, float(ROBOTS[site].crawl_delay(ua) or 0))
    attente = delai - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=120) as r:
        contenu = r.read()
    DERNIER[site] = time.monotonic()
    return contenu


def plat(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")


def date_fr(texte):
    j = re.search(r"(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})", plat(texte))
    return f"{j.group(3)}-{MOIS.index(j.group(2)) + 1:02d}-{int(j.group(1)):02d}" if j and j.group(2) in MOIS else None


def nom_simple(nom):
    """Pour comparer des noms de compagnies : majuscules sans accents, ponctuation et formes juridiques finales ôtées."""
    n = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().upper().replace("&", " AND ")
    mots = re.findall(r"[A-Z0-9]+", n)
    formes = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LTEE", "PLC", "LLC", "LP",
              "LLP", "AG", "SA", "NV", "SE", "AB", "ASA", "SPA", "BV", "ULC", "DE", "THE"}
    while mots and (mots[-1] in formes or len(mots[-1]) == 1):
        mots.pop()
    if mots[:1] == ["THE"]:  # « The Carlyle Group Inc » = « Carlyle Group Inc. » à la SEC
        mots = mots[1:]
    return " ".join(mots)


# ---------- Les infos publiées ----------
evs = []
for f in sorted((racine / "evenements").glob("*.jsonl"))[-3:]:
    for ligne in f.read_text(encoding="utf-8").splitlines():
        if ligne.strip():
            d = json.loads(ligne)
            if d["source"] in SOURCES:
                evs.append(d)
par_source = {s: [e for e in evs if e["source"] == s] for s in SOURCES}
dire("Infos publiées : " + ", ".join(f"{s} {len(v)}" for s, v in par_source.items()))
if not all(par_source.values()):
    ecarts.append("une des 6 sources n'a publié aucune info")

# ---------- Bureau de la concurrence ----------
if par_source["concurrence_ca"]:
    page = lire(par_source["concurrence_ca"][0]["official_url"]).decode("utf-8", "replace")
    rangs = {}
    for tr in re.findall(r"<tr.*?</tr>", page, re.S):
        c = [plat(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) == 5:
            rangs[(c[0], c[1])] = c
    sec = json.loads(lire("https://www.sec.gov/files/company_tickers_exchange.json"))
    noms_sec = {}
    for ligne in sec["data"]:
        r = dict(zip(sec["fields"], ligne))
        noms_sec.setdefault(r["ticker"], r["name"])
    ok = 0
    for e in par_source["concurrence_ca"]:
        d = e["data"]
        r = rangs.get((d["parties"], d["debut"]))
        if r is None:
            ecarts.append(f"fusion absente du rapport officiel : {d['parties']} ({d['debut']})")
            continue
        if e["kind"].endswith("conclu") and (r[2], r[4]) != (d["conclusion"], d["code"]):
            ecarts.append(f"fusion {d['parties']} : conclusion {r[2]} {r[4]} ≠ publiée {d['conclusion']} {d['code']}")
            continue
        acquereur, _, cibles = r[0].partition(" / ")
        parties = {nom_simple(x) for x in [acquereur, *re.split(r"\s*,\s*(?:et\s+)?|\s+et\s+", cibles)] if x.strip()}
        for t in e["tickers"]:
            if nom_simple(noms_sec.get(t, "")) not in parties:
                ecarts.append(f"fusion {d['parties']} : {t} ({noms_sec.get(t)}) n'est pas une des parties")
        ok += 1
    dire(f"Bureau de la concurrence : {ok}/{len(par_source['concurrence_ca'])} infos = rapport officiel relu "
         f"({len(rangs)} lignes) ; symboles : {sum(len(e['tickers']) for e in par_source['concurrence_ca'])} vérifiés à la SEC")

# ---------- Sanctions ----------
if par_source["sanctions_ca"]:
    xml = ET.fromstring(lire(par_source["sanctions_ca"][0]["data"]["liste_xml"]))
    compte = {}
    for rec in xml.findall("record"):
        jour = (rec.findtext("DateOfListing-DateDinscription") or "").strip()
        regime = (rec.findtext("Country-Pays") or "").split(" / ")[-1].strip()
        entite = " ".join((rec.findtext("EntityOrShip-EntiteOuNavire") or "").replace("\xa0", " ").split())
        personne = " ".join(f"{rec.findtext('GivenName-Prenom') or ''} {rec.findtext('LastName-NomDeFamille') or ''}"
                            .replace("\xa0", " ").split())
        compte.setdefault((jour, regime), []).append(entite or personne)
    for e in par_source["sanctions_ca"]:
        d = e["data"]
        officiel = sorted(compte.get((d["date"], d["regime"]), []))
        publie = sorted(d["entites"] + d["personnes"])
        dire(f"Sanctions {d['regime']} du {d['date']} : {len(officiel)} inscriptions dans le XML officiel · publiées {d['nombre']}")
        if officiel != publie or d["nombre"] != len(officiel):
            ecarts.append(f"sanctions {d['regime']} {d['date']} : noms ou nombre différents du XML officiel")

# ---------- Statistique Canada ----------
if par_source["statcan"]:
    cal = lire("https://www150.statcan.gc.ca/n1/dai-quo/cal1-fra.htm").decode("utf-8", "replace")
    menu = re.search(r'<select[^>]*id="select_keylist"[^>]*>(.*?)</select>', cal, re.S)
    principaux = [plat(o) for o in re.findall(r"<option[^>]*>(.*?)</option>", menu.group(1), re.S)] if menu else []
    NS = {"a": "http://www.w3.org/2005/Atom"}
    fil = ET.fromstring(lire("https://www150.statcan.gc.ca/n1/fr/rss/dai-quo/0-fra.atom"))
    entrees = {}
    for en in fil.findall("a:entry", NS):
        lien = en.find("a:link", NS).get("href")
        entrees[lien] = (" ".join("".join(en.find("a:title", NS).itertext()).split()),
                         datetime.fromisoformat(en.findtext("a:updated", "", NS)).astimezone(TORONTO).date().isoformat())
    ok = 0
    for e in par_source["statcan"]:
        t = entrees.get(e["official_url"])
        ind = e["data"]["indicateur"]
        if t is None:
            dire(f"StatCan : {e['official_url']} n'est plus dans le fil (100 jours) : non vérifié")
            continue
        if e["title"] != f"Statistique Canada : {t[0]}" or e["published_on"] != t[1]:
            ecarts.append(f"StatCan {e['official_id']} : titre ou date ≠ fil officiel ({t})")
        elif ind not in principaux or not t[0].startswith(ind + ", "):
            ecarts.append(f"StatCan {e['official_id']} : « {ind} » pas dans la liste officielle des grands indicateurs")
        else:
            ok += 1
    dire(f"Statistique Canada : {ok}/{len(par_source['statcan'])} infos = fil officiel, indicateurs dans la liste "
         f"officielle ({len(principaux)} noms)")

# ---------- Gazette : textes réglementaires ----------
textes = par_source["gazette_ca"] + [e for e in par_source["grands_projets_ca"] if e["kind"] == "decret_projet"]
ok = 0
for e in textes:
    d = e["data"]
    page = lire(e["official_url"]).decode("utf-8", "replace")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    m = re.fullmatch(r"(.+?)\s*:\s*((?:DORS|TR)/\d{4}-\d+)", plat(h1.group(1)) if h1 else "")
    enreg = re.search(r"Enregistrement\s*(?:<br\s*/?>)?\s*((?:DORS|TR)/\d{4}-\d+)\s+Le\s+([^<]+)</p>", page)
    if not m or (m.group(1), m.group(2)) != (d["titre"], e["official_id"]) or not enreg:
        ecarts.append(f"Gazette {e['official_id']} : titre ou numéro ≠ page officielle")
        continue
    jour = date_fr(enreg.group(2))
    if jour != e["occurred_on"]:
        ecarts.append(f"Gazette {e['official_id']} : enregistré le {jour} ≠ publié {e['occurred_on']}")
        continue
    if d.get("index", "").endswith("/index-fra.html"):
        index = lire(d["index"]).decode("utf-8", "replace")
        fichier = e["official_url"].rsplit("/", 1)[1]
        item = re.search(rf'<a href="{re.escape(fichier)}">(.*?)</a>(.*?)</li>', index, re.S)
        loi_index = plat(re.split(r"<br\s*/?>", item.group(1))[-1]) if item else None
        if not item or e["official_id"] not in plat(item.group(2)) or loi_index != d["loi"]:
            ecarts.append(f"Gazette {e['official_id']} : absent de l'index du numéro, ou loi différente ({loi_index})")
            continue
    ok += 1
dire(f"Gazette du Canada : {ok}/{len(textes)} textes = page officielle relue (titre, numéro, date) et index du numéro")

# ---------- Grands projets : avis de la Partie I ----------
avis = [e for e in par_source["grands_projets_ca"] if e["kind"] == "avis_projet"]
ok = 0
for e in avis:
    base, _, ancre = e["official_url"].partition("#")
    page = lire(base).decode("utf-8", "replace")
    debut = page.find(f'id="{ancre}"') if ancre else page.find("LOI VISANT À BÂTIR LE CANADA")
    section = page[debut:]
    fin = re.search(r"<h2[ >]", section[10:])
    section = section[: fin.start() + 10] if fin and debut >= 0 else section
    nom = re.search(r"Nom du projet</cite></h4>\s*<p[^>]*>(.*?)</p>", section, re.S)
    premier = re.search(r"<p[^>]*>(.*?)</p>", section, re.S)
    date_numero = re.search(r"<p>Le\s+([^<]+)</p>", page)
    if not date_numero or date_fr(date_numero.group(1)) != e["published_on"]:
        ecarts.append(f"avis {e['official_id']} : date du numéro ≠ publiée {e['published_on']}")
    elif debut < 0 or not nom or plat(nom.group(1)) != e["data"]["projet"]:
        ecarts.append(f"avis {e['official_id']} : projet ≠ page officielle")
    elif not premier or not re.search(r"afin d[’']\s*(?:y\s+)?inscrire", plat(premier.group(1))) \
            or "annexe" not in plat(premier.group(1)):  # « afin d'inscrire » ou « afin d'y inscrire »
        ecarts.append(f"avis {e['official_id']} : la phrase officielle « afin d'inscrire … annexe 1 » est absente")
    else:
        ok += 1
dire(f"Avis de la Loi visant à bâtir le Canada : {ok}/{len(avis)} = page officielle relue (projet, phrase officielle)")
autres = [e for e in par_source["grands_projets_ca"] if e["kind"] == "projet_soutenu"]
if autres:
    page = lire("https://www.canada.ca/fr/conseil-prive/bureau-grands-projets/projets/national.html").decode("utf-8", "replace")
    absents = [e["official_url"] for e in autres if urlparse(e["official_url"]).path not in page]
    dire(f"Projets ajoutés à la liste du Bureau : {len(autres) - len(absents)}/{len(autres)} présents sur la page officielle")
    if absents:
        ecarts.append(f"projets absents de la liste officielle : {absents}")

# ---------- LEGISinfo ----------
ETAPES = {"chambre-1": ("HouseBillStages", "Première lecture"), "chambre-2": ("HouseBillStages", "Deuxième lecture"),
          "chambre-3": ("HouseBillStages", "Troisième lecture"), "senat-1": ("SenateBillStages", "Première lecture"),
          "senat-2": ("SenateBillStages", "Deuxième lecture"), "senat-3": ("SenateBillStages", "Troisième lecture")}
fiches, ok = {}, 0
for e in par_source["legisinfo"]:
    d = e["data"]
    if e["official_url"] not in fiches:
        fiches[e["official_url"]] = json.loads(lire(e["official_url"] + "/json").decode("utf-8-sig"))[0]
    fiche = fiches[e["official_url"]]
    publie = datetime.fromisoformat(d["date_officielle"]).astimezone(timezone.utc).replace(tzinfo=None)
    if d["cle"] == "sanction":
        officiel = fiche.get("ReceivedRoyalAssentDateTime")
    else:
        chambre, nom = ETAPES[d["cle"]]
        faites = [s for s in fiche["BillStages"].get(chambre) or []
                  if s["BillStageNameFr"] == nom and (s.get("StateNameFr") or "").startswith("Terminé")]
        officiel = faites[-1]["StateAsOfDate"] if faites else None
    ecart = abs((datetime.fromisoformat(officiel) - publie).total_seconds()) if officiel else None
    if ecart is None or ecart > 2:
        ecarts.append(f"LEGISinfo {e['official_id']} : étape à {officiel} (UTC) dans la fiche ≠ publiée {d['date_officielle']}")
    else:
        ok += 1
dire(f"LEGISinfo : {ok}/{len(par_source['legisinfo'])} étapes = date de l'étape dans la fiche officielle du projet "
     f"({len(fiches)} fiches relues)")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque info relue à sa source officielle.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
