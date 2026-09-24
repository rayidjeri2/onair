"""Génération du tableau de bord HTML autonome (données embarquées)."""

from __future__ import annotations

import json
from pathlib import Path

from .simulation import Resultats

MODELE = Path(__file__).parent / "modeles" / "tableau.html"


def construire(resultats: Resultats, chemin: Path, titre: str | None = None) -> Path:
    """Écrit une page HTML autonome : aucune dépendance réseau, ouvrable hors ligne."""
    donnees = resultats.vers_dict()
    charge = json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
    page = MODELE.read_text(encoding="utf-8")
    page = page.replace("__TITRE__", titre or f"{resultats.station} — simulation d'antenne")
    page = page.replace("__DONNEES__", charge)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(page, encoding="utf-8")
    return chemin
