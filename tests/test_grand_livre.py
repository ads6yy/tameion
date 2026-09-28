from datetime import date
from decimal import Decimal

import pytest

from tameion.grand_livre import COMPTE_TRESORERIE, GrandLivre, constat_rapprochement

ENTETE = """
2026-09-01 open Assets:Arc:Tresorerie USDC
2026-09-01 open Equity:Apport USDC
2026-09-01 open Expenses:Frais:Gas USDC

2026-09-28 * "Apport initial"
  Assets:Arc:Tresorerie  5.000000000000000000 USDC
  Equity:Apport  -5.000000000000000000 USDC
"""


@pytest.fixture
def grand_livre(tmp_path):
    chemin = tmp_path / "main.beancount"
    chemin.write_text(ENTETE, encoding="utf-8")
    return GrandLivre(chemin)


def test_operation_le_meme_jour_apres_un_rapprochement_est_acceptee(grand_livre):
    """Régression : l'ancienne assertion `balance` du lendemain refusait ce paiement."""
    grand_livre.ajouter(constat_rapprochement(date(2026, 9, 28), COMPTE_TRESORERIE, Decimal("5.000000000000000000"), 1))
    grand_livre.ajouter(
        '2026-09-28 * "Arc" "Gas"\n'
        "  Expenses:Frais:Gas  0.000525000000000000 USDC\n"
        "  Assets:Arc:Tresorerie  -0.000525000000000000 USDC"
    )
    assert grand_livre.verifier() == []
    assert grand_livre.solde(COMPTE_TRESORERIE) == Decimal("4.999475000000000000")


def test_ecriture_desequilibree_refusee_et_fichier_restaure(grand_livre):
    avant = grand_livre.chemin.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        grand_livre.ajouter(
            '2026-09-28 * "Faux"\n'
            "  Expenses:Frais:Gas  1.000000 USDC\n"
            "  Assets:Arc:Tresorerie  -0.900000 USDC"
        )
    assert grand_livre.chemin.read_text(encoding="utf-8") == avant
