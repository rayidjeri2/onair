"""Simulation d'une société qui part d'une personne seule sur une terre vierge."""

from .modele import Etat, Personne, Parcelle, Chantier
from .moteur import ajouter_personne, affecter, avancer, creer_societe, lancer_chantier

__all__ = [
    "Etat", "Personne", "Parcelle", "Chantier",
    "creer_societe", "avancer", "ajouter_personne", "affecter", "lancer_chantier",
]
