"""2e lecture INDÉPENDANTE (n'importe rien du robot) des transactions du cabinet publiées (rapports 278-T de l'OGE).

Chaque rapport du cabinet publié avec ses lignes est retéléchargé (lien direct, sans formulaire 201 ; robots.txt vérifié)
et relu avec un AUTRE outil : pdftotext -layout (poppler), puis des expressions régulières ligne par ligne.
Comparé ligne par ligne au robot : numéro, description, type, date, avis tardif, montant. Chaque info d'une compagnie
doit reprendre des lignes du rapport dont le symbole écrit entre parenthèses est le sien. Les rapports du président
(images numérisées) ne doivent avoir aucune ligne.
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

racine, sortie = Path(sys.argv[1]), Path(sys.argv[2])
UA = "Radar projet personnel"
H = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
DEBUT = re.compile(r"^\s{0,4}(\d{1,3})\s{2,}(.*?)\s{2,}(Purchase|Sale|Exchange)\s{2,}(\d{2}/\d{2}/\d{4})\s{2,}(Yes|No)\s{2,}(.+?)\s*$")
MONTANT_SUITE = re.compile(r"^\s{20,}(\$[\d,]+)\s*$")
robots, lignes_sortie, ecarts = {}, [], []


def dire(t):
    print(t)
    lignes_sortie.append(t)


def telecharger(url):
    hote = urlparse(url).hostname
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        r = requests.get(f"https://{hote}/robots.txt", headers=H, timeout=(20, 40))
        if r.status_code in (401, 403) or r.status_code >= 500:
            rp.disallow_all = True
        elif r.status_code >= 400:
            rp.allow_all = True
        else:
            rp.parse(r.text.splitlines())
        robots[hote] = rp
    if not robots[hote].can_fetch(UA, url):
        raise SystemExit(f"robots.txt interdit {url}")
    time.sleep(1.5)
    r = requests.get(url, headers=H, timeout=(20, 120))
    r.raise_for_status()
    return r.content


def lire(pdf):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        texte = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, check=True).stdout
    res, cur, dans = [], None, False
    for l in texte.splitlines():
        if re.match(r"^\s*#\s+DESCRIPTION\s+TYPE\s+DATE\s+NOTIFICATION\s+AMOUNT", l):
            dans = True
            continue
        if not dans:
            continue
        if re.match(r"^\s*(Endnotes|Summary of Contents)\b", l):
            break
        if re.search(r" - Page \d+\s*$", l) or re.match(r"^\s*(RECEIVED OVER|30 DAYS AGO)\s*$", l) or not l.strip():
            continue
        m = DEBUT.match(l)
        if m:
            if cur:
                res.append(cur)
            cur = dict(zip(("n", "description", "type", "date", "avis", "montant"), [g.strip() for g in m.groups()]))
            continue
        if cur:
            s = MONTANT_SUITE.match(l)
            if s and cur["montant"].endswith("-"):
                cur["montant"] += " " + s.group(1)
            else:
                bouts = re.split(r"\s{2,}", l.strip())
                if bouts and re.fullmatch(r"\$[\d,]+", bouts[-1]) and cur["montant"].endswith("-"):
                    cur["montant"] += " " + bouts.pop()
                if bouts:
                    cur["description"] += " " + " ".join(bouts)
    if cur:
        res.append(cur)
    return res


def desc(t):
    return re.sub(r"\s+", "", t.replace("See Endnote", "")).upper()


def iso(us):
    m, j, a = us.split("/")
    return f"{a}-{m}-{j}"


evs = {}
for f in sorted((racine / "evenements").glob("*.jsonl")):
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            e = json.loads(l)
            if e["source"] == "oge_278t":
                evs[e["id"]] = e
rapports = [e for e in evs.values() if e["kind"] == "rapport_278t"]
compagnies = [e for e in evs.values() if e["kind"] != "rapport_278t"]
dire(f"Rapports de l'OGE publiés : {len(rapports)} · infos de compagnies : {len(compagnies)}")
total, identiques = 0, 0
par_url = {}
for e in sorted(rapports, key=lambda e: e["official_url"]):
    nom = e["official_url"].rsplit("/", 1)[1]
    if e["data"].get("titre") == "President":
        if "transactions" in e["data"]:
            ecarts.append(f"{nom} : rapport du président lu (il devait rester en liste)")
        dire(f"{nom} : président, liste seulement (non lu) · OK")
        continue
    if "transactions" not in e["data"]:
        ecarts.append(f"{nom} : rapport du cabinet sans lignes")
        continue
    a = lire(telecharger(e["official_url"]))
    b = e["data"]["transactions"]
    par_url[e["official_url"]] = {t["n"]: t for t in b}
    pareil = 0
    for x, y in zip(a, b):
        if (x["n"], desc(x["description"]), x["type"], iso(x["date"]), x["avis"], " ".join(x["montant"].split())) == \
                (y["n"], desc(y["description"]), y["type"], y["date"], y["avis"], " ".join(y["montant"].split())):
            pareil += 1
        else:
            ecarts.append(f"{nom} ligne {x['n']} : pdftotext {x} ≠ robot {y}")
    if len(a) != len(b):
        ecarts.append(f"{nom} : pdftotext {len(a)} lignes ≠ robot {len(b)}")
    total += len(b)
    identiques += pareil
    dire(f"{nom} : robot {len(b)} lignes · pdftotext {len(a)} · identiques {pareil}")
for e in compagnies:
    lignes = par_url.get(e["official_url"], {})
    for t in e["data"]["transactions"]:
        r = lignes.get(t["n"])
        m = re.search(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*$", re.sub(r"\bSee Endnote\b", " ", r["description"] if r else "").strip())
        if not r or not m or m.group(1).replace(".", "-") != e["tickers"][0]:
            ecarts.append(f"{e['title']} : ligne {t['n']} absente du rapport ou d'un autre symbole")
dire(f"Lignes comparées : {identiques}/{total} identiques · infos de compagnies vérifiées : {len(compagnies)}")
dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : 2e lecture indépendante (pdftotext) = lignes publiées par le robot.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
sortie.write_text("\n".join(lignes_sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
