from decimal import Decimal

import pytest

from tameion.controles import controler_facture, controler_paiement
from tameion.montants import usdc_vers_wei, wei_vers_usdc

ADRESSE = "0xEDca0e8636738A29Dd42539A40F3C5974f641C3a"
FOURNISSEURS = {"alpha": {"nom": "Alpha", "adresse": ADRESSE, "compte_charge": "Expenses:X"}}
COMMANDES = {"BC-1": {"fournisseur": "alpha", "montant": "0.250000", "recu_le": "2026-09-25"}}


def facture(**surcharge):
    base = {"id": "F-1", "fournisseur": "alpha", "commande": "BC-1", "montant": "0.250000", "adresse_paiement": ADRESSE}
    return base | surcharge


def test_facture_conforme():
    assert controler_facture(facture(), FOURNISSEURS, COMMANDES) == []


def test_adresse_de_paiement_modifiee_refusee():
    refus = controler_facture(facture(adresse_paiement="0x" + "1" * 40), FOURNISSEURS, COMMANDES)
    assert any("différente du référentiel" in r for r in refus)


def test_montant_different_de_la_commande_refuse():
    refus = controler_facture(facture(montant="0.260000"), FOURNISSEURS, COMMANDES)
    assert any("!= montant commande" in r for r in refus)


def test_precision_imprecise_refusee():
    refus = controler_facture(facture(montant="0.25"), FOURNISSEURS, COMMANDES)
    assert any("6 décimales" in r for r in refus)


def test_reception_absente_refusee():
    commandes = {"BC-1": COMMANDES["BC-1"] | {"recu_le": None}}
    assert any("réception" in r for r in controler_facture(facture(), FOURNISSEURS, commandes))


def _paiement(**surcharge):
    args = dict(comptabilisees={"F-1"}, payees=set(), envois_en_attente={}, plafond=Decimal("0.50"),
                solde_wei=10**18, cout_max_wei=3 * 10**17)
    return controler_paiement(facture(), **(args | surcharge))


def test_paiement_conforme():
    assert _paiement() == []


def test_double_paiement_refuse():
    assert any("déjà payée" in r for r in _paiement(payees={"F-1"}))


def test_envoi_en_attente_bloque_le_nouvel_essai():
    assert any("sans confirmation" in r for r in _paiement(envois_en_attente={"F-1": "0xabc"}))


def test_plafond_et_solde():
    refus = _paiement(plafond=Decimal("0.10"), solde_wei=1)
    assert any("plafond" in r for r in refus) and any("solde insuffisant" in r for r in refus)


def test_conversions_exactes():
    assert usdc_vers_wei(Decimal("0.250000")) == 250_000_000_000_000_000
    assert wei_vers_usdc(21_000 * 20 * 10**9) == Decimal("0.000420000000000000")
    with pytest.raises(ValueError):
        usdc_vers_wei(Decimal("1e-19"))
