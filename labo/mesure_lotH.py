"""Lot H : MESURE du détecteur strict des annonces de rachat d'actions sur 10 jours ouvrables de vrais 8-K.

Mêmes règles d'accès que le robot : robots.txt lu d'abord, au moins 1,5 s entre deux requêtes, le courriel seulement
dans l'identification envoyée à la SEC. Comme le robot : seulement les compagnies cotées (liste officielle de la SEC),
seulement les 8-K avec les points 2.02, 7.01 ou 8.01, seulement le document principal et les communiqués (EX-99).

Gardé pour relire à la main : TOUTES les phrases qui parlent de rachat (« repurchase », « buyback »), avec la décision
du détecteur strict ; le texte complet des dépôts où une phrase parle aussi d'autoriser ou d'augmenter.
"""
import gzip
import html
import json
import re
import sys
import time
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from detecteur_rachats import CANDIDAT, analyser, decider, nouveaute, phrases  # noqa: E402

UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
# Arguments : dernier jour, nombre de jours ouvrables, dossier de sortie (par défaut : les 10 jours du 21 sept. au 2 oct.)
FIN = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 10, 2)
NOMBRE = int(sys.argv[2]) if len(sys.argv) > 2 else 10
SORTIE = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("labo/resultats-lotH")
SORTIE.mkdir(parents=True, exist_ok=True)
DEBUT = time.monotonic()
LIMITE_S = 270 * 60
JOURS = [FIN - timedelta(days=i) for i in range(3 * NOMBRE)]
JOURS = [j for j in JOURS if j.weekday() < 5][:NOMBRE]
POINTS = {"results of operations and financial condition": "2.02", "regulation fd disclosure": "7.01",
          "other events": "8.01"}
AUTORISE = re.compile(r"authoriz|authoris|approv|increas|expand|adopt|upsiz|replenish", re.I)
resume, dernier = [], [0.0]
rp = urllib.robotparser.RobotFileParser()


def dire(t=""):
    print(t, flush=True)
    resume.append(t)
    (SORTIE / "resume.md").write_text("\n".join(resume) + "\n", encoding="utf-8")


def lire(url, max_octets=30_000_000):
    if not rp.can_fetch(UA_SEC, url):
        return None, b""
    attente = 1.5 - (time.monotonic() - dernier[0])
    if attente > 0:
        time.sleep(attente)
    try:
        r = requests.get(url, headers={"User-Agent": UA_SEC, "Accept-Encoding": "gzip, deflate"}, timeout=(20, 180),
                         stream=True)
        morceaux, taille = [], 0
        for m in r.iter_content(1 << 16):
            morceaux.append(m)
            taille += len(m)
            if taille > max_octets:
                break
        r.close()
        return r.status_code, b"".join(morceaux)
    except Exception as exc:  # noqa: BLE001
        return f"erreur {type(exc).__name__}", b""
    finally:
        dernier[0] = time.monotonic()


def lire_ok(url):
    statut, c = lire(url)
    if statut != 200:
        raise RuntimeError(f"HTTP {statut} : {url}")
    return c


def texte_doc(brut: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", brut)
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", t)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").replace("​", " ").split())


r = requests.get("https://www.sec.gov/robots.txt", headers={"User-Agent": UA_SEC}, timeout=60)
rp.parse(r.text.splitlines())
dire(f"# Lot H : mesure du détecteur strict des rachats d'actions (robots.txt de la SEC : HTTP {r.status_code})")
statut, contenu = lire("https://www.sec.gov/files/company_tickers_exchange.json")
cotes = {int(l[0]): (l[2], l[3]) for l in json.loads(contenu)["data"]}
dire(f"Compagnies cotées (liste officielle de la SEC) : {len(set(cotes))}")
depots, phr, textes, compte = [], [], {}, {"8-K": 0, "cotés": 0, "points": 0, "lus": 0}
for jour in JOURS:
    if time.monotonic() - DEBUT > LIMITE_S:
        dire(f"(arrêt : temps permis atteint avant le {jour})")
        break
    statut, contenu = lire(f"https://www.sec.gov/Archives/edgar/daily-index/{jour.year}/QTR{(jour.month - 1) // 3 + 1}/"
                           f"master.{jour:%Y%m%d}.idx")
    if statut != 200:
        dire(f"- {jour} : index HTTP {statut}")
        continue
    par_acc = {}
    for l in contenu.decode("latin-1").splitlines():
        p = l.split("|")
        if len(p) == 5 and p[0].strip().isdigit() and p[2].strip() == "8-K":
            acc = p[4].rsplit("/", 1)[1].removesuffix(".txt")
            par_acc.setdefault(acc, {"acc": acc, "jour": jour.isoformat(), "fichier": p[4].strip(), "filers": []})
            par_acc[acc]["filers"].append((int(p[0]), p[1].strip()))
    n_jour = 0
    for d in par_acc.values():
        compte["8-K"] += 1
        cote = next(((c, n) for c, n in d["filers"] if c in cotes), None)
        if not cote:
            continue
        compte["cotés"] += 1
        if time.monotonic() - DEBUT > LIMITE_S:
            break
        cik = cote[0]
        dossier = f"https://www.sec.gov/Archives/edgar/data/{cik}/{d['acc'].replace('-', '')}"
        statut, entete = lire(f"{dossier}/{d['acc']}-index-headers.html", 2_000_000)
        if statut != 200:
            d["erreur"] = f"en-tête HTTP {statut}"
            depots.append(d)
            continue
        items = sorted({POINTS[x.strip().lower()] for x in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)",
                                                                       html.unescape(entete.decode("utf-8", "replace")))
                        if x.strip().lower() in POINTS})
        if not items:
            continue
        compte["points"] += 1
        statut, brut = lire(f"https://www.sec.gov/Archives/{d['fichier']}")
        if statut != 200:
            d["erreur"] = f"dépôt HTTP {statut}"
            depots.append(d)
            continue
        compte["lus"] += 1
        n_jour += 1
        txt = brut.decode("utf-8", "replace")  # comme le robot (documents lus en UTF-8)
        d.update({"cik": cik, "nom": cote[1], "symbole": cotes[cik][0], "bourse": cotes[cik][1], "points": items,
                  "docs": []})
        lus_docs, garder = [], False
        for m in re.finditer(r"<DOCUMENT>\s*<TYPE>([^\n<]+)(.*?)</DOCUMENT>", txt, re.S):
            typ = m.group(1).strip().upper()
            if not (typ.startswith("8-K") or typ.startswith("EX-99")):
                continue
            t = texte_doc(m.group(2))
            d["docs"].append(typ)
            lus_docs.append((typ, t))
            for i, p in enumerate(phrases(t)):
                if not CANDIDAT.search(p):
                    continue
                a = analyser(p, jour)
                phr.append({"acc": d["acc"], "nom": cote[1], "symbole": cotes[cik][0], "jour": d["jour"], "doc": typ,
                            "phrase": p[:2000], **a})
                if AUTORISE.search(p):
                    garder = True
            if garder:
                textes.setdefault(d["acc"], {})[typ] = t
        d["decision"] = decider(lus_docs, jour)
        if d["decision"]["statut"] == "annonce":  # vérification de nouveauté : les 8-K des 90 jours avant
            x = d["decision"]
            try:
                deja, relus = nouveaute(lire_ok, cik, d["acc"], jour, (x["dollars"], x["actions"]))
                x["nouveaute_relus"] = relus
                if deja:
                    d["decision"] = {"statut": "déjà annoncée", "dans": deja, "avant": x}
            except Exception as exc:  # noqa: BLE001
                d["decision"] = {"statut": "nouveauté pas vérifiée", "erreur": str(exc)[:200], "avant": x}
        depots.append(d)
    dire(f"- {jour} : {len(par_acc)} 8-K · lus (cotés, points 2.02/7.01/8.01) : {n_jour}")
    (SORTIE / "depots.json").write_text(json.dumps(depots, ensure_ascii=False, indent=0), encoding="utf-8")
    (SORTIE / "phrases.json").write_text(json.dumps(phr, ensure_ascii=False, indent=0), encoding="utf-8")
    (SORTIE / "textes.json.gz").write_bytes(gzip.compress(json.dumps(textes, ensure_ascii=False).encode(), 9))

dire()
dire(f"8-K : {compte['8-K']} · de compagnies cotées : {compte['cotés']} · avec 2.02, 7.01 ou 8.01 : {compte['points']} · "
     f"lus : {compte['lus']} · erreurs : {sum(1 for d in depots if 'erreur' in d)}")
dire(f"Phrases qui parlent de rachat : {len(phr)} · avec un mot d'autorisation ou de hausse : "
     f"{sum(1 for p in phr if AUTORISE.search(p['phrase']))}")
annonces = [d for d in depots if d.get("decision", {}).get("statut") == "annonce"]
dire(f"## Annonces retenues par le détecteur strict : {len(annonces)}")
for d in annonces:
    x = d["decision"]
    montant = f"{x['dollars'] / 1e6:,.1f} M$" if x["dollars"] else f"{x['actions']:,.0f} actions"
    dire(f"- {d['jour']} · {d['nom']} ({d['symbole']}) · {x['sorte']} · {montant} · {d['acc']}")
    for doc, phrase in x["phrases"]:
        dire(f"  - [{doc}] {phrase[:400]}")
contra = [d for d in depots if d.get("decision", {}).get("statut") not in (None, "rien", "annonce")]
dire(f"## Dépôts écartés (phrases qui ne disent pas la même chose, même programme plus vieux, moins de 10 M$) : {len(contra)}")
for d in contra:
    dire(f"- {d['nom']} ({d['symbole']}) · {d['decision']} · {d['acc']}")
dire("## Phrases rejetées qui parlent d'autoriser ou d'augmenter un rachat (à relire à la main)")
raisons = {}
for p in phr:
    if "rejet" in p and AUTORISE.search(p["phrase"]):
        raisons[p["rejet"].split(" :")[0]] = raisons.get(p["rejet"].split(" :")[0], 0) + 1
        dire(f"- {p['nom'][:40]} ({p['symbole']}) [{p['doc']}] {p['rejet']} : {p['phrase'][:500]}")
dire(f"Raisons : {raisons}")
dire(f"Durée : {(time.monotonic() - DEBUT) / 60:.0f} min")
