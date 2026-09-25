"""Les découvertes : ce que la société apprend, et peut oublier.

Un savoir ne s'achète pas, il se gagne en faisant — forger longtemps finit par
donner la métallurgie. Il ouvre des constructions, améliore des rendements, et
se perd si plus personne ne le pratique et que rien ne l'a consigné.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .catalogue import effet_total
from .modele import Etat

AGES = {
    "fondations": "Premiers gestes",
    "fer": "Le fer et la roue",
    "mecanique": "La mécanique",
    "industrie": "Industrie naissante",
}


@dataclass(frozen=True)
class Savoir:
    cle: str
    nom: str
    age: str
    description: str
    cout: float                       # points de pratique à accumuler
    sources: dict[str, float]         # tâche → points par jour-homme
    population_min: int = 1           # un savoir demande une société assez grande
    prerequis: list[str] = field(default_factory=list)
    batiments: list[str] = field(default_factory=list)   # ce qu'il débloque
    effets: dict[str, float] = field(default_factory=dict)
    competence: str = ""              # compétence qui l'entretient


SAVOIRS: dict[str, Savoir] = {}


def _s(**kw) -> None:
    savoir = Savoir(**kw)
    SAVOIRS[savoir.cle] = savoir


# --- premiers gestes ------------------------------------------------------
_s(cle="vannerie", nom="Vannerie et cordage", age="fondations", cout=600,
   description="Tresser paniers, cordes et claies : tout devient plus facile à porter.",
   sources={"artisanat": 1.0, "nourriture": 0.3}, competence="artisanat",
   effets={"rendement_cueillette": 0.15, "conservation": 0.05})
_s(cle="agronomie", nom="Agronomie", age="fondations", cout=1600,
   description="Rotations, semences choisies, lecture du ciel : la terre rend davantage.",
   sources={"nourriture": 1.0}, competence="agriculture",
   effets={"rendement_agricole": 0.25})
_s(cle="charpente", nom="Charpente", age="fondations", cout=1400,
   description="Assemblages qui tiennent : on bâtit plus vite et plus grand.",
   sources={"construction": 1.0, "artisanat": 0.4}, competence="construction",
   effets={"rendement_construction": 0.2}, batiments=["moulin"])
_s(cle="hydraulique", nom="Hydraulique", age="fondations", cout=1300,
   description="Conduire l'eau, la retenir, la faire descendre toute seule.",
   sources={"eau": 1.0}, competence="eau",
   effets={"rendement_eau": 0.25}, batiments=["aqueduc"])
_s(cle="soins", nom="Art de soigner", age="fondations", cout=1400,
   description="Plantes, attelles, propreté : on meurt moins de ce qui se soigne.",
   sources={"soin": 1.2}, competence="soin", effets={"salubrite": 6})
_s(cle="ecriture", nom="Écriture", age="fondations", cout=1800, population_min=6,
   description="Consigner au lieu de se souvenir. C'est ce qui empêche d'oublier le reste.",
   sources={"enseignement": 1.2, "organisation": 0.5}, competence="enseignement",
   effets={"memoire": 1.0}, batiments=["archives"])

# --- le fer et la roue ----------------------------------------------------
_s(cle="poterie", nom="Poterie et four", age="fer", cout=2400, population_min=8,
   description="Cuire la terre : des jarres qui gardent le grain au sec.",
   sources={"artisanat": 1.0}, prerequis=["vannerie"], competence="artisanat",
   effets={"conservation": 0.12}, batiments=["four_poterie"])
_s(cle="metallurgie", nom="Métallurgie", age="fer", cout=4500, population_min=10,
   description="Tirer le métal du minerai et le travailler. Le vrai basculement technique.",
   sources={"artisanat": 1.0, "pierre": 0.4}, prerequis=["poterie"], competence="artisanat",
   effets={"rendement_outils": 0.4}, batiments=["haut_fourneau", "charrue"])
_s(cle="roue", nom="La roue", age="fer", cout=3000, population_min=8,
   description="Brouettes et charrettes : porter cesse d'être le goulot d'étranglement.",
   sources={"construction": 0.7, "artisanat": 0.7}, prerequis=["charpente"],
   competence="artisanat", effets={"logistique": 0.15}, batiments=["brouettes"])
_s(cle="traction", nom="Traction animale", age="fer", cout=3600, population_min=12,
   description="Atteler les bêtes : un homme et un bœuf labourent ce que dix ne feraient pas.",
   sources={"nourriture": 0.8, "construction": 0.3}, prerequis=["agronomie", "roue"],
   competence="agriculture", effets={"rendement_agricole": 0.3}, batiments=["attelage"])

# --- la mécanique ---------------------------------------------------------
_s(cle="engrenage", nom="Engrenages", age="mecanique", cout=6500, population_min=15,
   description="Transmettre et démultiplier la force : la machine commence ici.",
   sources={"artisanat": 1.0}, prerequis=["metallurgie", "roue"], competence="artisanat",
   effets={"rendement_artisanat": 0.3}, batiments=["metier_tisser", "scierie_hydraulique"])
_s(cle="textile", nom="Textile", age="mecanique", cout=5000, population_min=15,
   description="Filer, tisser, habiller tout le monde sans dépendre de personne.",
   sources={"artisanat": 0.8, "cuisine": 0.4}, prerequis=["engrenage"], competence="artisanat",
   effets={"confort": 10})
_s(cle="medecine", nom="Médecine", age="mecanique", cout=7000, population_min=18,
   description="Comprendre les maladies au lieu de les subir.",
   sources={"soin": 1.0, "enseignement": 0.5}, prerequis=["soins", "ecriture"],
   competence="soin", effets={"soin": 0.6, "salubrite": 10}, batiments=["hopital"])
_s(cle="comptabilite", nom="Compter et prévoir", age="mecanique", cout=5000, population_min=15,
   description="Tenir les comptes du grenier : on ne découvre plus la disette en février.",
   sources={"organisation": 1.2}, prerequis=["ecriture"], competence="organisation",
   effets={"gouvernance": 6, "conservation": 0.1})

# --- industrie naissante --------------------------------------------------
_s(cle="vapeur", nom="Machine à vapeur", age="industrie", cout=14000, population_min=25,
   description="Brûler pour produire du mouvement : la force cesse d'être humaine.",
   sources={"artisanat": 1.0, "energie": 0.8}, prerequis=["engrenage", "metallurgie"],
   competence="artisanat", effets={"rendement_artisanat": 0.4},
   batiments=["atelier_mecanise"])
_s(cle="ciment", nom="Ciment", age="industrie", cout=10000, population_min=20,
   description="Une pierre qu'on coule : bâtir vite, haut, et pour longtemps.",
   sources={"pierre": 1.0, "construction": 0.6}, prerequis=["poterie", "charpente"],
   competence="construction", effets={"rendement_construction": 0.35})
_s(cle="electricite", nom="Électricité", age="industrie", cout=18000, population_min=30,
   description="Transporter l'énergie jusque dans les ateliers et les maisons.",
   sources={"energie": 1.2, "artisanat": 0.5}, prerequis=["vapeur"], competence="energie",
   effets={"confort": 12}, batiments=["reseau_electrique"])


# --- progression ----------------------------------------------------------

POINTS_RECHERCHE = 2.4   # ce que rapporte un jour-homme consacré à chercher


def progresser(etat: Etat, travail: dict[str, float], alea: random.Random) -> None:
    """Un jour de pratique fait avancer les savoirs accessibles."""
    accessibles = [s for s in SAVOIRS.values() if _accessible(etat, s)]
    if not accessibles:
        _oublier(etat, alea)
        return

    recherche = travail.get("recherche", 0.0) * POINTS_RECHERCHE
    # la recherche se porte sur le savoir le plus avancé, la pratique sur le sien
    cibles = sorted(accessibles, key=lambda s: -etat.savoirs.get(s.cle, 0.0) / s.cout)
    for savoir in accessibles:
        gagne = sum(travail.get(tache, 0.0) * poids for tache, poids in savoir.sources.items())
        if savoir is cibles[0]:
            gagne += recherche
        if gagne <= 0:
            continue
        etat.savoirs[savoir.cle] = etat.savoirs.get(savoir.cle, 0.0) + gagne
        if etat.savoirs[savoir.cle] >= savoir.cout:
            _acquerir(etat, savoir)
    _oublier(etat, alea)


def _accessible(etat: Etat, savoir: Savoir) -> bool:
    """Un savoir demande ses prérequis — et une société assez nombreuse.

    Cinq personnes qui survivent n'inventent pas la machine à vapeur : il faut
    assez de bras dégagés de la subsistance pour que quelqu'un cherche.
    """
    if savoir.cle in etat.decouvertes:
        return False
    if etat.population < savoir.population_min:
        return False
    return all(p in etat.decouvertes for p in savoir.prerequis)


def _acquerir(etat: Etat, savoir: Savoir) -> None:
    etat.decouvertes.append(savoir.cle)
    etat.savoirs.pop(savoir.cle, None)
    etat.journal.noter(
        etat.jour,
        f"Découverte : {savoir.nom}. {savoir.description}",
        "decouverte")


def _oublier(etat: Etat, alea: random.Random) -> None:
    """Un savoir que plus personne ne pratique finit par se perdre.

    L'écriture et les archives mettent la société à l'abri de cet oubli.
    """
    if etat.memoire_ecrite:
        return
    for cle in list(etat.decouvertes):
        savoir = SAVOIRS.get(cle)
        if savoir is None or not savoir.competence:
            continue
        porteurs = sum(1 for p in etat.personnes
                       if not p.enfant and p.competences.get(savoir.competence, 0) >= 0.3)
        if porteurs == 0 and alea.random() < 0.004:
            etat.decouvertes.remove(cle)
            etat.journal.noter(
                etat.jour,
                f"Plus personne ne sait {savoir.nom.lower()} : le savoir se perd.", "drame")


def effet_savoirs(etat: Etat, nom: str) -> float:
    """Somme d'un effet sur toutes les découvertes acquises."""
    return sum(SAVOIRS[c].effets.get(nom, 0.0) for c in etat.decouvertes if c in SAVOIRS)


def batiments_debloques(etat: Etat) -> set[str]:
    debloques: set[str] = set()
    for cle in etat.decouvertes:
        savoir = SAVOIRS.get(cle)
        if savoir:
            debloques.update(savoir.batiments)
    return debloques


def resume(etat: Etat) -> dict:
    """Ce que l'interface affiche : acquis, en cours, et ce qui reste fermé."""
    en_cours = []
    for savoir in SAVOIRS.values():
        if savoir.cle in etat.decouvertes or not _accessible(etat, savoir):
            continue
        points = etat.savoirs.get(savoir.cle, 0.0)
        en_cours.append({
            "cle": savoir.cle, "nom": savoir.nom, "age": savoir.age,
            "description": savoir.description,
            "part": round(min(1.0, points / savoir.cout), 3),
            "population_min": savoir.population_min,
            "points": round(points), "cout": savoir.cout,
            "sources": list(savoir.sources),
        })
    en_cours.sort(key=lambda s: -s["part"])
    return {
        "ages": AGES,
        "acquis": [
            {"cle": c, "nom": SAVOIRS[c].nom, "age": SAVOIRS[c].age,
             "description": SAVOIRS[c].description}
            for c in etat.decouvertes if c in SAVOIRS
        ],
        "en_cours": en_cours,
        "a_venir": [
            {"cle": s.cle, "nom": s.nom, "age": s.age,
             "exige": ([SAVOIRS[p].nom for p in s.prerequis if p not in etat.decouvertes]
                       + ([f"{s.population_min} habitants"]
                          if etat.population < s.population_min else []))}
            for s in SAVOIRS.values()
            if s.cle not in etat.decouvertes and not _accessible(etat, s)
        ],
        "memoire": etat.memoire_ecrite,
    }
