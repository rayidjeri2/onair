import json

import pytest

from societe import serveur


@pytest.fixture(autouse=True)
def partie_neuve():
    serveur.PARTIE.etat = None
    yield
    serveur.PARTIE.etat = None


def test_parcours_complet_par_l_api():
    d = serveur.traiter("/api/nouvelle", {"nom": "Ana", "age": 30, "graine": 3})
    assert d["etat"]["derive"]["population"] == 1
    assert d["chantiers"] and d["referentiel"]["taches"]

    serveur.traiter("/api/chantier", {"cle": "source"})
    serveur.traiter("/api/affectation", {"id": 1, "tache": "construction"})
    d = serveur.traiter("/api/avancer", {"jours": 25})
    assert d["etat"]["jour"] == 25
    assert d["etat"]["batiments"].get("source") == 1

    d = serveur.traiter("/api/personne", {"nom": "Tomas", "age": 28, "specialite": "eau"})
    assert d["etat"]["derive"]["population"] == 2

    d = serveur.traiter("/api/affectations", {"affectations": {"1": "nourriture", "2": "eau"}})
    assert [p["tache"] for p in d["etat"]["personnes"]] == ["nourriture", "eau"]


def test_action_sans_partie_refusee():
    with pytest.raises(ValueError, match="aucune partie"):
        serveur.traiter("/api/avancer", {"jours": 1})


def test_route_inconnue():
    serveur.traiter("/api/nouvelle", {})
    with pytest.raises(ValueError, match="route inconnue"):
        serveur.traiter("/api/nimporte", {})


def test_sauver_puis_charger(tmp_path, monkeypatch):
    monkeypatch.setattr(serveur, "SAUVEGARDES", tmp_path)
    serveur.traiter("/api/nouvelle", {"nom": "Ana", "graine": 9})
    serveur.traiter("/api/avancer", {"jours": 30})
    serveur.traiter("/api/sauver", {"nom": "essai"})
    assert (tmp_path / "essai.json").exists()

    serveur.traiter("/api/nouvelle", {"nom": "Autre"})
    d = serveur.traiter("/api/charger", {"nom": "essai"})
    assert d["etat"]["jour"] == 30
    assert d["etat"]["personnes"][0]["nom"] == "Ana"


def test_nom_de_sauvegarde_assaini(tmp_path, monkeypatch):
    monkeypatch.setattr(serveur, "SAUVEGARDES", tmp_path)
    serveur.traiter("/api/nouvelle", {})
    serveur.traiter("/api/sauver", {"nom": "../../evasion"})
    assert [f.name for f in tmp_path.iterdir()] == ["evasion.json"]


def test_instantane_serialisable_en_json():
    d = serveur.traiter("/api/nouvelle", {})
    json.dumps(d)


def test_affectation_groupee_ignore_les_enfants():
    from societe import moteur
    serveur.traiter("/api/nouvelle", {})
    etat = serveur.PARTIE.exige()
    enfant = moteur.ajouter_personne(etat, "Nino", 6, "agriculture")
    d = serveur.traiter("/api/affectations",
                        {"affectations": {"1": "bois", str(enfant.id): "bois"}})
    taches = {p["id"]: p["tache"] for p in d["etat"]["personnes"]}
    assert taches[1] == "bois"
    assert taches[enfant.id] == "repos"


def test_affectation_directe_d_un_enfant_refusee():
    from societe import moteur
    serveur.traiter("/api/nouvelle", {})
    etat = serveur.PARTIE.exige()
    enfant = moteur.ajouter_personne(etat, "Nino", 6, "agriculture")
    with pytest.raises(ValueError, match="6 ans"):
        serveur.traiter("/api/affectation", {"id": enfant.id, "tache": "bois"})


def test_politique_natalite():
    serveur.traiter("/api/nouvelle", {})
    d = serveur.traiter("/api/politique", {"cle": "natalite", "valeur": 0.9})
    assert d["etat"]["politique"]["natalite"] == 0.9
    d = serveur.traiter("/api/politique", {"cle": "natalite", "valeur": 5})
    assert d["etat"]["politique"]["natalite"] == 1.0
    with pytest.raises(ValueError, match="politique inconnue"):
        serveur.traiter("/api/politique", {"cle": "guerre", "valeur": 1})
