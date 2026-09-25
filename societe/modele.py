"""Structures de données de la société : terre, personnes, stocks, chantiers."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

SAISONS = ["printemps", "été", "automne", "hiver"]

TACHES = {
    "nourriture": "Cultiver et récolter",
    "eau": "Aller chercher et gérer l'eau",
    "bois": "Bûcheronner",
    "pierre": "Extraire pierre et terre",
    "construction": "Travailler sur le chantier en cours",
    "artisanat": "Fabriquer planches, outils, matériaux",
    "cuisine": "Cuisiner et conserver",
    "soin": "Soigner et prendre soin",
    "enseignement": "Transmettre les savoir-faire",
    "organisation": "Coordonner le collectif",
    "repos": "Se reposer",
}

COMPETENCES = [
    "construction",
    "agriculture",
    "eau",
    "energie",
    "artisanat",
    "cuisine",
    "soin",
    "enseignement",
    "organisation",
]

TACHE_COMPETENCE = {
    "nourriture": "agriculture",
    "eau": "eau",
    "bois": "construction",
    "pierre": "construction",
    "construction": "construction",
    "artisanat": "artisanat",
    "cuisine": "cuisine",
    "soin": "soin",
    "enseignement": "enseignement",
    "organisation": "organisation",
    "repos": None,
}

RESSOURCES = {
    "nourriture": "portions-jour",
    "eau": "litres",
    "bois": "stères",
    "pierre": "tonnes",
    "terre": "m³",
    "recup": "kg récupérés",
    "compost": "m³",
    "planches": "m²",
    "outils": "lots",
    "electricite": "kWh",
}

TYPES_PARCELLE = {
    "friche": "Friche, terre non aménagée",
    "foret": "Forêt (bois, ombre, biodiversité)",
    "potager": "Potager et cultures vivrières",
    "verger": "Verger et forêt comestible",
    "pature": "Pâture pour les animaux",
    "bati": "Zone bâtie",
    "eau": "Étang, source, retenue",
}


AGE_TRAVAIL = 14        # on ne confie pas de tâche avant cet âge
AGE_ADULTE = 18
AGE_FIN_FERTILITE = 45
GESTATION = 274         # jours


@dataclass
class Personne:
    id: int
    nom: str
    age: int
    arrivee: int  # jour d'arrivée (ou de naissance)
    competences: dict[str, float] = field(default_factory=dict)
    tache: str = "construction"
    energie: float = 100.0
    sante: float = 100.0
    moral: float = 70.0
    histoire: str = ""
    jours_par_tache: dict[str, int] = field(default_factory=dict)
    # --- démographie
    sexe: str = "f"               # "f" ou "h" : simplification pour la gestation
    parents: list[int] = field(default_factory=list)
    enfants: list[int] = field(default_factory=list)
    partenaire: int | None = None
    grossesse: int | None = None  # jours de gestation écoulés
    autre_parent: int | None = None
    nee_ici: bool = False
    anniversaire: int = 0         # jour de l'année où l'âge augmente

    @property
    def enfant(self) -> bool:
        return self.age < AGE_TRAVAIL

    @property
    def adulte(self) -> bool:
        return self.age >= AGE_ADULTE

    @property
    def fertile(self) -> bool:
        return self.sexe == "f" and AGE_ADULTE <= self.age <= AGE_FIN_FERTILITE

    @property
    def classe_age(self) -> str:
        if self.age < 6:
            return "petite enfance"
        if self.age < AGE_TRAVAIL:
            return "enfance"
        if self.age < AGE_ADULTE:
            return "adolescence"
        if self.age < 60:
            return "âge actif"
        return "anciens"

    def __post_init__(self) -> None:
        for c in COMPETENCES:
            self.competences.setdefault(c, 0.1)

    @property
    def competence_principale(self) -> str:
        return max(self.competences, key=lambda c: self.competences[c])

    def part_ration(self) -> float:
        """Un enfant mange moins qu'un adulte."""
        if self.age < 5:
            return 0.4
        if self.age < AGE_TRAVAIL:
            return 0.7
        if self.age > 65:
            return 0.85
        return 1.0

    def facteur_age(self) -> float:
        """Les enfants et les anciens travaillent moins ; le pic est vers 30 ans."""
        if self.age < 14:
            return max(0.0, (self.age - 6) / 16)
        if self.age > 60:
            return max(0.25, 1.0 - (self.age - 60) / 45)
        return 1.0

    def capacite_travail(self) -> float:
        """Jours-homme effectivement disponibles aujourd'hui (0 à ~1,1)."""
        forme = (0.45 * self.energie + 0.35 * self.sante + 0.20 * self.moral) / 100
        capacite = forme * self.facteur_age()
        if self.grossesse is not None:
            capacite *= 1.0 if self.grossesse < GESTATION * 0.6 else 0.55
        return max(0.0, capacite)

    def efficacite(self, tache: str) -> float:
        """Rendement sur une tâche : compétence + habitude (spécialisation)."""
        comp = TACHE_COMPETENCE.get(tache)
        niveau = self.competences.get(comp, 0.1) if comp else 0.0
        habitude = min(0.25, self.jours_par_tache.get(tache, 0) / 400)
        return 0.35 + 1.3 * niveau + habitude


@dataclass
class Parcelle:
    id: int
    type: str
    hectares: float
    maturite: float = 1.0  # les vergers mettent des années à produire

    @property
    def libelle(self) -> str:
        return TYPES_PARCELLE.get(self.type, self.type)


@dataclass
class Chantier:
    """Un chantier lancé : il consomme des jours-homme jusqu'à l'achèvement."""

    cle: str
    nom: str
    travail_requis: float
    travail_fait: float = 0.0
    materiaux: dict[str, float] = field(default_factory=dict)
    materiaux_livres: bool = False

    @property
    def avancement(self) -> float:
        return min(1.0, self.travail_fait / self.travail_requis) if self.travail_requis else 1.0


@dataclass
class Territoire:
    km2: float = 1_000_000.0
    parcelles: list[Parcelle] = field(default_factory=list)
    prochain_id: int = 1

    def ajouter(self, type: str, hectares: float, maturite: float = 1.0) -> Parcelle:
        p = Parcelle(id=self.prochain_id, type=type, hectares=hectares, maturite=maturite)
        self.prochain_id += 1
        self.parcelles.append(p)
        return p

    def surface(self, type: str) -> float:
        return sum(p.hectares for p in self.parcelles if p.type == type)

    def surface_productive(self, type: str) -> float:
        return sum(p.hectares * p.maturite for p in self.parcelles if p.type == type)

    @property
    def hectares_amenages(self) -> float:
        return sum(p.hectares for p in self.parcelles if p.type != "friche")

    @property
    def part_amenagee(self) -> float:
        return self.hectares_amenages / (self.km2 * 100.0)


@dataclass
class Meteo:
    temperature: float = 12.0
    pluie: float = 0.0  # mm du jour
    description: str = "temps calme"


@dataclass
class Journal:
    entrees: list[dict[str, Any]] = field(default_factory=list)

    def noter(self, jour: int, texte: str, genre: str = "info") -> None:
        self.entrees.append({"jour": jour, "texte": texte, "genre": genre})
        del self.entrees[:-400]


@dataclass
class Etat:
    """L'état complet de la société, entièrement sérialisable en JSON."""

    graine: int = 1
    jour: int = 0
    territoire: Territoire = field(default_factory=Territoire)
    personnes: list[Personne] = field(default_factory=list)
    prochain_id_personne: int = 1
    stocks: dict[str, float] = field(default_factory=lambda: {r: 0.0 for r in RESSOURCES})
    batiments: dict[str, int] = field(default_factory=dict)
    chantier: Chantier | None = None
    savoirs: dict[str, float] = field(default_factory=dict)
    cohesion: float = 1.0
    gouvernance: str = "fondateur"
    meteo: Meteo = field(default_factory=Meteo)
    journal: Journal = field(default_factory=Journal)
    historique: list[dict[str, float]] = field(default_factory=list)
    en_peril: bool = False
    politique: dict[str, float] = field(default_factory=lambda: {"natalite": 0.5})
    demographie: dict[str, float] = field(default_factory=lambda: {
        "naissances": 0, "deces": 0, "ages_au_deces": 0.0, "couples_formes": 0,
    })
    alertes: dict[str, int] = field(default_factory=dict)
    termine: str | None = None

    # -- calendrier -------------------------------------------------------

    @property
    def annee(self) -> int:
        return self.jour // 365 + 1

    @property
    def jour_annee(self) -> int:
        return self.jour % 365

    @property
    def saison(self) -> str:
        return SAISONS[int(self.jour_annee / 365 * 4) % 4]

    @property
    def date_lisible(self) -> str:
        return f"an {self.annee}, jour {self.jour_annee + 1} ({self.saison})"

    # -- agrégats ---------------------------------------------------------

    @property
    def population(self) -> int:
        return len(self.personnes)

    def batiment(self, cle: str) -> int:
        return self.batiments.get(cle, 0)

    def moyenne(self, champ: str) -> float:
        if not self.personnes:
            return 0.0
        return sum(getattr(p, champ) for p in self.personnes) / len(self.personnes)

    def taux_dependance(self) -> float:
        """Personnes à charge (enfants et anciens) par personne en âge de travailler."""
        actifs = sum(1 for p in self.personnes if AGE_TRAVAIL <= p.age < 65)
        charges = len(self.personnes) - actifs
        return charges / actifs if actifs else float(charges)

    def esperance_vie(self) -> float | None:
        """Âge moyen au décès, une fois qu'il y a eu des décès."""
        morts = self.demographie.get("deces", 0)
        if not morts:
            return None
        return round(self.demographie["ages_au_deces"] / morts, 1)

    def pyramide(self, pas: int = 10) -> list[dict[str, Any]]:
        """Répartition par tranche d'âge, pour l'affichage."""
        tranches: dict[int, dict[str, int]] = {}
        for p in self.personnes:
            cle = (p.age // pas) * pas
            t = tranches.setdefault(cle, {"f": 0, "h": 0})
            t[p.sexe if p.sexe in t else "f"] += 1
        return [{"de": cle, "a": cle + pas - 1, **t} for cle, t in sorted(tranches.items())]

    def personne(self, id: int) -> Personne | None:
        return next((p for p in self.personnes if p.id == id), None)

    # -- sérialisation ----------------------------------------------------

    def vers_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["derive"] = {
            "date": self.date_lisible,
            "annee": self.annee,
            "jour_annee": self.jour_annee,
            "saison": self.saison,
            "population": self.population,
            "hectares_amenages": round(self.territoire.hectares_amenages, 2),
            "part_amenagee": self.territoire.part_amenagee,
            "moral": round(self.moyenne("moral"), 1),
            "sante": round(self.moyenne("sante"), 1),
            "energie": round(self.moyenne("energie"), 1),
            "enfants": sum(1 for p in self.personnes if p.enfant),
            "actifs": sum(1 for p in self.personnes if AGE_TRAVAIL <= p.age < 60),
            "anciens": sum(1 for p in self.personnes if p.age >= 60),
            "grossesses": sum(1 for p in self.personnes if p.grossesse is not None),
            "age_moyen": round(self.moyenne("age"), 1),
            "dependance": round(self.taux_dependance(), 2),
            "esperance_vie": self.esperance_vie(),
            "pyramide": self.pyramide(),
        }
        return d

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Etat":
        d = dict(d)
        d.pop("derive", None)
        terr = d.pop("territoire", {})
        terr = Territoire(
            km2=terr.get("km2", 1_000_000.0),
            parcelles=[Parcelle(**p) for p in terr.get("parcelles", [])],
            prochain_id=terr.get("prochain_id", 1),
        )
        personnes = [Personne(**p) for p in d.pop("personnes", [])]
        chantier = d.pop("chantier", None)
        meteo = Meteo(**d.pop("meteo", {}))
        journal = Journal(**d.pop("journal", {"entrees": []}))
        etat = cls(territoire=terr, personnes=personnes, meteo=meteo, journal=journal, **d)
        etat.chantier = Chantier(**chantier) if chantier else None
        return etat


def echelle_douce(x: float, k: float = 1.0) -> float:
    """Saturation douce dans [0, 1[ : sert pour les rendements décroissants."""
    return 1.0 - math.exp(-k * max(0.0, x))
