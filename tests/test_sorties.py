import json

from onair import Simulation, graphiques, web
from onair.cli import main
from onair.scenarios import population_reference, station_reference


def resultats():
    return Simulation(station_reference(), population_reference(), jours=1).executer()


def test_graphiques_produits(tmp_path):
    chemins = graphiques.tous(resultats(), tmp_path)
    assert len(chemins) == 4
    assert all(c.exists() and c.stat().st_size > 5_000 for c in chemins)


def test_tableau_autonome(tmp_path):
    page = web.construire(resultats(), tmp_path / "t.html")
    html = page.read_text(encoding="utf-8")
    assert "__DONNEES__" not in html and "__TITRE__" not in html
    # aucune ressource externe : le seul "http" toléré est l'espace de noms SVG
    sans_ns = html.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in sans_ns and "https://" not in sans_ns


def test_cli(tmp_path, capsys):
    code = main(["--jours", "1", "--sorties", str(tmp_path), "--sans-graphiques"])
    assert code == 0
    base = tmp_path / "reference"
    assert (base / "tableau.html").exists()
    json.loads((base / "resultats.json").read_text(encoding="utf-8"))
    assert "audience moyenne" in capsys.readouterr().out
