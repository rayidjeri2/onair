"""Graphiques matplotlib (sortie PNG) — palette validée, une seule échelle par axe."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .modele import JOURS  # noqa: E402
from .simulation import Resultats  # noqa: E402

SURFACE = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_SECONDAIRE = "#52514e"
GRILLE = "#e3e2dd"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
RAMPE = LinearSegmentedColormap.from_list("onair_bleu", ["#f2f6fc", "#2a78d6", "#123a6b"])


def _style(ax, titre: str, sous_titre: str = "") -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for cote in ("top", "right"):
        ax.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        ax.spines[cote].set_color(GRILLE)
    ax.tick_params(colors=ENCRE_SECONDAIRE, labelsize=9)
    ax.grid(axis="y", color=GRILLE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(titre, color=ENCRE, fontsize=13, loc="left", pad=16 if sous_titre else 10)
    if sous_titre:
        ax.text(0, 1.02, sous_titre, transform=ax.transAxes, color=ENCRE_SECONDAIRE,
                fontsize=9.5, va="bottom")


def _milliers(ax) -> None:
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:,.0f} k".replace(",", " "))


def journee_type(resultats: Resultats, chemin: Path) -> Path:
    """Courbe d'audience moyenne heure par heure."""
    valeurs = resultats.par_heure()
    heures = list(range(24))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(heures, valeurs, color=SERIES[0], linewidth=2, zorder=3)
    ax.fill_between(heures, valeurs, color=SERIES[0], alpha=0.10, zorder=2)
    pic = max(range(24), key=lambda h: valeurs[h])
    ax.plot([pic], [valeurs[pic]], "o", markersize=9, color=SERIES[0],
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    ax.annotate(f"{valeurs[pic]/1000:.0f} k à {pic}h", (pic, valeurs[pic]),
                textcoords="offset points", xytext=(8, 8), color=ENCRE, fontsize=10)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
    ax.set_xlim(0, 23)
    ax.set_ylim(bottom=0)
    _milliers(ax)
    _style(ax, "Audience moyenne d'une journée type", f"{resultats.station} · auditeurs simultanés")
    fig.tight_layout()
    fig.savefig(chemin, dpi=160)
    plt.close(fig)
    return chemin


def segments_empiles(resultats: Resultats, chemin: Path) -> Path:
    """Composition de l'audience heure par heure, par segment."""
    noms = [s for s in resultats.echantillons[0].par_segment]
    sommes = {n: [0.0] * 24 for n in noms}
    compte = [0] * 24
    for e in resultats.echantillons:
        h = int(e.heure) % 24
        compte[h] += 1
        for n, v in e.par_segment.items():
            sommes[n][h] += v
    series = {n: [sommes[n][h] / compte[h] if compte[h] else 0.0 for h in range(24)] for n in noms}

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.stackplot(range(24), *series.values(), labels=list(series),
                 colors=SERIES[: len(series)], edgecolor=SURFACE, linewidth=1.5)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
    ax.set_xlim(0, 23)
    ax.set_ylim(bottom=0)
    _milliers(ax)
    legende = ax.legend(loc="upper left", frameon=False, fontsize=9, ncols=2)
    for texte in legende.get_texts():
        texte.set_color(ENCRE_SECONDAIRE)
    _style(ax, "Composition de l'audience par public", "auditeurs simultanés, moyenne sur la période")
    fig.tight_layout()
    fig.savefig(chemin, dpi=160)
    plt.close(fig)
    return chemin


def carte_semaine(resultats: Resultats, chemin: Path) -> Path:
    """Carte de chaleur jour x heure (magnitude : rampe séquentielle à une teinte)."""
    matrice = resultats.grille_jour_heure()
    fig, ax = plt.subplots(figsize=(9, 3.6))
    image = ax.imshow(matrice, aspect="auto", cmap=RAMPE, origin="upper")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h}h" for h in range(0, 24, 2)])
    ax.set_yticks(range(7))
    ax.set_yticklabels([j.capitalize() for j in JOURS])
    ax.grid(False)
    barre = fig.colorbar(image, ax=ax, pad=0.02)
    barre.ax.tick_params(colors=ENCRE_SECONDAIRE, labelsize=8)
    barre.outline.set_visible(False)
    barre.ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f} k")
    _style(ax, "Audience par jour et par heure", "auditeurs simultanés")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(chemin, dpi=160)
    plt.close(fig)
    return chemin


def classement_emissions(resultats: Resultats, chemin: Path) -> Path:
    """Classement des émissions par audience moyenne (une seule série : pas de légende)."""
    stats = resultats.classement()
    noms = [s.nom for s in stats][::-1]
    valeurs = [s.audience_moyenne for s in stats][::-1]
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(noms) + 2))
    barres = ax.barh(noms, valeurs, color=SERIES[0], height=0.62)
    for barre, valeur in zip(barres, valeurs):
        ax.text(valeur + max(valeurs) * 0.01, barre.get_y() + barre.get_height() / 2,
                f"{valeur/1000:.0f} k", va="center", color=ENCRE_SECONDAIRE, fontsize=9)
    ax.set_xlim(0, max(valeurs) * 1.12)
    ax.grid(axis="x", color=GRILLE, linewidth=0.8)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f} k")
    _style(ax, "Audience moyenne par émission", "auditeurs simultanés pendant la diffusion")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(chemin, dpi=160)
    plt.close(fig)
    return chemin


def tous(resultats: Resultats, dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    return [
        journee_type(resultats, dossier / "journee_type.png"),
        segments_empiles(resultats, dossier / "segments.png"),
        carte_semaine(resultats, dossier / "carte_semaine.png"),
        classement_emissions(resultats, dossier / "classement.png"),
    ]
