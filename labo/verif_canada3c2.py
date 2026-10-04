"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) des infos du lot 3c, livraison 2, publiées par le robot.

Relit chaque source officielle elle-même (robots.txt vérifié pour chaque site, au moins 1,5 s entre deux requêtes
au même site, Crawl-delay respecté ; « Radar projet personnel ») et compare à data/evenements :
- sante_canada : (1) la liste officielle complète des avis de conformité (API) : chaque avis d'une classe « NSA » des
  60 jours avant la lecture du robot doit être publié, et rien d'autre ; (2) la fiche publique de chaque avis
  (nocInfo) : date, fabricant, catégorie, avec conditions, marques et ingrédients ;
- ccc : la page des rapports (le rapport le plus récent, choisi par sa date ; la date de mise à jour de la page) et le
  PDF lu par un AUTRE outil que le robot (pdftotext de Poppler) : période, nombre de transactions, fourchettes dans
  l'ordre, exportateurs anonymes et nommés, totaux.
Les contrats fédéraux ont leur propre vérification (verif_contrats.py : relecture complète, 20 s entre 2 requêtes).
"""
import gzip
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import Counter
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import acces  # labo/acces.py : un site qui ne répond pas = « non vérifiable », jamais un plantage

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("canada3c2.txt")
UA = "Radar projet personnel"
SOURCES = ("sante_canada", "ccc")
TORONTO = ZoneInfo("America/Toronto")
LISTE_NOC = "https://health-products.canada.ca/api/notice-of-compliance/noticeofcompliancemain/?lang=fr&type=json"
API_NOC = "https://health-products.canada.ca/api/notice-of-compliance/"
CLASSES_NSA = ("Nouvelle substance active (NSA)", "Priorité-NSA")
PAGE_CCC = "https://www.ccc.ca/en/about/corporate-reports/"
ROBOTS, DERNIER, ENTETES = {}, {}, {}
ecarts, lignes = [], []
acces.installer(lignes, SORTIE)


def dire(t):
    print(t)
    lignes.append(t)


def lire(url):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if site not in ROBOTS:
        # robots.txt lu avec notre identification : 401/403 = interdit, 404 = permis
        rp = urllib.robotparser.RobotFileParser()
        try:
            with acces.ouvrir(urllib.request.Request(site + "/robots.txt", headers={"User-Agent": UA}),
                                        timeout=60) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) or exc.code >= 500:
                rp.disallow_all = True
            else:
                rp.allow_all = True
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(UA, url):
        raise acces.NonVerifiable(f"robots.txt ne permet pas {url}")
    delai = max(1.5, float(ROBOTS[site].crawl_delay(UA) or 0))
    attente = delai - (time.monotonic() - DERNIER.get(site, 0.0))
    if attente > 0:
        time.sleep(attente)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with acces.ouvrir(req, timeout=180) as r:
        contenu = r.read()
        ENTETES[url] = dict(r.headers)
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            contenu = gzip.decompress(contenu)
    DERNIER[site] = time.monotonic()
    return contenu


def plat(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).replace("\xa0", " ").split())


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
etat = json.loads((racine / "etat_sources.json").read_text(encoding="utf-8"))
for s in SOURCES + ("contrats_ca_10k",):
    e = etat.get(s, {})
    dire(f"État du robot, {s} : dernière lecture réussie {e.get('dernier_succes')}, erreur : {e.get('derniere_erreur')}")
    if not e.get("dernier_succes") or e.get("derniere_erreur"):
        ecarts.append(f"{s} : pas de lecture réussie, ou une erreur ({e.get('derniere_erreur')})")

# ---------- Santé Canada : la liste officielle complète ----------
with acces.section('Santé Canada (liste officielle et fiches publiques)'):
    lu_le = datetime.fromisoformat(etat["sante_canada"]["dernier_succes"]).date()  # date UTC, comme le robot
    depuis = (lu_le - timedelta(days=60)).isoformat()
    brut_noc = lire(LISTE_NOC)
    avis = json.loads(brut_noc.decode("utf-8-sig"))
    if not avis:  # liste vide : montrer la réponse exacte du site (pour savoir si c'est le site ou Radar)
        dire(f"Santé Canada : RÉPONSE VIDE · {len(brut_noc)} octets · en-têtes {ENTETES.get(LISTE_NOC)} · début {brut_noc[:200]!r}")
    fenetre = [x for x in avis if (x.get("noc_date") or "") >= depuis]
    classes = Counter(x.get("noc_submission_class") for x in fenetre)
    dire(f"Santé Canada : liste officielle {len(avis)} avis ; {len(fenetre)} depuis le {depuis} (60 jours avant la lecture "
         f"du {lu_le}), par classe : {dict(classes.most_common())}")
    for c in classes:
        if c not in CLASSES_NSA and re.search(r"NSA|substance active", c or "", re.I):
            ecarts.append(f"classe « {c} » ({classes[c]} avis) : nouvelle substance active non lue par le robot ?")
    attendus = {str(x["noc_number"]): x for x in fenetre if x.get("noc_submission_class") in CLASSES_NSA}
    publies = {e["official_id"]: e for e in par_source["sante_canada"]}
    for n in sorted(set(attendus) - set(publies)):
        produits = json.loads(lire(f"{API_NOC}drugproduct/?id={n}&lang=fr&type=json").decode("utf-8-sig"))
        ingr = json.loads(lire(f"{API_NOC}medicinalingredient/?id={n}&lang=fr&type=json").decode("utf-8-sig"))
        if produits and ingr:
            ecarts.append(f"avis {n} ({attendus[n]['noc_submission_class']}, {attendus[n]['noc_date']}) : absent de Radar")
        else:
            dire(f"Santé Canada : avis {n} pas encore publié par Radar, fiches officielles vides (le robot réessaiera)")
    for n in sorted(set(publies) - set(attendus)):
        if publies[n]["occurred_on"] >= depuis:
            ecarts.append(f"avis {n} publié par Radar mais pas dans la liste officielle des NSA des 60 jours")
    dire(f"Santé Canada : {len(set(attendus) & set(publies))}/{len(attendus)} avis NSA de la liste officielle publiés : "
         + ", ".join(f"{n} ({attendus[n]['noc_date']}, {attendus[n]['noc_submission_class']})" for n in sorted(attendus)))

    # ---------- Santé Canada : la fiche publique de chaque avis ----------
    ok = 0
    for n, e in sorted(publies.items()):
        d = e["data"]
        page = lire(e["official_url"]).decode("utf-8", "replace")
        debut = page.find("<main")
        t = plat(page[debut:page.find("</main>")] if debut >= 0 else page)
        date = re.search(r"Date de l.avis de conformité : (\d{4}-\d\d-\d\d)", t)
        fab = re.search(r"Fabricant : (.*?) Type de produit :", t)
        cond = re.search(r"AC avec conditions : (Oui|Non)", t)
        cat = re.search(r"Catégorie de la présentation : (.*?) Marque 1 de", t)
        marques = sorted({" ".join(m.split()) for m in re.findall(r"Marque \d+ de \d+ : (.*?) Produit \d+ de \d+", t)})
        pb = []
        if not date or date.group(1) != e["occurred_on"] or e["published_on"] != e["occurred_on"]:
            pb.append(f"date {date.group(1) if date else '?'} ≠ {e['occurred_on']}")
        if not fab or fab.group(1) != d["fabricant"] or not e["title"].endswith(f", de {fab.group(1) if fab else '?'}"):
            pb.append(f"fabricant « {fab.group(1) if fab else '?'} » ≠ « {d['fabricant']} »")
        if not cond or (cond.group(1) == "Oui") != d["avec_conditions"] \
                or (cond.group(1) == "Oui") != any("avec conditions" in x for x in e.get("notes") or []):
            pb.append(f"avec conditions {cond.group(1) if cond else '?'} ≠ {d['avec_conditions']}")
        if not cat or cat.group(1) != d["classe"] \
                or (cat.group(1) == "Priorité-NSA") != any("Examen prioritaire" in x for x in e.get("notes") or []):
            pb.append(f"catégorie « {cat.group(1) if cat else '?'} » ≠ « {d['classe']} »")
        if marques != sorted(d["marques"]) or not all(m in e["title"] for m in marques):
            pb.append(f"marques {marques} ≠ {d['marques']}")
        absents = [i["nom"] for i in d["ingredients"] if i["nom"].upper() not in t.upper()]
        if absents or not d["ingredients"]:
            pb.append(f"ingrédients absents de la fiche : {absents}")
        if pb:
            ecarts.append(f"avis {n} : " + " ; ".join(pb))
        else:
            ok += 1
        dire(f"Santé Canada {n} : « {e['title']} » · fiche : {date.group(1) if date else '?'}, "
             f"{cat.group(1) if cat else '?'}, avec conditions : {cond.group(1) if cond else '?'} · "
             + ("conforme" if not pb else "ÉCART"))
    dire(f"Santé Canada : {ok}/{len(publies)} = fiche publique relue (date, fabricant, catégorie, conditions, marques, "
         "ingrédients)")

# ---------- CCC : la page des rapports ----------
with acces.section('CCC (rapport trimestriel)'):
    MOIS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
            "December")
    page = lire(PAGE_CCC).decode("utf-8", "replace")
    i, j = page.find('id="transactions"'), page.find('id="Events"')
    rapports = {}
    for href, lib in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page[i:j] if i >= 0 and j > i else "", re.S):
        m = re.search(r"Quarter ending (\w+) (\d+), (\d{4})", plat(lib))
        if m and m.group(1) in MOIS:
            rapports[f"{m.group(3)}-{MOIS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"] = urljoin(PAGE_CCC, href)
    fin_page = max(rapports) if rapports else None
    modif = re.search(r'<meta property="article:modified_time" content="([^"]+)"', page)
    modif_jour = datetime.fromisoformat(modif.group(1)).astimezone(TORONTO).date().isoformat() if modif else None
    dire(f"CCC : {len(rapports)} rapports trimestriels sur la page ; le plus récent : fin {fin_page} ; page modifiée le "
         f"{modif_jour} (heure de Toronto)")
    cccs = sorted(par_source["ccc"], key=lambda e: e["occurred_on"])
    if not cccs or not fin_page:
        ecarts.append("CCC : aucune info publiée, ou page des rapports illisible")
    else:
        e = cccs[-1]
        d = e["data"]
        pdf = lire(rapports[fin_page])
        depose = ENTETES[rapports[fin_page]].get("Last-Modified")
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.flush()
            texte = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, check=True).stdout.decode()
        periode = re.search(r"Pour la période\s*:\s*(\d{4}-\d\d-\d\d)\s+to/à\s+(\d{4}-\d\d-\d\d)", texte)
        fourchettes = []
        for m in re.finditer(r"<\s*\$([\d,]+\.\d\d)|>\s*\$([\d,]+\.\d\d)|\$([\d,]+\.\d\d)\s*[–-]\s*\$([\d,]+\.\d\d)", texte):
            v = [float(x.replace(",", "")) if x else None for x in m.groups()]
            fourchettes.append((0.0, v[0]) if v[0] is not None else (v[1], None) if v[1] is not None else (v[2], v[3]))
        robot = [(t["min"], t["max"]) for t in d["transactions"]]
        anonymes = len(re.findall(r"Canadian Exporter", texte))
        mots = set(re.findall(r"[\w&'-]+", texte))  # même découpage en mots des 2 côtés
        noms = sorted({t["exportateur"] for t in d["transactions"] if not t["exportateur"].startswith("Canadian Exporter")})
        noms_absents = [n for n in noms if not set(re.findall(r"[\w&'-]+", n)) <= mots]
        total_min = sum(a for a, _ in fourchettes)
        total_max = None if any(b is None for _, b in fourchettes) else sum(b for _, b in fourchettes)
        attendu_publie = max(fin_page, modif_jour or fin_page)
        dire(f"CCC : PDF {rapports[fin_page]} (fichier déposé le {depose}) · période {periode.groups() if periode else '?'} "
             f"· {len(fourchettes)} fourchettes lues par pdftotext, {len(robot)} transactions publiées par Radar · "
             f"{anonymes} « Canadian Exporter » · {len(noms)} exportateurs nommés")
        dire(f"CCC : titre publié « {e['title']} »")
        pb = []
        if e["official_url"] != rapports[fin_page] or d.get("fin_lien") != fin_page:
            pb.append(f"lien {e['official_url']} ≠ rapport le plus récent {rapports[fin_page]}")
        if not periode or (d["debut"], d["fin"]) != periode.groups() or e["official_id"] != ":".join(periode.groups()):
            pb.append(f"période {(d['debut'], d['fin'])} ≠ PDF {periode.groups() if periode else '?'}")
        if (e["occurred_on"], e["published_on"]) != (fin_page, attendu_publie):
            pb.append(f"dates {(e['occurred_on'], e['published_on'])} ≠ {(fin_page, attendu_publie)}")
        if robot != fourchettes:
            pb.append(f"fourchettes dans l'ordre ≠ ({len(robot)} contre {len(fourchettes)} ; 1re différence : "
                      + str(next(((k, a, b) for k, (a, b) in enumerate(zip(robot, fourchettes)) if a != b), "longueur")) + ")")
        if f"{len(fourchettes)} transactions signées" not in e["title"] or d.get("nombre") != len(fourchettes):
            pb.append("nombre de transactions du titre ≠ PDF")
        if d.get("anonymes") != anonymes:
            pb.append(f"exportateurs anonymes {d.get('anonymes')} ≠ PDF {anonymes}")
        if noms_absents:
            pb.append(f"exportateurs nommés absents du PDF : {noms_absents}")
        if (e.get("amount_min"), e.get("amount_max")) != (total_min, total_max):
            pb.append(f"totaux {(e.get('amount_min'), e.get('amount_max'))} ≠ PDF {(total_min, total_max)}")
        if pb:
            ecarts.append("CCC : " + " ; ".join(pb))
        dire(f"CCC : rapport relu (lien, période, dates, {len(fourchettes)} fourchettes dans l'ordre, exportateurs, totaux "
             f"{total_min:,.0f} $ à {'sans plafond' if total_max is None else f'{total_max:,.0f} $'}) : "
             + ("conforme" if not pb else "ÉCART"))

dire("\n".join(ecarts) if ecarts else ("AUCUN ÉCART dans ce qui a pu être relu." if acces.NON_VERIFIABLES
                                       else "AUCUN ÉCART : chaque info relue à sa source officielle."))
for ligne in acces.lignes_non_verifiables():
    dire(ligne)
dire(acces.verdict(ecarts))
SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
