"""Essai du juge sur le FAUX jeu de recherche : 2 programmations pareilles ou non, une règle qui plante, les critères
recalculés à la main à partir des fichiers du juge."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
TMP = ICI / "tmp_juger"
ok = []


def verifier(nom, condition, detail=""):
    ok.append(bool(condition))
    print(f"{'OK    ' if condition else 'ÉCHEC '} {nom} {detail}")


shutil.rmtree(TMP, ignore_errors=True)
(TMP / "regles").mkdir(parents=True)
(TMP / "verif").mkdir()
subprocess.run([sys.executable, str(ICI / "faux_jeu.py"), str(TMP / "donnees")], check=True, capture_output=True)
REGLE = '''ID = "{id}"
DUREE = 63
MAX_POSITIONS = 5
def garder(e, ctx):
    return e["sens"] == "achat" and (e["valeur_m"] or 0) >= {seuil}
'''
(TMP / "regles" / "a.py").write_text(REGLE.format(id="a", seuil=300))
(TMP / "verif" / "a.py").write_text(REGLE.format(id="a", seuil=300).replace("(e[\"valeur_m\"] or 0) >= 300",
                                                                           "not (e[\"valeur_m\"] is None or e[\"valeur_m\"] < 300)"))
(TMP / "regles" / "b.py").write_text(REGLE.format(id="b", seuil=300))
(TMP / "verif" / "b.py").write_text(REGLE.format(id="b", seuil=500))
(TMP / "regles" / "c.py").write_text('ID = "c"\ndef garder(e, ctx):\n    return 1 / 0\n')
(TMP / "regles" / "d.py").write_text(REGLE.format(id="d", seuil=300))
(TMP / "regles" / "e.py").write_text('ID = "e"\nIMPOSSIBLE = "décide avec des échecs pas encore publiés"\n'
                                     'def garder(e, ctx):\n    return False\n')
(TMP / "regles" / "f.py").write_text(REGLE.format(id="f", seuil=300) + "TEMOIN = True\n")
(TMP / "verif" / "f.py").write_text(REGLE.format(id="f", seuil=300) + "TEMOIN = True\n")
r = subprocess.run([sys.executable, str(ICI.parent / "juger.py"), "--donnees", str(TMP / "donnees"), "--sortie",
                    str(TMP / "res"), "--regles", str(TMP / "regles"), "--verif", str(TMP / "verif")],
                   capture_output=True, text=True)
verifier("Le juge finit même si une règle plante", r.returncode == 0, r.stderr[-300:])
tous = json.loads((TMP / "res" / "tous.json").read_text())
verifier("2 programmations pareilles (écrites autrement) → identiques", tous["a"]["deux_programmations"] == "identiques")
verifier("2 programmations différentes → différentes, avec les écarts, et la règle ne passe pas",
         tous["b"]["deux_programmations"] == "différentes" and tous["b"]["ecarts"]["seulement_testeur"] and not tous["b"]["passe"])
verifier("Règle qui plante → ERREUR notée, ne passe pas", "ZeroDivisionError" in tous["c"].get("erreur", "") and not tous["c"]["passe"])
verifier("Sans vérificateur → ne peut pas passer", tous["d"]["deux_programmations"] == "vérificateur absent" and not tous["d"]["passe"])
x = tous["a"]
pa = x["par_annee"]
verifier("Les 3 années de la découverte, et seulement elles", list(pa) == ["2023-2024", "2024-2025", "2025-2026"], str(list(pa)))
c1 = all(v["portefeuille"] > v["spy_garde"] for v in pa.values())
c3 = sum(v["achats"] for v in pa.values()) >= 30 and all(v["achats"] >= 5 for v in pa.values())
verifier("Critères 1 et 3 recalculés à la main = ceux du juge", (c1, c3) == (x["criteres"]["1_bat_spy_chaque_annee"],
                                                                         x["criteres"]["3_achats"]), str(x["criteres"]))
verifier("t calculé sur les mois de la période seulement (36 écarts mensuels, juillet 2023 à juin 2026)", x["mois"] == 36, str(x["mois"]))
verifier("Années gagnées = nombre d'années où le portefeuille bat le S&P 500",
         x["periode_entiere"]["annees_gagnees"] == sum(v["portefeuille"] > v["spy_garde"] for v in pa.values()))
verifier("Signaux : achetés + perdus + écartés ≤ signaux", sum(v for k, v in x["signaux"].items() if k != "signaux") <= x["signaux"]["signaux"],
         str(x["signaux"]))
trans = json.loads((TMP / "res" / "a.transactions.json").read_text())
verifier("Aucun achat d'un dépôt du contexte (avant le 1er juillet 2023)", all(t["achat"] >= "2023-07-01" for t in trans))
resume = (TMP / "res" / "resume.md").read_text()
verifier("Résumé : une ligne par règle", all(f"| {k} |" in resume for k in "abcdef"))
verifier("Règle écartée (IMPOSSIBLE) : notée avec sa raison, pas simulée, ne passe pas",
         tous["e"].get("ecartee", "").startswith("décide") and not tous["e"]["passe"] and "stats" not in tous["e"])
verifier("Témoin : simulé et comparé, mais ne peut jamais passer", tous["f"]["temoin"] and not tous["f"]["passe"]
         and tous["f"]["deux_programmations"] == "identiques")
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} vérifications réussies")
sys.exit(0 if all(ok) else 1)
