"""Intendance automatique : la société se gère toute seule si on le demande.

Ce module joue le rôle du joueur : il décide chaque matin qui fait quoi et
quel chantier ouvrir. Les règles sont explicites et ordonnées, de la survie
au développement, pour qu'on puisse lire le raisonnement plutôt que de le
subir.
"""

from __future__ import annotations

import math

from .catalogue import MODELES, disponibles, effet_total
from .modele import Etat, Personne

# Ordre de développement, une fois les besoins vitaux couverts.
DEVELOPPEMENT = [
    "source", "potager", "cabane", "toilettes_seches", "cave", "filtre",
    "compostage", "atelier", "scierie", "hangar", "cuisine", "poulailler",
    "place", "dispensaire", "verger", "reservoir", "solaire", "batteries",
    "rocket_stove", "ecole", "conseil", "archives", "serre", "forge",
    "recyclerie", "ruches", "troupeau", "douche_solaire", "chemin",
    "eolienne", "etang", "quartiers", "reforestation",
]

# Chantiers à dégainer quand un besoin vital n'est plus couvert.
URGENCES = {
    "eau": ["puits", "source", "reservoir", "etang"],
    "abri": ["maison_terre", "cabane", "campement"],
    "grenier": ["cave", "hangar"],
    "champs": ["potager", "defrichage"],
    "gouvernance": ["quartiers", "conseil", "place", "archives", "ecole"],
}


def decider(etat: Etat) -> None:
    """Une journée de décisions : d'abord le chantier, puis les affectations."""
    from . import moteur  # import tardif : le moteur importe ce module

    cible = cible_chantier(etat)
    if etat.chantier is None and cible and _materiaux_reunis(etat, cible):
        try:
            moteur.lancer_chantier(etat, cible)
        except ValueError:
            pass
    _affecter_tout_le_monde(etat, cible)


# --- choix du chantier ----------------------------------------------------

def _ouvrables(etat: Etat) -> dict[str, dict]:
    """Chantiers dont les prérequis et la population sont satisfaits."""
    return {c["cle"]: c for c in disponibles(etat) if not c["bloque"]}


def _materiaux_reunis(etat: Etat, cle: str) -> bool:
    modele = MODELES[cle]
    return all(etat.stocks.get(r, 0.0) >= q for r, q in modele.materiaux.items())


def cible_chantier(etat: Etat) -> str | None:
    """Le chantier visé — même si les matériaux manquent encore.

    C'est lui qui oriente le travail de collecte : on va chercher le bois et
    la pierre de ce qu'on a décidé de construire.
    """
    from . import moteur

    if etat.chantier is not None:
        return etat.chantier.cle
    ouvrables = _ouvrables(etat)
    if not ouvrables:
        return None

    besoins: list[str] = []
    if moteur.eau_besoin_jour(etat) > moteur.eau_apport_jour(etat):
        besoins.append("eau")
    if effet_total(etat, "abri") < etat.population:
        besoins.append("abri")
    if etat.stocks["nourriture"] > moteur.capacite_grenier(etat) * 0.92:
        besoins.append("grenier")
    if etat.territoire.surface("potager") < etat.population * 0.35:
        besoins.append("champs")
    # un groupe qui dépasse sa capacité de coordination se paralyse :
    # c'est aussi urgent que l'eau, et cela se répare en construisant.
    capacite = moteur.CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance")
    if etat.population > capacite:
        besoins.insert(0 if etat.population > capacite * 1.5 else len(besoins), "gouvernance")

    for besoin in besoins:
        for cle in URGENCES[besoin]:
            if cle in ouvrables:
                return cle
    for cle in DEVELOPPEMENT:
        if cle in ouvrables and not ouvrables[cle]["construit"]:
            return cle

    # Tout est bâti. On n'agrandit que ce qui répond à un besoin mesuré :
    # sans cette condition, l'intendance empilerait des bâtiments sans fin.
    grenier = moteur.capacite_grenier(etat)
    encore = [
        ("quartiers", etat.population > capacite),
        ("maison_terre", effet_total(etat, "abri") < etat.population),
        ("potager", etat.territoire.surface("potager") < etat.population * 0.35),
        ("hangar", etat.stocks["nourriture"] > grenier * 0.85),
        ("reservoir", moteur.eau_besoin_jour(etat) > moteur.eau_apport_jour(etat)),
        ("puits", moteur.eau_besoin_jour(etat) > moteur.eau_apport_jour(etat)),
        ("reforestation", etat.territoire.surface("foret") < etat.population * 1.5),
    ]
    for cle, necessaire in encore:
        if necessaire and cle in ouvrables:
            return cle
    return None


# --- répartition du travail ----------------------------------------------

def _besoins_de_collecte(etat: Etat, cible: str | None) -> dict[str, float]:
    """Ce qu'il manque pour le chantier visé, par ressource."""
    if not cible or cible not in MODELES:
        return {}
    return {
        r: q - etat.stocks.get(r, 0.0)
        for r, q in MODELES[cible].materiaux.items()
        if etat.stocks.get(r, 0.0) < q
    }


def _affecter_tout_le_monde(etat: Etat, cible: str | None) -> None:
    from . import moteur

    adultes = [p for p in etat.personnes if not p.enfant]
    for enfant in (p for p in etat.personnes if p.enfant):
        enfant.tache = "repos"
    if not adultes:
        return

    a = moteur.apercu(etat)
    libres = list(adultes)
    plan: dict[int, str] = {}

    def prendre(tache: str, combien: int) -> None:
        """Affecte les plus efficaces disponibles à une tâche."""
        for _ in range(min(int(combien), len(libres))):
            choisi = max(libres, key=lambda p: p.efficacite(tache))
            libres.remove(choisi)
            plan[choisi.id] = tache

    n = len(adultes)
    besoin_nourriture = a["autonomie_nourriture_jours"]
    manques = _besoins_de_collecte(etat, cible)

    # 1. boire
    if a["eau_deficit"] > 0 and a["autonomie_eau_jours"] < 6:
        porteurs = math.ceil(a["eau_deficit"] / 110)
        prendre("eau", min(porteurs, max(1, n // 2)))

    # 2. manger — plus de bras si les réserves fondent, et on stocke pour l'hiver
    objectif = 110 if etat.saison in ("été", "automne") else 45
    if besoin_nourriture < objectif:
        rations = sum(p.part_ration() for p in etat.personnes)
        urgence = 1.8 if besoin_nourriture < 15 else 1.0
        prendre("nourriture", max(1, math.ceil(rations / 2.3 * urgence)))

    # 3. rassembler les matériaux du chantier visé
    for ressource, manque in sorted(manques.items(), key=lambda x: -x[1]):
        if ressource == "planches" and etat.stocks["bois"] < 3:
            prendre("bois", 1)
        elif ressource == "planches":
            prendre("artisanat", 1)
        elif ressource in ("pierre", "terre"):
            prendre("pierre", 1)
        elif ressource == "bois":
            prendre("bois", 1)

    # 4. soigner, transmettre, coordonner — quand le groupe le justifie
    if n >= 4 and etat.moyenne("sante") < 78:
        prendre("soin", 1)
    if n >= 8 and sum(1 for p in etat.personnes if p.enfant) >= 3:
        prendre("enseignement", 1)
    if etat.population > a["capacite_gouvernance"]:
        prendre("organisation", min(2, max(1, n // 8)))

    # 5. le reste bâtit, ou va chercher à manger s'il n'y a rien à bâtir
    reste = "construction" if etat.chantier else "nourriture"
    for p in list(libres):
        plan[p.id] = reste
        libres.remove(p)

    for id_personne, tache in plan.items():
        try:
            moteur.affecter(etat, id_personne, tache)
        except ValueError:
            continue


def resume(etat: Etat) -> dict:
    """De quoi expliquer dans l'interface ce que l'intendance est en train de faire."""
    cible = cible_chantier(etat)
    manques = _besoins_de_collecte(etat, cible)
    return {
        "cible": cible,
        "cible_nom": MODELES[cible].nom if cible else None,
        "manquants": {r: round(q, 1) for r, q in manques.items()},
    }
