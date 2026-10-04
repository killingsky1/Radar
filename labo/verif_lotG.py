"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot G : les résultats de Radar.

Mêmes règles d'accès : robots.txt lu d'abord avec notre identification, au moins 1,5 s entre deux requêtes ; le courriel
seulement pour la SEC. Refait ici, avec un autre code :
- l'historique : chaque compagnie des listes publiées (score actuel) a son entrée, vue aujourd'hui ; aucune en double ;
- les fichiers d'échecs de livraison de la SEC (octobre 2026 et après) retéléchargés : calendrier des dates de
  règlement, prix et CUSIP ;
- pour chaque entrée : départ (2e date de règlement après le jour de la suggestion, puis 2 de plus au plus), arrivée à
  7 et 30 jours (+3 jours), marché (SPY, IVV, VOO aux mêmes dates, à 0,3 point près), CUSIP, sauts anormaux, « en
  attente » et sa date (1re moitié du mois : fin du mois ; 2e moitié : le 15 du mois suivant) ;
- le résumé (taux de réussite) refait à partir des lignes.
"""
import io
import json
import re
import sys
import time
import urllib.request
import urllib.robotparser
import zipfile
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lotG.txt")
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
PAGE = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
ecarts, sortie, dernier = [], [], [0.0]
rp = urllib.robotparser.RobotFileParser()


def dire(t):
    print(t, flush=True)
    sortie.append(t)


def lire(url):
    if not rp.can_fetch(UA_SEC, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = 1.5 - (time.monotonic() - dernier[0])
    if attente > 0:
        time.sleep(attente)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA_SEC}), timeout=180) as r:
        c = r.read()
    dernier[0] = time.monotonic()
    return c


with urllib.request.urlopen(urllib.request.Request("https://www.sec.gov/robots.txt", headers={"User-Agent": UA_SEC}),
                            timeout=60) as r:
    rp.parse(r.read().decode("utf-8", "replace").splitlines())

h = json.loads((racine / "resultats" / "suggestions.json").read_text(encoding="utf-8"))["entrees"]
pub = json.loads((racine / "app" / "resultats.json").read_text(encoding="utf-8"))
auj = json.loads((racine / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
jour_calcul = datetime.fromisoformat(auj["genere_a"]).astimezone(ZoneInfo("America/Toronto")).date().isoformat()

# ---------- Historique ----------
for sens in ("hausse", "baisse"):
    for x in auj[sens]:
        siennes = [e for e in h if e["symbole"] == x["symbole"] and e["sens"] == sens]
        if not siennes:
            ecarts.append(f"{x['symbole']} ({sens}) est dans la liste publiée mais pas dans l'historique")
        elif max(e["vue"] for e in siennes) != jour_calcul:
            ecarts.append(f"{x['symbole']} ({sens}) : vue {max(e['vue'] for e in siennes)} ≠ jour du calcul {jour_calcul}")
cles = [(e["symbole"], e["sens"], e["entree"]) for e in h]
if len(cles) != len(set(cles)):
    ecarts.append("entrée en double dans l'historique")
dire(f"Historique : {len(h)} entrées ; listes publiées le {jour_calcul} : {len(auj['hausse'])} à la hausse, "
     f"{len(auj['baisse'])} à la baisse, toutes suivies : {'OUI' if not ecarts else 'NON'}")

# ---------- Fichiers de la SEC (octobre 2026 et après) ----------
page = lire(PAGE).decode("utf-8", "replace")
liens = {m.group(2) + m.group(3).lower(): m.group(1) if m.group(1).startswith("http") else "https://www.sec.gov" + m.group(1)
         for m in re.finditer(r"""href=["']([^"']*cnsfails(\d{6})([ab])\.zip)["']""", page, re.I)}
suivis = {e["symbole"] for e in h} | {"SPY", "IVV", "VOO"}
calendrier, prix, fin_couverte = set(), {}, None
for cle in sorted(c for c in liens if c >= "202610a"):
    with zipfile.ZipFile(io.BytesIO(lire(liens[cle]))) as z:
        lignes = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    if lignes[0].strip() != "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE":
        ecarts.append(f"{cle} : en-tête inattendu")
    for l in lignes[1:]:
        p = l.split("|")
        if len(p) == 6 and re.fullmatch(r"\d{8}", p[0]):
            calendrier.add(p[0])
            if p[2] in suivis and re.fullmatch(r"\d+(\.\d+)?", p[5]):
                prix.setdefault(p[2], {})[p[0]] = (float(p[5]), p[1])
    a, m = int(cle[:4]), int(cle[4:6])
    fin = f"{cle[:6]}14" if cle[6] == "a" else f"{cle[:6]}{monthrange(a, m)[1]}"
    fin_couverte = max(fin_couverte or fin, fin)
    dire(f"- {cle} relu à la SEC : {len(lignes)} lignes")
cal = sorted(calendrier)
dire(f"Fichiers de la SEC depuis octobre 2026 : {len([c for c in liens if c >= '202610a'])} · couverts jusqu'au "
     f"{fin_couverte or '(aucun encore)'}")


def plus(j, n):
    return (date(int(j[:4]), int(j[4:6]), int(j[6:])) + timedelta(days=n)).strftime("%Y%m%d")


def publication(j):
    a, m, d = int(j[:4]), int(j[4:6]), int(j[6:])
    return (date(a, m, monthrange(a, m)[1]) if d <= 14 else date(a + (m == 12), m % 12 + 1, 15)).isoformat()


def attendu(e):
    jour = datetime.fromisoformat(e["entree"]).astimezone(ZoneInfo("America/Toronto")).strftime("%Y%m%d")
    apres = [j for j in cal if j > jour][1:4]
    ps = prix.get(e["symbole"], {})
    dep = next((j for j in apres if j in ps), None)
    if dep is None:
        if len(apres) < 3:
            return {"depart": {"statut": "en_attente", "attendu_vers": publication(plus(max(jour, fin_couverte or jour), 1))}}
        return {"depart": {"statut": "pas_de_prix"}}
    out = {"depart": {"statut": "ok", "date": dep, "prix": ps[dep][0], "cusip": ps[dep][1]}, "horizons": {}}
    for n in (7, 30):
        cible, limite = plus(dep, n), plus(dep, n + 3)
        arr = next((j for j in cal if cible <= j <= limite and j in ps), None)
        if arr is None:
            out["horizons"][str(n)] = ({"statut": "en_attente", "attendu_vers": publication(max(cible, plus(fin_couverte, 1)) if fin_couverte else cible)}
                                       if (fin_couverte or "") < limite else {"statut": "pas_de_prix"})
            continue
        var = round(ps[arr][0] / ps[dep][0] - 1, 4)
        if ps[arr][1] != ps[dep][1]:
            out["horizons"][str(n)] = {"statut": "pas_comparable", "variation": var}
            continue
        suite = [ps[j][0] for j in cal if dep <= j <= arr and j in ps]
        if any(max(a / b, b / a) > 1.8 for a, b in zip(suite, suite[1:])) or not -0.5 <= var <= 1.0:
            out["horizons"][str(n)] = {"statut": "a_verifier", "variation": var}
            continue
        f = {x: round(prix[x][arr][0] / prix[x][dep][0] - 1, 4) for x in ("SPY", "IVV", "VOO")
             if dep in prix.get(x, {}) and arr in prix.get(x, {})}
        if not f or max(f.values()) - min(f.values()) > 0.003:
            out["horizons"][str(n)] = {"statut": "mesure", "variation": var, "battu": None}
            continue
        fonds = next(x for x in ("SPY", "IVV", "VOO") if x in f)
        battu = var > f[fonds] if e["sens"] == "hausse" else var < f[fonds]
        out["horizons"][str(n)] = {"statut": "mesure", "variation": var, "fonds": fonds, "marche": f[fonds], "battu": battu}
    return out


# ---------- Chaque ligne publiée contre le calcul d'ici ----------
publiees = {(l["symbole"], l["sens"], l["entree"]): l for l in pub["lignes"]}
if set(publiees) != set(cles):
    ecarts.append("les lignes publiées ≠ l'historique")
ok = 0
for e in h:
    a, l = attendu(e), publiees.get((e["symbole"], e["sens"], e["entree"]))
    if l is None:
        continue
    pb = []
    if {k: a["depart"][k] for k in a["depart"]} != {k: l["depart"].get(k) for k in a["depart"]}:
        pb.append(f"départ {l['depart']} ≠ {a['depart']}")
    for n in ("7", "30"):
        attendu_h = a.get("horizons", {}).get(n, a["depart"] if a["depart"]["statut"] != "ok" else None)
        vrai = l["horizons"][n]
        if attendu_h is None or vrai["statut"] != attendu_h["statut"]:
            pb.append(f"{n} jours : {vrai['statut']} ≠ {attendu_h and attendu_h['statut']}")
            continue
        for k in ("variation", "battu", "attendu_vers"):
            if k in attendu_h and attendu_h[k] != vrai.get(k):
                pb.append(f"{n} jours, {k} : {vrai.get(k)} ≠ {attendu_h[k]}")
        if "fonds" in attendu_h and (vrai.get("marche") or {}).get("fonds") != attendu_h["fonds"]:
            pb.append(f"{n} jours, fonds {(vrai.get('marche') or {}).get('fonds')} ≠ {attendu_h['fonds']}")
    if pb:
        ecarts.append(f"{e['symbole']} ({e['sens']}) : " + " ; ".join(pb))
    else:
        ok += 1
dire(f"Lignes refaites ici : {ok}/{len(h)} identiques (départ, 1 semaine, 1 mois, marché, verdict, date d'attente)")

# ---------- Résumé ----------
for n in ("7", "30"):
    for sens in ("hausse", "baisse"):
        ms = [l["horizons"][n] for l in pub["lignes"] if l["sens"] == sens and l["horizons"][n]["statut"] == "mesure"
              and l["horizons"][n].get("battu") is not None]
        r = pub["resume"][f"{sens}_{n}"]
        if (r["mesurees"], r["battu"]) != (len(ms), sum(m["battu"] for m in ms)):
            ecarts.append(f"résumé {sens} {n} jours : {r} ≠ {len(ms)} mesurées, {sum(m['battu'] for m in ms)} battues")
        dire(f"  {n} jours, {sens} : {r['mesurees']} mesurées, {r['battu']} ont frappé juste, {r['en_attente']} en attente")
dire(f"Prochains prix de la SEC vers : {pub.get('prochains_prix_vers')}")
dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chaque résultat refait à partir des fichiers officiels de la SEC.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(sortie) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
