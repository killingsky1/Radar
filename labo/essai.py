"""Essai réel des nouveaux lecteurs (le site n'est pas touché), puis vérification INDÉPENDANTE.

1. Le robot lit les vraies sources d'aujourd'hui dans une copie des données (/tmp/essai).
2. Pour chaque info produite (échantillon), on retourne au document officiel et on relit les faits
   avec une AUTRE méthode que celle du robot. Toute différence est listée.
Résultat : labo/essai/ (infos produites, état des sources, rapport de vérification).
"""

from __future__ import annotations

import html
import io
import json
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "labo" / "essai"
DONNEES = Path("/tmp/essai")
SOURCES = ["nhtsa", "doj_antitrust", "sec_poursuites", "sanctions_us", "ftc_fusions", "fda", "sec_13f", "maison_blanche", "fed", "banque_canada", "sec_form144", "sec_offres", "cftc_cot",
           "registre_federal", "ventes_armes", "senat_ptr", "chambre_ptr", "nouvelles_defense_ca", "nouvelles_eco_ca"]
UA = {"User-Agent": "Radar projet personnel"}  # comme le robot : le courriel ne part qu'à la SEC
UA_SEC = {"User-Agent": "Radar projet personnel math-veronneau1@hotmail.com"}
PAR_SOURCE = 12  # infos vérifiées par source (au hasard)
session = requests.Session()


def get(url, **kw):
    time.sleep(0.5)
    hote = (urlparse(url).hostname or "").lower()
    ua = UA_SEC if hote == "sec.gov" or hote.endswith(".sec.gov") else UA
    r = session.get(url, headers={**ua, **kw.pop("headers", {})}, timeout=60, **kw)
    r.raise_for_status()
    return r


def lire_page(url):
    """Le texte d'une page en UTF-8 (requests devine parfois latin-1 et abîme les caractères spéciaux)."""
    return get(url).content.decode("utf-8", "replace")


def normal(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or "")).replace("’", "'").replace("‘", "'")
    return " ".join(t.split()).lower()


PLAGES = {"$1,001 - $15,000": (1001, 15000), "$15,001 - $50,000": (15001, 50000), "$50,001 - $100,000": (50001, 100000),
          "$100,001 - $250,000": (100001, 250000), "$250,001 - $500,000": (250001, 500000),
          "$500,001 - $1,000,000": (500001, 1000000), "$1,000,001 - $5,000,000": (1000001, 5000000),
          "$5,000,001 - $25,000,000": (5000001, 25000000), "$25,000,001 - $50,000,000": (25000001, 50000000)}


# ---------- Vérifications, une par sorte de source ----------


def verifier_registre(ev):
    num, d = ev["official_id"], ev["data"]
    if d.get("etape") == "inspection_publique":  # même forme d'adresse que le champ json_url de l'API
        off = get(f"https://www.federalregister.gov/api/v1/public_inspection_documents/{num}").json()
    else:
        off = get(f"https://www.federalregister.gov/api/v1/documents/{num}.json").json()
    ecarts = []
    if normal(off.get("title")) != normal(d.get("titre_officiel")):
        ecarts.append(f"titre : API « {off.get('title')} » ≠ robot « {d.get('titre_officiel')} »")
    noms_api = sorted(normal(a.get("name") or a.get("raw_name")) for a in off.get("agencies") or [])
    if noms_api != sorted(normal(a) for a in d.get("agences") or []):
        ecarts.append(f"agences : {noms_api} ≠ {d.get('agences')}")
    if get(ev["official_url"]).status_code != 200:
        ecarts.append("lien officiel ne répond pas")
    if ev["source"] == "ventes_armes":
        brut = get(off["raw_text_url"]).text if off.get("raw_text_url") else ""
        lignes = [normal(l) for l in html.unescape(re.sub(r"<[^>]+>", "", brut)).splitlines()]
        texte_brut = re.sub(r"\[\[page \d+\]\]", " ", " ".join(lignes))
        m_ach = re.search(r"\(i\) (?:\(u\) )?(?:prospective )?purchaser:\s*(.+?)\s*\(ii\)", texte_brut)
        acheteur = m_ach.group(1).strip() if m_ach else None
        if (acheteur or "") != normal((d.get("vente") or {}).get("acheteur")):
            ecarts.append(f"acheteur : texte « {acheteur} » ≠ robot « {(d.get('vente') or {}).get('acheteur')} »")
        texte = " ".join(lignes)
        totaux = re.findall(r"total\.*\s*\$\s*([\d.]+)\s*(million|billion)", texte)
        if totaux:
            n, u = totaux[0]
            attendu = float(n) * (1e9 if u == "billion" else 1e6)
            if ev.get("amount_min") != attendu:
                ecarts.append(f"montant : texte {attendu} ≠ robot {ev.get('amount_min')}")
        elif ev.get("amount_min") is not None:
            ecarts.append("montant lu par le robot mais introuvable par la 2e méthode")
        for f in (d.get("vente") or {}).get("fournisseurs") or []:
            if normal(f) not in texte:
                ecarts.append(f"fournisseur absent du texte : {f}")
    return ecarts


def verifier_canada(ev):
    page = lire_page(ev["official_url"])
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    ecarts = []
    if not h1 or normal(re.sub(r"</?sup>", "", h1.group(1))) != normal(ev["title"]):  # « 5<sup>e</sup> » = « 5e »
        ecarts.append(f"titre de la page « {normal(h1.group(1)) if h1 else '?'} » ≠ robot « {ev['title']} »")
    if normal(ev["data"]["ministere"]) not in normal(page):
        ecarts.append(f"ministère absent de la page : {ev['data']['ministere']}")
    return ecarts


class Rangées(HTMLParser):
    """2e méthode pour le Sénat : l'analyseur HTML standard de Python (le robot utilise des expressions régulières)."""

    def __init__(self):
        super().__init__()
        self.rangees, self._r, self._c, self.dans_tbody = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self.dans_tbody = True
        elif tag == "tr" and self.dans_tbody:
            self._r = []
        elif tag == "td" and self._r is not None:
            self._c = []

    def handle_endtag(self, tag):
        if tag == "td" and self._c is not None:
            self._r.append(" ".join("".join(self._c).split()))
            self._c = None
        elif tag == "tr" and self._r is not None:
            self.rangees.append(self._r)
            self._r = None
        elif tag == "tbody":
            self.dans_tbody = False

    def handle_data(self, data):
        if self._c is not None:
            self._c.append(data)


def accepter_conditions_senat():
    accueil = get("https://efdsearch.senate.gov/search/home/").text
    jeton = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', accueil).group(1)
    session.post("https://efdsearch.senate.gov/search/home/", data={"prohibition_agreement": "1", "csrfmiddlewaretoken": jeton},
                 headers={**UA, "Referer": "https://efdsearch.senate.gov/search/home/"}, timeout=60)


def comparer_transactions(ev, transactions):
    """transactions : (symbole, sens P/S, date ISO, montant) relues par la 2e méthode."""
    symbole = ev["tickers"][0]
    sens = "P" if ev["kind"].startswith("achat") else "S"
    option = ev["kind"].endswith("_option")
    gardees = [t for t in transactions if t[0] == symbole and t[1] == sens and t[4] == option]
    ecarts = []
    if len(gardees) != len(ev["data"]["transactions"]):
        ecarts.append(f"nombre de transactions : 2e méthode {len(gardees)} ≠ robot {len(ev['data']['transactions'])}")
    plages = [PLAGES.get(t[3]) for t in gardees]
    if all(plages) and plages:
        bas, haut = sum(p[0] for p in plages), sum(p[1] for p in plages)
        if (bas, haut) != (ev.get("amount_min"), ev.get("amount_max")):
            ecarts.append(f"montant : 2e méthode {bas}-{haut} ≠ robot {ev.get('amount_min')}-{ev.get('amount_max')}")
    dates = sorted(t[2] for t in gardees if t[2])
    if dates and dates[0] != ev["occurred_on"]:
        ecarts.append(f"date : 2e méthode {dates[0]} ≠ robot {ev['occurred_on']}")
    return ecarts


def iso(us):
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", us.strip())
    return date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat() if m else None


def verifier_senat(ev):
    p = Rangées()
    p.feed(lire_page(ev["official_url"]))
    tx = []
    for r in p.rangees:
        if len(r) >= 8 and r[5] in ("Stock", "Stock Option"):
            sens = {"Purchase": "P", "Sale (Full)": "S", "Sale (Partial)": "S"}.get(r[6])
            tx.append((r[3].upper().replace(".", "-"), sens, iso(r[1]), r[7], r[5] == "Stock Option"))
    return comparer_transactions(ev, tx)


def verifier_chambre(ev):
    import pdfplumber
    from hashlib import sha256

    contenu = get(ev["official_url"]).content
    ecarts = [] if sha256(contenu).hexdigest() == ev["sha256"] else ["le PDF officiel a changé depuis la lecture"]
    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        texte = "\n".join((pg.extract_text() or "") for pg in pdf.pages).replace("\x00", " ")
    lignes = [l for l in texte.splitlines() if l.strip() and not l.startswith(("ID Owner Asset", "Type Date Gains", "$200?"))]
    motif = re.compile(r"^(?:(SP|JT|DC) )?(.+?) (P|S|S \(partial\)|E) (\d{2}/\d{2}/\d{4}) (\d{2}/\d{2}/\d{4}) (.*)$")
    tx = []
    for i, l in enumerate(lignes):
        m = motif.match(l)
        if not m:
            continue
        actif, montant = [m.group(2)], m.group(6)
        for s in lignes[i + 1:i + 6]:
            if re.match(r"^[A-Z] +([A-Z] +)?:", s) or motif.match(s):
                break
            mm = re.search(r"(\$[\d,]+)\s*$", s)
            if mm and montant.rstrip().endswith("-"):
                montant += " " + mm.group(1)
                s = s[:mm.start()]
            actif.append(s.strip())
        a = " ".join(actif)
        sym = re.findall(r"\(([A-Z][A-Z0-9.]{0,6})\)", a)
        code = re.findall(r"\[([A-Z0-9]{2})\]", a)
        if sym and code and code[-1] in ("ST", "OP"):
            tx.append((sym[-1].replace(".", "-"), {"P": "P", "S": "S", "S (partial)": "S"}.get(m.group(3)),
                       iso(m.group(4)), " ".join(montant.split()), code[-1] == "OP"))
    return ecarts + comparer_transactions(ev, tx)


def verifier_maison_blanche(ev):
    page = lire_page(ev["official_url"])
    titre = re.search(r"<title>(.*?)</title>", page, re.S)
    ecarts = []
    if not titre or normal(ev["data"]["titre_officiel"]) not in normal(titre.group(1)):
        ecarts.append(f"titre de la page « {normal(titre.group(1)) if titre else '?'} » ≠ « {ev['data']['titre_officiel']} »")
    for c in ev.get("confirmations") or []:  # la confirmation pointe vers un document du Registre au même titre
        off = get(f"https://www.federalregister.gov/api/v1/documents/{c['official_id']}.json").json()
        if re.sub(r"[^a-z0-9]", "", normal(off.get("title"))) != re.sub(r"[^a-z0-9]", "", normal(ev["data"]["titre_officiel"])):
            ecarts.append(f"confirmation au titre différent : {off.get('title')}")
    return ecarts


def verifier_fed(ev):
    texte = normal(lire_page(ev["official_url"])).translate(dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-"))
    phrase = re.search(r"decided to (\w+) the target range for the federal funds rate.*?percent(?!age)", texte)
    ecarts = []
    if not phrase:
        return ["phrase de décision introuvable"]
    chiffres = re.findall(r"(\d+(?:-\d+/\d+)?|\d+/\d+) to (\d+(?:-\d+/\d+)?) percent", phrase.group(0))
    def n(x):
        if "/" in x:
            e, _, f = x.partition("-") if "-" in x else ("0", "", x)
            a, b = f.split("/")
            return float(e) + int(a) / int(b)
        return float(x)
    if not chiffres or (n(chiffres[-1][0]), n(chiffres[-1][1])) != (ev["data"]["bas"], ev["data"]["haut"]):
        ecarts.append(f"fourchette : texte {chiffres} ≠ robot {ev['data'].get('bas')}-{ev['data'].get('haut')}")
    vote = re.search(r"by a (\d+) [–-] (\d+) vote", texte)
    if vote and f"{vote.group(1)}-{vote.group(2)}" != ev["data"].get("vote"):
        ecarts.append(f"vote : texte {vote.groups()} ≠ robot {ev['data'].get('vote')}")
    return ecarts


def verifier_bdc(ev):
    texte = normal(lire_page(ev["official_url"]))
    morceau = texte.split("its target for the overnight rate", 1)
    if len(morceau) < 2:
        return ["phrase de décision introuvable"]
    m = re.match(r"\s*(?:by \d+ basis points )?(?:at|to) ([\d.]+)([¼½¾]?)%", morceau[1])
    if not m:
        return [f"taux introuvable : {morceau[1][:60]}"]
    taux = float(m.group(1) or 0) + {"¼": .25, "½": .5, "¾": .75, "": 0}[m.group(2)]
    return [] if abs(taux - ev["data"]["taux"]) < 1e-9 else [f"taux : texte {taux} ≠ robot {ev['data']['taux']}"]


def verifier_144(ev):
    from hashlib import sha256

    acc = ev["official_id"]
    cik = ev["official_url"].split("/edgar/data/")[1].split("/")[0]
    brut = get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}.txt").content
    ecarts = [] if sha256(brut).hexdigest() == ev["sha256"] else ["le document SEC a changé depuis la lecture"]
    t = brut.decode("utf-8", "replace")
    valeur = sum(float(x.replace(",", "")) for x in re.findall(r"<(?:\w+:)?aggregateMarketValue>\s*([\d.,]+)\s*<", t))
    actions = sum(float(x.replace(",", "")) for x in re.findall(r"<(?:\w+:)?noOfUnitsSold>\s*([\d.,]+)\s*<", t))
    if abs(valeur - ev["amount_max"]) > 0.01:
        ecarts.append(f"valeur : document {valeur} ≠ robot {ev['amount_max']}")
    if abs(actions - ev["data"]["actions"]) > 1e-6:
        ecarts.append(f"actions : document {actions} ≠ robot {ev['data']['actions']}")
    return ecarts


def verifier_offre(ev):
    from hashlib import sha256

    acc = ev["official_id"]
    dossier = ev["official_url"].rsplit("/", 1)[0]
    brut = get(f"{dossier}/{acc}-index-headers.html").content
    entete = re.search(rb"<SEC-HEADER>.*?</SEC-HEADER>", brut, re.S)
    canon = sha256(b" ".join(entete.group(0).split())).hexdigest() if entete else None
    ecarts = [] if ev["sha256"] in (sha256(brut).hexdigest(), canon) else ["le document SEC a changé depuis la lecture"]
    t = html.unescape(brut.decode("utf-8", "replace"))
    forme = re.search(r"CONFORMED SUBMISSION TYPE:\s*(\S[^\n<]*)", t)
    if ev["data"]["cible"] not in t:
        ecarts.append(f"compagnie visée absente du document : {ev['data']['cible']}")
    for _, nom in ev["data"]["acheteurs"]:
        if nom not in t:
            ecarts.append(f"acheteur absent du document : {nom}")
    if not forme:
        ecarts.append("forme introuvable")
    return ecarts


def verifier_cftc(ev):
    [r] = get(ev["official_url"]).json()
    net = int(r["noncomm_positions_long_all"]) - int(r["noncomm_positions_short_all"])
    var = int(r["change_in_noncomm_long_all"]) - int(r["change_in_noncomm_short_all"])
    ecarts = []
    if (net, var) != (ev["data"]["net"], ev["data"]["variation"]):
        ecarts.append(f"net/variation : API {net}/{var} ≠ robot {ev['data']['net']}/{ev['data']['variation']}")
    if r["market_and_exchange_names"] != ev["data"]["nom_officiel"]:
        ecarts.append("nom du marché différent")
    return ecarts


MOIS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]


def textes_pdf(contenu):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def verifier_fda(ev):
    """2e méthode, 2 documents officiels autres que la fiche openFDA du robot :
    - la page Drugs@FDA (HTML) : date d'action, « ORIG-1 Approval », classe « Type 1 » (médicament) ou
      « Biologic License Application » (produit biologique : la page écrit « N/A » comme classe), marque, compagnie ;
    - la lettre d'approbation (PDF) : numéro, marque, « approved » et date de la signature électronique.
      Lettre en image (1re page sans texte) : seule la page de signature électronique est lisible.
    """
    d = ev["data"]
    jour = date.fromisoformat(ev["published_on"])
    mmjjaaaa = f"{jour.month:02d}/{jour.day:02d}/{jour.year}"
    num = d["application"]
    ecarts = []
    page = " ".join(re.sub(r"<[^>]+>", " ", lire_page(ev["official_url"])).split()).upper()
    approbation = f"{mmjjaaaa} ORIG-{d['numero_soumission']} APPROVAL"
    if num.startswith("NDA") and not re.search(rf"{re.escape(approbation)} TYPE 1\b", page):
        ecarts.append(f"Drugs@FDA : pas d'approbation originale de type 1 le {mmjjaaaa}")
    if num.startswith("BLA") and (approbation not in page or f"BIOLOGIC LICENSE APPLICATION (BLA) : {num[3:]}" not in page):
        ecarts.append(f"Drugs@FDA : pas d'approbation originale du produit biologique le {mmjjaaaa}")
    for marque in d["marques"]:
        if marque.upper() not in page:
            ecarts.append(f"Drugs@FDA : marque {marque} absente")
    if f"COMPANY: {str(d['sponsor']).upper()}" not in page:
        ecarts.append(f"Drugs@FDA : compagnie {d['sponsor']} absente")
    textes = textes_pdf(get(d["lettre"]).content)
    tout = " ".join(" ".join(textes).split()).upper()
    if mmjjaaaa not in tout:
        ecarts.append(f"lettre : date de signature {mmjjaaaa} absente")
    if not textes or not textes[0].strip():
        return ecarts  # lettre en image : le reste est vérifié par Drugs@FDA
    if not re.search(rf"{num[:3]}\s*{num[3:]}", tout):
        ecarts.append(f"lettre : numéro {num} absent")
    for marque in d["marques"]:
        if marque.upper() not in tout:
            ecarts.append(f"lettre : marque {marque} absente")
    if "APPROVED" not in tout:
        ecarts.append("lettre : le mot « approved » est absent")
    return ecarts


def actions_13f(cik, acc, cusip):
    """2e méthode : expressions régulières sur la table officielle (le robot utilise un analyseur XML)."""
    dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    items = get(f"{dossier}/index.json").json()["directory"]["item"]
    table = next(i["name"] for i in items if i["name"].endswith(".xml") and i["name"] != "primary_doc.xml")
    xml = get(f"{dossier}/{table}").content.decode("utf-8", "replace")
    total = 0
    for bloc in re.findall(r"<(?:\w+:)?infoTable>(.*?)</(?:\w+:)?infoTable>", xml, re.S):
        c = re.search(r"<(?:\w+:)?cusip>\s*([0-9A-Za-z]{9})\s*<", bloc)
        if not c or c.group(1).upper() != cusip or re.search(r"<(?:\w+:)?putCall>", bloc):
            continue
        if not re.search(r"<(?:\w+:)?sshPrnamtType>\s*SH\s*<", bloc):
            continue
        total += int(float(re.search(r"<(?:\w+:)?sshPrnamt>\s*([\d.]+)\s*<", bloc).group(1)))
    return total


def verifier_13f(ev):
    d = ev["data"]
    acc = ev["official_id"].split(":")[0]
    a, b = actions_13f(d["cik_fonds"], d["acc_precedent"], d["cusip"]), actions_13f(d["cik_fonds"], acc, d["cusip"])
    ecarts = []
    if (a, b) != (d["actions_avant"], d["actions_apres"]):
        ecarts.append(f"actions : document {a} -> {b} ≠ robot {d['actions_avant']} -> {d['actions_apres']}")
    if ev["published_on"] not in lire_page(ev["official_url"]):
        ecarts.append("date de dépôt absente de la page officielle")
    return ecarts


def verifier_nhtsa(ev):
    """2e méthode : export CSV du même portail (le robot lit le JSON), filtré sur le numéro de rappel."""
    import csv
    num = ev["official_id"]
    texte = get(f"https://datahub.transportation.gov/resource/6axg-epim.csv?nhtsa_id={num}").content.decode("utf-8")
    lignes = list(csv.DictReader(io.StringIO(texte)))
    if len(lignes) != 1:
        return [f"{len(lignes)} ligne(s) pour {num} dans l'export CSV"]
    l = lignes[0]
    d = ev["data"]
    ecarts = []
    if int(float(l["potentially_affected"])) != d["unites"]:
        ecarts.append(f"véhicules : CSV {l['potentially_affected']} ≠ robot {d['unites']}")
    if l["manufacturer"].strip() != d["constructeur"]:
        ecarts.append(f"constructeur : CSV {l['manufacturer']} ≠ robot {d['constructeur']}")
    if l["report_received_date"][:10] != ev["published_on"]:
        ecarts.append(f"date : CSV {l['report_received_date'][:10]} ≠ robot {ev['published_on']}")
    if l["subject"].strip() != (d.get("sujet") or "").strip():
        ecarts.append("sujet différent")
    return ecarts


def verifier_doj(ev):
    """2e méthode : la page du communiqué lui-même (le robot lit le flux RSS)."""
    page = normal(lire_page(ev["official_url"]))
    titre = normal(ev["data"]["titre_officiel"])
    ecarts = [] if titre[:80] in page else ["titre absent de la page du communiqué"]
    jour = date.fromisoformat(ev["published_on"])
    if f"{MOIS_EN[jour.month - 1]} {jour.day}, {jour.year}".lower() not in page:
        ecarts.append(f"date {jour} absente de la page")
    return ecarts


def verifier_sec_poursuites(ev):
    """2e méthode : le document officiel (PDF de l'ordonnance) doit nommer la compagnie."""
    t = normal(" ".join(textes_pdf(get(ev["official_url"]).content)))
    nom = normal(ev["data"]["nom_officiel"]).replace(",", "")
    t2 = t.replace(",", "")
    ecarts = [] if nom[:40] in t2 else [f"{ev['data']['nom_officiel']} absent du document officiel"]
    if ev["kind"] == "suspension_cotation" and "suspension of trading" not in t:
        ecarts.append("le document ne parle pas de suspension de cotation")
    return ecarts


def verifier_ofac(ev):
    """2e méthode : découper chaque liste HTML en fiches (séparées par des sauts de ligne <br><br> ou des fins de
    paragraphe) et compter celles qui portent une étiquette [PROGRAMME] (le robot compte les étiquettes du texte)."""
    page = lire_page(ev["official_url"])
    corps = page[page.find("field--name-field-body"):]
    ajouts, retraits = {}, 0
    noms = {"individual": "personnes", "entit": "entités", "vessel": "navires", "aircraft": "aéronefs"}
    sections = re.split(r"(The following[^<]{5,120}:)", corps)
    for i in range(1, len(sections) - 1, 2):
        entete = sections[i].lower()
        bloc = sections[i + 1].split("The following")[0]
        n = len([f for f in re.split(r"<br\s*/?>\s*<br\s*/?>|</p>", bloc) if re.search(r"\[[A-Z0-9-]+\]", f)])
        if "added" in entete:
            cat = next((v for k, v in noms.items() if k in entete), "fiches")
            ajouts[cat] = ajouts.get(cat, 0) + n
        elif "deletion" in entete or "removed" in entete:
            retraits += n
    ecarts = []
    if ajouts != ev["data"]["ajouts"]:
        ecarts.append(f"ajouts : page {ajouts} ≠ robot {ev['data']['ajouts']}")
    if retraits != ev["data"]["retraits"]:
        ecarts.append(f"retraits : page {retraits} ≠ robot {ev['data']['retraits']}")
    return ecarts


def verifier_ftc(ev):
    """2e méthode : la page de l'avis (le robot lit le flux RSS)."""
    page = normal(lire_page(ev["official_url"]))
    d = ev["data"]
    ecarts = []
    for etiquette, valeur in (("numéro", d["numero"]), ("acquéreur", d["acquereur"]), ("partie visée", d["partie_visee"])):
        if normal(valeur) not in page:
            ecarts.append(f"{etiquette} {valeur} absent de la page")
    jour = date.fromisoformat(ev["occurred_on"])
    if f"{MOIS_EN[jour.month - 1]} {jour.day}, {jour.year}".lower() not in page:
        ecarts.append(f"date {jour} absente de la page")
    return ecarts


VERIFS = {
    "nhtsa": verifier_nhtsa, "doj_antitrust": verifier_doj, "sec_poursuites": verifier_sec_poursuites,
    "sanctions_us": verifier_ofac, "ftc_fusions": verifier_ftc,
    "fda": verifier_fda, "sec_13f": verifier_13f,
    "maison_blanche": verifier_maison_blanche, "fed": verifier_fed, "banque_canada": verifier_bdc,
    "sec_form144": verifier_144, "sec_offres": verifier_offre, "cftc_cot": verifier_cftc,"registre_federal": verifier_registre, "ventes_armes": verifier_registre, "senat_ptr": verifier_senat,
          "chambre_ptr": verifier_chambre, "nouvelles_defense_ca": verifier_canada, "nouvelles_eco_ca": verifier_canada}


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(DONNEES, ignore_errors=True)
    shutil.copytree(RACINE / "data", DONNEES)
    run = subprocess.run([sys.executable, "-m", "radar.run", "--donnees", str(DONNEES), "--sources", ",".join(SOURCES)],
                         cwd=RACINE / "robot", capture_output=True, text=True)
    (SORTIE / "sortie_robot.txt").write_text(run.stdout + "\n" + run.stderr, encoding="utf-8")
    evs = []
    for dossier in ("evenements", "a_verifier"):
        for f in sorted((DONNEES / dossier).glob("*.jsonl")):
            evs += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()
                    if l.strip() and json.loads(l)["source"] in SOURCES]
    (SORTIE / "infos.json").write_text(json.dumps(evs, ensure_ascii=False, indent=1), encoding="utf-8")
    # Pages des décisions de la Fed mises de côté : pour améliorer le lecteur sans rien deviner.
    for e in evs:
        if e["source"] == "fed" and e["badge"] == "a_verifier":
            try:
                (SORTIE / "textes").mkdir(exist_ok=True)
                (SORTIE / "textes" / f"{e['official_id']}.htm").write_bytes(get(e["official_url"]).content)
            except Exception:  # noqa: BLE001
                pass
    # Textes des avis d'armes mis de côté : pour améliorer le lecteur sans rien deviner.
    for e in evs:
        if e["source"] == "ventes_armes" and e["badge"] == "a_verifier":
            try:
                num = e["official_id"]
                off = get(f"https://www.federalregister.gov/api/v1/documents/{num}.json").json()
                (SORTIE / "textes").mkdir(exist_ok=True)
                (SORTIE / "textes" / f"{num}.txt").write_text(get(off["raw_text_url"]).text, encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
    etat = json.loads((DONNEES / "etat_sources.json").read_text(encoding="utf-8"))
    (SORTIE / "etat.json").write_text(json.dumps({s: etat.get(s) for s in SOURCES}, ensure_ascii=False, indent=1), encoding="utf-8")

    lignes = ["# Essai réel et vérification indépendante", "", f"Infos produites : {len(evs)}", ""]
    try:
        accepter_conditions_senat()
    except Exception as e:  # noqa: BLE001
        lignes.append(f"Sénat : conditions non acceptées ({e})")
    random.seed(20261002)
    total = bons = 0
    for s in SOURCES:
        a_lui = [e for e in evs if e["source"] == s]
        badges = {b: sum(e["badge"] == b for e in a_lui) for b in ("officiel", "confirme", "a_verifier")}
        lignes += [f"## {s}", f"- produites : {len(a_lui)} {badges}", f"- état : {etat.get(s)}"]
        for e in random.sample(a_lui, min(PAR_SOURCE, len(a_lui))):
            total += 1
            try:
                ecarts = VERIFS[s](e)
            except Exception as exc:  # noqa: BLE001
                ecarts = [f"vérification impossible : {type(exc).__name__}: {exc}"[:200]]
            bons += not ecarts
            lignes.append(f"- {'OK ' if not ecarts else 'ÉCART'} {e['title'][:110]}")
            lignes += [f"    - {x}" for x in ecarts]
        lignes.append("")
    lignes.insert(3, f"Vérifiées au hasard : {total} — identiques : {bons}")
    (SORTIE / "verification.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))


if __name__ == "__main__":
    main()
