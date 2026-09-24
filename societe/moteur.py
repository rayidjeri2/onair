"""Moteur de la simulation : une journée de la société à chaque pas.

Tout est déterministe à graine fixée. Les constantes sont regroupées en tête
de fichier pour pouvoir être ajustées sans relire la logique.
"""

from __future__ import annotations

import random
from typing import Any

from .catalogue import MODELES, effet_total
from .modele import (
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
EAU_BASE_MAX = 400.0          # ce qu'on peut stocker sans réservoir
EAU_NATURELLE = 70.0          # le ruisseau : de quoi tenir seul, pas à plusieurs
PORTIONS_PAR_JOUR_HOMME = 4.2
CUEILLETTE_PAR_JOUR_HOMME = 3.0  # ce que rend la cueillette, sans parcelle
PORTIONS_MAX_PAR_HECTARE = 8.0
BOIS_PAR_JOUR_HOMME = 1.2
PIERRE_PAR_JOUR_HOMME = 0.6
TERRE_PAR_JOUR_HOMME = 2.0
PLANCHES_PAR_STERE = 6.0
EAU_PORTEE_PAR_JOUR_HOMME = 140.0
GASPILLAGE_NOURRITURE = 0.018  # part des stocks perdue chaque jour
CAPACITE_GOUVERNANCE_BASE = 5.0

SAISON_RENDEMENT = {"printemps": 1.0, "été": 1.35, "automne": 1.15, "hiver": 0.2}
SAISON_SOLEIL = {"printemps": 1.0, "été": 1.3, "automne": 0.75, "hiver": 0.45}
SAISON_TEMPERATURE = {"printemps": 14.0, "été": 24.0, "automne": 13.0, "hiver": 4.0}
SAISON_PLUIE = {"printemps": 0.45, "été": 0.12, "automne": 0.5, "hiver": 0.55}

PRENOMS = [
    "Ana", "Iris", "Tomas", "Noa", "Lior", "Kaya", "Sacha", "Mila", "Yann", "Zoé",
    "Ilan", "Nour", "Ewen", "Lina", "Basile", "Maya", "Théo", "Alba", "Ruben", "Sol",
]


# --- création -------------------------------------------------------------

def creer_societe(nom_fondateur: str = "Ana", age: int = 30, graine: int = 1) -> Etat:
    """Jour 0 : une personne débarque sur un million de km² de terre vierge."""
    etat = Etat(graine=graine, territoire=Territoire(km2=1_000_000.0))
    fondateur = Personne(
        id=1, nom=nom_fondateur.strip() or "Ana", age=age, arrivee=0,
        competences={c: 0.15 for c in COMPETENCES},
        tache="nourriture",
        histoire="Arrivée seule, sans rien d'autre que ses mains.",
    )
    fondateur.competences["construction"] = 0.3
    fondateur.competences["agriculture"] = 0.25
    etat.personnes.append(fondateur)
    etat.prochain_id_personne = 2
    etat.stocks.update({"nourriture": 30.0, "eau": 300.0, "outils": 1.0})
    etat.territoire.ajouter("friche", 100.0)
    etat.territoire.ajouter("foret", 40.0)
    etat.journal = Journal()
    etat.journal.noter(0, f"{fondateur.nom} pose son sac. Un million de kilomètres carrés, "
                          "personne d'autre, et tout à faire.", "jalon")
    _mettre_a_jour_meteo(etat, random.Random(graine))
    _enregistrer_historique(etat)
    return etat


# --- actions du joueur ----------------------------------------------------

def ajouter_personne(etat: Etat, nom: str, age: int, specialite: str,
                     histoire: str = "") -> Personne:
    if specialite not in COMPETENCES:
        raise ValueError(f"spécialité inconnue : {specialite}")
    if not 1 <= age <= 100:
        raise ValueError("âge invalide")
    p = Personne(
        id=etat.prochain_id_personne,
        nom=nom.strip() or random.Random(etat.jour).choice(PRENOMS),
        age=age,
        arrivee=etat.jour,
        competences={c: 0.12 for c in COMPETENCES},
        tache="construction" if etat.chantier else "nourriture",
        histoire=histoire,
    )
    p.competences[specialite] = 0.55
    if age < 14:
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


def affecter(etat: Etat, id_personne: int, tache: str) -> None:
    if tache not in TACHE_COMPETENCE:
        raise ValueError(f"tâche inconnue : {tache}")
    p = etat.personne(id_personne)
    if p is None:
        raise ValueError("personne inconnue")
    p.tache = tache


def lancer_chantier(etat: Etat, cle: str) -> Chantier:
    if etat.chantier is not None:
        raise ValueError("un chantier est déjà en cours")
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
    etat.chantier = Chantier(cle=cle, nom=modele.nom, travail_requis=modele.travail,
                             materiaux=dict(modele.materiaux), materiaux_livres=True)
    etat.journal.noter(etat.jour, f"Chantier ouvert : {modele.nom}.", "chantier")
    return etat.chantier


def annuler_chantier(etat: Etat) -> None:
    if etat.chantier is None:
        return
    for ressource, quantite in etat.chantier.materiaux.items():
        etat.stocks[ressource] = etat.stocks.get(ressource, 0.0) + quantite * 0.6
    etat.journal.noter(etat.jour, f"Chantier abandonné : {etat.chantier.nom}. "
                                  "Une partie des matériaux est récupérée.", "alerte")
    etat.chantier = None


# --- déroulement d'une journée -------------------------------------------

def avancer(etat: Etat, jours: int = 1) -> Etat:
    for _ in range(max(1, jours)):
        if etat.termine:
            break
        _un_jour(etat)
    return etat


def _un_jour(etat: Etat) -> None:
    etat.jour += 1
    alea = random.Random(etat.graine * 1_000_003 + etat.jour)
    _mettre_a_jour_meteo(etat, alea)

    travail = _repartir_travail(etat)
    _produire(etat, travail, alea)
    _avancer_chantier(etat, travail)
    _consommer(etat)
    _mettre_a_jour_personnes(etat, travail)
    _mettre_a_jour_cohesion(etat)
    _faire_murir(etat)
    _alerter(etat)
    _evenement(etat, alea)
    _verifier_fin(etat)
    _enregistrer_historique(etat)


def _mettre_a_jour_meteo(etat: Etat, alea: random.Random) -> None:
    saison = etat.saison
    base = SAISON_TEMPERATURE[saison]
    temperature = base + alea.gauss(0, 4)
    pluie = 0.0
    if alea.random() < SAISON_PLUIE[saison]:
        pluie = abs(alea.gauss(6, 5))
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


def coordination(etat: Etat) -> float:
    """Au-delà de ce que la gouvernance peut tenir, chaque personne coûte."""
    capacite = CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance")
    surcharge = max(0.0, etat.population - capacite)
    return 1.0 / (1.0 + 0.075 * surcharge) * (0.75 + 0.25 * etat.cohesion)


def _repartir_travail(etat: Etat) -> dict[str, float]:
    """Jours-homme effectifs par tâche, après coordination."""
    facteur = coordination(etat)
    travail: dict[str, float] = {t: 0.0 for t in TACHE_COMPETENCE}
    for p in etat.personnes:
        if p.tache == "repos":
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
    eau_max = EAU_BASE_MAX + effet_total(etat, "eau_max")
    captage = 1.0 + effet_total(etat, "captage")
    s["eau"] += etat.meteo.pluie * 12.0 * captage
    s["eau"] += EAU_NATURELLE + effet_total(etat, "eau_jour")
    s["eau"] += travail["eau"] * EAU_PORTEE_PAR_JOUR_HOMME
    s["eau"] = min(eau_max, s["eau"])

    # --- nourriture
    rendement = 1.0 + effet_total(etat, "rendement")
    saisonnier = SAISON_RENDEMENT[saison]
    if saison == "hiver":
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
    cueillette = travail["nourriture"] * CUEILLETTE_PAR_JOUR_HOMME * saisonnier * sauvage
    recolte = cultive + cueillette
    passif = effet_total(etat, "nourriture_jour")
    passif += etat.territoire.surface_productive("verger") * 2.2 * saisonnier
    s["nourriture"] += recolte + passif

    # --- bois, pierre, terre
    foret = etat.territoire.surface("foret")
    dispo_bois = min(1.0, foret / max(1.0, etat.population * 4))
    s["bois"] += travail["bois"] * BOIS_PAR_JOUR_HOMME * dispo_bois
    s["pierre"] += travail["pierre"] * PIERRE_PAR_JOUR_HOMME
    s["terre"] += travail["pierre"] * TERRE_PAR_JOUR_HOMME

    # --- artisanat : le bois devient planches, on fabrique des outils
    ratio = 1.0 + effet_total(etat, "planches_ratio")
    artisanat = travail["artisanat"] * (1.0 + effet_total(etat, "artisanat"))
    steres = min(s["bois"], artisanat * 0.8)
    s["bois"] -= steres
    s["planches"] += steres * PLANCHES_PAR_STERE * ratio / 2.0
    s["planches"] += effet_total(etat, "planches_jour")
    s["outils"] += effet_total(etat, "outils_jour") + artisanat * 0.02
    s["recup"] += effet_total(etat, "recup_jour") + 0.4

    # --- compost et électricité
    s["compost"] += effet_total(etat, "compost_jour") + travail["nourriture"] * 0.01
    elec_max = effet_total(etat, "elec_max")
    production_elec = (effet_total(etat, "solaire") * SAISON_SOLEIL[saison]
                       + effet_total(etat, "eolien") * (0.6 + alea.random() * 0.8))
    s["electricite"] = min(elec_max, s["electricite"] + production_elec)

    # --- pertes
    conservation = min(0.8, effet_total(etat, "conservation"))
    s["nourriture"] *= 1.0 - GASPILLAGE_NOURRITURE * (1.0 - conservation)
    for cle in s:
        s[cle] = max(0.0, round(s[cle], 3))


def _avancer_chantier(etat: Etat, travail: dict[str, float]) -> None:
    if etat.chantier is None:
        return
    outils = 1.0 + min(0.3, etat.stocks.get("outils", 0.0) * 0.04)
    logistique = 1.0 + effet_total(etat, "logistique")
    etat.chantier.travail_fait += travail["construction"] * outils * logistique
    if etat.chantier.travail_fait >= etat.chantier.travail_requis:
        _terminer_chantier(etat)


def _terminer_chantier(etat: Etat) -> None:
    chantier = etat.chantier
    assert chantier is not None
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
    etat.chantier = None


def _consommer(etat: Etat) -> None:
    s = etat.stocks
    population = etat.population
    besoin = population * BESOIN_NOURRITURE
    s["nourriture"] -= besoin
    etat.en_peril = s["nourriture"] < 0
    ration = 1.0 if s["nourriture"] >= 0 else max(0.0, 1.0 + s["nourriture"] / max(besoin, 1e-9))
    s["nourriture"] = max(0.0, s["nourriture"])

    besoin_eau = population * BESOIN_EAU
    s["eau"] -= besoin_eau
    soif = s["eau"] < 0
    s["eau"] = max(0.0, s["eau"])

    if etat.saison in ("hiver", "automne"):
        economie = 1.0 - min(0.6, effet_total(etat, "isolation") * 0.12
                             + effet_total(etat, "bois_economie") * 0.2)
        s["bois"] = max(0.0, s["bois"] - population * 0.07 * economie)

    s["electricite"] = max(0.0, s["electricite"] - population * 0.35)
    etat._ration = ration  # type: ignore[attr-defined]
    etat._soif = soif  # type: ignore[attr-defined]


def _mettre_a_jour_personnes(etat: Etat, travail: dict[str, float]) -> None:
    ration = getattr(etat, "_ration", 1.0)
    soif = getattr(etat, "_soif", False)
    abri = effet_total(etat, "abri")
    confort = effet_total(etat, "confort")
    salubrite = effet_total(etat, "salubrite")
    soin = travail["soin"] * (1.0 + effet_total(etat, "soin"))
    enseignement = travail["enseignement"] * (1.0 + effet_total(etat, "enseignement"))
    froid = etat.meteo.temperature < 5 and etat.stocks["bois"] <= 0.5
    abrite = abri >= etat.population
    partis = []

    for p in etat.personnes:
        # énergie : le repos recharge, le travail use
        if p.tache == "repos" or p.energie < 18:
            # sous un certain seuil, le corps impose le repos
            p.energie = min(100.0, p.energie + 22.0)
        else:
            p.energie = max(0.0, p.energie - 12.0 + (9.0 if abrite else 3.0)
                            + 6.0 * ration + min(6.0, soin * 3.0))
            p.energie = min(100.0, p.energie)

        # santé
        delta = 0.0
        delta += 1.6 if ration >= 1.0 else -7.0 * (1.0 - ration)
        delta += -6.0 if soif else 0.4
        delta += salubrite * 0.12 - 0.6
        delta += -3.0 if froid else 0.0
        delta += min(4.0, soin * 2.5)
        delta += -1.2 if not abrite else 0.0
        delta -= max(0.0, (p.age - 65)) * 0.05
        p.sante = max(0.0, min(100.0, p.sante + delta))

        # moral : on tend vers un niveau cible plutôt que d'accumuler
        cible = 45.0
        cible += min(18.0, confort * 0.5)
        cible += 12.0 * (etat.cohesion - 0.5)
        cible += min(12.0, effet_total(etat, "variete") * 0.35)
        cible -= 45.0 * (1.0 - ration)
        cible += 6.0 if abrite else -9.0
        cible += 5.0 if p.energie > 55 else -8.0
        cible += 4.0 if etat.population > 1 else -9.0  # la solitude pèse
        cible += 3.0 if etat.chantier else -3.0  # avoir un cap commun
        p.moral = max(0.0, min(100.0, p.moral + (cible - p.moral) * 0.12))

        # apprentissage : par la pratique, et par l'enseignement des autres
        comp = TACHE_COMPETENCE.get(p.tache)
        if comp:
            p.competences[comp] = min(1.0, p.competences[comp] + 0.0022 * (1.1 - p.competences[comp]))
        if enseignement and etat.population > 1:
            gain = 0.0016 * enseignement / etat.population
            for c in COMPETENCES:
                p.competences[c] = min(1.0, p.competences[c] + gain)

        if etat.jour % 365 == 0:
            p.age += 1

        if p.sante <= 0:
            partis.append((p, "meurt"))
        elif p.moral <= 4 and etat.population > 1:
            partis.append((p, "s'en va"))

    for p, raison in partis:
        etat.personnes.remove(p)
        etat.journal.noter(etat.jour, f"{p.nom} {raison}.", "drame")


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
            if etat.chantier:
                etat.chantier.travail_fait *= 0.75
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
    })
    del etat.historique[:-4000]


def apercu(etat: Etat) -> dict[str, Any]:
    """Quelques indicateurs utiles à l'affichage."""
    besoin = etat.population * BESOIN_NOURRITURE
    return {
        "autonomie_nourriture_jours": round(etat.stocks["nourriture"] / besoin, 1) if besoin else 0,
        "autonomie_eau_jours": round(etat.stocks["eau"] / (etat.population * BESOIN_EAU), 1)
        if etat.population else 0,
        "abri": effet_total(etat, "abri"),
        "confort": effet_total(etat, "confort"),
        "capacite_gouvernance": CAPACITE_GOUVERNANCE_BASE + effet_total(etat, "gouvernance"),
        "coordination": round(coordination(etat), 3),
        "eau_max": EAU_BASE_MAX + effet_total(etat, "eau_max"),
        "elec_max": effet_total(etat, "elec_max"),
    }
