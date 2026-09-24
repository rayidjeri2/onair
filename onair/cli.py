"""Ligne de commande : lancer une simulation, écrire graphiques et tableau de bord."""

from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from . import graphiques, web
from .scenarios import SCENARIOS, population_reference
from .simulation import Simulation


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="onair", description="Simulateur de grille radio à événements discrets."
    )
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="reference",
                   help="grille à simuler (défaut : reference)")
    p.add_argument("--jours", type=int, default=7, help="nombre de jours simulés (défaut : 7)")
    p.add_argument("--graine", type=int, default=42, help="graine aléatoire (défaut : 42)")
    p.add_argument("--bruit", type=float, default=0.05,
                   help="écart-type du bruit multiplicatif, 0 pour un résultat déterministe")
    p.add_argument("--sorties", type=Path, default=Path("sorties"),
                   help="dossier de sortie (défaut : ./sorties)")
    p.add_argument("--sans-graphiques", action="store_true", help="ne pas produire les PNG")
    p.add_argument("--ouvrir", action="store_true",
                   help="ouvrir le tableau de bord dans le navigateur")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)

    station = SCENARIOS[args.scenario]()
    anomalies = station.grille.verifier()
    for anomalie in anomalies:
        print(f"⚠  {anomalie}")

    sim = Simulation(station, population_reference(), jours=args.jours,
                     graine=args.graine, bruit=args.bruit)
    resultats = sim.executer()

    args.sorties.mkdir(parents=True, exist_ok=True)
    base = args.sorties / args.scenario
    base.mkdir(parents=True, exist_ok=True)

    (base / "resultats.json").write_text(
        json.dumps(resultats.vers_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not args.sans_graphiques:
        graphiques.tous(resultats, base)
    tableau = web.construire(resultats, base / "tableau.html")

    k = resultats
    print(f"\n{station.nom} · {args.jours} jour(s)")
    print(f"  audience moyenne  : {k.audience_moyenne:>12,.0f} auditeurs".replace(",", " "))
    print(f"  pic d'audience    : {k.pic_audience:>12,.0f} auditeurs".replace(",", " "))
    print(f"  part de population: {k.part_population:>12.1%}")
    print(f"  recette pub       : {k.revenu_total:>12,.0f} €".replace(",", " "))
    print(f"  départs en pub    : {k.abandons_pub:>12,.0f} auditeurs".replace(",", " "))
    print(f"\nTableau de bord : {tableau}")

    if args.ouvrir:
        webbrowser.open(tableau.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
