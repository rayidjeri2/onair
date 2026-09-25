"""Moteur de la simulation : une journée de la société à chaque pas.

Tout est déterministe à graine fixée. Les constantes sont regroupées en tête
de fichier pour pouvoir être ajustées sans relire la logique.
"""

from __future__ import annotations

import random
from typing import Any

from . import carte, demographie, intendance, marche, metiers, savoirs
from .catalogue import MODELES, effet_total
from .modele import (
    AGE_TRAVAIL,
    COMPETENCES,
    TACHE_COMPETENCE,
    Chantier,
    Etat,
    Journal,
    Personne,
    Territoire,
)

# --- constantes de calibrage ---------------------------------------------
BESOIN_NOURRITURE = 1.0       # portions par personne et par jour
BESOIN_EAU = 50.0             # litres par personne et par jour
EAU_BASE_MAX = 400.0          # réserve commune, sans réservoir
EAU_PAR_PERSONNE = 60.0       # ce que chaque foyer garde en jarres
EAU_NATURELLE = 150.0         # le ruisseau : de quoi tenir à deux ou trois, pas plus
STOCK_NOURRITURE_BASE = 120.0  # réserve commune minimale
STOCK_PAR_PERSONNE = 40.0      # ce que chaque foyer garde chez lui
PORTIONS_PAR_JOUR_HOMME = 4.2
CUEILLETTE_PAR_JOUR_HOMME = 3.0  # ce que rend la cueillette, sans parcelle
PORTIONS_MAX_PAR_HECTARE = 8.0
BOIS_PAR_JOUR_HOMME = 1.2
PIERRE_PAR_JOUR_HOMME = 0.6
TERRE_PAR_JOUR_HOMME = 2.0
PLANCHES_PAR_STERE = 6.0
EAU_PORTEE_PAR_JOUR_HOMME = 140.0
GASPILLAGE_NOURRITURE = 0.012  # part des stocks perdue chaque jour
CAPACITE_GOUVERNANCE_BASE = 5.0

SAISON_RENDEMENT = {"printemps": 1.0, "été": 1.35, "automne": 1.3, "hiver": 0.3}
SAISON_SOLEIL = {"printemps": 1.0, "été": 1.3, "automne": 0.75, "hiver": 0.45}
SAISON_TEMPERATURE = {"printemps": 14.0, "été": 24.0, "automne": 13.0, "hiver": 4.0}
SAISON_PLUIE = {"printemps": 0.45, "été": 0.12, "automne": 0.5, "hiver": 0.55}

# --- création -------------------------------------------------------------

def creer_societe(nom_fondateur: str = "Ana", age: int = 30, graine: int = 1,
                  sexe: str = "f") -> Etat:
    """Jour 0 : une personne débarque sur un million de km² de terre vierge."""
    etat = Etat(graine=graine, territoire=Territoire(km2=1_000_000.0))
    fondateur = Personne(
        id=1, nom=nom_fondateur.strip() or "Ana", age=age, arrivee=0,
        competences={c: 0.15 for c in COMPETENCES},
        tache="nourriture",
        sexe=sexe if sexe in ("f", "h") else "f",
        histoire="Arrivé seul, sans rien d'autre que ses mains." if sexe == "h"
        else "Arrivée seule, sans rien d'autre que ses mains.",
    )
    fondateur.competences["construction"] = 0.3
    fondateur.competences["agriculture"] = 0.25
    etat.personnes.append(fondateur)
    etat.prochain_id_personne = 2
    etat.stocks.update({"nourriture": 30.0, "eau": 300.0, "outils": 1.0})
    etat.territoire.ajouter("friche", 100.0)
    etat.territoire.ajouter("foret", 40.0)
    # l'installation : un toit et un champ, le point de départ de la société
    etat.batiments["campement"] = 1
    etat.territoire.ajouter("potager", 1.0)
    etat.journal = Journal()
    etat.journal.noter(0, f"{fondateur.nom} pose son sac. Un million de kilomètres carrés, "
                          "personne d'autre, et tout à faire.", "jalon")
    etat.journal.noter(0, "Premier abri monté, premier champ défriché et semé. "
                          "Une société commence.", "jalon")
    _mettre_a_jour_meteo(etat, random.Random(graine))
    _enregistrer_historique(etat)
    return etat


# --- actions du joueur ----------------------------------------------------

def ajouter_personne(etat: Etat, nom: str, age: int, specialite: str,
                     histoire: str = "", sexe: str = "f",
                     polyvalence: float | None = None) -> Personne:
    if specialite not in COMPETENCES:
        raise ValueError(f"spécialité inconnue : {specialite}")
    if not 1 <= age <= 100:
        raise ValueError("âge invalide")
    p = Personne(
        id=etat.prochain_id_personne,
        nom=nom.strip() or demographie.prenom_libre(
            etat, sexe, random.Random(etat.graine + etat.jour + etat.prochain_id_personne)),
        age=age,
        arrivee=etat.jour,
        competences={c: 0.12 for c in COMPETENCES},
        tache="construction" if etat.chantiers else "nourriture",
        sexe=sexe if sexe in ("f", "h") else "f",
        anniversaire=etat.jour_annee,
        histoire=histoire,
        polyvalence=0.35 if polyvalence is None else max(0.0, min(1.0, polyvalence)),
    )
    p.competences[specialite] = 0.55
    if age < AGE_TRAVAIL:
        p.tache = "repos"
        for c in COMPETENCES:
            p.competences[c] = 0.05
    etat.prochain_id_personne += 1
    etat.personnes.append(p)
    if etat.termine:  # une arrivée relance une société éteinte
        etat.termine = None
    etat.journal.noter(
        etat.jour,
        f"{p.nom}, {age} ans, rejoint le lieu ({specialite}). "
        f"La société compte {etat.population} personnes.",
        "arrivee",
    )
    return p


def _age_tire(alea: random.Random) -> int:
    """Qui arrive dans un lieu pareil : surtout des jeunes adultes, quelques familles."""
    tirage = alea.random()
    if tirage < 0.58:
        return alea.randint(18, 35)
    if tirage < 0.80:
        return alea.randint(36, 50)
    if tirage < 0.92:
        return alea.randint(8, 17)
    if tirage < 0.98:
        return alea.randint(51, 66)
    return alea.randint(1, 7)


def personne_au_hasard(etat: Etat, alea: random.Random | None = None) -> Personne:
    """Fait venir quelqu'un dont on ne sait rien à l'avance."""
    alea = alea or random.Random(etat.graine * 7919 + etat.jour * 31 + etat.prochain_id_personne)
    sexe = "f" if alea.random() < 0.5 else "h"
    age = _age_tire(alea)
    specialite = alea.choice(COMPETENCES)
    return ajouter_personne(
        etat,
        nom=demographie.prenom_libre(etat, sexe, alea),
        age=age,
        specialite=specialite,
        histoire=alea.choice(demographie.ARRIVEES) if age >= AGE_TRAVAIL else "",
        sexe=sexe,
        # certains ne savent faire qu'une chose, d'autres se débrouillent partout
        polyvalence=round(min(1.0, max(0.0, alea.betavariate(2.2, 2.2))), 2),
    )


def faire_venir(etat: Etat, nombre: int = 1) -> list[Personne]:
    """Plusieurs arrivées d'un coup, chacune tirée au hasard."""
    if not 1 <= nombre <= 50:
        raise ValueError("on ne fait venir qu'entre 1 et 50 personnes à la fois")
    alea = random.Random(etat.graine * 104_729 + etat.jour * 97 + etat.prochain_id_personne)
    venus = [personne_au_hasard(etat, alea) for _ in range(nombre)]
    if nombre > 1:
        etat.journal.noter(
            etat.jour,
            f"{nombre} personnes s'installent d'un coup : "
            f"{', '.join(p.nom for p in venus)}. La société compte {etat.population} personnes.",
            "arrivee")
    return venus


def affecter(etat: Etat, id_personne: int, tache: str) -> None:
    if tache not in TACHE_COMPETENCE:
        raise ValueError(f"tâche inconnue : {tache}")
    p = etat.personne(id_personne)
    if p is None:
        raise ValueError("personne inconnue")
    if p.enfant and tache != "repos":
        raise ValueError(f"{p.nom} n'a que {p.age} ans")
    if p.metier and tache not in (metiers.METIERS[p.metier].tache, "repos"):
        raise ValueError(
            f"{p.nom} exerce le métier de {metiers.METIERS[p.metier].nom.lower()}")
    p.tache = tache


def regler_intendance(etat: Etat, actif: bool) -> None:
    """Confie (ou reprend) la conduite quotidienne du lieu."""
    etat.intendance = bool(actif)
    etat.journal.noter(
        etat.jour,
        "L'intendance prend la main : affectations et chantiers sont décidés chaque matin."
        if etat.intendance else "Vous reprenez la main sur les affectations et les chantiers.",
        "info")
    if etat.intendance:
        intendance.decider(etat)


BORNES_POLITIQUE = {
    "natalite": (0.0, 1.0),
    "commerce": (0.0, 1.0),
    "impot": (0.0, 1.0),
    "reserve_jours": (0.0, 400.0),
}


def regler_politique(etat: Etat, cle: str, valeur: float) -> None:
    """Les orientations que le collectif se donne."""
    if cle not in etat.politique:
        raise ValueError(f"politique inconnue : {cle}")
    bas, haut = BORNES_POLITIQUE.get(cle, (0.0, 1.0))
    etat.politique[cle] = max(bas, min(haut, float(valeur)))


def lancer_chantier(etat: Etat, cle: str) -> Chantier:
    if len(etat.chantiers) >= etat.chantiers_max:
        raise ValueError(
            f"déjà {len(etat.chantiers)} chantiers ouverts : il en faut plus de bras")
    if etat.chantier_ouvert(cle):
        raise ValueError("ce chantier est déjà en cours")
    modele = MODELES.get(cle)
    if modele is None:
        raise ValueError(f"chantier inconnu : {cle}")
    if etat.batiment(cle) and not modele.repetable:
        raise ValueError("déjà construit")
    for pre in modele.prerequis:
        if not etat.batiment(pre):
            raise ValueError(f"prérequis manquant : {MODELES[pre].nom}")
    if etat.population < modele.population_min:
        raise ValueError(f"il faut {modele.population_min} personnes")
    for ressource, quantite in modele.materiaux.items():
        if etat.stocks.get(ressource, 0.0) < quantite:
            raise ValueError(f"matériaux manquants : {ressource}")
    for ressource, quantite in modele.materiaux.items():
        etat.stocks[ressource] -= quantite
    chantier = Chantier(cle=cle, nom=modele.nom, travail_requis=modele.travail,
                        materiaux=dict(modele.materiaux), materiaux_livres=True)
    etat.chantiers.append(chantier)
    etat.journal.noter(etat.jour, f"Chantier ouvert : {modele.nom}.", "chantier")
    return chantier


def annuler_chantier(etat: Etat, cle: str | None = None) -> None:
    """Abandonne un chantier (le premier ouvert si on n'en nomme aucun)."""
    if not etat.chantiers:
        return
    chantier = etat.chantier_ouvert(cle) if cle else etat.chantiers[0]
    if chantier is None:
        return
    for ressource, quantite in chantier.materiaux.items():
        etat.stocks[ressource] = etat.stocks.get(ressource, 0.0) + quantite * 0.6
    etat.chantiers.remove(chantier)
    etat.journal.noter(etat.jour, f"Chantier abandonné : {chantier.nom}. "
                                  "Une partie des matériaux est récupérée.", "alerte")


# --- déroulement d'une journée -------------------------------------------

def avancer(etat: Etat, jours: int = 1) -> Etat:
    for _ in range(max(1, jours)):
        if etat.termine:
            break
        _un_jour(etat)
    return etat


def _un_jour(etat: Etat) -> None:
    etat.jour += 1
    avant = dict(etat.stocks)
    alea = random.Random(etat.graine * 1_000_003 + etat.jour)
    _mettre_a_jour_meteo(etat, alea)
    if etat.intendance:
        intendance.decider(etat)

    travail = _repartir_travail(etat)
    _produire(etat, travail, alea)
    _avancer_chantier(etat, travail)
    savoirs.progresser(etat, travail, alea)
    marche.passer_le_jour(etat, alea)
    _consommer(etat)
    _mettre_a_jour_personnes(etat, travail, alea)
    demographie.passer_le_jour(etat, alea)
    _mettre_a_jour_cohesion(etat)
    _faire_murir(etat)
    _alerter(etat)
    _evenement(etat, alea)
    _verifier_fin(etat)
    # garde-fou : un stock ne descend jamais sous zéro, quoi qu'il arrive
    for ressource, quantite in etat.stocks.items():
        if quantite < 0:
            etat.stocks[ressource] = 0.0
    etat.flux = {c: round(etat.stocks[c] - avant.get(c, 0.0), 2) for c in etat.stocks}
    _enregistrer_historique(etat)


def _mettre_a_jour_meteo(etat: Etat, alea: random.Random) -> None:
    saison = etat.saison
    climat = etat.climat
    base = SAISON_TEMPERATURE[saison] + climat.get("temperature", 0.0)
    if saison == "hiver":
        base -= 4.0 * (climat.get("durete_hiver", 1.0) - 1.0)
    temperature = base + alea.gauss(0, 4)
    pluie = 0.0
    if alea.random() < SAISON_PLUIE[saison] * climat.get("pluie", 1.0):
        pluie = abs(alea.gauss(6, 5)) * climat.get("pluie", 1.0)
    if temperature > 30:
        description = "chaleur écrasante"
    elif temperature < 2:
        description = "gel"
    elif pluie > 12:
        description = "forte pluie"
    elif pluie > 0:
        description = "pluie"
    else:
        description = "temps sec"
    etat.meteo.temperature = round(temperature, 1)
    etat.meteo.pluie = round(pluie, 1)
    etat.meteo.description = description


def multiplicateur(etat: Etat, nom: str) -> float:
    """Gain de productivité apporté par l'outillage bâti et les savoirs acquis."""
    return 1.0 + effet_total(etat, nom) + savoirs.effet_savoirs(etat, nom)


def coordination(etat: Etat) -> float:
    """Au-delà de ce que la gouvernance peut tenir, chaque personne coûte."""
    capacite = (CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance")
                + savoirs.effet_savoirs(etat, "gouvernance"))
    surcharge = max(0.0, etat.population - capacite)
    # la perte sature : un gros dépassement fait mal sans être immédiatement fatal
    penalite = 0.085 * surcharge ** 0.75
    return 1.0 / (1.0 + penalite) * (0.75 + 0.25 * etat.cohesion)


def _repartir_travail(etat: Etat) -> dict[str, float]:
    """Jours-homme effectifs par tâche, après coordination."""
    facteur = coordination(etat)
    travail: dict[str, float] = {t: 0.0 for t in TACHE_COMPETENCE}
    for p in etat.personnes:
        if p.tache == "repos" or p.enfant:
            continue
        travail[p.tache] += p.capacite_travail() * p.efficacite(p.tache) * facteur
        p.jours_par_tache[p.tache] = p.jours_par_tache.get(p.tache, 0) + 1
    bonus_orga = 1.0 + min(0.25, travail.get("organisation", 0.0) * 0.12)
    for tache in travail:
        if tache != "organisation":
            travail[tache] *= bonus_orga
    return travail


def _produire(etat: Etat, travail: dict[str, float], alea: random.Random) -> None:
    s = etat.stocks
    saison = etat.saison

    # --- eau
    eau_max = capacites(etat)["eau"]
    captage = 1.0 + effet_total(etat, "captage")
    s["eau"] += etat.meteo.pluie * 12.0 * captage
    s["eau"] += EAU_NATURELLE + effet_total(etat, "eau_jour")
    s["eau"] += (travail["eau"] * EAU_PORTEE_PAR_JOUR_HOMME
                 * multiplicateur(etat, "rendement_eau"))
    s["eau"] = min(eau_max, s["eau"])

    # --- nourriture
    rendement = ((1.0 + effet_total(etat, "rendement"))
                 * etat.climat.get("fertilite", 1.0)
                 * multiplicateur(etat, "rendement_agricole"))
    saisonnier = SAISON_RENDEMENT[saison]
    if saison == "hiver":
        saisonnier = max(0.02, saisonnier / max(0.2, etat.climat.get("durete_hiver", 1.0)))
        saisonnier += effet_total(etat, "saison_froide")
    surface = etat.territoire.surface_productive("potager")
    stress_hydrique = 1.0 if s["eau"] > etat.population * BESOIN_EAU * 2 else 0.6
    if effet_total(etat, "irrigation"):
        stress_hydrique = min(1.0, stress_hydrique + 0.25)
    potentiel = travail["nourriture"] * PORTIONS_PAR_JOUR_HOMME * rendement * saisonnier
    plafond = surface * PORTIONS_MAX_PAR_HECTARE * saisonnier * rendement
    cultive = min(potentiel, plafond) * stress_hydrique
    # cueillette et chasse : ce qu'on tire du terrain sans l'avoir aménagé
    sauvage = min(1.0, (etat.territoire.surface("foret") + etat.territoire.surface("friche"))
                  / max(1.0, etat.population * 6))
    cueillette = (travail["nourriture"] * CUEILLETTE_PAR_JOUR_HOMME * saisonnier * sauvage
                  * multiplicateur(etat, "rendement_cueillette"))
    recolte = cultive + cueillette
    passif = effet_total(etat, "nourriture_jour")
    passif += etat.territoire.surface_productive("verger") * 2.2 * saisonnier
    s["nourriture"] += recolte + passif

    # --- bois, pierre, terre
    foret = etat.territoire.surface("foret")
    dispo_bois = min(1.0, foret / max(1.0, etat.population * 4))
    s["bois"] += (travail["bois"] * BOIS_PAR_JOUR_HOMME * dispo_bois
                  * multiplicateur(etat, "rendement_bois"))
    pierre = multiplicateur(etat, "rendement_pierre")
    s["pierre"] += travail["pierre"] * PIERRE_PAR_JOUR_HOMME * pierre
    s["terre"] += travail["pierre"] * TERRE_PAR_JOUR_HOMME * pierre

    # --- artisanat : le bois devient planches, on fabrique des outils
    ratio = 1.0 + effet_total(etat, "planches_ratio")
    artisanat = (travail["artisanat"] * (1.0 + effet_total(etat, "artisanat"))
                 * multiplicateur(etat, "rendement_artisanat"))
    steres = min(s["bois"], artisanat * 0.8)
    s["bois"] -= steres
    s["planches"] += steres * PLANCHES_PAR_STERE * ratio / 2.0
    s["planches"] += effet_total(etat, "planches_jour")
    s["outils"] += ((effet_total(etat, "outils_jour") + artisanat * 0.02)
                    * multiplicateur(etat, "rendement_outils"))
    s["recup"] += effet_total(etat, "recup_jour") + 0.4

    # --- compost et électricité
    s["compost"] += effet_total(etat, "compost_jour") + travail["nourriture"] * 0.01
    elec_max = effet_total(etat, "elec_max")
    production_elec = (effet_total(etat, "solaire") * SAISON_SOLEIL[saison]
                       + effet_total(etat, "eolien") * (0.6 + alea.random() * 0.8))
    s["electricite"] = min(elec_max, s["electricite"] + production_elec)

    # --- ce qu'on ne peut ni ranger ni entretenir finit par se perdre
    plafonds = capacites(etat)
    for ressource in ("outils", "recup", "bois", "planches", "pierre", "terre", "compost"):
        plafond = plafonds.get(ressource)
        if plafond and s[ressource] > plafond:
            if s[ressource] > plafond * 1.05:
                _dire_une_fois(etat, f"deborde_{ressource}", 60,
                               f"Le stock de {ressource} déborde : ce qui reste dehors se perd. "
                               "Un hangar ou une cave y remédierait.")
            s[ressource] = plafond

    # --- pertes : ce qui dépasse la capacité de conservation est perdu
    conservation = min(0.85, effet_total(etat, "conservation")
                       + savoirs.effet_savoirs(etat, "conservation"))
    s["nourriture"] *= 1.0 - GASPILLAGE_NOURRITURE * (1.0 - conservation)
    grenier = capacite_grenier(etat)
    if s["nourriture"] > grenier:
        perdu = s["nourriture"] - grenier
        s["nourriture"] = grenier
        if perdu > grenier * 0.05:
            _dire_une_fois(etat, "grenier", 30,
                           f"Les réserves débordent : {perdu:.0f} portions perdues faute de place. "
                           "Il faut des caves et des hangars.")
    for cle in s:
        s[cle] = max(0.0, round(s[cle], 3))


def _avancer_chantier(etat: Etat, travail: dict[str, float]) -> None:
    """Les bras se répartissent à parts égales entre les chantiers ouverts."""
    if not etat.chantiers:
        return
    outils = 1.0 + min(0.3, etat.stocks.get("outils", 0.0) * 0.04)
    logistique = 1.0 + effet_total(etat, "logistique") + savoirs.effet_savoirs(etat, "logistique")
    part = (travail["construction"] * outils * logistique
            * multiplicateur(etat, "rendement_construction") / len(etat.chantiers))
    for chantier in list(etat.chantiers):
        chantier.travail_fait += part
        if chantier.travail_fait >= chantier.travail_requis:
            _terminer_chantier(etat, chantier)


def _terminer_chantier(etat: Etat, chantier: Chantier) -> None:
    modele = MODELES[chantier.cle]
    etat.batiments[chantier.cle] = etat.batiment(chantier.cle) + 1
    for effet, valeur in modele.effets.items():
        if effet.startswith("parcelle_"):
            type_parcelle = effet.removeprefix("parcelle_")
            if type_parcelle == "friche":
                continue  # le défrichage se contente de libérer de la friche
            maturite = 0.05 if type_parcelle in ("verger", "foret") else 1.0
            etat.territoire.ajouter(type_parcelle, valeur, maturite)
        elif effet in etat.stocks:
            etat.stocks[effet] += valeur
    etat.journal.noter(etat.jour, f"{modele.nom} : achevé.", "jalon")
    etat.chantiers.remove(chantier)


def _consommer(etat: Etat) -> None:
    s = etat.stocks
    population = etat.population
    besoin = sum(p.part_ration() for p in etat.personnes) * BESOIN_NOURRITURE
    s["nourriture"] -= besoin
    etat.en_peril = s["nourriture"] < 0
    ration = 1.0 if s["nourriture"] >= 0 else max(0.0, 1.0 + s["nourriture"] / max(besoin, 1e-9))
    s["nourriture"] = max(0.0, s["nourriture"])

    besoin_eau = sum(0.6 if p.enfant else 1.0 for p in etat.personnes) * BESOIN_EAU
    # la soif est graduelle : boire 90 % de ce qu'il faut n'est pas mourir de soif
    part_eau = 1.0 if besoin_eau <= 0 else min(1.0, s["eau"] / besoin_eau)
    s["eau"] = max(0.0, s["eau"] - besoin_eau)

    if etat.saison in ("hiver", "automne"):
        economie = 1.0 - min(0.6, effet_total(etat, "isolation") * 0.12
                             + effet_total(etat, "bois_economie") * 0.2)
        s["bois"] = max(0.0, s["bois"] - population * 0.07 * economie)

    s["electricite"] = max(0.0, s["electricite"] - population * 0.35)
    etat._ration = ration  # type: ignore[attr-defined]
    etat._part_eau = part_eau  # type: ignore[attr-defined]


def _mettre_a_jour_personnes(etat: Etat, travail: dict[str, float],
                             alea: random.Random) -> None:
    ration = getattr(etat, "_ration", 1.0)
    part_eau = getattr(etat, "_part_eau", 1.0)
    abri = effet_total(etat, "abri")
    confort = effet_total(etat, "confort") + savoirs.effet_savoirs(etat, "confort")
    salubrite = effet_total(etat, "salubrite") + savoirs.effet_savoirs(etat, "salubrite")
    soin = travail["soin"] * (1.0 + effet_total(etat, "soin")
                              + savoirs.effet_savoirs(etat, "soin"))
    enseignement = travail["enseignement"] * (1.0 + effet_total(etat, "enseignement"))
    froid = etat.meteo.temperature < 5 and etat.stocks["bois"] <= 0.5
    # l'abri se partage : la couverture est progressive, pas tout ou rien
    couverture = min(1.0, abri / etat.population) if etat.population else 1.0
    abrite = couverture >= 1.0
    partis = []

    for p in etat.personnes:
        # énergie : le repos recharge, le travail use
        if p.tache == "repos" or p.energie < 18:
            # sous un certain seuil, le corps impose le repos
            p.energie = min(100.0, p.energie + 22.0)
        else:
            p.energie = max(0.0, p.energie - 12.0 + (3.0 + 6.0 * couverture)
                            + 6.0 * ration + min(6.0, soin * 3.0))
            p.energie = min(100.0, p.energie)

        # santé
        delta = 0.0
        delta += 1.6 if ration >= 1.0 else -7.0 * (1.0 - ration)
        delta += 0.4 - 7.0 * (1.0 - part_eau)
        delta += salubrite * 0.12 - 0.6
        delta += -3.0 if froid else 0.0
        delta += min(4.0, soin * 2.5)
        delta += -1.6 * (1.0 - couverture)
        delta -= max(0.0, (p.age - 65)) * 0.05
        p.sante = max(0.0, min(100.0, p.sante + delta))

        # moral : on tend vers un niveau cible plutôt que d'accumuler
        cible = 45.0
        cible += min(18.0, confort * 0.5)
        cible += 12.0 * (etat.cohesion - 0.5)
        cible += min(12.0, effet_total(etat, "variete") * 0.35)
        cible -= 45.0 * (1.0 - ration)
        cible += -9.0 + 15.0 * couverture
        cible += 5.0 if p.energie > 55 else -8.0
        cible += 4.0 if etat.population > 1 else -9.0  # la solitude pèse
        cible += 3.0 if etat.chantiers else -3.0  # avoir un cap commun
        cible += 4.0 if p.partenaire is not None else 0.0
        cible += min(4.0, 1.5 * sum(1 for e in etat.personnes if e.id in p.enfants))
        p.moral = max(0.0, min(100.0, p.moral + (cible - p.moral) * 0.12))

        # apprentissage : par la pratique, et par l'enseignement des autres
        if p.enfant:
            continue
        comp = TACHE_COMPETENCE.get(p.tache)
        if comp:
            vitesse = 0.0022 * (2.0 if p.metier else 1.0)
            p.competences[comp] = min(1.0, p.competences[comp]
                                      + vitesse * (1.1 - p.competences[comp]))
        if enseignement and etat.population > 1:
            gain = 0.0016 * enseignement / etat.population
            for c in COMPETENCES:
                p.competences[c] = min(1.0, p.competences[c] + gain)

        if p.sante <= 0:
            partis.append((p, "meurt d'épuisement"))
        elif _veut_partir(etat, p, alea):
            partis.append((p, "s'en va, découragé" if p.sexe == "h" else "s'en va, découragée"))

    for p, raison in partis:
        etat.journal.noter(etat.jour, f"{p.nom} {raison}.", "drame")
        if raison.startswith("meurt"):
            demographie._retirer(etat, p)
        else:
            etat.personnes.remove(p)
            _detacher(etat, p)


def _veut_partir(etat: Etat, p: Personne, alea: random.Random) -> bool:
    """On ne part pas d'un coup, et on ne laisse pas ses enfants derrière soi."""
    if not p.adulte or p.moral > 6 or etat.population <= 2:
        return False
    if any(e.id in p.enfants and e.enfant for e in etat.personnes):
        return False
    if p.grossesse is not None:
        return False
    return alea.random() < 0.12


def _detacher(etat: Etat, p: Personne) -> None:
    for autre in etat.personnes:
        if autre.partenaire == p.id:
            autre.partenaire = None
        if autre.autre_parent == p.id:
            autre.autre_parent = None


def _mettre_a_jour_cohesion(etat: Etat) -> None:
    capacite = CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance")
    tension = max(0.0, etat.population - capacite) * 0.04
    cible = min(1.0, 0.75 + effet_total(etat, "cohesion") - tension
                + (etat.moyenne("moral") - 60) / 300)
    etat.cohesion += (max(0.05, cible) - etat.cohesion) * 0.08
    etat.cohesion = round(max(0.0, min(1.0, etat.cohesion)), 4)
    if etat.batiment("conseil"):
        etat.gouvernance = "conseil"
    elif etat.batiment("place"):
        etat.gouvernance = "assemblée"
    else:
        etat.gouvernance = "fondateur"


def _faire_murir(etat: Etat) -> None:
    """Vergers et forêts mettent des années à donner."""
    for parcelle in etat.territoire.parcelles:
        if parcelle.type in ("verger", "foret") and parcelle.maturite < 1.0:
            parcelle.maturite = round(min(1.0, parcelle.maturite + 1 / 1095), 4)


EVENEMENTS = [
    ("secheresse", "été", 0.012, "Sécheresse : les réserves d'eau fondent."),
    ("tempete", "automne", 0.010, "Tempête : des dégâts sur les constructions."),
    ("gel", "printemps", 0.010, "Gel tardif : une partie des semis est perdue."),
    ("maladie", None, 0.006, "Une fièvre traverse le lieu."),
    ("recolte", "automne", 0.020, "Récolte exceptionnelle."),
    ("visiteur", None, 0.010, "Des voyageurs de passage laissent du matériel."),
]


def _evenement(etat: Etat, alea: random.Random) -> None:
    for cle, saison, probabilite, texte in EVENEMENTS:
        if saison and etat.saison != saison:
            continue
        if alea.random() >= probabilite:
            continue
        genre = "alerte"
        if cle == "secheresse":
            etat.stocks["eau"] *= 0.35
        elif cle == "tempete":
            etat.stocks["planches"] *= 0.8
            for chantier in etat.chantiers:
                chantier.travail_fait *= 0.75
        elif cle == "gel":
            etat.stocks["nourriture"] *= 0.7
        elif cle == "maladie":
            for p in etat.personnes:
                p.sante = max(1.0, p.sante - alea.uniform(8, 25))
        elif cle == "recolte":
            etat.stocks["nourriture"] *= 1.5
            genre = "bonne"
        elif cle == "visiteur":
            etat.stocks["recup"] += 25
            etat.stocks["outils"] += 1
            genre = "bonne"
        etat.journal.noter(etat.jour, texte, genre)
        return


def _dire_une_fois(etat: Etat, cle: str, delai: int, texte: str, genre: str = "alerte") -> None:
    if etat.jour - etat.alertes.get(cle, -999) >= delai:
        etat.alertes[cle] = etat.jour
        etat.journal.noter(etat.jour, texte, genre)


def _alerter(etat: Etat, delai: int = 20) -> None:
    """Prévient le joueur des situations critiques, sans noyer le journal."""
    def dire(cle: str, texte: str, genre: str = "alerte") -> None:
        if etat.jour - etat.alertes.get(cle, -999) >= delai:
            etat.alertes[cle] = etat.jour
            etat.journal.noter(etat.jour, texte, genre)

    if etat.stocks["nourriture"] <= 0 and etat.population:
        dire("faim", "Les réserves de nourriture sont vides. On mange moins que nécessaire.")
    if etat.stocks["eau"] <= 0 and etat.population:
        dire("soif", "Plus d'eau stockée. Il faut aller la chercher, ou la capter.")
    if etat.population and eau_apport_jour(etat) < eau_besoin_jour(etat):
        manque = round(eau_besoin_jour(etat) - eau_apport_jour(etat))
        dire("debit_eau",
             f"Ce qui arrive naturellement ne couvre plus les besoins : {manque} litres manquent "
             "chaque jour. Il faut porter l'eau, ou capter la source.", "alerte")
    if etat.population and etat.moyenne("sante") < 45:
        dire("sante", "La santé du groupe se dégrade sérieusement.")
    if etat.population and etat.moyenne("moral") < 25:
        dire("moral", "Le moral est au plus bas. Quelqu'un finira par partir.")
    if effet_total(etat, "abri") < etat.population:
        dire("abri", "Il n'y a pas assez d'abri pour tout le monde.")
    if etat.saison == "automne" and etat.stocks["nourriture"] < etat.population * 40:
        dire("hiver", "L'hiver approche et les réserves ne suffiront pas. Stockez.", "alerte")
    if etat.population > CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance"):
        dire("coordination",
             "Le groupe est trop grand pour se coordonner ainsi : chacun travaille moins bien.",
             "alerte")


def _verifier_fin(etat: Etat) -> None:
    if not etat.personnes:
        etat.termine = "La société s'est éteinte."
        etat.journal.noter(etat.jour, etat.termine, "drame")


def _enregistrer_historique(etat: Etat) -> None:
    etat.historique.append({
        "jour": etat.jour,
        "population": etat.population,
        "nourriture": round(etat.stocks["nourriture"], 1),
        "eau": round(etat.stocks["eau"], 0),
        "moral": round(etat.moyenne("moral"), 1),
        "sante": round(etat.moyenne("sante"), 1),
        "cohesion": round(etat.cohesion, 3),
        "batiments": sum(etat.batiments.values()),
        "hectares": round(etat.territoire.hectares_amenages, 2),
        "enfants": sum(1 for p in etat.personnes if p.enfant),
        "naissances": etat.demographie["naissances"],
        "deces": etat.demographie["deces"],
        "age_moyen": round(etat.moyenne("age"), 1),
        "tresor": round(etat.tresor, 1),
        "inegalite": marche.inegalite(etat),
    })
    del etat.historique[:-4000]


def capacite_grenier(etat: Etat) -> float:
    """Ce que la société peut conserver : les foyers, plus les caves et les hangars."""
    return (STOCK_NOURRITURE_BASE + STOCK_PAR_PERSONNE * etat.population
            + effet_total(etat, "stock_max"))


def capacites(etat: Etat) -> dict[str, float]:
    """Plafonds de stockage, ressource par ressource.

    Ce qui dort dehors pourrit ou se disperse : les hangars et les caves
    (effet « stock_max ») repoussent ces plafonds.
    """
    n = etat.population
    abrite = effet_total(etat, "stock_max")
    return {
        "nourriture": capacite_grenier(etat),
        "eau": (EAU_BASE_MAX + EAU_PAR_PERSONNE * etat.population
                + effet_total(etat, "eau_max")),
        "electricite": effet_total(etat, "elec_max"),
        "outils": 3.0 + 2.0 * n,
        "recup": 200.0 + 60.0 * n + abrite,
        "bois": 40.0 + 12.0 * n + abrite / 4,
        "planches": 60.0 + 25.0 * n + abrite / 2,
        "pierre": 30.0 + 10.0 * n + abrite / 8,
        "terre": 60.0 + 20.0 * n + abrite / 8,
        "compost": 20.0 + 8.0 * n,
    }


def eau_apport_jour(etat: Etat) -> float:
    """Ce qui rentre chaque jour sans aller le chercher : ruisseau, source, captage."""
    return EAU_NATURELLE + effet_total(etat, "eau_jour")


def eau_besoin_jour(etat: Etat) -> float:
    return sum(0.6 if p.enfant else 1.0 for p in etat.personnes) * BESOIN_EAU


def apercu(etat: Etat) -> dict[str, Any]:
    """Quelques indicateurs utiles à l'affichage."""
    besoin = sum(p.part_ration() for p in etat.personnes) * BESOIN_NOURRITURE
    return {
        "autonomie_nourriture_jours": round(etat.stocks["nourriture"] / besoin, 1) if besoin else 0,
        "autonomie_eau_jours": round(etat.stocks["eau"] / eau_besoin_jour(etat), 1)
        if etat.population else 0,
        "eau_apport_jour": round(eau_apport_jour(etat)),
        "eau_besoin_jour": round(eau_besoin_jour(etat)),
        "eau_deficit": round(eau_besoin_jour(etat) - eau_apport_jour(etat)),
        "grenier": round(capacite_grenier(etat)),
        "capacites": {c: round(v) for c, v in capacites(etat).items()},
        "flux": etat.flux,
        "abri": effet_total(etat, "abri"),
        "confort": effet_total(etat, "confort"),
        "capacite_gouvernance": CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance"),
        "coordination": round(coordination(etat), 3),
        "eau_max": capacites(etat)["eau"],
        "elec_max": effet_total(etat, "elec_max"),
        "naissances": etat.demographie["naissances"],
        "deces": etat.demographie["deces"],
        "couples": sum(1 for p in etat.personnes if p.partenaire is not None) // 2,
        "risques": {
            p.id: round(demographie.risque_annuel(etat, p) * 100, 2) for p in etat.personnes
        },
        # rendement de chacun sur chaque tâche : sert à choisir qui redéployer
        "intendance": intendance.resume(etat) if etat.personnes else {},
        "chantiers_max": etat.chantiers_max,
        "savoirs": savoirs.resume(etat),
        "metiers": metiers.resume(etat),
        "marche": marche.resume(etat),
        "productivite": {
            nom: round(multiplicateur(etat, f"rendement_{nom}"), 2)
            for nom in ("agricole", "bois", "pierre", "construction", "artisanat", "eau")
        },
        "rendements": {
            p.id: {t: round(p.efficacite(t), 3) for t in TACHE_COMPETENCE if t != "repos"}
            for p in etat.personnes if not p.enfant
        },
    }
