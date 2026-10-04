"""Section « Argent » de l'app : les vrais montants des dépôts officiels des 30 derniers jours (pas de documents ni de
lois). Chaque ligne vient d'une info validée (« Officiel » ou « Confirmé ») ; rien n'est estimé.

- Dirigeants (formulaire 4) : nombre d'actions × prix payé = total, tels qu'écrits dans le dépôt ; part de leurs
  actions seulement quand les lignes du dépôt se suivent dans un même compte (chaque « détenues après » = le précédent
  ± la ligne) ; si les lignes ont des prix très différents (ex. actions ordinaires et certificats américains), pas de
  prix moyen ni de total d'actions, seulement le total en dollars. Ventes planifiées d'avance (plan 10b5-1) marquées.
- Intentions de vente (formulaire 144) : actions et valeur au marché déclarées ; part des actions en circulation.
- Élus du Congrès et cabinet (OGE) : fourchettes officielles (la loi ne demande pas le montant exact).
- Contrats (USAspending, contrats fédéraux canadiens) : sommes engagées.
- Rachats d'actions annoncés (8-K, lot H) : le plafond autorisé par le conseil, pas un achat fait.
La même transaction déclarée par plusieurs entités liées ne compte qu'une fois (lot A). Seulement ce que le robot
garde : achats de dirigeants de 25 000 $ et plus, ventes de 1 M$ et plus, avis 144 de 1 M$ et plus (25 M$ si planifiés).
"""

from __future__ import annotations

from datetime import date, timedelta

from .collecteurs.sec import RELATIONS_144

PERIODE_JOURS = 30
THERMOMETRE_JOURS = 7
ECART_PRIX = 2.0  # prix le plus haut / le plus bas d'un même dépôt : au-delà, ce sont des titres différents

ELUS = {"achat_elu": 1, "vente_elu": -1, "achat_elu_option": 1, "vente_elu_option": -1,
        "achat_cabinet": 1, "vente_cabinet": -1}


def _declarants(ev: dict) -> str:
    noms = (ev.get("entities") or [])[:-1]
    if not noms:
        return ""
    return noms[0] if len(noms) == 1 else f"{noms[0]} et {len(noms) - 1} autre{'s' if len(noms) > 2 else ''}"


def part_de_ses_actions(lignes: list[dict], code: str) -> dict | None:
    """Part des actions du déclarant achetées (ou vendues), seulement si les lignes se suivent dans un même compte."""
    if not lignes or any(t.get("apres") is None or not t.get("actions") for t in lignes):
        return None
    signe = 1 if code == "P" else -1
    for a, b in zip(lignes, lignes[1:]):
        if abs(b["apres"] - (a["apres"] + signe * b["actions"])) > 0.5:
            return None  # comptes ou titres différents : on ne devine pas
    total = sum(t["actions"] for t in lignes)
    avant = lignes[0]["apres"] - signe * lignes[0]["actions"]
    if code == "P" and avant < 0.5:
        return {"nouvelle": True}
    if avant < 0.5:
        return None
    return {"pourcentage": round(total / avant * 100, 2)}


def ligne_form4(ev: dict) -> dict:
    d = ev["data"]
    code = "P" if ev["kind"] == "achat_initie" else "S"
    lignes = d.get("transactions") or []
    prix = [t["prix"] for t in lignes if t.get("prix")]
    multiples = bool(prix) and max(prix) / min(prix) > ECART_PRIX
    return {
        "famille": "dirigeants", "sens": 1 if code == "P" else -1, "qui": _declarants(ev), "role": ", ".join(d.get("roles") or []),
        "actions": None if multiples else d.get("actions"), "prix": None if multiples else d.get("prix_moyen"),
        "prix_multiples": multiples, "nb_lignes": len(lignes), "montant": ev["amount_min"],
        "part": part_de_ses_actions(lignes, code), "plan": bool(d.get("plan_10b5_1")) if code == "S" else False,
        "aussi": d.get("aussi_declare_par") or [],
    }


def ligne_form144(ev: dict) -> dict:
    d = ev["data"]
    lignes = d.get("lignes") or []
    # Chaque ligne répète le total en circulation de SON titre : jamais d'addition ; un seul titre, un seul total, sinon rien
    totaux = {l.get("en_circulation") for l in lignes if l.get("en_circulation")}
    titres = {(l.get("classe") or "").strip().lower() for l in lignes}
    circulation = next(iter(totaux)) if len(totaux) == 1 and len(titres) == 1 else None
    actions = d.get("actions")
    return {
        "famille": "intentions", "sens": -1, "qui": d.get("vendeur") or _declarants(ev),
        "role": ", ".join(RELATIONS_144.get(r.strip().lower(), r) for r in d.get("relations") or []), "actions": actions,
        "prix": round(ev["amount_min"] / actions, 4) if actions else None, "prix_multiples": False,
        "nb_lignes": len(lignes), "montant": ev["amount_min"],
        "part": ({"pourcentage_compagnie": round(actions / circulation * 100, 3)} if actions and circulation else None),
        "plan": bool(d.get("plan_10b5_1")), "aussi": [],
    }


def ligne_elu(ev: dict) -> dict:
    d = ev["data"]
    if ev["source"] == "oge_278t":
        qui = f"{d.get('nom', '')} ({d.get('titre', '')}, {d.get('agence', '')})"
    else:
        qui = f"{d.get('elu', '')} ({'Sénat' if d.get('chambre') == 'senat' else 'Chambre'})"
    return {
        "famille": "elus", "sens": ELUS[ev["kind"]], "qui": qui, "role": "options" if "option" in ev["kind"] else "",
        "actions": None, "prix": None, "prix_multiples": False, "nb_lignes": len(d.get("transactions") or []),
        "montant": None, "montant_min": ev.get("amount_min"), "montant_max": ev.get("amount_max"),
        "part": None, "plan": False, "aussi": [],
    }


def ligne_contrat(ev: dict) -> dict:
    d = ev["data"]
    return {
        "famille": "contrats", "sens": 0, "qui": d.get("fournisseur") or _declarants(ev),
        "role": d.get("agence") or d.get("ministere") or "", "actions": None, "prix": None, "prix_multiples": False,
        "nb_lignes": 1, "montant": ev.get("amount_min"), "part": None, "plan": False, "aussi": [],
    }


def ligne_rachat(ev: dict) -> dict:
    return {
        "famille": "rachats", "sens": 0, "qui": (ev.get("entities") or [""])[0], "role": ev["data"].get("sorte") or "",
        "actions": None, "prix": None, "prix_multiples": False, "nb_lignes": 1, "montant": ev.get("amount_min"),
        "part": None, "plan": False, "aussi": [],
    }


def compagnie(ev: dict) -> str:
    d = ev.get("data") or {}
    if ev["source"] in ("sec_form4", "sec_form144"):
        return (ev.get("entities") or [""])[-1]
    if ev["source"] == "sec_rachats":
        return (ev.get("entities") or [""])[0]
    if ev["source"] in ("chambre_ptr", "senat_ptr", "oge_278t"):
        return d.get("nom_sec") or ""
    return d.get("fournisseur") or ""


def ligne(ev: dict) -> dict | None:
    s, k = ev["source"], ev["kind"]
    if s == "sec_form4" and k in ("achat_initie", "vente_initie") and ev.get("amount_min"):
        corps = ligne_form4(ev)
    elif s == "sec_form144" and ev.get("amount_min"):
        corps = ligne_form144(ev)
    elif s in ("chambre_ptr", "senat_ptr", "oge_278t") and k in ELUS and ev.get("tickers") and ev.get("amount_min"):
        corps = ligne_elu(ev)
    elif s in ("usaspending", "contrats_ca_10k") and ev.get("amount_min"):
        corps = ligne_contrat(ev)
    elif s == "sec_rachats" and k == "rachat_annonce" and ev.get("amount_min"):
        corps = ligne_rachat(ev)
    else:
        return None
    return {"id": ev["id"], "source": s, "symbole": (ev.get("tickers") or [None])[0], "compagnie": compagnie(ev),
            "devise": ev.get("currency") or "USD", "date": ev["occurred_on"], "publie": ev["published_on"], **corps}


def thermometre(lignes: list[dict], jour: date) -> dict:
    """Dirigeants, 7 derniers jours (date de dépôt) : achats contre ventes décidées sur le moment ; les ventes
    planifiées d'avance (10b5-1) sont à part : elles disent peu de choses."""
    depuis = (jour - timedelta(days=THERMOMETRE_JOURS - 1)).isoformat()
    t = {"achats": [0, 0.0], "ventes_libres": [0, 0.0], "ventes_planifiees": [0, 0.0], "intentions": [0, 0.0]}
    for l in lignes:
        if l["publie"] < depuis:
            continue
        if l["famille"] == "dirigeants":
            cle = "achats" if l["sens"] > 0 else ("ventes_planifiees" if l["plan"] else "ventes_libres")
        elif l["famille"] == "intentions":
            cle = "intentions"
        else:
            continue
        t[cle][0] += 1
        t[cle][1] += l["montant"] or 0
    return {"depuis": depuis, **{k: {"nombre": n, "montant": round(m, 2)} for k, (n, m) in t.items()}}


def preparer(fil: list[dict], jour: date) -> tuple[dict, dict]:
    """(argent.json, argent_infos.json) : les lignes triées du plus gros montant au plus petit, et les infos complètes
    (chargées par l'app seulement quand on touche une ligne)."""
    depuis = (jour - timedelta(days=PERIODE_JOURS - 1)).isoformat()
    lignes, infos = [], {}
    for ev in fil:
        if ev["published_on"] < depuis or (ev.get("data") or {}).get("meme_transaction_que"):
            continue
        if ev.get("badge") not in ("officiel", "confirme"):
            continue
        l = ligne(ev)
        if l is None:
            continue
        lignes.append(l)
        infos[ev["id"]] = ev
    lignes.sort(key=lambda l: (-(l["montant"] if l["montant"] is not None else l.get("montant_min") or 0), l["id"]))
    dernier = max((l["publie"] for l in lignes), default=None)
    return ({"jour": jour.isoformat(), "depuis": depuis, "dernier_jour": dernier, "lignes": lignes,
             "thermometre": thermometre(lignes, jour),
             "seuils": "Ce que Radar garde : achats de dirigeants de 25 000 $ et plus, ventes de 1 M$ et plus, avis "
                       "de vente (144) de 1 M$ et plus (25 M$ si planifiés d'avance), rachats d'actions annoncés de 10 M$ et "
                       "plus (un plafond autorisé, pas un achat fait). Élus et cabinet : fourchettes officielles."}, infos)
