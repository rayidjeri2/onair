"""Scénarios prêts à l'emploi : une station de référence et ses variantes."""

from __future__ import annotations

from dataclasses import replace

from .audience import PopulationAuditeurs, Segment
from .modele import Creneau, Emission, Grille, Station

ANIMATEURS = {
    "lea": ("Léa Marchand", 0.8),
    "samir": ("Samir Ould", 0.6),
    "nina": ("Nina Berger", 0.45),
    "paul": ("Paul Estève", 0.7),
    "auto": ("Pilote automatique", 0.15),
}


def _animateur(cle: str):
    from .modele import Animateur

    nom, notoriete = ANIMATEURS[cle]
    return Animateur(nom=nom, notoriete=notoriete)


def grille_reference() -> Grille:
    """Une grille plausible : matinale forte, journée musicale, soirée talk."""
    matinale = Emission("Le Réveil", "matinale", 0.85, _animateur("lea"), 3, 3.0)
    midi = Emission("Midi Actu", "actualite", 0.7, _animateur("samir"), 3, 3.0)
    apres_midi = Emission("Playlist Continue", "musique", 0.6, _animateur("nina"), 2, 3.0)
    retour = Emission("Grand Retour", "talk", 0.75, _animateur("paul"), 3, 2.5)
    soiree = Emission("Session Live", "musique", 0.8, _animateur("nina"), 1, 2.0)
    nuit = Emission("Nuit Blanche", "nuit", 0.4, _animateur("auto"), 0, 0.0)
    sport = Emission("Tribune Sport", "sport", 0.7, _animateur("samir"), 2, 3.0)

    grille = Grille()
    for jour in ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]:
        grille.ajouter(Creneau(jour, 0.0, 6.0, nuit))
        grille.ajouter(Creneau(jour, 6.0, 4.0, matinale))
        grille.ajouter(Creneau(jour, 10.0, 2.0, apres_midi))
        grille.ajouter(Creneau(jour, 12.0, 2.0, midi))
        grille.ajouter(Creneau(jour, 14.0, 3.0, apres_midi))
        grille.ajouter(Creneau(jour, 17.0, 3.0, retour))
        grille.ajouter(Creneau(jour, 20.0, 4.0, soiree))
    for jour in ["samedi", "dimanche"]:
        grille.ajouter(Creneau(jour, 0.0, 7.0, nuit))
        grille.ajouter(Creneau(jour, 7.0, 4.0, apres_midi))
        grille.ajouter(Creneau(jour, 11.0, 3.0, midi))
        grille.ajouter(Creneau(jour, 14.0, 4.0, sport))
        grille.ajouter(Creneau(jour, 18.0, 2.0, retour))
        grille.ajouter(Creneau(jour, 20.0, 4.0, soiree))
    return grille


def _profil(valeurs: dict[range | int, float], defaut: float = 0.05) -> list[float]:
    dispo = [defaut] * 24
    for cle, v in valeurs.items():
        for h in ([cle] if isinstance(cle, int) else cle):
            dispo[h] = v
    return dispo


def population_reference() -> PopulationAuditeurs:
    """Quatre publics types d'une zone de diffusion d'environ 900 000 personnes."""
    actifs = Segment(
        nom="Actifs navetteurs",
        population=380_000,
        affinites={"matinale": 0.9, "actualite": 0.7, "talk": 0.55, "musique": 0.4,
                   "sport": 0.3, "nuit": 0.05},
        dispo=_profil({range(6, 10): 0.85, range(10, 12): 0.2, range(12, 14): 0.45,
                       range(14, 17): 0.2, range(17, 20): 0.8, range(20, 23): 0.25}),
        tolerance_pub=0.55,
        inertie=0.7,
    )
    jeunes = Segment(
        nom="Jeunes urbains",
        population=240_000,
        affinites={"musique": 0.95, "talk": 0.5, "sport": 0.45, "actualite": 0.25,
                   "matinale": 0.35, "nuit": 0.5},
        dispo=_profil({range(7, 9): 0.4, range(12, 14): 0.3, range(17, 20): 0.55,
                       range(20, 24): 0.8, range(0, 3): 0.35}),
        tolerance_pub=0.25,
        inertie=0.35,
    )
    domicile = Segment(
        nom="À domicile",
        population=190_000,
        affinites={"musique": 0.7, "talk": 0.75, "actualite": 0.6, "matinale": 0.6,
                   "sport": 0.2, "nuit": 0.15},
        dispo=_profil({range(8, 12): 0.7, range(12, 14): 0.5, range(14, 18): 0.65,
                       range(18, 22): 0.3}),
        tolerance_pub=0.7,
        inertie=0.8,
    )
    passionnes = Segment(
        nom="Passionnés de sport",
        population=95_000,
        affinites={"sport": 0.95, "actualite": 0.5, "talk": 0.4, "matinale": 0.3,
                   "musique": 0.2, "nuit": 0.1},
        dispo=_profil({range(7, 9): 0.35, range(12, 14): 0.4, range(14, 19): 0.6,
                       range(19, 23): 0.55}),
        tolerance_pub=0.6,
        inertie=0.5,
    )
    return PopulationAuditeurs([actifs, jeunes, domicile, passionnes])


def station_reference() -> Station:
    return Station(nom="Onair FM", grille=grille_reference())


def variante_saturee(station: Station) -> Station:
    """Même grille, mais deux fois plus de publicité : le scénario « trop de pub »."""
    grille = Grille(
        [
            replace(
                c,
                emission=replace(
                    c.emission, pubs_par_heure=min(8, c.emission.pubs_par_heure * 2)
                ),
            )
            for c in station.grille.creneaux
        ]
    )
    return replace(station, nom=f"{station.nom} (pub x2)", grille=grille)


def variante_sans_vedette(station: Station) -> Station:
    """Tous les animateurs remplacés par le pilote automatique."""
    auto = _animateur("auto")
    grille = Grille(
        [replace(c, emission=replace(c.emission, animateur=auto)) for c in station.grille.creneaux]
    )
    return replace(station, nom=f"{station.nom} (sans vedette)", grille=grille)


SCENARIOS = {
    "reference": station_reference,
    "pub-x2": lambda: variante_saturee(station_reference()),
    "sans-vedette": lambda: variante_sans_vedette(station_reference()),
}
