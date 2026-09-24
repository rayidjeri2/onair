"""onair — simulateur de grille radio à événements discrets."""

from .core import Echeancier, Evenement
from .modele import Animateur, Creneau, Emission, Grille, Station
from .audience import Segment, PopulationAuditeurs
from .simulation import Simulation, Resultats

__all__ = [
    "Echeancier",
    "Evenement",
    "Animateur",
    "Creneau",
    "Emission",
    "Grille",
    "Station",
    "Segment",
    "PopulationAuditeurs",
    "Simulation",
    "Resultats",
]
