"""Essai réel du lecteur 13F sur une VRAIE journée de dépôts (vendredi 14 août 2026, date limite du 2e trimestre),
puis vérification indépendante de chaque info (expressions régulières sur les tables officielles).

Le robot est lancé comme s'il était le lundi 17 août : il lit l'index officiel du 14 août en direct à la SEC.
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "robot"))
sys.path.insert(0, str(RACINE / "labo"))

from radar.collecteurs import fonds13f  # noqa: E402
from radar.http import ClientPoli  # noqa: E402
from radar.run import executer  # noqa: E402

import essai  # noqa: E402

SORTIE = RACINE / "labo" / "essai13f"
DONNEES = Path("/tmp/essai13f")


def main():
    shutil.rmtree(DONNEES, ignore_errors=True)
    DONNEES.mkdir(parents=True)
    SORTIE.mkdir(parents=True, exist_ok=True)
    client = ClientPoli("math-veronneau1@hotmail.com")
    rapport = executer(DONNEES, client=client, maintenant=datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
                       collecteurs={"sec_13f": fonds13f.collecter})
    evs = [json.loads(l) for f in sorted((DONNEES / "evenements").glob("*.jsonl"))
           for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    evs += [json.loads(l) for f in sorted((DONNEES / "a_verifier").glob("*.jsonl"))
            for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    (SORTIE / "infos.json").write_text(json.dumps(evs, ensure_ascii=False, indent=1), encoding="utf-8")
    lignes = ["# Essai réel 13F (journée du 14 août 2026) et vérification indépendante", "",
              f"Rapport du robot : {json.dumps(rapport.get('sec_13f'), ensure_ascii=False)}",
              f"Infos produites : {len(evs)} · fonds : {sorted({e['data']['fonds'] for e in evs})}", ""]
    bons = 0
    for e in evs:
        try:
            ecarts = essai.verifier_13f(e)
        except Exception as x:  # noqa: BLE001
            ecarts = [f"vérification impossible : {type(x).__name__}: {x}"]
        bons += not ecarts
        lignes.append(f"- **{'OK' if not ecarts else 'ÉCART'}** [{e['badge']}] {e['title']} · {e['tickers']}"
                      + ("" if not ecarts else " — " + " ; ".join(ecarts)))
    lignes.insert(4, f"Vérifiées : {len(evs)} — identiques : {bons}")
    (SORTIE / "rapport.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))


if __name__ == "__main__":
    main()
