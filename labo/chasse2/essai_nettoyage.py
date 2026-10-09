"""Essai du nettoyage des prix (labo/chasse2/PLAN.md, correction 2) sur les vrais cas trouvés par la sonde des prix
(labo/chasse2/sonde_prix.json) et deux cas qui doivent rester. Lancement : python labo/chasse2/essai_nettoyage.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as c  # noqa: E402

CAS = {  # nom : (clôtures lues, clôtures attendues après nettoyage)
    "PCYC 26-28 mai 2015 (0,01 $ entre deux vrais prix)": ([256.82, 256.99, 0.01, 261.25, 262.0], [256.82, 256.99, 261.25, 262.0]),
    "AON 1er avril 2020 (0,01 $ au 1er jour du nouveau code)": ([163.15, 0.01, 153.68, 157.26], [163.15, 153.68, 157.26]),
    "AVGO janvier 2016 (1,00 $ au 1er jour du nouveau code)": ([122.35, 133.71, 1.0, 133.24, 134.0], [122.35, 133.71, 133.24, 134.0]),
    "ELLH juin 2018 (0,01 $ deux fois au début)": ([0.01, 0.01, 80.0, 79.5, 85.0], [80.0, 79.5, 85.0]),
    "deux prix bidons de 1 $ de suite": ([50.0, 1.0, 1.0, 51.0], [50.0, 51.0]),
    "vrai fractionnement 4 pour 1 : gardé": ([400.0, 404.0, 101.0, 102.0, 103.0, 101.5], [400.0, 404.0, 101.0, 102.0, 103.0, 101.5]),
    "vraie chute de 70 % : gardée": ([30.0, 9.0, 8.5, 8.0, 7.0], [30.0, 9.0, 8.5, 8.0, 7.0]),
}
ok = []
for nom, (lu, attendu) in CAS.items():
    g = c.nettoyer(np.array(lu), {"prix de 0,01 $": 0, "écarts qui reviennent": 0})
    garde = [x for x, k in zip(lu, g) if k]
    ok.append(garde == attendu)
    print(f"{'OK ' if garde == attendu else 'NON'} {nom} : {garde}")
print(f"{sum(ok)}/{len(ok)} réussis")
sys.exit(0 if all(ok) else 1)
