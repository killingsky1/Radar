"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot H : les rachats d'actions.

Mêmes règles d'accès : robots.txt lu d'abord avec notre identification, au moins 1,5 s entre deux requêtes ; le courriel
seulement dans l'identification envoyée à la SEC. Refait ici, avec un autre code (detecteur_rachats.py, écrit à part) :
- chaque annonce publiée (source sec_rachats) : en-tête officiel relu (points 2.02, 7.01 ou 8.01, date de dépôt, CIK),
  chaque document relu ; chaque extrait est mot pour mot dans son document ; le détecteur du labo relit chaque extrait :
  même sorte (nouveau ou hausse) et même montant que le titre et l'onglet Argent ; symbole = CIK dans la liste
  officielle de la SEC ; 10 M$ et plus ;
- avec --jour AAAA-MM-JJ : TOUS les 8-K de ce jour (compagnies cotées, points 2.02, 7.01 ou 8.01) relus en entier : les
  annonces trouvées ici = celles publiées par le robot pour ce jour (ni oubli, ni de trop) ;
- rachats faits (app/rachats.json) : le fichier « frames » de la SEC relu ; pour chaque compagnie, même CIK que la liste
  officielle, même montant, mêmes dates, même numéro de dépôt.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from detecteur_rachats import analyser, decider, decision, nouveaute  # noqa: E402

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else Path("lotH.txt")
JOUR = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--jour=")), None)
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
POINTS = {"results of operations and financial condition": "2.02", "regulation fd disclosure": "7.01",
          "other events": "8.01"}
ecarts, sortie, dernier, robots = [], [], [0.0], {}


def dire(t=""):
    print(t, flush=True)
    sortie.append(t)


def lire(url):
    hote = url.split("/")[2]
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://{hote}/robots.txt", headers={"User-Agent": UA_SEC}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) or e.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True  # 404 : pas de robots.txt, tout est permis
        robots[hote] = rp
    if not robots[hote].can_fetch(UA_SEC, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = 1.5 - (time.monotonic() - dernier[0])
    if attente > 0:
        time.sleep(attente)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA_SEC}), timeout=180) as r:
            return r.read()
    finally:
        dernier[0] = time.monotonic()


def texte(brut) -> str:
    """HTML -> texte (fait ici, sans le code du robot) : les blocs séparés par une espace, les entités décodées."""
    t = brut.decode("utf-8", "replace") if isinstance(brut, bytes) else brut
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", t)
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", t)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").split())


def montant_fr(d):
    if d >= 1e9:
        return f"{d / 1e9:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",") + " G$"
    return f"{d / 1e6:,.1f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",") + " M$"


liste = json.loads(lire("https://www.sec.gov/files/company_tickers_exchange.json"))
cotes = {}
for cik, nom, symbole, bourse in liste["data"]:
    if bourse in ("Nasdaq", "NYSE", "CBOE"):
        cotes.setdefault(int(cik), []).append(symbole)
evs = [json.loads(l) for f in sorted((racine / "evenements").glob("*.jsonl"))
       for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
annonces = [e for e in evs if e["source"] == "sec_rachats"]
argent = json.loads((racine / "app" / "argent.json").read_text(encoding="utf-8"))
lignes = {l["id"]: l for l in argent["lignes"] if l["famille"] == "rachats"}
dire(f"Annonces de rachat publiées : {len(annonces)} · lignes « Rachats » dans l'onglet Argent : {len(lignes)}")

# ---------- Chaque annonce publiée, relue à la SEC ----------
ok = 0
for e in annonces:
    pb, d = [], e["data"]
    acc = e["official_id"]
    cik = int(re.search(r"/data/(\d+)/", e["official_url"]).group(1))
    entete = lire(e["official_url"].replace("-index.htm", "-index-headers.html")).decode("utf-8", "replace")
    items = sorted({POINTS[x.strip().lower()] for x in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)", html.unescape(entete))
                    if x.strip().lower() in POINTS})
    if not items or items != sorted(d["points"]):
        pb.append(f"points du 8-K {items} ≠ {d['points']}")
    depose = re.search(r"FILED AS OF DATE:\s*(\d{8})", entete).group(1)
    if f"{depose[:4]}-{depose[4:6]}-{depose[6:]}" != e["published_on"]:
        pb.append(f"date de dépôt {depose} ≠ {e['published_on']}")
    deposants = {int(c) for c in re.findall(r"CENTRAL INDEX KEY:\s*(\d+)", entete)}
    if not any(e["tickers"][0] in cotes.get(c, []) for c in deposants):
        pb.append(f"{e['tickers'][0]} n'est le symbole d'aucun déposant ({sorted(deposants)}) dans la liste de la SEC")
    trouves = []
    for doc in d["documents"]:
        t = texte(lire(doc["url"]))
        for x in doc["extraits"]:
            if " ".join(x.split()) not in t:
                pb.append(f"extrait absent du document {doc['type']} : {x[:80]}")
            a = analyser(x, date.fromisoformat(e["published_on"]))
            if "sorte" not in a:
                pb.append(f"le labo rejette l'extrait ({a['rejet']}) : {x[:80]}")
            else:
                trouves.append(a)
    dec = decision(trouves)
    if dec["statut"] != "annonce" or (dec["sorte"], dec["dollars"], dec["actions"]) != (d["sorte"], d["dollars"], d["actions"]):
        pb.append(f"labo : {dec} ≠ robot : {(d['sorte'], d['dollars'], d['actions'])}")
    # Nouveauté refaite ici : les 8-K des 90 jours avant, relus au complet (.txt), n'annonçaient pas déjà ce montant
    deja, relus = nouveaute(lire, int(d["cik"]), acc, date.fromisoformat(e["published_on"]), (d["dollars"], d["actions"]))
    if deja:
        pb.append(f"le même montant était déjà annoncé dans le 8-K {deja}")
    if sorted(relus) != sorted((d.get("nouveaute") or {}).get("depots_relus") or []):
        pb.append(f"8-K des 90 jours relus : labo {sorted(relus)} ≠ robot {sorted((d.get('nouveaute') or {}).get('depots_relus') or [])}")
    if d["dollars"] is not None:
        if d["dollars"] < 10_000_000:
            pb.append("moins de 10 M$")
        if montant_fr(d["dollars"]) not in e["title"] or e["amount_min"] != d["dollars"]:
            pb.append(f"titre ou montant : « {e['title']} » / {e['amount_min']}")
        l = lignes.get(e["id"])
        if e["published_on"] >= argent["depuis"] and (l is None or l["montant"] != d["dollars"] or l["sens"] != 0):
            pb.append(f"ligne de l'onglet Argent : {l}")
    if pb:
        ecarts.append(f"{e['entities'][0]} ({acc}) : " + " ; ".join(pb))
    else:
        ok += 1
    dire(f"- {e['published_on']} · {e['tickers'][0]} · {d['sorte']} · "
         f"{montant_fr(d['dollars']) if d['dollars'] else str(d['actions']) + ' actions'} · {acc} : "
         f"{'OK' if not pb else 'PROBLÈME'}")
dire(f"Annonces relues à la SEC : {ok}/{len(annonces)} identiques (points, date, symbole, extraits mot pour mot, sorte, "
     f"montant, onglet Argent)")

# ---------- Un jour au complet : ni oubli, ni de trop ----------
if JOUR:
    j = date.fromisoformat(JOUR)
    idx = lire(f"https://www.sec.gov/Archives/edgar/daily-index/{j.year}/QTR{(j.month - 1) // 3 + 1}/"
               f"master.{j:%Y%m%d}.idx").decode("latin-1")
    depots = {}
    for l in idx.splitlines():
        p = l.split("|")
        if len(p) == 5 and p[0].strip().isdigit() and p[2].strip() == "8-K":
            depots.setdefault(p[4].rsplit("/", 1)[1].removesuffix(".txt"), {"fichier": p[4].strip(), "ciks": []})["ciks"].append(int(p[0]))
    attendus, lus = {}, 0
    for acc, x in depots.items():
        cik = next((c for c in x["ciks"] if c in cotes), None)
        if cik is None:
            continue
        entete = lire(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index-headers.html")
        if not any(y.strip().lower() in POINTS for y in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)",
                                                                    html.unescape(entete.decode("utf-8", "replace")))):
            continue
        brut = lire(f"https://www.sec.gov/Archives/{x['fichier']}").decode("utf-8", "replace")
        lus += 1
        docs = [(m.group(1).strip().upper(), texte(m.group(2)))
                for m in re.finditer(r"<DOCUMENT>\s*<TYPE>([^\n<]+)(.*?)</DOCUMENT>", brut, re.S)
                if m.group(1).strip().upper().startswith(("8-K", "EX-99"))]
        dec = decider(docs, j)
        if dec["statut"] == "annonce" and not nouveaute(lire, cik, acc, j, (dec["dollars"], dec["actions"]))[0]:
            attendus[acc] = (dec["sorte"], dec["dollars"], dec["actions"])
    publies = {e["official_id"]: (e["data"]["sorte"], e["data"]["dollars"], e["data"]["actions"]) for e in annonces
               if e["published_on"] == JOUR}
    dire(f"Jour {JOUR} : {len(depots)} 8-K, {lus} lus en entier (cotés, points 2.02/7.01/8.01) · annonces trouvées ici : "
         f"{len(attendus)} · publiées par le robot : {len(publies)}")
    for acc in sorted(set(attendus) | set(publies)):
        if attendus.get(acc) != publies.get(acc):
            ecarts.append(f"jour {JOUR}, {acc} : labo {attendus.get(acc)} ≠ robot {publies.get(acc)}")
    dire(f"  ni oubli ni de trop : {'OUI' if all(attendus.get(a) == publies.get(a) for a in set(attendus) | set(publies)) else 'NON'}")

# ---------- Rachats faits (XBRL) ----------
p = racine / "app" / "rachats.json"
if p.exists():
    app = json.loads(p.read_text(encoding="utf-8"))
    frames = json.loads(lire(f"https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/"
                             f"{app['cadre']}.json"))
    par_cik = {x["cik"]: x for x in frames["data"]}
    bons = 0
    for s, x in app["par_symbole"].items():
        cik = x.get("cik")
        pb = []
        if cik is not None and s not in cotes.get(int(cik), []):
            pb.append(f"CIK {cik} n'a pas le symbole {s} dans la liste de la SEC")
        f = par_cik.get(int(cik)) if cik is not None else None
        if f is None:
            if "montant" in x or "illisible" in x:
                pb.append("montant publié, mais pas dans le fichier de la SEC")
        elif f["val"] < 0:
            if not x.get("illisible") or "montant" in x:
                pb.append(f"montant négatif ({f['val']}) pas marqué illisible")
        elif (x.get("montant"), x.get("debut"), x.get("fin"), x.get("accn")) != (f["val"], f["start"], f["end"], f["accn"]):
            pb.append(f"{(x.get('montant'), x.get('debut'), x.get('fin'), x.get('accn'))} ≠ SEC {(f['val'], f['start'], f['end'], f['accn'])}")
        elif x.get("lien") != (f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accn'].replace('-', '')}/{f['accn']}-index.htm"):
            pb.append(f"lien {x.get('lien')}")
        if pb:
            ecarts.append(f"rachats faits, {s} : " + " ; ".join(pb))
        else:
            bons += 1
    dire(f"Rachats faits ({app['cadre']}, {len(frames['data'])} compagnies dans le fichier de la SEC) : {bons}/"
         f"{len(app['par_symbole'])} compagnies des listes identiques (CIK, montant, dates, numéro de dépôt, lien)")
else:
    dire("Rachats faits : app/rachats.json pas encore publié")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque rachat relu dans les documents officiels de la SEC.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
