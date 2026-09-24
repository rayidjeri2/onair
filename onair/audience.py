"""Modèle d'audience par segments.

On ne simule pas des auditeurs un par un : chaque segment est une population
homogène dont on suit l'effectif à l'écoute. C'est plus rapide et suffisant
pour comparer des grilles, tout en gardant une dynamique d'arrivée/de départ
(inertie, zapping pendant les pubs, lassitude).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Segment:
    """Un public type.

    population    : taille du vivier
    affinites     : attrait par genre (0-1)
    dispo         : disponibilité horaire, 24 valeurs (0-1), une par heure
    tolerance_pub : 1 = la pub ne dérange pas, 0 = départ immédiat
    inertie       : 0-1, tendance à rester même quand l'attrait baisse
    """

    nom: str
    population: int
    affinites: dict[str, float]
    dispo: list[float]
    tolerance_pub: float = 0.5
    inertie: float = 0.6
    a_lecoute: float = field(default=0.0, init=False)
    lassitude: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if len(self.dispo) != 24:
            raise ValueError("dispo doit contenir 24 valeurs (une par heure)")
        if self.population < 0:
            raise ValueError("population doit être >= 0")
        for borne, valeur in (("tolerance_pub", self.tolerance_pub), ("inertie", self.inertie)):
            if not 0.0 <= valeur <= 1.0:
                raise ValueError(f"{borne} doit être dans [0, 1]")

    def disponibilite(self, heure: float) -> float:
        """Disponibilité interpolée à une heure décimale."""
        h = heure % 24.0
        bas = int(math.floor(h))
        haut = (bas + 1) % 24
        t = h - bas
        return self.dispo[bas] * (1 - t) + self.dispo[haut] * t

    def attrait(self, genre: str, qualite: float, notoriete: float, heure: float) -> float:
        """Attrait instantané d'un programme pour ce segment, dans [0, 1]."""
        affinite = self.affinites.get(genre, 0.1)
        editorial = 0.65 * qualite + 0.35 * notoriete
        brut = affinite * editorial * self.disponibilite(heure)
        return max(0.0, min(1.0, brut * (1.0 - 0.4 * self.lassitude)))


@dataclass
class PopulationAuditeurs:
    """L'ensemble des segments d'une zone de diffusion."""

    segments: list[Segment]

    @property
    def total(self) -> int:
        return sum(s.population for s in self.segments)

    @property
    def a_lecoute(self) -> float:
        return sum(s.a_lecoute for s in self.segments)

    def reinitialiser(self) -> None:
        for s in self.segments:
            s.a_lecoute = 0.0
            s.lassitude = 0.0
