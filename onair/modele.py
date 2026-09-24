"""Modèle de la station : émissions, animateurs, grille."""

from __future__ import annotations

from dataclasses import dataclass, field

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
GENRES = ["matinale", "musique", "talk", "actualite", "sport", "nuit"]


@dataclass(frozen=True)
class Animateur:
    """Un animateur ; `notoriete` (0-1) amplifie l'attrait de ses émissions."""

    nom: str
    notoriete: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.notoriete <= 1.0:
            raise ValueError("notoriete doit être dans [0, 1]")


@dataclass(frozen=True)
class Emission:
    """Un programme diffusable.

    qualite       : qualité éditoriale perçue (0-1)
    pubs_par_heure: nombre de coupures publicitaires par heure
    duree_pub     : durée d'une coupure, en minutes
    """

    nom: str
    genre: str
    qualite: float
    animateur: Animateur
    pubs_par_heure: int = 2
    duree_pub: float = 3.0

    def __post_init__(self) -> None:
        if self.genre not in GENRES:
            raise ValueError(f"genre inconnu : {self.genre!r} (attendu : {GENRES})")
        if not 0.0 <= self.qualite <= 1.0:
            raise ValueError("qualite doit être dans [0, 1]")
        if self.pubs_par_heure < 0:
            raise ValueError("pubs_par_heure doit être >= 0")
        if self.duree_pub < 0:
            raise ValueError("duree_pub doit être >= 0")

    @property
    def charge_pub(self) -> float:
        """Part de l'antenne occupée par la publicité (0-1)."""
        return min(1.0, self.pubs_par_heure * self.duree_pub / 60.0)


@dataclass(frozen=True)
class Creneau:
    """Une case de la grille : `jour` peut valoir "*" pour tous les jours."""

    jour: str
    debut: float  # heure décimale, ex. 6.5 pour 6h30
    duree: float  # en heures
    emission: Emission

    def __post_init__(self) -> None:
        if self.jour != "*" and self.jour not in JOURS:
            raise ValueError(f"jour inconnu : {self.jour!r}")
        if not 0.0 <= self.debut < 24.0:
            raise ValueError("debut doit être dans [0, 24[")
        if not 0.0 < self.duree <= 24.0:
            raise ValueError("duree doit être dans ]0, 24]")

    def jours(self) -> list[str]:
        return list(JOURS) if self.jour == "*" else [self.jour]


@dataclass
class Grille:
    """La grille des programmes, dépliée jour par jour."""

    creneaux: list[Creneau] = field(default_factory=list)

    def ajouter(self, creneau: Creneau) -> "Grille":
        self.creneaux.append(creneau)
        return self

    def du_jour(self, jour: str) -> list[Creneau]:
        cases = [c for c in self.creneaux if jour in c.jours()]
        return sorted(cases, key=lambda c: c.debut)

    def verifier(self) -> list[str]:
        """Retourne la liste des anomalies (chevauchements, trous)."""
        anomalies: list[str] = []
        for jour in JOURS:
            cases = self.du_jour(jour)
            for precedent, suivant in zip(cases, cases[1:]):
                fin = precedent.debut + precedent.duree
                if fin > suivant.debut + 1e-9:
                    anomalies.append(
                        f"{jour} : {precedent.emission.nom} chevauche "
                        f"{suivant.emission.nom} à {suivant.debut:g}h"
                    )
                elif fin < suivant.debut - 1e-9:
                    anomalies.append(
                        f"{jour} : trou d'antenne de {fin:g}h à {suivant.debut:g}h"
                    )
        return anomalies


@dataclass
class Station:
    """Paramètres de la station."""

    nom: str
    grille: Grille
    cpm: float = 12.0  # euros pour mille auditeurs exposés à un spot
    spots_par_coupure: int = 4
