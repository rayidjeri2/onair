"""Boucle de simulation : la grille rencontre l'audience."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .audience import PopulationAuditeurs
from .core import Echeancier, Evenement, Repartiteur
from .modele import JOURS, Creneau, Station

PAS = 5.0  # minutes entre deux échantillons

TAU_ARRIVEE = 12.0  # constante de temps de montée en audience (min)
TAU_DEPART_BASE = 8.0  # constante de temps de départ, avant inertie (min)


@dataclass
class Echantillon:
    minute: float
    jour: str
    heure: float
    emission: str
    genre: str
    en_pub: bool
    auditeurs: float
    par_segment: dict[str, float]


@dataclass
class StatsEmission:
    nom: str
    genre: str
    animateur: str
    minutes: float = 0.0
    somme_auditeurs: float = 0.0
    pic: float = 0.0
    abandons_pub: float = 0.0
    revenu: float = 0.0

    @property
    def audience_moyenne(self) -> float:
        return self.somme_auditeurs / (self.minutes / PAS) if self.minutes else 0.0


@dataclass
class Resultats:
    station: str
    jours: int
    population: int
    echantillons: list[Echantillon] = field(default_factory=list)
    emissions: dict[str, StatsEmission] = field(default_factory=dict)
    revenu_total: float = 0.0
    abandons_pub: float = 0.0

    @property
    def audience_moyenne(self) -> float:
        if not self.echantillons:
            return 0.0
        return sum(e.auditeurs for e in self.echantillons) / len(self.echantillons)

    @property
    def pic_audience(self) -> float:
        return max((e.auditeurs for e in self.echantillons), default=0.0)

    @property
    def part_population(self) -> float:
        return self.audience_moyenne / self.population if self.population else 0.0

    def par_heure(self) -> list[float]:
        """Audience moyenne pour chacune des 24 heures de la journée."""
        sommes = [0.0] * 24
        compte = [0] * 24
        for e in self.echantillons:
            h = int(e.heure) % 24
            sommes[h] += e.auditeurs
            compte[h] += 1
        return [s / c if c else 0.0 for s, c in zip(sommes, compte)]

    def grille_jour_heure(self) -> list[list[float]]:
        """Matrice 7 jours x 24 heures de l'audience moyenne."""
        sommes = [[0.0] * 24 for _ in JOURS]
        compte = [[0] * 24 for _ in JOURS]
        index = {j: i for i, j in enumerate(JOURS)}
        for e in self.echantillons:
            j, h = index[e.jour], int(e.heure) % 24
            sommes[j][h] += e.auditeurs
            compte[j][h] += 1
        return [
            [s / c if c else 0.0 for s, c in zip(ligne_s, ligne_c)]
            for ligne_s, ligne_c in zip(sommes, compte)
        ]

    def classement(self) -> list[StatsEmission]:
        return sorted(
            self.emissions.values(), key=lambda s: s.audience_moyenne, reverse=True
        )

    def vers_dict(self) -> dict:
        return {
            "station": self.station,
            "jours": self.jours,
            "population": self.population,
            "pas_minutes": PAS,
            "indicateurs": {
                "audience_moyenne": round(self.audience_moyenne, 1),
                "pic_audience": round(self.pic_audience, 1),
                "part_population": round(self.part_population, 4),
                "revenu_total": round(self.revenu_total, 2),
                "abandons_pub": round(self.abandons_pub, 1),
            },
            "serie": [
                {
                    "minute": e.minute,
                    "jour": e.jour,
                    "heure": round(e.heure, 3),
                    "emission": e.emission,
                    "genre": e.genre,
                    "pub": e.en_pub,
                    "auditeurs": round(e.auditeurs, 1),
                    "segments": {k: round(v, 1) for k, v in e.par_segment.items()},
                }
                for e in self.echantillons
            ],
            "par_heure": [round(v, 1) for v in self.par_heure()],
            "jour_heure": [[round(v, 1) for v in ligne] for ligne in self.grille_jour_heure()],
            "emissions": [
                {
                    "nom": s.nom,
                    "genre": s.genre,
                    "animateur": s.animateur,
                    "audience_moyenne": round(s.audience_moyenne, 1),
                    "pic": round(s.pic, 1),
                    "heures_antenne": round(s.minutes / 60.0, 1),
                    "abandons_pub": round(s.abandons_pub, 1),
                    "revenu": round(s.revenu, 2),
                }
                for s in self.classement()
            ],
        }


class Simulation:
    """Déroule `jours` journées d'antenne et collecte les mesures."""

    def __init__(
        self,
        station: Station,
        population: PopulationAuditeurs,
        jours: int = 7,
        graine: int = 42,
        bruit: float = 0.05,
    ) -> None:
        if jours < 1:
            raise ValueError("jours doit être >= 1")
        self.station = station
        self.population = population
        self.jours = jours
        self.bruit = bruit
        self.alea = random.Random(graine)

        self.echeancier = Echeancier()
        self.repartiteur = Repartiteur()
        self.resultats = Resultats(
            station=station.nom, jours=jours, population=population.total
        )

        self._creneau: Creneau | None = None
        self._en_pub = False
        self._genre_precedent: str | None = None
        self._auditeurs_debut_pub = 0.0
        self._brancher()

    # -- planification ----------------------------------------------------

    def _brancher(self) -> None:
        rep = self.repartiteur

        @rep.sur("debut_emission")
        def _(ev: Evenement) -> None:
            self._demarrer_emission(ev.charge)

        @rep.sur("debut_pub")
        def _(ev: Evenement) -> None:
            self._en_pub = True
            self._auditeurs_debut_pub = self.population.a_lecoute

        @rep.sur("fin_pub")
        def _(ev: Evenement) -> None:
            self._terminer_pub()

        @rep.sur("pas")
        def _(ev: Evenement) -> None:
            self._avancer()

    def _planifier_grille(self) -> None:
        for jour_index in range(self.jours):
            jour = JOURS[jour_index % 7]
            for creneau in self.station.grille.du_jour(jour):
                depart = jour_index * 1440.0 + creneau.debut * 60.0
                self.echeancier.planifier(depart, "debut_emission", (jour, creneau))
                self._planifier_pubs(depart, creneau)

    def _planifier_pubs(self, depart: float, creneau: Creneau) -> None:
        emission = creneau.emission
        duree_min = creneau.duree * 60.0
        total = int(round(emission.pubs_par_heure * creneau.duree))
        if total <= 0 or emission.duree_pub <= 0:
            return
        # Les coupures sont réparties régulièrement, jamais sur la dernière minute.
        for i in range(total):
            offset = duree_min * (i + 1) / (total + 1)
            debut_pub = depart + offset
            fin_pub = min(debut_pub + emission.duree_pub, depart + duree_min)
            if fin_pub <= debut_pub:
                continue
            self.echeancier.planifier(debut_pub, "debut_pub", creneau)
            self.echeancier.planifier(fin_pub, "fin_pub", creneau)

    def _planifier_pas(self) -> None:
        fin = self.jours * 1440.0
        t = 0.0
        while t <= fin:
            self.echeancier.planifier(t, "pas", None)
            t += PAS

    # -- dynamique --------------------------------------------------------

    def _demarrer_emission(self, charge: tuple[str, Creneau]) -> None:
        _, creneau = charge
        emission = creneau.emission
        self._creneau = creneau
        self._en_pub = False
        for segment in self.population.segments:
            if self._genre_precedent == emission.genre:
                segment.lassitude = min(1.0, segment.lassitude + 0.12)
            else:
                segment.lassitude *= 0.4
        self._genre_precedent = emission.genre
        self.resultats.emissions.setdefault(
            emission.nom,
            StatsEmission(emission.nom, emission.genre, emission.animateur.nom),
        )

    def _terminer_pub(self) -> None:
        if not self._en_pub or self._creneau is None:
            self._en_pub = False
            return
        self._en_pub = False
        perdus = max(0.0, self._auditeurs_debut_pub - self.population.a_lecoute)
        stats = self.resultats.emissions[self._creneau.emission.nom]
        stats.abandons_pub += perdus
        self.resultats.abandons_pub += perdus

        exposes = (self._auditeurs_debut_pub + self.population.a_lecoute) / 2.0
        revenu = self.station.spots_par_coupure * (exposes / 1000.0) * self.station.cpm
        stats.revenu += revenu
        self.resultats.revenu_total += revenu

    def _avancer(self) -> None:
        minute = self.echeancier.horloge
        jour = JOURS[int(minute // 1440) % 7]
        heure = (minute % 1440) / 60.0
        creneau = self._creneau

        par_segment: dict[str, float] = {}
        for segment in self.population.segments:
            if creneau is None:
                cible = 0.0
            else:
                emission = creneau.emission
                attrait = segment.attrait(
                    emission.genre,
                    emission.qualite,
                    emission.animateur.notoriete,
                    heure,
                )
                if self._en_pub:
                    attrait *= 1.0 - 0.8 * (1.0 - segment.tolerance_pub)
                cible = segment.population * attrait

            if self.bruit:
                cible *= max(0.0, 1.0 + self.alea.gauss(0.0, self.bruit))

            monte = cible > segment.a_lecoute
            tau = TAU_ARRIVEE if monte else TAU_DEPART_BASE * (1.0 + 4.0 * segment.inertie)
            segment.a_lecoute += (cible - segment.a_lecoute) * (1.0 - math.exp(-PAS / tau))
            segment.a_lecoute = max(0.0, segment.a_lecoute)
            par_segment[segment.nom] = segment.a_lecoute

        total = sum(par_segment.values())
        self.resultats.echantillons.append(
            Echantillon(
                minute=minute,
                jour=jour,
                heure=heure,
                emission=creneau.emission.nom if creneau else "antenne fermée",
                genre=creneau.emission.genre if creneau else "-",
                en_pub=self._en_pub,
                auditeurs=total,
                par_segment=par_segment,
            )
        )
        if creneau is not None:
            stats = self.resultats.emissions[creneau.emission.nom]
            stats.minutes += PAS
            stats.somme_auditeurs += total
            stats.pic = max(stats.pic, total)

    # -- exécution --------------------------------------------------------

    def executer(self) -> Resultats:
        self.population.reinitialiser()
        self._planifier_grille()
        self._planifier_pas()
        fin = self.jours * 1440.0
        for ev in self.echeancier.derouler(fin):
            self.repartiteur.traiter(ev)
        return self.resultats
