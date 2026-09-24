from dataclasses import replace

from onair import Simulation
from onair.audience import PopulationAuditeurs, Segment
from onair.scenarios import population_reference, station_reference, variante_saturee
from onair.simulation import PAS


def test_audience_bornee_par_la_population():
    r = Simulation(station_reference(), population_reference(), jours=2).executer()
    assert 0 < r.audience_moyenne < r.population
    assert r.pic_audience <= r.population


def test_resultat_deterministe_sans_bruit():
    a = Simulation(station_reference(), population_reference(), jours=2, bruit=0).executer()
    b = Simulation(station_reference(), population_reference(), jours=2, bruit=0).executer()
    assert a.audience_moyenne == b.audience_moyenne


def test_meme_graine_meme_resultat():
    a = Simulation(station_reference(), population_reference(), jours=2, graine=7).executer()
    b = Simulation(station_reference(), population_reference(), jours=2, graine=7).executer()
    assert a.revenu_total == b.revenu_total


def test_doubler_la_pub_fait_baisser_laudience():
    ref = Simulation(station_reference(), population_reference(), jours=3, bruit=0).executer()
    pub = Simulation(variante_saturee(station_reference()), population_reference(),
                     jours=3, bruit=0).executer()
    assert pub.audience_moyenne < ref.audience_moyenne
    assert pub.abandons_pub > ref.abandons_pub


def test_segment_indisponible_nallume_pas_la_radio():
    muet = Segment(nom="Absents", population=100_000,
                   affinites={g: 1.0 for g in ["matinale", "musique", "talk",
                                               "actualite", "sport", "nuit"]},
                   dispo=[0.0] * 24)
    r = Simulation(station_reference(), PopulationAuditeurs([muet]), jours=1, bruit=0).executer()
    assert r.audience_moyenne == 0.0


def test_echantillonnage_complet():
    jours = 2
    r = Simulation(station_reference(), population_reference(), jours=jours).executer()
    assert len(r.echantillons) == int(jours * 1440 / PAS) + 1


def test_export_json_serialisable():
    import json

    r = Simulation(station_reference(), population_reference(), jours=1).executer()
    d = r.vers_dict()
    json.dumps(d)
    assert len(d["par_heure"]) == 24
    assert len(d["jour_heure"]) == 7
    assert d["emissions"][0]["audience_moyenne"] >= d["emissions"][-1]["audience_moyenne"]
