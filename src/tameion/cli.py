"""Commandes : init, factures, comptabiliser, payer, rapprocher, verifier."""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from eth_account import Account

from . import config as cfg
from .chaine import Chaine
from .controles import controler_facture, controler_paiement
from .grand_livre import COMPTE_APPORT, COMPTE_FOURNISSEURS, COMPTE_GAS, COMPTE_TRESORERIE, GrandLivre
from .montants import usdc_vers_wei, wei_vers_usdc


def _lire_json(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


def _factures(c: cfg.Config) -> dict[str, dict]:
    return {f["id"]: f for f in (_lire_json(p) for p in sorted(c.factures.glob("*.json")))}


def _facture(c: cfg.Config, fid: str) -> dict:
    factures = _factures(c)
    if fid not in factures:
        raise SystemExit(f"Facture inconnue : {fid}")
    return factures[fid]


def _envois_en_attente(c: cfg.Config) -> dict[str, str]:
    """Dernier statut par facture ; 'envoye' sans 'confirme'/'echec' = en attente."""
    dernier: dict[str, dict] = {}
    if c.envois.exists():
        for ligne in c.envois.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                e = json.loads(ligne)
                dernier[e["facture"]] = e
    return {fid: e["tx_hash"] for fid, e in dernier.items() if e["statut"] == "envoye"}


def _journaliser_envoi(c: cfg.Config, fid: str, tx_hash: str, statut: str) -> None:
    ligne = {"facture": fid, "tx_hash": tx_hash, "statut": statut, "horodatage": datetime.now(timezone.utc).isoformat()}
    with c.envois.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne) + "\n")


def _chaine(c: cfg.Config) -> Chaine:
    return Chaine(c.rpc_url, c.chain_id, c.min_base_fee_gwei)


def cmd_init(c: cfg.Config, _args) -> None:
    gl = GrandLivre(c.ledger)
    if gl.a_un_apport():
        raise SystemExit("Apport initial déjà enregistré.")
    solde = wei_vers_usdc(_chaine(c).solde_wei(c.adresse_wallet))
    aujourdhui = date.today()
    gl.ajouter(
        f'{aujourdhui} * "Apport initial" "Solde constaté sur Arc testnet"\n'
        f'  nature: "apport"\n'
        f"  {COMPTE_TRESORERIE}  {solde:f} USDC\n"
        f"  {COMPTE_APPORT}  {-solde:f} USDC\n\n"
        f"{aujourdhui + timedelta(days=1)} balance {COMPTE_TRESORERIE}  {solde:f} USDC"
    )
    print(f"Apport initial enregistré : {solde:f} USDC")


def cmd_factures(c: cfg.Config, _args) -> None:
    gl = GrandLivre(c.ledger)
    comptabilisees, payees = gl.factures("facture"), gl.factures("paiement")
    fournisseurs, commandes = _lire_json(c.fournisseurs), _lire_json(c.commandes)
    for fid, f in _factures(c).items():
        statut = "payée" if fid in payees else "comptabilisée" if fid in comptabilisees else "à comptabiliser"
        print(f"{fid}  {f['montant']} USDC  {fournisseurs.get(f['fournisseur'], {}).get('nom', f['fournisseur'])}  [{statut}]")
        for r in controler_facture(f, fournisseurs, commandes):
            print(f"    REFUS : {r}")


def cmd_comptabiliser(c: cfg.Config, args) -> None:
    gl = GrandLivre(c.ledger)
    facture = _facture(c, args.facture)
    fournisseurs, commandes = _lire_json(c.fournisseurs), _lire_json(c.commandes)
    if facture["id"] in gl.factures("facture"):
        raise SystemExit(f"{facture['id']} est déjà comptabilisée.")
    refus = controler_facture(facture, fournisseurs, commandes)
    if refus:
        raise SystemExit("Comptabilisation refusée :\n  " + "\n  ".join(refus))
    fournisseur = fournisseurs[facture["fournisseur"]]
    montant = Decimal(facture["montant"])
    gl.ajouter(
        f'{facture["date"]} * "{fournisseur["nom"]}" "Facture {facture["id"]} : {facture["libelle"]}"\n'
        f'  nature: "facture"\n'
        f'  facture: "{facture["id"]}"\n'
        f'  commande: "{facture["commande"]}"\n'
        f'  document: "{c.factures.relative_to(c.racine) / (facture["id"] + ".json")}"\n'
        f"  {fournisseur['compte_charge']}  {montant:f} USDC\n"
        f"  {COMPTE_FOURNISSEURS}  {-montant:f} USDC"
    )
    print(f"{facture['id']} comptabilisée : {montant:f} USDC dus à {fournisseur['nom']}")


def cmd_payer(c: cfg.Config, args) -> None:
    gl = GrandLivre(c.ledger)
    facture = _facture(c, args.facture)
    fournisseurs, commandes = _lire_json(c.fournisseurs), _lire_json(c.commandes)
    chaine = _chaine(c)
    valeur_wei = usdc_vers_wei(Decimal(facture["montant"]))

    # Le référentiel est recontrôlé au moment de payer : il a pu changer depuis la comptabilisation.
    refus = controler_facture(facture, fournisseurs, commandes) + controler_paiement(
        facture,
        comptabilisees=gl.factures("facture"),
        payees=gl.factures("paiement"),
        envois_en_attente=_envois_en_attente(c),
        plafond=c.plafond_paiement,
        solde_wei=chaine.solde_wei(c.adresse_wallet),
        cout_max_wei=chaine.cout_max_wei(valeur_wei),
    )
    if refus:
        raise SystemExit("Paiement refusé :\n  " + "\n  ".join(refus))

    fournisseur = fournisseurs[facture["fournisseur"]]
    destinataire = fournisseur["adresse"]
    print(f"Plan : {facture['montant']} USDC ({valeur_wei} wei) de {c.adresse_wallet} vers {fournisseur['nom']} {destinataire}")
    if not args.executer:
        print("Simulation uniquement. Relancer avec --executer pour envoyer.")
        return

    cle = cfg.cle_privee()
    if Account.from_key(cle).address.lower() != c.adresse_wallet.lower():
        raise SystemExit("La clé privée ne correspond pas à wallet.address de config.toml.")

    tx_hash = chaine.envoyer(cle, destinataire, valeur_wei)
    _journaliser_envoi(c, facture["id"], tx_hash, "envoye")  # avant l'attente : un crash ici bloque tout nouvel essai
    print(f"Envoyée : {c.explorer_url}/tx/{tx_hash}")

    succes, frais_wei, bloc = chaine.attendre(tx_hash)
    frais = wei_vers_usdc(frais_wei)
    montant = Decimal(facture["montant"])
    if not succes:
        _journaliser_envoi(c, facture["id"], tx_hash, "echec")
        gl.ajouter(
            f'{date.today()} * "Arc" "Échec paiement {facture["id"]} (gas seul)"\n'
            f'  tx_hash: "{tx_hash}"\n'
            f"  {COMPTE_GAS}  {frais:f} USDC\n"
            f"  {COMPTE_TRESORERIE}  {-frais:f} USDC"
        )
        raise SystemExit(f"Transaction revert (bloc {bloc}) : seul le gas a été débité et enregistré.")

    gl.ajouter(
        f'{date.today()} * "{fournisseur["nom"]}" "Paiement {facture["id"]}"\n'
        f'  nature: "paiement"\n'
        f'  facture: "{facture["id"]}"\n'
        f'  tx_hash: "{tx_hash}"\n'
        f'  bloc: "{bloc}"\n'
        f"  {COMPTE_FOURNISSEURS}  {montant:f} USDC\n"
        f"  {COMPTE_GAS}  {frais:f} USDC\n"
        f"  {COMPTE_TRESORERIE}  {-(montant + frais):f} USDC"
    )
    _journaliser_envoi(c, facture["id"], tx_hash, "confirme")
    print(f"Payée et comptabilisée (bloc {bloc}, gas {frais:f} USDC). Lancer `tameion rapprocher`.")


def cmd_rapprocher(c: cfg.Config, _args) -> None:
    gl = GrandLivre(c.ledger)
    onchain = wei_vers_usdc(_chaine(c).solde_wei(c.adresse_wallet))
    livre = gl.solde(COMPTE_TRESORERIE)
    print(f"Solde onchain       : {onchain:f} USDC")
    print(f"Solde grand livre   : {livre} USDC")
    if onchain != livre:
        raise SystemExit(
            f"ÉCART de {onchain - livre} USDC : une opération manque ou est fausse dans le grand livre. "
            "Rien n'a été écrit."
        )
    # Une assertion beancount porte sur le début de sa journée : on la date du lendemain.
    gl.ajouter(f"{date.today() + timedelta(days=1)} balance {COMPTE_TRESORERIE}  {onchain:f} USDC")
    print("Rapproché : assertion de solde ajoutée.")


def cmd_verifier(c: cfg.Config, _args) -> None:
    erreurs = GrandLivre(c.ledger).verifier()
    if erreurs:
        raise SystemExit("Grand livre invalide :\n  " + "\n  ".join(erreurs))
    print("Grand livre valide.")


def main() -> None:
    p = argparse.ArgumentParser(prog="tameion")
    sp = p.add_subparsers(dest="commande", required=True)
    sp.add_parser("init", help="Enregistre l'apport initial à partir du solde onchain").set_defaults(fn=cmd_init)
    sp.add_parser("factures", help="Liste les factures et les contrôles").set_defaults(fn=cmd_factures)
    s = sp.add_parser("comptabiliser", help="Comptabilise une facture après contrôles")
    s.add_argument("facture")
    s.set_defaults(fn=cmd_comptabiliser)
    s = sp.add_parser("payer", help="Paie une facture (simulation par défaut)")
    s.add_argument("facture")
    s.add_argument("--executer", action="store_true", help="Envoie réellement la transaction")
    s.set_defaults(fn=cmd_payer)
    sp.add_parser("rapprocher", help="Compare solde onchain et grand livre").set_defaults(fn=cmd_rapprocher)
    sp.add_parser("verifier", help="Valide le grand livre avec beancount").set_defaults(fn=cmd_verifier)
    args = p.parse_args()
    args.fn(cfg.charger(), args)
