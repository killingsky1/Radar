"""Chasse A, les données : la similarité de chaque 10-K avec le 10-K précédent de la même compagnie (labo/chasse2/PLAN.md).

Compagnies : celles qui ont été au moins une fois parmi les 1 000 plus grosses (univers de la chasse B), juillet 2009 à
mai 2026. Leurs 10-K déposés de 2008 à juin 2026 (liste : cies.jsonl.gz de la base, tirée de submissions.zip). Pour
chaque 10-K : le document principal sur EDGAR ; texte sans balises (l'en-tête XBRL caché des rapports « inline » retiré),
mots en lettres, minuscules ; similarité cosinus des fréquences de mots avec le 10-K précédent (déposé 300 à 430 jours
avant). Seuls les résultats sont gardés (pas les textes). Une compagnie à la fois, reprise possible (fait.txt) ; arrêt
propre avant l'heure limite (un passage du robot). Lecture polie : le client du robot (5 requêtes par seconde au plus à
la SEC, courriel dans l'en-tête) ; robots.txt vérifié (« Allow: /Archives/edgar/data ») ; 401 ou 403 = arrêt.
Usage : python labo/chasse2/rapports_a.py --base cache2/base --dossier cache2/a --jusqu_a 2026-10-09T21:45
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import chasse_b as b
import commun as c

ROBOT = Path(os.environ.get("TOURNOI_ROBOT", "principal/robot"))
sys.path.insert(0, str(ROBOT.resolve()))
DEBUT_10K, FIN_10K = "2008-01-01", "2026-06-30"
JOURS_MIN, JOURS_MAX = 300, 430
ENTETE_XBRL = re.compile(r"<ix:header>.*?</ix:header>", re.S | re.I)
SCRIPTS = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
BALISES = re.compile(r"<[^>]+>")
MOTS = re.compile(r"[a-z]+")
CLIENT = None


def client():
    global CLIENT
    if CLIENT is None:
        from radar.http import ClientPoli
        from radar.run import CONFIG, _charger_json
        CLIENT = ClientPoli(_charger_json(CONFIG).get("contact", ""), delai=120)
    return CLIENT


def lire(url):
    """Le contenu ; 404 = None ; 401 ou 403 = arrêt immédiat (on ne contourne jamais un refus)."""
    from radar.http import ErreurSource
    try:
        return client().get(url).contenu
    except ErreurSource as exc:
        if re.search(r"HTTP 40[13]\b", str(exc)):
            raise SystemExit(f"INTERDIT par le site, arrêt sans contourner : {exc}")
        if "HTTP 404" in str(exc):
            return None
        return "ERREUR"


def robots_permis():
    """robots.txt de la SEC relu au départ : les documents des 10-K doivent être permis ; illisible = arrêt."""
    from urllib import robotparser
    t = lire("https://www.sec.gov/robots.txt")
    if t == "ERREUR":
        raise SystemExit("robots.txt de la SEC illisible : arrêt, rien n'est lu")
    r = robotparser.RobotFileParser()
    r.parse((t or b"").decode("utf-8", "replace").splitlines())
    if not r.can_fetch("Radar", "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"):
        raise SystemExit("robots.txt de la SEC interdit maintenant les documents d'EDGAR : arrêt")


def mots(contenu):
    texte = contenu.decode("utf-8", "replace")
    texte = ENTETE_XBRL.sub(" ", texte)
    texte = SCRIPTS.sub(" ", texte)
    texte = html.unescape(BALISES.sub(" ", texte))
    return Counter(MOTS.findall(texte.lower()))


def cosinus(a, b_):
    if not a or not b_:
        return None
    if len(a) > len(b_):
        a, b_ = b_, a
    produit = sum(v * b_.get(m, 0) for m, v in a.items())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b_.values()))
    return produit / (na * nb) if na and nb else None


def compagnies_de_l_univers(base):
    """Les CIK qui ont été au moins une fois parmi les 1 000 plus grosses compagnies (même calcul que la chasse B)."""
    px = c.Prix(base)
    carte, cies = b.Carte(base), b.charger_compagnies(base)
    fins = px.fins_de_mois(px.cal[0], px.cal[-1])
    ciks = set()
    for m in fins:
        if m > c.entier(c.FIN):
            continue
        candidats = []
        for s, cik in carte.au(m // 100).items():
            if s not in px.d or cik not in cies:
                continue
            x = px.dernier(s, m, b.TOL_MOIS)
            if not x or x[1] < b.PRIX_MIN:
                continue
            n = cies[cik].nb_actions(m)
            if n:
                candidats.append((x[1] * n, cik))
        candidats.sort(reverse=True)
        ciks.update(cik for _, cik in candidats[:b.UNIVERS])
    return ciks


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True)
    a.add_argument("--dossier", required=True)
    a.add_argument("--jusqu_a", default=None, help="heure limite UTC (AAAA-MM-JJTHH:MM) : arrêt propre avant")
    x = a.parse_args()
    dossier = Path(x.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    limite = datetime.fromisoformat(x.jusqu_a).replace(tzinfo=timezone.utc).timestamp() if x.jusqu_a else None
    liste = dossier / "compagnies.json"
    if liste.exists():
        ciks = json.loads(liste.read_text())
    else:
        ciks = sorted(compagnies_de_l_univers(x.base), key=int)
        liste.write_text(json.dumps(ciks))
    robots_permis()
    faits = set((dossier / "fait.txt").read_text().split()) if (dossier / "fait.txt").exists() else set()
    dix_k = {}
    for cie in c.lire_jsonl(Path(x.base) / "cies.jsonl.gz"):
        if cie["cik"] in ciks:
            dix_k[cie["cik"]] = [k for k in cie["dix_k"] if DEBUT_10K <= k[0] <= FIN_10K]
    total = sum(len(dix_k.get(k, [])) for k in ciks)
    print(f"compagnies : {len(ciks):,} · déjà faites : {len(faits):,} · 10-K à lire en tout : {total:,}", flush=True)
    compte = Counter()
    t0 = time.time()
    with open(dossier / "similarites.jsonl", "a", encoding="utf-8") as sortie, \
            open(dossier / "fait.txt", "a", encoding="utf-8") as fait:
        for n, cik in enumerate(ciks):
            if cik in faits:
                continue
            if limite and time.time() > limite:
                print(f"heure limite : arrêt propre ({n:,}/{len(ciks):,} compagnies)", flush=True)
                break
            precedent, lignes = None, []
            for depot, acc, doc, periode in sorted(dix_k.get(cik, [])):
                if not doc:
                    compte["sans document principal"] += 1
                    continue
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
                contenu = lire(url)
                if contenu is None or contenu == "ERREUR":
                    compte["illisibles" if contenu == "ERREUR" else "introuvables"] += 1
                    continue
                compte["lus"] += 1
                compte["octets"] += len(contenu)
                m = mots(contenu)
                sim = None
                if precedent is not None:
                    ecart = (date.fromisoformat(depot) - date.fromisoformat(precedent[0])).days
                    if JOURS_MIN <= ecart <= JOURS_MAX:
                        sim = cosinus(m, precedent[1])
                lignes.append({"cik": cik, "depot": depot, "acc": acc, "mots": sum(m.values()),
                               "similarite": None if sim is None else round(sim, 6)})
                precedent = (depot, m)
            for l in lignes:
                sortie.write(json.dumps(l) + "\n")
            sortie.flush()
            fait.write(cik + "\n")
            fait.flush()
            if n % 50 == 0:
                vitesse = compte["lus"] / max(time.time() - t0, 1)
                print(f"  {n:,}/{len(ciks):,} compagnies · lus {compte['lus']:,} ({vitesse:.1f}/s, "
                      f"{compte['octets'] / 1e9:.1f} Go) · {dict(compte)}", flush=True)
    resume = {"compagnies": len(ciks), "faites": len(set((dossier / "fait.txt").read_text().split())),
              "dix_k_en_tout": total, "ce_passage": dict(compte)}
    (dossier / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1))
    print(json.dumps(resume, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
