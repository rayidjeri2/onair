"""Démographie : couples, grossesses, naissances, enfance, vieillissement, décès.

Les paramètres visent des ordres de grandeur pré-industriels : beaucoup
d'enfants, une mortalité infantile réelle, une espérance de vie qui dépend
directement de ce que la société a construit (dispensaire, salubrité, vivres).
"""

from __future__ import annotations

import math
import random

from .catalogue import effet_total
from .modele import (
    AGE_ADULTE,
    AGE_TRAVAIL,
    COMPETENCES,
    GESTATION,
    Etat,
    Personne,
)

PROBA_COUPLE_JOUR = 0.010        # par paire compatible et par jour
PROBA_CONCEPTION_JOUR = 0.011    # par femme fertile en couple, conditions idéales
PROBA_FAUSSE_COUCHE = 0.0035     # par jour, quand la santé est basse
RISQUE_ACCOUCHEMENT = 0.020      # décès maternel, sans dispensaire
MORTALITE_BASE = 0.00055         # risque annuel de référence à 30 ans
MORTALITE_PENTE = 0.082          # croissance exponentielle avec l'âge
MORTALITE_PETITE_ENFANCE = 0.075  # risque annuel avant 2 ans, sans rien

# Registre de noms d'inspiration éthiopienne : prénoms courants et noms de lieux.
PRENOMS_F = [
    "Abeba", "Alem", "Almaz", "Aster", "Ayana", "Azeb", "Birtukan", "Desta", "Edna",
    "Fanta", "Gelila", "Hana", "Hirut", "Kidist", "Lensa", "Makeda", "Marta", "Meron",
    "Mulu", "Nardos", "Rahel", "Saba", "Selam", "Semira", "Senait", "Tigist", "Tirhas",
    "Wubet", "Yodit", "Zala", "Zewditu", "Adwa", "Abeeba", "Lalibela", "Sheba",
]
PRENOMS_H = [
    "Abel", "Abera", "Addis", "Amanuel", "Ayele", "Bekele", "Berhanu", "Chala", "Dawit",
    "Endale", "Fikru", "Gebre", "Girma", "Haile", "Kebede", "Lemma", "Mekonnen", "Mulugeta",
    "Nahom", "Robel", "Samson", "Solomon", "Tadesse", "Tesfaye", "Tewodros", "Workneh",
    "Yared", "Yohannes", "Zeleke", "Afar", "Ameesh", "Gonder", "Harar", "Shewa",
]

# D'où viennent celles et ceux qui arrivent — piochées au hasard.
ARRIVEES = [
    "a marché trois semaines pour arriver ici",
    "a suivi la rivière jusqu'à voir de la fumée",
    "a débarqué avec une caisse d'outils et rien d'autre",
    "a entendu parler du lieu par des voyageurs",
    "cherchait une terre où l'on ne doit rien à personne",
    "a quitté la ville sans prévenir personne",
    "connaît les plantes et les saisons mieux que quiconque",
    "a passé l'hiver ici, puis n'est jamais reparti",
    "a traversé les hauts plateaux à pied",
    "ne dit pas d'où elle ou il vient",
    "vient d'un village qui n'avait plus d'eau",
    "a promis de ne rester qu'une saison",
    "voulait apprendre à bâtir de ses mains",
    "a frappé à la porte un soir de tempête",
]

def passer_le_jour(etat: Etat, alea: random.Random) -> None:
    """Toute la démographie d'une journée, dans l'ordre de la vie."""
    _vieillir(etat)
    _eduquer(etat)
    _former_les_couples(etat, alea)
    _concevoir(etat, alea)
    _porter(etat, alea)
    _mourir(etat, alea)


# --- âge et enfance -------------------------------------------------------

def _vieillir(etat: Etat) -> None:
    for p in etat.personnes:
        if etat.jour_annee == p.anniversaire and etat.jour > 0:
            p.age += 1
            if p.age == AGE_TRAVAIL:
                p.tache = "nourriture"
                etat.journal.noter(
                    etat.jour,
                    f"{p.nom} a {AGE_TRAVAIL} ans et prend sa part du travail.", "jalon")


def _eduquer(etat: Etat) -> None:
    """Les enfants apprennent : par l'école si elle existe, sinon en regardant faire."""
    ecole = effet_total(etat, "enseignement")
    enseignants = sum(1 for p in etat.personnes if p.tache == "enseignement")
    if not any(p.enfant for p in etat.personnes):
        return
    intensite = 0.0009 * (1.0 + ecole) * (1.0 + 0.6 * enseignants)
    for p in etat.personnes:
        if not p.enfant or p.age < 5:
            continue
        # un enfant hérite surtout de ce que ses parents savent faire
        modeles = [q for q in etat.personnes if q.id in p.parents] or etat.personnes
        for competence in COMPETENCES:
            reference = max((q.competences.get(competence, 0.0) for q in modeles), default=0.0)
            if p.competences.get(competence, 0.0) < reference:
                p.competences[competence] = min(
                    reference, p.competences.get(competence, 0.0) + intensite)


# --- couples --------------------------------------------------------------

def _apparentes(a: Personne, b: Personne) -> bool:
    """Interdit les couples entre parent et enfant, et entre frères et sœurs."""
    if a.id in b.parents or b.id in a.parents:
        return True
    return bool(set(a.parents) & set(b.parents)) and bool(a.parents)


def _former_les_couples(etat: Etat, alea: random.Random) -> None:
    libres = [p for p in etat.personnes if p.adulte and p.partenaire is None]
    femmes = [p for p in libres if p.sexe == "f"]
    hommes = [p for p in libres if p.sexe == "h"]
    if not femmes or not hommes:
        return
    for femme in femmes:
        candidats = [h for h in hommes
                     if h.partenaire is None
                     and not _apparentes(femme, h)
                     and abs(h.age - femme.age) <= 20]
        if not candidats:
            continue
        # un groupe qui va bien et qui se voit forme plus facilement des couples
        chance = PROBA_COUPLE_JOUR * etat.cohesion * (etat.moyenne("moral") / 60)
        if alea.random() >= min(0.08, chance):
            continue
        homme = alea.choice(candidats)
        femme.partenaire, homme.partenaire = homme.id, femme.id
        etat.demographie["couples_formes"] += 1
        etat.journal.noter(etat.jour, f"{femme.nom} et {homme.nom} se mettent ensemble.", "bonne")


# --- conception et grossesse ---------------------------------------------

def _concevoir(etat: Etat, alea: random.Random) -> None:
    desir = etat.politique.get("natalite", 0.5) * 2.0  # 0 = aucun enfant, 2 = autant que possible
    if desir <= 0:
        return
    vivres = etat.stocks["nourriture"] / max(1.0, etat.population)
    abri_libre = effet_total(etat, "abri") - etat.population
    for mere in etat.personnes:
        if not mere.fertile or mere.grossesse is not None or mere.partenaire is None:
            continue
        petits = sum(1 for e in etat.personnes if e.id in mere.enfants and e.age < 5)
        chance = PROBA_CONCEPTION_JOUR * desir
        chance *= mere.sante / 100.0
        chance *= min(1.0, 0.4 + mere.moral / 100.0)
        chance *= min(1.5, 0.3 + vivres / 20.0)       # on ne fait pas d'enfant à jeun
        chance *= 1.0 if abri_libre >= 1 else 0.45    # ni sans place pour le coucher
        chance *= 0.55 ** petits                      # la charge des tout-petits freine
        chance *= max(0.15, 1.0 - (mere.age - 32) / 26) if mere.age > 32 else 1.0
        if alea.random() < max(0.0, chance):
            mere.grossesse = 0
            mere.autre_parent = mere.partenaire
            etat.journal.noter(etat.jour, f"{mere.nom} attend un enfant.", "bonne")


def _porter(etat: Etat, alea: random.Random) -> None:
    for mere in list(etat.personnes):
        if mere.grossesse is None:
            continue
        mere.grossesse += 1
        if mere.sante < 45 and alea.random() < PROBA_FAUSSE_COUCHE:
            mere.grossesse = None
            mere.autre_parent = None
            mere.moral = max(0.0, mere.moral - 18)
            etat.journal.noter(etat.jour, f"{mere.nom} perd l'enfant qu'elle attendait.", "drame")
            continue
        if mere.grossesse >= GESTATION:
            _accoucher(etat, mere, alea)


def prenom_libre(etat: Etat, sexe: str, alea: random.Random) -> str:
    pris = {p.nom for p in etat.personnes}
    pool = [n for n in (PRENOMS_F if sexe == "f" else PRENOMS_H) if n not in pris]
    if pool:
        return alea.choice(pool)
    base = alea.choice(PRENOMS_F if sexe == "f" else PRENOMS_H)
    return f"{base} {alea.randint(2, 99)}"


def _accoucher(etat: Etat, mere: Personne, alea: random.Random) -> None:
    mere.grossesse = None
    pere_id = mere.autre_parent
    mere.autre_parent = None
    soin = 1.0 - min(0.8, effet_total(etat, "soin") + effet_total(etat, "salubrite") / 40)
    sexe = "f" if alea.random() < 0.5 else "h"

    if alea.random() < RISQUE_ACCOUCHEMENT * soin * (1.4 if mere.sante < 55 else 1.0):
        etat.journal.noter(etat.jour, f"{mere.nom} meurt en couches.", "drame")
        _retirer(etat, mere)
        if alea.random() < 0.5:
            return  # l'enfant ne survit pas non plus
    else:
        mere.sante = max(25.0, mere.sante - 12)
        mere.moral = min(100.0, mere.moral + 10)

    enfant = Personne(
        id=etat.prochain_id_personne,
        nom=prenom_libre(etat, sexe, alea),
        age=0,
        arrivee=etat.jour,
        competences={c: 0.0 for c in COMPETENCES},
        tache="repos",
        energie=100.0, sante=100.0, moral=75.0,
        sexe=sexe,
        parents=[i for i in (mere.id, pere_id) if i is not None],
        nee_ici=True,
        anniversaire=etat.jour_annee,
        polyvalence=round(min(1.0, max(0.0, alea.gauss(
            (mere.polyvalence + (etat.personne(pere_id).polyvalence
                                 if etat.personne(pere_id) else mere.polyvalence)) / 2, 0.18))), 2),
        histoire=f"né ici le {etat.jour_annee + 1}e jour de l'an {etat.annee}"
        if sexe == "h" else f"née ici le {etat.jour_annee + 1}e jour de l'an {etat.annee}",
    )
    etat.prochain_id_personne += 1
    etat.personnes.append(enfant)
    etat.demographie["naissances"] += 1
    for parent_id in enfant.parents:
        parent = etat.personne(parent_id)
        if parent:
            parent.enfants.append(enfant.id)
    etat.journal.noter(
        etat.jour,
        f"Naissance de {enfant.nom}. La société compte {etat.population} personnes.",
        "naissance")


# --- mortalité ------------------------------------------------------------

def risque_annuel(etat: Etat, p: Personne) -> float:
    """Probabilité de mourir dans l'année, selon l'âge et les conditions."""
    if p.age < 2:
        base = MORTALITE_PETITE_ENFANCE
    else:
        base = MORTALITE_BASE * math.exp(MORTALITE_PENTE * (p.age - 30))
    fragilite = 1.0 + max(0.0, 70.0 - p.sante) / 22.0
    secours = 1.0 - min(0.65, effet_total(etat, "soin") * 0.35
                        + effet_total(etat, "salubrite") * 0.012)
    return min(0.95, base * fragilite * secours)


def _mourir(etat: Etat, alea: random.Random) -> None:
    for p in list(etat.personnes):
        if alea.random() < risque_annuel(etat, p) / 365.0:
            cause = "de maladie" if p.age < 55 else "de vieillesse"
            if p.age < 2:
                cause = "en bas âge"
            etat.journal.noter(etat.jour, f"{p.nom} meurt {cause}, à {p.age} ans.", "drame")
            _retirer(etat, p)


def _retirer(etat: Etat, p: Personne) -> None:
    """Retire une personne et dénoue ses liens, en comptant le décès."""
    if p not in etat.personnes:
        return
    etat.personnes.remove(p)
    etat.demographie["deces"] += 1
    etat.demographie["ages_au_deces"] += p.age
    for autre in etat.personnes:
        if autre.partenaire == p.id:
            autre.partenaire = None
            autre.moral = max(0.0, autre.moral - 22)
        if autre.autre_parent == p.id:
            autre.autre_parent = None
    orphelins = [q for q in etat.personnes if p.id in q.parents and q.enfant]
    if orphelins and etat.population:
        etat.journal.noter(
            etat.jour,
            f"{', '.join(o.nom for o in orphelins)} : le groupe prend le relais.", "alerte")
