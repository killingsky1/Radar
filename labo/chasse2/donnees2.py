"""Chasse 2, étape 0 : la base des chasses B (tout le marché) et C (météo des initiés), de juillet 2009 à septembre 2026.

Même méthode que le jeu du tournoi (labo/tournoi/donnees.py, ses fonctions sont réutilisées telles quelles), mais pour
TOUTES les compagnies, pas seulement celles où un dirigeant achète :
- prix : clôtures des fichiers d'échecs de livraison de la SEC, tous les symboles, de 200907a (le plus ancien offert,
  mesuré par la reconnaissance) à aujourd'hui ; calendrier du tournoi + fermetures de l'ouragan Sandy (29 et 30
  octobre 2012, absentes du tournoi qui commençait en 2015) ;
- initiés : chaque formulaire 4 original avec achat (P) ou vente (S) en bourse, 2006q1 à 2026q2 (cache du tournoi,
  aucune nouvelle requête) ;
- finances et actions en circulation : companyfacts.zip (cache du tournoi), PREMIÈRE version déposée, toutes les
  compagnies ;
- 13D et 13G : index trimestriels d'EDGAR, 2009q1 à 2026q2 (cache du tournoi dès 2015q2, le reste lu ici) ;
- compagnies : submissions.zip (cache de la reconnaissance) : nom, code d'industrie (SIC), symboles actuels, et la
  liste des 10-K (pour la chasse A).
Rien n'est calculé sur les rendements ici : seulement des nombres de lignes (labo/chasse2/donnees/resume.json).
Lecture polie : le client du robot (5 requêtes par seconde au plus à la SEC) ; robots.txt vérifié par la
reconnaissance (tout permis, aucun délai demandé) ; 401 ou 403 = arrêt.
"""
import gzip
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "tournoi"))
import donnees as t  # noqa: E402  les fonctions du tournoi, telles quelles

CACHE_T = Path(os.environ.get("TOURNOI_CACHE", "cache"))  # cache du tournoi : lu seulement
CACHE2 = Path(os.environ.get("CHASSE2_CACHE", "cache2"))
BASE = CACHE2 / "base"
SORTIE = Path(os.environ.get("CHASSE2_SORTIE", "labo/chasse2/donnees"))
PRIX_DEBUT = "200907a"
INITIES = ("2006q1", "2026q2")
TREIZE = ("2009q1", "2026q2")
SANDY = {"2012-10-29", "2012-10-30"}  # Bourse de New York fermée (ouragan Sandy)
compte = Counter()


def dire(x):
    t.dire(x)


def lire_cache(nom):
    """Un fichier du cache du tournoi, sinon de celui de la chasse 2 (None s'il n'est dans aucun)."""
    for c in (CACHE_T, CACHE2):
        if (c / nom).exists():
            return (c / nom).read_bytes()
    return None


def telecharger(url, nom):
    """Lu une fois et gardé dans le cache de la chasse 2 (le cache du tournoi n'est jamais modifié)."""
    b = lire_cache(nom)
    if b is not None:
        return b
    t.CACHE = CACHE2  # brut() écrit dans son CACHE : celui de la chasse 2
    b = t.brut(url, nom)
    compte["requêtes"] += 1
    return b


def ecrire(nom, lignes):
    BASE.mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(BASE / nom, "wt", encoding="utf-8") as f:
        for x in lignes:
            f.write(json.dumps(x, separators=(",", ":"), ensure_ascii=False) + "\n")
            n += 1
    return n


# ---------- Prix ----------

def prix():
    t.FERMETURES_SPECIALES = set(t.FERMETURES_SPECIALES) | SANDY
    page = telecharger(t.prix_sec.PAGE, "pages/ftd.html").decode("utf-8", "replace")
    liens = t.fichiers_ftd(page)
    cles = sorted(c for c in liens if c >= PRIX_DEBUT)
    reglements = set()
    for c in cles:  # 1er passage : les dates de règlement de tous les fichiers (calendrier des clôtures)
        lignes = t.lignes_ftd(telecharger(liens[c], f"ftd/{c}.zip"), c)
        reglements.update(l[:8] for l in lignes if len(l) > 8 and l[8] == "|" and l[:8].isdigit())
    cloture_de = t.calendrier_clotures(reglements)
    sandy = [r for r in sorted(reglements) if "20121026" < r < "20121102"]
    dire(f"règlements autour de Sandy : {sandy} → clôtures {[cloture_de.get(r) for r in sandy]}")
    p = t.Prix()
    for c in cles:  # 2e passage : tous les symboles
        compte["lignes de prix"] += p.ajouter_fichier(t.lignes_ftd(telecharger(liens[c], f"ftd/{c}.zip"), c), None,
                                                      cloture_de)
    p.trier()
    calendrier = sorted(set(cloture_de.values()))
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "calendrier.json").write_text(json.dumps(calendrier))
    n = ecrire("prix.jsonl.gz", p.lignes(list(p.d), "2009-01-01"))
    for m in ("SPY", "IWM"):
        if m not in p.d:
            raise SystemExit(f"pas de prix pour {m}")
    dire(f"fichiers d'échecs : {len(cles)} ({cles[0]} … {cles[-1]}) · symboles : {n:,} · lignes : "
         f"{compte['lignes de prix']:,} · clôtures du {calendrier[0]} au {calendrier[-1]} · SPY : {len(p.d['SPY']):,} jours")
    return {"fichiers": len(cles), "premier": cles[0], "dernier": cles[-1], "symboles": n,
            "lignes": compte["lignes de prix"], "clotures": [calendrier[0], calendrier[-1]], "jours": len(calendrier),
            "spy_jours": len(p.d["SPY"]), "sandy": {r: cloture_de.get(r) for r in sandy}}


# ---------- Initiés ----------

CEO, CFO = re.compile(r"\b(CEO|CHIEF EXECUTIVE)", re.I), re.compile(r"\b(CFO|CHIEF FINANCIAL)", re.I)


def inities():
    symboles, sens, bornes = defaultdict(Counter), Counter(), []

    def lignes():  # trimestre par trimestre (triés par date dans le trimestre) : jamais tout en mémoire
        for q in t.trimestres(*INITIES):
            b = lire_cache(f"tournoi/ds/{q}.json.gz")
            if b is None:
                raise SystemExit(f"jeu de données des initiés absent du cache du tournoi : {q}")
            sortie = []
            for e in t.faire_evenements(json.loads(gzip.decompress(b))):
                titres = " ".join(i.get("titre") or "" for i in e["inities"])
                roles = {r for i in e["inities"] for r in i["roles"]}
                sortie.append([e["depot"], e["cik"], e["symbole"], e["sens"], e["montant"], e["actions"],
                               len(e["inities"]), int(bool(CEO.search(titres))), int(bool(CFO.search(titres))),
                               int("administrateur" in roles), int("dirigeant" in roles),
                               int("actionnaire de 10 %" in roles), e["part"], e["plan_10b5_1"]])
                if e["symbole"]:
                    symboles[e["cik"]][(e["symbole"], e["depot"][:7])] += 1
            sortie.sort(key=lambda x: (x[0], x[1], x[3]))
            sens.update(x[3] for x in sortie)
            bornes.extend(x[0] for x in sortie[:1] + sortie[-1:])
            yield from sortie
    n = ecrire("inities.jsonl.gz", lignes())
    # Symboles écrits dans les formulaires 4, par compagnie et par mois (pour relier un symbole des prix à sa compagnie)
    carte = [[cik, s, m, k] for cik, c in symboles.items() for (s, m), k in sorted(c.items(), key=lambda x: x[0][1])]
    ecrire("symboles_f4.jsonl.gz", carte)
    dire(f"initiés : {n:,} infos ({dict(sens)}) de {min(bornes)} à {max(bornes)} · compagnies : {len(symboles):,}")
    return {"infos": n, "par_sens": dict(sens), "du": min(bornes), "au": max(bornes), "compagnies": len(symboles),
            "symboles_par_mois": len(carte)}


# ---------- Finances et actions (toutes les compagnies) ----------

def finances():
    z = zipfile.ZipFile(CACHE_T / "tournoi" / "companyfacts.zip")
    noms = [n for n in z.namelist() if re.fullmatch(r"CIK\d{10}\.json", n)]

    def lignes():
        for i, nom in enumerate(noms):
            try:
                actions, fi = t.extraire_faits(z.read(nom))
            except (ValueError, KeyError, TypeError):
                compte["faits illisibles"] += 1
                continue
            if not actions and not fi:
                compte["sans faits utiles"] += 1
                continue
            compte["compagnies avec faits"] += 1
            yield {"cik": str(int(nom[3:13])), "actions": actions, "finances": fi}
            if i % 3000 == 0:
                dire(f"  faits XBRL : {i:,}/{len(noms):,}")
    n = ecrire("faits.jsonl.gz", lignes())
    dire(f"faits XBRL : {n:,} compagnies sur {len(noms):,} · illisibles : {compte['faits illisibles']} · "
         f"sans faits utiles : {compte['sans faits utiles']}")
    return {"compagnies": n, "fichiers": len(noms), "illisibles": compte["faits illisibles"]}


# ---------- 13D et 13G ----------

def treize():
    toutes = []
    for q in t.trimestres(*TREIZE):
        b = lire_cache(f"tournoi/13/{q}.json.gz") or lire_cache(f"13/{q}.json.gz")
        if b is not None:
            x = json.loads(gzip.decompress(b))
        else:
            an, tr = q[:4], q[5]
            t.CACHE = CACHE2
            texte = t.brut(f"{t.sec.ARCHIVES}/edgar/full-index/{an}/QTR{tr}/master.idx")  # gros : pas gardé brut
            compte["requêtes"] += 1
            x = t.lire_13(texte.decode("latin-1"), None)
            (CACHE2 / "13").mkdir(parents=True, exist_ok=True)
            (CACHE2 / "13" / f"{q}.json.gz").write_bytes(gzip.compress(json.dumps(x, separators=(",", ":")).encode()))
        toutes += x
        compte[f"13 {q[:4]}"] += len(x)
    toutes.sort()
    n = ecrire("treize.jsonl.gz", toutes)
    formes = Counter(x[1] for x in toutes)
    dire(f"13D et 13G : {n:,} dépôts ({dict(formes)}) de {toutes[0][0]} à {toutes[-1][0]}")
    return {"depots": n, "formes": dict(formes), "du": toutes[0][0], "au": toutes[-1][0],
            "par_annee": {a: compte[f"13 {a}"] for a in sorted({q[:4] for q in t.trimestres(*TREIZE)})}}


# ---------- Compagnies (submissions.zip) ----------

def compagnies():
    chemin = CACHE2 / "submissions.zip"
    if not chemin.exists():
        raise SystemExit("submissions.zip absent du cache de la chasse 2 (reconnaissance)")
    infos, dix_k = {}, defaultdict(list)
    with zipfile.ZipFile(chemin) as z:
        for nom in z.namelist():
            m = re.fullmatch(r"CIK(\d{10})(?:-submissions-\d+)?\.json", nom)
            if not m:
                continue
            try:
                d = json.loads(z.read(nom))
            except ValueError:
                compte["submissions illisibles"] += 1
                continue
            cik = str(int(m.group(1)))
            if "filings" in d:
                infos[cik] = {"nom": d.get("name"), "sic": d.get("sic"), "symboles": d.get("tickers") or [],
                              "bourses": d.get("exchanges") or []}
                r = d["filings"].get("recent", {})
            else:
                r = d
            for k, f in enumerate(r.get("form") or []):
                if f == "10-K":
                    dix_k[cik].append([r["filingDate"][k], r["accessionNumber"][k], (r.get("primaryDocument") or [""])[k],
                                       (r.get("reportDate") or [""])[k]])
    lignes = []
    for cik, i in infos.items():
        if cik in dix_k:
            lignes.append({"cik": cik, **i, "dix_k": sorted(dix_k[cik])})
    n = ecrire("cies.jsonl.gz", lignes)
    total = sum(len(v) for v in dix_k.values())
    dire(f"compagnies avec au moins un 10-K : {n:,} · 10-K : {total:,}")
    return {"compagnies_avec_10k": n, "dix_k": total}


def main():
    dire("# Chasse 2, étape 0 : la base des chasses B et C")
    resume = {}
    for nom, faire in (("initiés", inities), ("compagnies", compagnies), ("finances", finances), ("13", treize),
                       ("prix", prix)):
        resume[nom] = faire()
    resume["compte"] = dict(compte)
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (SORTIE / "journal.md").write_text("\n".join(t.journal) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
