"""Noyau réutilisable de simulation à événements discrets.

Rien ici ne connaît la radio : c'est un échéancier générique, réutilisable
pour un autre domaine (trafic, infrastructure, épidémie...).
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


@dataclass(order=True)
class Evenement:
    """Un événement planifié à l'instant `date` (en minutes de simulation)."""

    date: float
    ordre: int = field(compare=True)
    type: str = field(compare=False, default="")
    charge: Any = field(compare=False, default=None)


class Echeancier:
    """File de priorité d'événements + horloge de simulation."""

    def __init__(self) -> None:
        self._file: list[Evenement] = []
        self._compteur = itertools.count()
        self.horloge: float = 0.0

    def __len__(self) -> int:
        return len(self._file)

    def planifier(self, date: float, type: str, charge: Any = None) -> Evenement:
        if date < self.horloge:
            raise ValueError(
                f"événement planifié dans le passé : {date} < {self.horloge}"
            )
        ev = Evenement(date=date, ordre=next(self._compteur), type=type, charge=charge)
        heapq.heappush(self._file, ev)
        return ev

    def dans(self, delai: float, type: str, charge: Any = None) -> Evenement:
        return self.planifier(self.horloge + delai, type, charge)

    def prochain(self) -> Evenement | None:
        if not self._file:
            return None
        ev = heapq.heappop(self._file)
        self.horloge = ev.date
        return ev

    def derouler(self, fin: float) -> Iterator[Evenement]:
        """Itère sur les événements jusqu'à `fin` (bornes incluses)."""
        while self._file and self._file[0].date <= fin:
            ev = self.prochain()
            assert ev is not None
            yield ev
        self.horloge = max(self.horloge, fin)


Gestionnaire = Callable[[Evenement], None]


class Repartiteur:
    """Associe un type d'événement à un gestionnaire."""

    def __init__(self) -> None:
        self._table: dict[str, Gestionnaire] = {}

    def sur(self, type: str) -> Callable[[Gestionnaire], Gestionnaire]:
        def decorateur(fn: Gestionnaire) -> Gestionnaire:
            self._table[type] = fn
            return fn

        return decorateur

    def traiter(self, ev: Evenement) -> None:
        gestionnaire = self._table.get(ev.type)
        if gestionnaire is None:
            raise KeyError(f"aucun gestionnaire pour l'événement {ev.type!r}")
        gestionnaire(ev)
