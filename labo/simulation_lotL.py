"""Lot L, avant la mise en ligne : simulation avec le code de la branche « travail » (dossier code/) sur une COPIE des
vraies données du robot (branche main, dossier principal/). Rien n'est publié : on lit les vraies sources (SEC, Kenneth
French) comme le robot le fera, puis on calcule les listes AVANT (sans les 2 règles) et APRÈS (avec), sur les mêmes infos.

Sortie : labo/simulation-lotL/resume.md (et listes.json).
"""
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path("code/robot").resolve()))
from radar import emetteurs, publish, score  # noqa: E402
from radar.collecteurs import inities, sec, taille  # noqa: E402
from radar.http import ClientPoli  # noqa: E402
from radar.run import CONFIG, Contexte, _charger_json  # noqa: E402
from radar.store import Depot  # noqa: E402

SORTIE = Path("labo/simulation-lotL")
SORTIE.mkdir(parents=True, exist_ok=True)
lignes = []


def dire(t=""):
    print(t, flush=True)
    lignes.append(t)
    (SORTIE / "resume.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")


donnees = Path(tempfile.mkdtemp()) / "data"
shutil.copytree("principal/data", donnees)
maintenant = datetime.now(timezone.utc).replace(microsecond=0)
ctx = Contexte(client=ClientPoli(_charger_json(CONFIG).get("contact", "")), maintenant=maintenant, donnees=donnees)
dire(f"# Simulation du lot L ({maintenant.isoformat()})\n")
dire("Code : branche travail. Données : copie de la branche main. Rien n'est publié.\n")

dire("## 1. Les 2 nouvelles sources, lues pour vrai")
inities.collecter(ctx)
r = inities.charger(donnees)
for annee, c in r["annees"].items():
    dire(f"- initiés : classement pour {annee} avec {c['depuis']} · {c['transactions']:,} transactions en bourse lues · "
         f"par CIK {c['compte']['cik']} · par nom {c['compte']['noms']}")
    dire(f"- fichiers : {len(c['fichiers'])} ({c['fichiers'][0].rsplit('/', 1)[-1]} … {c['fichiers'][-1].rsplit('/', 1)[-1]})")
taille.collecter(ctx)
t = taille.charger(donnees)
dire(f"- seuils du NYSE : mois {t['seuils']['mois']} · {t['seuils']['compagnies_nyse']} compagnies · 30e centile "
     f"{t['seuils']['p30']:,} M$ · 70e {t['seuils']['p70']:,} M$")
dire(f"- actions en circulation : {len(t['actions']):,} compagnies · frames {t['frames']}")
dire(f"- prix de la SEC : {len(t['prix']):,} symboles · fichiers {t['fichiers_prix']}")
sec.symboles(ctx)
tous = Depot(donnees).lire("evenements")
bilan = emetteurs.rafraichir(ctx, emetteurs.symboles_recents(tous, maintenant.date()))
fiches = emetteurs.charger(donnees)
dire(f"- fiches SEC relues (rapports déposés) : {bilan} · fiches avec rapports : "
     f"{sum('rapports' in f for f in fiches.values())}/{len(fiches)}")

dire("\n## 2. Les listes avant et après, sur les mêmes infos")
pour_score = sorted((e for e in tous if not e.get("data", {}).get("meme_acte_que")), key=publish._plus_recent, reverse=True)
elus = json.loads((donnees / "app" / "elus.json").read_text(encoding="utf-8"))
chefs = {nom for nom, info in elus["par_elu"].items() if info["chef"]}
precedent = json.loads((donnees / "app" / "aujourdhui.json").read_text(encoding="utf-8"))
fonds = emetteurs.fonds(donnees)
jour = score.jour_de_calcul(maintenant)
tailles = taille.pour_score(donnees, fiches, jour)
avant = score.calculer(pour_score, maintenant, precedent, None, fonds=fonds, chefs=chefs)
apres = score.calculer(pour_score, maintenant, precedent, None, fonds=fonds, chefs=chefs, routiniers=r, tailles=tailles)


def court(x):
    if not x:
        return "—"
    if x.get("taille"):
        return f"{x['taille']} ({x['valeur_m']:,.0f} M$)"
    return f"inconnue ({x.get('raison')})"


for sens in ("hausse", "baisse"):
    a = {x["symbole"]: x for x in avant[sens]}
    b = {x["symbole"]: x for x in apres[sens]}
    dire(f"\n### {sens.capitalize()} : {len(a)} avant → {len(b)} après")
    dire("| Symbole | Avant | Après | Taille | Changement |")
    dire("|---|---|---|---|---|")
    for s in sorted(set(a) | set(b), key=lambda s: -(b.get(s) or a.get(s))["note10"]):
        x, y = a.get(s), b.get(s)
        quoi = "sort" if x and not y else "entre" if y and not x else ("monte" if y["note10"] > x["note10"] else
                                                                        "baisse" if y["note10"] < x["note10"] else "=")
        dire(f"| {s} | {x['note10'] if x else '—'} | {y['note10'] if y else '—'} | {court(tailles.get(s))} | {quoi} |")

dire("\n## 3. Les infos devenues « routinières » (0 point)")
n = 0
for ev in pour_score:
    if ev["source"] != "sec_form4" or ev.get("badge") not in ("officiel", "confirme"):
        continue
    if (jour - datetime.fromisoformat(ev["published_on"]).date()).days > score.AGE_MAX:
        continue
    m = inities.routinier(r, ev)
    if m:
        n += 1
        dire(f"- {ev['tickers'][0]} · {ev['kind']} · {', '.join(ev['entities'][:-1])} · transaction du {ev['occurred_on']} · "
             f"mois : {inities.en_mots(m)} · {ev['official_url']}")
dire(f"- total : {n} info(s) de formulaire 4 sur {sum(e['source'] == 'sec_form4' for e in pour_score)}")

dire("\n## 4. Tailles des compagnies avec un achat de dirigeant (90 jours)")
achats = sorted({ev["tickers"][0] for ev in pour_score if ev["source"] == "sec_form4" and ev["kind"] == "achat_initie"
                 and ev.get("tickers")})
compte = Counter((tailles.get(s) or {}).get("taille") or ("sans fiche" if s not in tailles else "inconnue")
                 for s in achats)
dire(f"- {len(achats)} compagnies : {dict(compte)}")
raisons = Counter((tailles.get(s) or {}).get("raison") for s in achats if s in tailles and not tailles[s].get("taille"))
dire(f"- raisons des tailles inconnues : {dict(raisons)}")
for s in achats:
    if (tailles.get(s) or {}).get("taille") == "petite":
        x = tailles[s]
        dire(f"- petite : {s} · {x['actions'][0]:,} actions au {x['actions'][1]} × {x['prix'][1]} $ ({x['prix'][0]}) = "
             f"{x['valeur_m']:,} M$")

(SORTIE / "listes.json").write_text(json.dumps({
    "avant": {s: [(x["symbole"], x["note10"]) for x in avant[s]] for s in ("hausse", "baisse")},
    "apres": {s: [(x["symbole"], x["note10"], (x.get("taille") or {}).get("taille")) for x in apres[s]]
              for s in ("hausse", "baisse")}}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
dire("\nVERDICT : simulation faite")
