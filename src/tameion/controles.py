"""Contrôles purs (sans réseau ni fichier). Chaque fonction renvoie la liste des refus, vide si tout va bien."""
from decimal import Decimal

from .montants import DECIMALES_FACTURE, decimales


def controler_facture(facture: dict, fournisseurs: dict, commandes: dict) -> list[str]:
    """Rapprochement à trois (facture / bon de commande / réception) et contrôle du référentiel fournisseur."""
    refus = []
    montant_texte = facture["montant"]
    if decimales(montant_texte) != DECIMALES_FACTURE:
        refus.append(f"montant {montant_texte} : {DECIMALES_FACTURE} décimales exactes attendues")
    montant = Decimal(montant_texte)
    if montant <= 0:
        refus.append("montant nul ou négatif")

    fournisseur = fournisseurs.get(facture["fournisseur"])
    if fournisseur is None:
        refus.append(f"fournisseur inconnu du référentiel : {facture['fournisseur']}")
    elif facture["adresse_paiement"].lower() != fournisseur["adresse"].lower():
        refus.append(
            f"adresse de paiement {facture['adresse_paiement']} différente du référentiel "
            f"({fournisseur['adresse']}) : changement de coordonnées à valider hors outil"
        )

    commande = commandes.get(facture["commande"])
    if commande is None:
        refus.append(f"bon de commande introuvable : {facture['commande']}")
    else:
        if commande["fournisseur"] != facture["fournisseur"]:
            refus.append(f"le bon {facture['commande']} est au nom d'un autre fournisseur")
        if Decimal(commande["montant"]) != montant:
            refus.append(f"montant facture {montant_texte} != montant commande {commande['montant']}")
        if not commande.get("recu_le"):
            refus.append(f"réception non constatée pour {facture['commande']}")
    return refus


def controler_paiement(
    facture: dict,
    comptabilisees: set[str],
    payees: set[str],
    envois_en_attente: dict[str, str],
    plafond: Decimal,
    solde_wei: int,
    cout_max_wei: int,
) -> list[str]:
    """Contrôles juste avant l'envoi : idempotence, plafond, solde."""
    refus = []
    fid = facture["id"]
    if fid not in comptabilisees:
        refus.append(f"{fid} n'est pas comptabilisée : lancer `tameion comptabiliser {fid}` d'abord")
    if fid in payees:
        refus.append(f"{fid} est déjà payée dans le grand livre")
    if fid in envois_en_attente:
        refus.append(f"envoi déjà parti pour {fid} sans confirmation (tx {envois_en_attente[fid]}) : vérifier avant tout nouvel essai")
    if Decimal(facture["montant"]) > plafond:
        refus.append(f"montant {facture['montant']} au-dessus du plafond {plafond}")
    if solde_wei < cout_max_wei:
        refus.append(f"solde insuffisant : {solde_wei} wei < {cout_max_wei} wei (montant + gas max)")
    return refus
