"""Commerce extérieur et monnaie.

Jusqu'ici, le surplus au-delà du grenier était purement perdu. Avec une route
et des caravanes, il devient de l'argent — donc autre chose. Et l'argent, une
fois là, se répartit : la société cesse d'être un seul pot commun.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .catalogue import effet_total
from .modele import Etat

# Prix de référence d'une unité, en pièces. C'est la valeur que le monde
# extérieur accorde à ce que le lieu produit ou consomme.
PRIX_BASE = {
    "nourriture": 1.2,
    "bois": 2.0,
    "pierre": 3.5,
    "terre": 0.6,
    "recup": 0.8,
    "planches": 1.6,
    "outils": 28.0,
    "compost": 1.0,
    "electricite": 2.5,
}

MARGE_ACHAT = 1.35      # on achète plus cher qu'on ne vend
DELAI_CARAVANE = 60     # jours entre deux passages, sans chemin d'accès
IMPOT_DEFAUT = 0.25     # part des ventes qui va au trésor commun


@dataclass
class Offre:
    ressource: str
    quantite: float
    prix: float
    valeur: float


def prix_courant(etat: Etat, ressource: str, alea: random.Random | None = None) -> float:
    """Le prix du jour : la base, l'éloignement, et l'humeur du marché.

    Le chemin d'accès rapproche le lieu des marchés et resserre l'écart entre
    prix d'achat et prix de vente.
    """
    base = PRIX_BASE.get(ressource, 1.0)
    eloignement = 1.0 - min(0.35, effet_total(etat, "logistique"))
    humeur = 1.0
    if alea is not None:
        humeur = 1.0 + alea.gauss(0.0, 0.12)
    return max(0.05, base * eloignement * humeur)


def surplus(etat: Etat) -> dict[str, float]:
    """Ce dont la société peut se séparer sans se mettre en danger."""
    from . import moteur

    plafonds = moteur.capacites(etat)
    garde = {
        "nourriture": moteur.eau_besoin_jour(etat) and 0 or 0,  # remplacé ci-dessous
    }
    besoin_jour = sum(p.part_ration() for p in etat.personnes)
    garde = {
        "nourriture": besoin_jour * etat.politique.get("reserve_jours", 90),
        "bois": etat.population * 4,
        "pierre": etat.population * 3,
        "planches": etat.population * 8,
        "terre": etat.population * 3,
        "recup": etat.population * 10,
        "compost": etat.population * 2,
        "outils": etat.population * 0.6,
    }
    vendable: dict[str, float] = {}
    for ressource, reserve in garde.items():
        dispo = etat.stocks.get(ressource, 0.0) - reserve
        plafond = plafonds.get(ressource)
        if plafond:                       # ce qui allait déborder part en premier
            dispo = max(dispo, etat.stocks.get(ressource, 0.0) - plafond * 0.85)
        if dispo > 1:
            vendable[ressource] = dispo
    return vendable


def manques(etat: Etat) -> dict[str, float]:
    """Ce qu'il vaut la peine d'acheter : ce qui bloque les chantiers."""
    from .catalogue import disponibles

    besoins: dict[str, float] = {}
    for chantier in disponibles(etat):
        if chantier["bloque"]:
            continue
        for ressource, quantite in chantier["manquants"].items():
            besoins[ressource] = max(besoins.get(ressource, 0.0), quantite)
    if etat.stocks.get("outils", 0.0) < etat.population * 0.4:
        besoins["outils"] = etat.population * 0.4 - etat.stocks.get("outils", 0.0)
    return besoins


def caravane(etat: Etat, alea: random.Random, forcee: bool = False) -> dict:
    """Un passage de caravane : on vend le surplus, on achète ce qui manque."""
    if not etat.politique.get("commerce", 1.0) and not forcee:
        return {"passee": False, "raison": "route fermée"}

    # ce qu'une caravane peut emporter : la route et la taille du lieu comptent
    capacite = 90 * (1 + 4 * effet_total(etat, "logistique")) * max(1.0, etat.population / 10)
    # Les marchands n'ont pas une bourse sans fond : ils repartent quand ils
    # ont dépensé ce qu'ils avaient. C'est ce qui empêche un lieu de vendre
    # des montagnes de grain à prix constant.
    bourse_caravane = 250 + 45 * etat.population * (1 + effet_total(etat, "logistique"))
    ventes: list[Offre] = []
    achats: list[Offre] = []
    recette = 0.0

    for ressource, quantite in sorted(surplus(etat).items(),
                                      key=lambda x: -x[1] * PRIX_BASE.get(x[0], 1)):
        if capacite <= 0:
            break
        prix = prix_courant(etat, ressource, alea)
        # plus on remplit la caravane d'une même chose, moins la dernière
        # unité vaut cher : les marchands savent qu'on cherche à s'en défaire
        offert = min(quantite, capacite)
        prix *= 1.0 - 0.3 * (offert / max(capacite, 1.0))
        vendu = min(offert, (bourse_caravane - recette) / prix if prix else 0)
        if vendu < 1:
            continue
        valeur = vendu * prix
        etat.stocks[ressource] -= vendu
        recette += valeur
        capacite -= vendu
        if recette >= bourse_caravane:
            ventes.append(Offre(ressource, round(vendu, 1), round(prix, 2), round(valeur, 1)))
            break
        ventes.append(Offre(ressource, round(vendu, 1), round(prix, 2), round(valeur, 1)))

    # On partage la recette AVANT d'acheter : seule la part commune est
    # dépensable, sinon le trésor pourrait passer sous zéro.
    _repartir(etat, recette)

    depense = 0.0
    for ressource, quantite in sorted(manques(etat).items(),
                                      key=lambda x: -x[1] * PRIX_BASE.get(x[0], 1)):
        prix = prix_courant(etat, ressource, alea) * MARGE_ACHAT
        reste = etat.tresor - depense
        abordable = min(quantite, reste / prix if prix else 0)
        if abordable < 1:
            continue
        cout = abordable * prix
        etat.stocks[ressource] = etat.stocks.get(ressource, 0.0) + abordable
        depense += cout
        achats.append(Offre(ressource, round(abordable, 1), round(prix, 2), round(cout, 1)))

    _depenser(etat)
    etat.tresor = round(max(0.0, etat.tresor - depense), 2)
    etat.dernier_marche = {
        "jour": etat.jour,
        "ventes": [vars(o) for o in ventes],
        "achats": [vars(o) for o in achats],
        "recette": round(recette, 1),
        "depense": round(depense, 1),
    }
    if ventes or achats:
        etat.journal.noter(
            etat.jour,
            "Une caravane passe : "
            + (f"{round(recette)} pièces de ventes" if ventes else "rien à vendre")
            + (f", {round(depense)} pièces d'achats" if achats else ""),
            "commerce")
    return {"passee": True, **etat.dernier_marche}


def _repartir(etat: Etat, recette: float) -> None:
    """La recette se partage : une part au trésor commun, le reste aux gens.

    Chacun touche à proportion de ce qu'il a produit ce jour-là — c'est de là
    que naissent les écarts de fortune.
    """
    if recette <= 0:
        return
    part_commune = etat.politique.get("impot", IMPOT_DEFAUT)
    etat.tresor = round(etat.tresor + recette * part_commune, 2)
    a_partager = recette * (1 - part_commune)
    actifs = [p for p in etat.personnes if not p.enfant]
    if not actifs or a_partager <= 0:
        etat.tresor = round(etat.tresor + a_partager, 2)
        return
    poids = {p.id: max(0.1, p.capacite_travail() * p.efficacite(p.tache)) for p in actifs}
    total = sum(poids.values())
    for p in actifs:
        p.avoir = round(p.avoir + a_partager * poids[p.id] / total, 2)


def _depenser(etat: Etat) -> str:
    """Chacun achète pour soi ce qu'il peut s'offrir.

    C'est là que la fortune cesse d'être un nombre : elle devient du confort,
    donc du moral — et l'écart entre riches et pauvres devient visible dans
    l'humeur du lieu.
    """
    for p in etat.personnes:
        if p.avoir <= 0:
            continue
        depense = p.avoir * 0.12
        p.avoir = round(p.avoir - depense, 2)
        p.moral = min(100.0, p.moral + min(8.0, depense / 25.0))
    return ""


def inegalite(etat: Etat) -> float:
    """Indice de Gini des fortunes individuelles (0 = égalité parfaite)."""
    avoirs = sorted(p.avoir for p in etat.personnes if not p.enfant)
    n = len(avoirs)
    if n < 2:
        return 0.0
    total = sum(avoirs)
    if total <= 0:
        return 0.0
    cumul = sum((i + 1) * a for i, a in enumerate(avoirs))
    return round((2 * cumul) / (n * total) - (n + 1) / n, 3)


def attirer(etat: Etat, alea: random.Random) -> None:
    """La prospérité se sait : les gens viennent où il y a de quoi vivre.

    Chaque arrivée coûte au trésor — on installe les nouveaux venus.
    """
    from . import moteur

    if etat.tresor < 400 or not etat.politique.get("commerce", 1.0):
        return
    attrait = min(0.02, etat.tresor / 120_000)
    if effet_total(etat, "abri") <= etat.population:
        attrait *= 0.2          # personne ne vient s'il n'y a pas où dormir
    if alea.random() < attrait:
        venu = moteur.personne_au_hasard(etat, alea)
        venu.histoire = "attiré par ce qui se raconte sur ce lieu"
        etat.tresor = round(max(0.0, etat.tresor - 200), 2)
        etat.journal.noter(
            etat.jour,
            f"{venu.nom} arrive : la réputation du lieu a voyagé.", "arrivee")


def passer_le_jour(etat: Etat, alea: random.Random) -> None:
    """Fait passer une caravane quand c'est son heure."""
    attirer(etat, alea)
    if not etat.politique.get("commerce", 1.0):
        return
    delai = DELAI_CARAVANE / (1.0 + effet_total(etat, "logistique") * 2)
    if etat.jour - etat.dernier_marche.get("jour", -999) < delai:
        return
    if not etat.batiment("chemin") and not etat.decouvertes.count("roue"):
        return          # sans chemin ni roue, personne ne vient jusqu'ici
    caravane(etat, alea)


def resume(etat: Etat) -> dict:
    """Ce que l'interface montre du commerce."""
    alea = random.Random(etat.graine * 17 + etat.jour // 10)
    ouvert = bool(etat.batiment("chemin") or "roue" in etat.decouvertes)
    return {
        "tresor": round(etat.tresor, 1),
        "avoir_total": round(sum(p.avoir for p in etat.personnes), 1),
        "avoir_moyen": round(
            sum(p.avoir for p in etat.personnes) / max(1, etat.population), 1),
        "inegalite": inegalite(etat),
        "route_ouverte": ouvert,
        "commerce_actif": bool(etat.politique.get("commerce", 1.0)),
        "impot": etat.politique.get("impot", IMPOT_DEFAUT),
        "reserve_jours": etat.politique.get("reserve_jours", 90),
        "prochaine_caravane": max(0, round(
            DELAI_CARAVANE / (1.0 + effet_total(etat, "logistique") * 2)
            - (etat.jour - etat.dernier_marche.get("jour", -999)))) if ouvert else None,
        "prix": {r: round(prix_courant(etat, r, alea), 2) for r in PRIX_BASE},
        "surplus": {r: round(q, 1) for r, q in surplus(etat).items()},
        "manques": {r: round(q, 1) for r, q in manques(etat).items()},
        "dernier": etat.dernier_marche,
    }
