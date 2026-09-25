"""La carte du lieu : une vue 2D du terrain, des bâtiments et des gens.

La carte n'est pas stockée dans l'état : elle est recalculée à chaque
affichage, à partir des surfaces, des constructions et des tâches du jour.
Tout y est déterministe — une même société donne toujours le même plan, et
une parcelle qui s'agrandit garde les cases qu'elle occupait déjà.
"""

from __future__ import annotations

import math
from typing import Any

from .catalogue import MODELES
from .modele import Etat

LARGEUR = 46
HAUTEUR = 26
CENTRE = (LARGEUR // 2, HAUTEUR // 2 - 1)

# Où chaque usage aime s'installer : près du hameau, loin, ou près de l'eau.
AFFINITES = {
    "eau": "riviere",
    "potager": "proche",
    "verger": "proche",
    "pature": "moyen",
    "foret": "loin",
    "friche": "loin",
}
ORDRE = ["eau", "potager", "verger", "pature", "foret", "friche"]

# Une lettre par usage : la grille voyage en texte, c'est bien plus léger
# qu'un tableau de chaînes pour chaque case.
LETTRES = {"friche": ".", "foret": "T", "potager": "p", "verger": "v",
           "pature": "u", "eau": "~", "bati": "#"}

# Les tâches de plein air : c'est là qu'on va chercher les gens sur la carte.
LIEU_DE_TACHE = {
    "nourriture": "potager",
    "eau": "eau",
    "bois": "foret",
    "pierre": "friche",
    "construction": "chantier",
    "artisanat": "bati",
    "cuisine": "bati",
    "soin": "bati",
    "enseignement": "bati",
    "organisation": "bati",
    "recherche": "bati",
    "repos": "bati",
}


def _bruit(x: int, y: int, graine: int) -> float:
    """Un désordre reproductible : deux appels identiques donnent la même valeur."""
    n = math.sin(x * 127.1 + y * 311.7 + graine * 0.017) * 43758.5453
    return n - math.floor(n)


def _riviere(x: int) -> float:
    """La rivière traverse le lieu en serpentant."""
    return HAUTEUR * 0.72 + 3.2 * math.sin(x / 7.5) + 1.4 * math.sin(x / 3.1)


def _distance_centre(x: int, y: int) -> float:
    dx = (x - CENTRE[0]) / (LARGEUR / 2)
    dy = (y - CENTRE[1]) / (HAUTEUR / 2)
    return math.sqrt(dx * dx + dy * dy)


def _score(type_terrain: str, x: int, y: int, graine: int) -> float:
    """Plus le score est bas, plus la case convient à cet usage."""
    d = _distance_centre(x, y)
    bruit = _bruit(x, y, graine) * 0.35
    affinite = AFFINITES.get(type_terrain, "moyen")
    if affinite == "riviere":
        return abs(y - _riviere(x)) / HAUTEUR + bruit * 0.4
    if affinite == "proche":
        return d + bruit
    if affinite == "moyen":
        return abs(d - 0.55) + bruit
    return (1.6 - d) + bruit


def _cases_baties(etat: Etat) -> int:
    """Le hameau tient une case par type de construction, plus un peu d'air.

    On ne pose pas une case par bâtiment : à cent maisons en terre, le plan
    ne serait qu'un tapis de confettis. Un type, une case, un compteur.
    """
    types = len(etat.batiments) + len(etat.chantiers)
    return max(4, min(90, int(types * 1.8) + 2))


def tuiles(etat: Etat) -> list[list[str]]:
    """Le terrain, case par case."""
    surfaces = {t: etat.territoire.surface(t) for t in ORDRE}
    total_ha = sum(surfaces.values()) or 1.0
    libres = LARGEUR * HAUTEUR - _cases_baties(etat)

    grille = [["friche"] * LARGEUR for _ in range(HAUTEUR)]
    prises: set[tuple[int, int]] = set()

    # le hameau, au centre, d'abord
    centre_cases = sorted(
        ((x, y) for y in range(HAUTEUR) for x in range(LARGEUR)),
        key=lambda c: _distance_centre(*c) + _bruit(c[0], c[1], etat.graine) * 0.18,
    )[: _cases_baties(etat)]
    for x, y in centre_cases:
        grille[y][x] = "bati"
        prises.add((x, y))

    for type_terrain in ORDRE:
        part = surfaces[type_terrain] / total_ha
        combien = int(round(part * libres))
        if combien <= 0:
            continue
        candidats = sorted(
            ((x, y) for y in range(HAUTEUR) for x in range(LARGEUR) if (x, y) not in prises),
            key=lambda c: _score(type_terrain, c[0], c[1], etat.graine),
        )[:combien]
        for x, y in candidats:
            grille[y][x] = type_terrain
            prises.add((x, y))
    return grille


def batiments(etat: Etat) -> list[dict[str, Any]]:
    """Chaque construction posée dans le hameau, à une place stable."""
    cases = sorted(
        ((x, y) for y in range(HAUTEUR) for x in range(LARGEUR)),
        key=lambda c: _distance_centre(*c) + _bruit(c[0], c[1], etat.graine) * 0.18,
    )
    poses: list[dict[str, Any]] = []
    for index, cle in enumerate(sorted(etat.batiments)):   # ordre stable
        if index >= len(cases):
            break
        modele = MODELES.get(cle)
        x, y = cases[index]
        poses.append({
            "cle": cle,
            "nom": modele.nom if modele else cle,
            "categorie": modele.categorie if modele else "atelier",
            "x": x, "y": y,
            "nombre": etat.batiments[cle],
        })
    return poses


def chantiers(etat: Etat, places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les chantiers en cours, posés juste après le bâti existant."""
    cases = sorted(
        ((x, y) for y in range(HAUTEUR) for x in range(LARGEUR)),
        key=lambda c: _distance_centre(*c) + _bruit(c[0], c[1], etat.graine) * 0.18,
    )
    depart = len(places)
    dehors = []
    for i, chantier in enumerate(etat.chantiers):
        if depart + i >= len(cases):
            break
        x, y = cases[depart + i]
        dehors.append({
            "cle": chantier.cle, "nom": chantier.nom, "x": x, "y": y,
            "avancement": round(chantier.travail_fait / chantier.travail_requis, 3)
            if chantier.travail_requis else 1.0,
        })
    return dehors


def gens(etat: Etat, grille: list[list[str]], places: list[dict[str, Any]],
         travaux: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Où se trouve chacun aujourd'hui, selon ce qu'il fait."""
    par_type: dict[str, list[tuple[int, int]]] = {}
    for y in range(HAUTEUR):
        for x in range(LARGEUR):
            par_type.setdefault(grille[y][x], []).append((x, y))

    resultat = []
    for personne in etat.personnes:
        besoin = LIEU_DE_TACHE.get(personne.tache, "bati")
        if besoin == "chantier" and travaux:
            cible = travaux[personne.id % len(travaux)]
            x, y = cible["x"], cible["y"]
        else:
            cases = par_type.get(besoin) or par_type.get("bati") or [CENTRE]
            x, y = cases[personne.id * 7919 % len(cases)]
        decalage = _bruit(personne.id, etat.jour // 3, etat.graine)
        resultat.append({
            "id": personne.id, "nom": personne.nom, "tache": personne.tache,
            "enfant": personne.enfant, "metier": personne.metier,
            "x": round(x + 0.2 + 0.6 * decalage, 2),
            "y": round(y + 0.2 + 0.6 * _bruit(personne.id + 5, etat.jour // 3, etat.graine), 2),
        })
    return resultat


def dessiner(etat: Etat) -> dict[str, Any]:
    """Tout ce qu'il faut pour tracer la carte, prêt à envoyer à l'interface."""
    grille = tuiles(etat)
    places = batiments(etat)
    travaux = chantiers(etat, places)
    return {
        "largeur": LARGEUR,
        "hauteur": HAUTEUR,
        "lettres": {v: k for k, v in LETTRES.items()},
        "tuiles": ["".join(LETTRES[t] for t in ligne) for ligne in grille],
        "batiments": places,
        "chantiers": travaux,
        "gens": gens(etat, grille, places, travaux),
        "riviere": [round(_riviere(x), 2) for x in range(LARGEUR)],
        "surfaces": {t: round(etat.territoire.surface(t), 1) for t in ORDRE},
    }
