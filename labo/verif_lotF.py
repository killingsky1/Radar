"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot F : fins de blocage après une entrée en bourse.

Mêmes règles d'accès : robots.txt lu d'abord avec notre identification (401/403 = interdit), au moins 1,5 s entre deux
requêtes au même site ; « Radar projet personnel » et le courriel seulement pour la SEC.

Pour CHAQUE fin de blocage publiée par le robot (tous les mois gardés), le prospectus final (424B4) est relu à la SEC et
lu ici avec un autre lecteur (html.parser, pas des expressions sur les balises) :
- vraie entrée en bourse (« This is an initial public offering » / « Prior to this offering, there has been no public
  market ») ; pas un SPAC, pas une inscription directe, pas des actions déjà cotées ailleurs ;
- date du prospectus : chaque preuve trouvée ici (couverture, bas de la couverture, phrase des 25 jours) donne la même
  date, au moins une preuve directe, au plus 2 jours de semaine avant le dépôt (date officielle de l'en-tête SEC) ;
- une seule durée dans les phrases du blocage, aucune levée anticipée mentionnée ;
- fin = date + durée ; la phrase citée par le robot est mot pour mot dans le prospectus ; symbole = liste de la SEC ;
- 0 point dans la note ; le calendrier de l'app = exactement ces infos, triées, « passée » au bon endroit.
Avec --tout : TOUS les 424B4 depuis le 1er avril 2026 (index officiels) sont relus ; chaque prospectus que la règle
d'ici juge publiable doit être publié (ou en attente de son symbole), et rien d'autre.
"""
import gzip
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import acces  # labo/acces.py : un site qui ne répond pas = « non vérifiable », jamais un plantage

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lotF.txt")
TOUT = "--tout" in sys.argv
UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
ROBOTS, DERNIER = {}, {}
ecarts, sortie = [], []
acces.installer(sortie, SORTIE)
MOIS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
           "December"]
DATE_EN = r"((?:" + "|".join(MOIS_EN) + r")\s+\d{1,2},\s+\d{4})"


def dire(t):
    print(t, flush=True)
    sortie.append(t)


def lire(url):
    hote = urlparse(url).netloc
    ua = UA_SEC if hote.endswith("sec.gov") else UA
    if hote not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with acces.ouvrir(urllib.request.Request(f"https://{hote}/robots.txt", headers={"User-Agent": ua}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[hote] = rp
    if not ROBOTS[hote].can_fetch(ua, url):
        raise acces.NonVerifiable(f"robots.txt ne permet pas {url}")
    attente = 1.5 - (time.monotonic() - DERNIER.get(hote, 0.0))
    if attente > 0:
        time.sleep(attente)
    with acces.ouvrir(urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"}),
                                timeout=180) as r:
        contenu = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            contenu = gzip.decompress(contenu)
    DERNIER[hote] = time.monotonic()
    return contenu


class Texte(HTMLParser):
    """Texte du document : un espace pour chaque bloc (paragraphe, cellule…), rien pour une balise dans une ligne."""
    BLOCS = {"p", "div", "br", "td", "th", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "center"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.ignore = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignore += 1
        elif tag in self.BLOCS:
            self.morceaux.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignore = max(0, self.ignore - 1)
        elif tag in self.BLOCS:
            self.morceaux.append(" ")

    def handle_data(self, data):
        if not self.ignore:
            self.morceaux.append(data)

    def texte(self):
        return " ".join("".join(self.morceaux).replace("\xa0", " ").replace("​", " ").split())


def texte_424b4(brut: bytes):
    try:
        t = brut.decode("utf-8")
    except UnicodeDecodeError:
        t = brut.decode("cp1252", "replace")
    depose = re.search(r"FILED AS OF DATE:\s*(\d{8})", t)
    for doc in t.split("<DOCUMENT>")[1:]:
        type_doc = re.match(r"\s*<TYPE>([^\n<]+)", doc)
        if type_doc and type_doc.group(1).strip().upper().startswith("424B4"):
            corps = doc.split("<TEXT>", 1)[-1].split("</TEXT>", 1)[0]
            lecteur = Texte()
            lecteur.feed(corps)
            return lecteur.texte(), (datetime.strptime(depose.group(1), "%Y%m%d").date() if depose else None)
    return None, None


def d_en(s):
    return datetime.strptime(" ".join(s.split()), "%B %d, %Y").date()


def semaine(a, b):
    n = 0
    while a < b:
        a += timedelta(days=1)
        n += a.weekday() < 5
    return n


def regle(t, depose):
    """La règle refaite ici : (raisons, date du prospectus, durée)."""
    raisons, debut = [], t[:40000]
    if not re.search(r"this is (an|the|our) initial public offering|prior to this offering,? there (has|have) been no "
                     r"(established )?public market", debut, re.I):
        raisons.append("pas une entrée en bourse")
    if re.search(r"blank check company|special purpose acquisition|direct listing", debut, re.I):
        raisons.append("SPAC ou inscription directe")
    if re.search(r"last reported (sale|sales|closing|trading) price of (our|the|its)\s+(common|ordinary)", debut, re.I) or \
            any(not re.search(r"(until|once|when|after|if|before)\s*$", debut[:m.start()], re.I)
                for m in re.finditer(r"\b(our|its)\s+(common|ordinary)\s+(shares|stock)\s+(are|is)\s+(currently\s+)?"
                                     r"(listed|traded|quoted)\s+on\b", debut, re.I)):
        raisons.append("déjà cotée")
    preuves = []  # (date, directe)
    preuves += [(d_en(m.group(1)), True) for m in re.finditer(r"(?:The date of this prospectus is|Prospectus dated)\s+"
                                                               + DATE_EN, t[:120000])]
    sommaire = [m.start() for m in re.finditer(r"table of contents", t[:120000], re.I)][:2]
    if len(sommaire) == 2 and sommaire[0] <= 200:
        m = re.search(DATE_EN + r"\.?\s*$", t[sommaire[0]:sommaire[1]])
        if m:
            preuves.append((d_en(m.group(1)), True))
    for m in re.finditer(r"Through and including " + DATE_EN + r"\s*\((?:the )?25(?:th)? days? after the (date of this "
                         r"prospectus|commencement of this offering)", t, re.I):
        preuves.append((d_en(m.group(1)) - timedelta(days=25), m.group(2).lower().startswith("date")))
    dates = {d for d, _ in preuves}
    d0 = next(iter(dates)) if len(dates) == 1 else None
    if d0 is None or not any(direct for _, direct in preuves):
        raisons.append("date du prospectus pas prouvée")
    elif depose is None or d0 > depose or semaine(d0, depose) > 2:
        raisons.append("date loin du dépôt")
    durees = set()
    for s in re.split(r"(?<=[.;])[”\"’)]?\s+", t):
        if re.search(r"lock-?up|restricted period", s, re.I) and not re.search(
                r"Rule 144|Rule 701|effective date of the registration|25 days|underwriter(s'|'s)? warrants|FINRA Rule 5110",
                s, re.I):
            for m in re.finditer(r"(?:\((\d{2,3})\)|\b(\d{2,3}))[ -]days? (?:after|from|following) the date of (?:this|the "
                                 r"final) prospectus|(?:\((\d{2,3})\)|\b(\d{2,3}))-day (?:lock-?up|restricted) period", s, re.I):
                durees.add(int(next(g for g in m.groups() if g)))
    if len(durees) != 1:
        raisons.append(f"durées {sorted(durees)}")
    if re.search(r"early release|released early|earlier of[^.]{0,200}(lock-?up|restricted period|trading day)|(closing|last "
                 r"reported sale) price[^.]{0,250}(exceed|at least|greater than|equal to or greater)[^.]{0,150}offering price"
                 r"|(release|announcement) of (our |its )?(earnings|quarterly|financial results)[^.]{0,200}(lock-?up|restricted"
                 r" period)|(lock-?up|restricted period)[^.]{0,200}(release|announcement) of (our |its )?(earnings|quarterly|"
                 r"financial results)|(lock-?up|restricted period)[^.]{0,200}\b\d{1,3}(\.\d+)?\s?(%|percent) of[^.]{0,120}"
                 r"released", t, re.I):
        raisons.append("levée anticipée")
    return raisons, d0, (next(iter(durees)) if len(durees) == 1 else None)


# ---------- Les infos publiées par le robot (tous les mois gardés) ----------
publiees, attente = {}, {}
for f in sorted((racine / "evenements").glob("*.jsonl")):
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            e = json.loads(l)
            if e["source"] == "sec_blocage":
                publiees[e["id"]] = e
etat_robot = racine / "sec" / "blocage.json"
if etat_robot.exists():
    attente = json.loads(etat_robot.read_text(encoding="utf-8")).get("en_attente", {})
dire(f"Fins de blocage publiées par le robot : {len(publiees)} (en attente d'un symbole : {len(attente)})")
par_cik = {}

# ---------- Chaque fin de blocage relue à la SEC (fichier des symboles, prospectus 424B4) ----------
with acces.section('Fins de blocage (prospectus relus à la SEC)'):
    symboles = json.loads(lire("https://www.sec.gov/files/company_tickers_exchange.json"))
    for cik, nom, symbole, bourse in symboles["data"]:
        par_cik.setdefault(int(cik), []).append((symbole, bourse))

    ok = 0
    for i, e in sorted(publiees.items(), key=lambda x: x[1]["data"]["fin_blocage"]):
        d, pb = e["data"], []
        acc, cik = e["official_id"], d["cik"]
        t, depose = texte_424b4(lire(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}.txt"))
        if t is None:
            ecarts.append(f"{i} : pas de document 424B4 dans le dépôt")
            continue
        raisons, d0, n = regle(t, depose)
        if raisons:
            pb.append("la règle d'ici refuse : " + ", ".join(raisons))
        if d0 and d0.isoformat() != d["date_prospectus"]:
            pb.append(f"date du prospectus {d0} ≠ {d['date_prospectus']}")
        if depose and depose.isoformat() != e["published_on"]:
            pb.append(f"dépôt {depose} ≠ {e['published_on']}")
        if n and n != d["duree_jours"]:
            pb.append(f"durée {n} ≠ {d['duree_jours']}")
        if d0 and n and (d0 + timedelta(days=n)).isoformat() != d["fin_blocage"]:
            pb.append(f"fin {(d0 + timedelta(days=n))} ≠ {d['fin_blocage']}")
        for morceau in d["phrase_blocage"].removesuffix(" …").split(" … "):
            if morceau not in t:
                pb.append(f"phrase pas mot pour mot : « {morceau[:80]} »")
        if (e["tickers"][0], d["bourse"]) not in par_cik.get(int(cik), []):
            pb.append(f"symbole {e['tickers'][0]} ({d['bourse']}) pas celui de la SEC pour le CIK {cik}")
        if e.get("direction") != 0 or e.get("badge") not in ("officiel", "confirme"):
            pb.append(f"direction {e.get('direction')} ou badge {e.get('badge')}")
        if pb:
            ecarts.append(f"{i} ({e['tickers'][0]}) : " + " ; ".join(pb))
        else:
            ok += 1
            dire(f"  OK {e['tickers'][0]:5} {e['entities'][0][:34]:34} prospectus {d['date_prospectus']} + {d['duree_jours']} j "
                 f"= fin {d['fin_blocage']}")
    dire(f"Relues à la SEC : {ok}/{len(publiees)} = prospectus officiel (entrée en bourse, date, durée, fin, phrase, symbole)")

# ---------- 0 point dans la note ----------
auj = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
compte = [i["id"] for liste in ("hausse", "baisse") for x in auj.get(liste, []) for g in x.get("groupes", [])
          for i in g.get("infos", []) if i["id"].startswith("sec_blocage:") and i.get("compte")]
if compte:
    ecarts.append(f"fins de blocage qui comptent dans la note : {compte}")
dire(f"Note : {len(compte)} fin de blocage comptée (attendu : 0)")

# ---------- Calendrier de l'app ----------
cal = json.loads((racine / "app" / "calendrier.json").read_text(encoding="utf-8"))
jour = date.fromisoformat(cal["jour"])
attendues = sorted(((e["data"]["fin_blocage"], e["entities"][0], i) for i, e in publiees.items()
                    if e["data"]["fin_blocage"] >= (jour - timedelta(days=7)).isoformat()
                    and e.get("badge") in ("officiel", "confirme")))
if [l["id"] for l in cal["lignes"]] != [i for _, _, i in attendues]:
    ecarts.append("calendrier : lignes ≠ infos publiées (ou pas dans l'ordre)")
for l in cal["lignes"]:
    e = publiees.get(l["id"])
    if not e or (l["fin"], l["duree"], l["prospectus"], l["symbole"], l["passee"]) != (
            e["data"]["fin_blocage"], e["data"]["duree_jours"], e["data"]["date_prospectus"], e["tickers"][0],
            e["data"]["fin_blocage"] < cal["jour"]):
        ecarts.append(f"calendrier : ligne {l['id']} ≠ l'info publiée")
dire(f"Calendrier du {cal['jour']} : {len(cal['lignes'])} lignes ({sum(l['passee'] for l in cal['lignes'])} passée) = "
     f"infos publiées : {'OUI' if not any(x.startswith('calendrier') for x in ecarts) else 'NON'}")
for l in cal["lignes"][:12]:
    dire(f"  {l['fin']} {l['symbole']:5} {l['compagnie'][:40]} ({l['duree']} jours après le {l['prospectus']})")

# ---------- --tout : tous les 424B4 depuis le 1er avril 2026, règle d'ici contre le robot ----------
with acces.section('Tous les 424B4 depuis avril (--tout)'):
    if TOUT:
        depots = []
        aujourdhui = date.fromisoformat(cal["jour"])
        for annee, trim in ((2026, 2), (2026, 3)):
            brut = lire(f"https://www.sec.gov/Archives/edgar/full-index/{annee}/QTR{trim}/master.idx").decode("latin-1")
            depots += [l.split("|") for l in brut.splitlines() if l.count("|") == 4 and l.split("|")[2] == "424B4"
                       and l.split("|")[3] >= "2026-04-01"]
        j = date(2026, 10, 1)
        while j < aujourdhui:
            if j.weekday() < 5:
                try:
                    brut = lire(f"https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.{j:%Y%m%d}.idx").decode("latin-1")
                    depots += [l.split("|") for l in brut.splitlines() if l.count("|") == 4 and l.split("|")[2] == "424B4"]
                except urllib.error.HTTPError:
                    pass
            j += timedelta(days=1)
        vus, publiables = set(), {}
        for cik, nom, forme, depose_idx, fichier in depots:
            acc = fichier.rsplit("/", 1)[1][:-4]
            if acc in vus:
                continue
            vus.add(acc)
            try:
                t, depose = texte_424b4(lire(f"https://www.sec.gov/Archives/{fichier}"))
            except acces.NonVerifiable:
                raise  # la SEC ne répond pas : toute cette partie est « non vérifiable », pas une liste à trous
            except Exception as exc:  # noqa: BLE001
                dire(f"  illisible : {acc} ({exc})")
                continue
            if t is None:
                continue
            raisons, d0, n = regle(t, depose)
            if not raisons:
                publiables[acc] = (cik, nom, d0, n)
        ids_robot = {e["official_id"] for e in publiees.values()}
        cotes = {acc for acc, (cik, *_ ) in publiables.items() if any(b in ("Nasdaq", "NYSE", "CBOE") for _, b in par_cik.get(int(cik), []))}
        manquees = sorted(cotes - ids_robot - set(attente))
        en_trop = sorted(ids_robot - set(publiables))
        dire(f"Tous les 424B4 depuis le 1er avril 2026 : {len(vus)} relus ; publiables selon la règle d'ici : {len(publiables)} "
             f"(cotés au Nasdaq, au NYSE ou au CBOE : {len(cotes)}) ; publiées par le robot : {len(ids_robot)}")
        for acc in manquees:
            ecarts.append(f"publiable ici mais pas publiée par le robot : {acc} {publiables[acc][1]}")
        for acc in en_trop:
            ecarts.append(f"publiée par le robot mais refusée ici : {acc}")
        for acc, (cik, nom, d0, n) in sorted(publiables.items(), key=lambda x: x[1][2] + timedelta(days=x[1][3])):
            dire(f"  {'publiée ' if acc in ids_robot else ('attente  ' if acc in attente else 'NON COTÉE' if acc not in cotes else 'MANQUÉE  ')}"
                 f" {nom[:36]:36} {d0} + {n} j = {d0 + timedelta(days=n)}")

dire("\n".join(ecarts) if ecarts else ("AUCUN ÉCART dans ce qui a pu être relu." if acces.NON_VERIFIABLES
                                       else "AUCUN ÉCART : chaque fin de blocage relue à son prospectus officiel."))
for ligne in acces.lignes_non_verifiables():
    dire(ligne)
dire(acces.verdict(ecarts))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
