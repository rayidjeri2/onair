import random

import pytest

from societe import actions, marche, moteur
from societe.modele import Etat


def bourg(personnes=10, graine=3, route=True):
    e = moteur.creer_societe("Abeba", 28, graine=graine)
    moteur.faire_venir(e, personnes)
    e.batiments.update({"source": 1, "puits": 2, "maison_terre": 6, "cave": 1, "hangar": 1})
    if route:
        e.batiments["chemin"] = 1
    e.stocks.update({"nourriture": 3000, "planches": 400, "recup": 900, "bois": 60})
    return e


def test_prix_baisse_avec_l_eloignement_et_monte_avec_la_route():
    e = bourg(route=False)
    loin = marche.prix_courant(e, "planches")
    e.batiments["chemin"] = 1
    assert marche.prix_courant(e, "planches") < loin  # la logistique rapproche les marchés
    assert marche.prix_courant(e, "outils") > marche.prix_courant(e, "bois")


def test_le_surplus_epargne_la_reserve_strategique():
    e = bourg()
    e.batiments["hangar"] = 20        # de quoi stocker au-delà de la réserve voulue
    moteur.regler_politique(e, "reserve_jours", 400)
    assert "nourriture" not in marche.surplus(e)
    moteur.regler_politique(e, "reserve_jours", 5)
    assert marche.surplus(e)["nourriture"] > 1000


def test_ce_qui_ne_tient_pas_dans_le_grenier_part_quand_meme():
    """Garder 400 jours de vivres sans hangar n'a pas de sens : ça pourrirait."""
    e = bourg()                       # grenier bien plus petit que la réserve voulue
    moteur.regler_politique(e, "reserve_jours", 400)
    assert marche.surplus(e)["nourriture"] > 0


def test_une_caravane_vend_le_surplus_et_remplit_le_tresor():
    e = bourg()
    moteur.regler_politique(e, "reserve_jours", 10)
    bilan = marche.caravane(e, random.Random(1), forcee=True)
    assert bilan["passee"] and bilan["ventes"]
    assert bilan["recette"] > 0
    assert e.tresor > 0 or sum(p.avoir for p in e.personnes) > 0
    assert any(j["genre"] == "commerce" for j in e.journal.entrees)


def test_une_caravane_achete_ce_qui_bloque_les_chantiers():
    e = bourg()
    e.tresor = 5000
    e.stocks["planches"] = 0
    moteur.regler_politique(e, "reserve_jours", 10)
    bilan = marche.caravane(e, random.Random(2), forcee=True)
    assert bilan["achats"]
    assert e.stocks["planches"] > 0


def test_la_route_fermee_arrete_tout():
    e = bourg()
    moteur.regler_politique(e, "commerce", 0)
    assert marche.caravane(e, random.Random(3))["passee"] is False
    moteur.avancer(e, 200)
    assert e.tresor == 0


def test_sans_chemin_ni_roue_personne_ne_vient():
    e = bourg(route=False)
    moteur.avancer(e, 200)
    assert not e.dernier_marche
    e.decouvertes.append("roue")
    moteur.avancer(e, 120)
    assert e.dernier_marche


def test_l_impot_partage_entre_tresor_et_fortunes():
    def repartition(part):
        e = bourg()
        moteur.regler_politique(e, "impot", part)
        moteur.regler_politique(e, "reserve_jours", 10)
        marche.caravane(e, random.Random(4), forcee=True)
        return e.tresor, sum(p.avoir for p in e.personnes)

    tout_commun, rien_prive = repartition(1.0)
    rien_commun, tout_prive = repartition(0.0)
    assert tout_commun > rien_commun
    assert tout_prive > rien_prive


def test_l_inegalite_apparait_puis_se_corrige():
    e = bourg()
    moteur.regler_politique(e, "impot", 0.0)
    moteur.regler_politique(e, "reserve_jours", 10)
    for _ in range(4):
        marche.caravane(e, random.Random(5), forcee=True)
    assert marche.inegalite(e) > 0
    actions.appliquer(e, "redistribuer", {"part": 100})
    assert marche.inegalite(e) == pytest.approx(0.0, abs=0.01)


def test_la_fortune_se_depense_et_remonte_le_moral():
    e = bourg()
    for p in e.personnes:
        p.avoir = 500.0
        p.moral = 40.0
    marche._depenser(e)
    assert all(p.avoir < 500 for p in e.personnes)
    assert all(p.moral > 40 for p in e.personnes)


def test_la_prosperite_attire_du_monde():
    e = bourg()
    e.tresor = 100_000
    e.batiments["maison_terre"] = 40
    avant = e.population
    alea = random.Random(6)
    for _ in range(400):
        marche.attirer(e, alea)
    assert e.population > avant
    assert e.tresor < 100_000


def test_embaucher_avance_les_chantiers():
    e = bourg()
    e.tresor = 1000
    moteur.lancer_chantier(e, "defrichage")
    avant = e.chantiers[0].travail_fait
    actions.appliquer(e, "embaucher", {"pieces": 500})
    assert e.chantiers[0].travail_fait > avant
    assert e.tresor == pytest.approx(500)


def test_le_commerce_survit_a_la_sauvegarde():
    e = bourg()
    moteur.regler_politique(e, "reserve_jours", 10)
    marche.caravane(e, random.Random(7), forcee=True)
    copie = Etat.depuis_dict(e.vers_dict())
    assert copie.tresor == e.tresor
    assert copie.dernier_marche == e.dernier_marche
    assert [p.avoir for p in copie.personnes] == [p.avoir for p in e.personnes]
