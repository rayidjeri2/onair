"""Intendance automatique : la société se gère toute seule si on le demande.

Ce module joue le rôle du joueur : il décide chaque matin qui fait quoi et
quel chantier ouvrir. Les règles sont explicites et ordonnées, de la survie
au développement, pour qu'on puisse lire le raisonnement plutôt que de le
subir.
"""

from __future__ import annotations

import math

from . import metiers
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
    # ce que les découvertes ouvrent : l'outillage qui casse le plafond de productivité
    "moulin", "four_poterie", "aqueduc", "charrue", "haut_fourneau", "brouettes",
    "attelage", "metier_tisser", "scierie_hydraulique", "hopital",
    "atelier_mecanise", "reseau_electrique",
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

    # On ouvre autant de chantiers que le groupe peut en tenir. Un chantier
    # dont les matériaux manquent n'arrête pas la file : il devient la cible
    # de collecte, et on regarde le suivant.
    cible = None
    ecartes: set[str] = set()
    # Tant qu'un besoin vital n'est pas couvert, on ne disperse pas les bras :
    # un seul chantier à la fois, celui qui répare la cause.
    limite = 1 if _besoins_vitaux(etat) else etat.chantiers_max
    for _ in range(8):
        if len(etat.chantiers) >= limite:
            break
        vise = cible_chantier(etat, ecartes)
        if vise is None:
            break
        if _materiaux_reunis(etat, vise):
            try:
                moteur.lancer_chantier(etat, vise)
            except ValueError:
                ecartes.add(vise)
            continue
        cible = cible or vise    # ce qu'on va chercher à rassembler
        ecartes.add(vise)
    _confier_les_metiers(etat)
    _affecter_tout_le_monde(etat, cible or cible_chantier(etat))


# --- division du travail --------------------------------------------------

ORDRE_METIERS = [
    "charpentier", "laboureur", "forgeron", "carrier", "bucheron", "fontainier",
    "soigneur", "mecanicien", "scribe", "enseignant", "potier", "tisserand",
    "cuisinier", "intendant",
]


def _confier_les_metiers(etat: Etat) -> None:
    """On n'installe un artisan à plein temps que si le grenier le permet."""
    from . import moteur

    a = moteur.apercu(etat)
    if a["autonomie_nourriture_jours"] < 25:
        return
    ouverts = set(metiers.possibles(etat))
    deja = {p.metier for p in etat.personnes if p.metier}
    for cle in ORDRE_METIERS:
        if cle not in ouverts or cle in deja:
            continue
        if metiers.exerces(etat) >= metiers.places(etat):
            return
        tache = metiers.METIERS[cle].tache
        candidats = [p for p in etat.personnes if not p.enfant and not p.metier]
        if not candidats:
            return
        choisi = max(candidats, key=lambda p: p.niveau_effectif(tache))
        try:
            metiers.attribuer(etat, choisi.id, cle)
        except ValueError:
            continue


# --- choix du chantier ----------------------------------------------------

def _besoins_vitaux(etat: Etat) -> list[str]:
    """Ce qui manque au point de tuer : eau, toit, champs."""
    from . import moteur

    besoins = []
    if moteur.eau_besoin_jour(etat) > moteur.eau_apport_jour(etat):
        besoins.append("eau")
    if effet_total(etat, "abri") < etat.population:
        besoins.append("abri")
    if etat.territoire.surface("potager") < etat.population * 0.25:
        besoins.append("champs")
    return besoins


def _ouvrables(etat: Etat) -> dict[str, dict]:
    """Chantiers dont les prérequis et la population sont satisfaits."""
    return {c["cle"]: c for c in disponibles(etat) if not c["bloque"]}


def _materiaux_reunis(etat: Etat, cle: str) -> bool:
    modele = MODELES[cle]
    return all(etat.stocks.get(r, 0.0) >= q for r, q in modele.materiaux.items())


def cible_chantier(etat: Etat, ecartes: set[str] | None = None) -> str | None:
    """Le prochain chantier visé — même si les matériaux manquent encore.

    C'est lui qui oriente le travail de collecte : on va chercher le bois et
    la pierre de ce qu'on a décidé de construire. Les chantiers déjà ouverts
    ne sont pas proposés une seconde fois.
    """
    from . import moteur

    ecartes = ecartes or set()
    ouvrables = {c: v for c, v in _ouvrables(etat).items()
                 if not etat.chantier_ouvert(c) and c not in ecartes}
    if not ouvrables:
        return None

    besoins = _besoins_vitaux(etat)
    if etat.stocks["nourriture"] > moteur.capacite_grenier(etat) * 0.92:
        besoins.append("grenier")
    if etat.territoire.surface("potager") < etat.population * 0.35 and "champs" not in besoins:
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
        ("charrue", etat.batiment("charrue") < max(1, etat.population // 12)),
        ("brouettes", etat.batiment("brouettes") < max(1, etat.population // 15)),
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

    adultes = [p for p in etat.personnes if not p.enfant and not p.metier]
    for enfant in (p for p in etat.personnes if p.enfant):
        enfant.tache = "repos"
    for artisan in (p for p in etat.personnes if p.metier and not p.enfant):
        artisan.tache = metiers.METIERS[artisan.metier].tache
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

    # 0. réparer la cause avant de panser le symptôme : un chantier qui
    # apporte l'eau, l'abri ou les champs prime sur le portage à la main.
    vitaux = {"eau_jour", "eau_max", "abri", "parcelle_potager"}
    if any(set(MODELES[c.cle].effets) & vitaux for c in etat.chantiers):
        prendre("construction", 1)

    # 1. boire
    if a["eau_deficit"] > 0 and a["autonomie_eau_jours"] < 6:
        # un porteur ramène environ 85 litres par jour, pas les 140 théoriques :
        # son rendement dépend de sa forme et de sa compétence
        porteurs = math.ceil(a["eau_deficit"] / 85)
        prendre("eau", min(porteurs, max(1, (n * 2) // 3)))

    # 2. manger — plus de bras si les réserves fondent, et on stocke pour l'hiver
    objectif = 110 if etat.saison in ("été", "automne") else 45
    if besoin_nourriture < objectif:
        rations = sum(q.part_ration() for q in etat.personnes)
        urgence = 1.8 if besoin_nourriture < 15 else 1.0
        # tant qu'il reste de quoi tenir, on garde au moins un bras pour bâtir
        plafond = len(libres) if besoin_nourriture < 12 else max(1, len(libres) - 1)
        prendre("nourriture", min(plafond, max(1, math.ceil(rations / 2.3 * urgence))))

    # 3. bâtir — sans cette réserve, une société qui porte son eau à la main
    # la porterait éternellement au lieu de creuser un puits.
    if etat.chantiers and libres:
        prendre("construction", max(1, n // 4))

    # 4. rassembler les matériaux du chantier visé
    for ressource, manque in sorted(manques.items(), key=lambda x: -x[1]):
        if ressource == "planches" and etat.stocks["bois"] < 3:
            prendre("bois", 1)
        elif ressource == "planches":
            prendre("artisanat", 1)
        elif ressource in ("pierre", "terre"):
            prendre("pierre", 1)
        elif ressource == "bois":
            prendre("bois", 1)

    # 5. soigner, transmettre, coordonner — quand le groupe le justifie
    if n >= 4 and etat.moyenne("sante") < 78:
        prendre("soin", 1)
    if n >= 8 and sum(1 for p in etat.personnes if p.enfant) >= 3:
        prendre("enseignement", 1)
    if etat.population > a["capacite_gouvernance"]:
        prendre("organisation", min(2, max(1, n // 8)))

    # 6. chercher, quand le lieu est assez sûr pour qu'on lève le nez
    if n >= 6 and besoin_nourriture > 40 and libres:
        prendre("recherche", max(1, n // 6))

    # 7. le reste bâtit, ou va chercher à manger s'il n'y a rien à bâtir
    reste = "construction" if etat.chantiers else "nourriture"
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
