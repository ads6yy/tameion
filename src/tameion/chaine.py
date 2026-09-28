"""Accès à Arc testnet : lecture du solde natif, envoi d'USDC natif (18 décimales)."""
from eth_account import Account
from web3 import Web3

GAS_TRANSFERT = 21_000
GWEI = 10**9


class Chaine:
    def __init__(self, rpc_url: str, chain_id: int, min_base_fee_gwei: int):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.min_base_fee = min_base_fee_gwei * GWEI
        if self.w3.eth.chain_id != chain_id:
            raise SystemExit(f"Le RPC ne répond pas pour la chaîne {chain_id}")

    def solde_wei(self, adresse: str) -> int:
        return self.w3.eth.get_balance(Web3.to_checksum_address(adresse))

    def solde_au_dernier_bloc(self, adresse: str) -> tuple[int, int]:
        """(numéro de bloc, solde en wei à ce bloc) : le constat est rattaché à un bloc précis."""
        bloc = self.w3.eth.block_number
        return bloc, self.w3.eth.get_balance(Web3.to_checksum_address(adresse), block_identifier=bloc)

    def frais_max(self) -> tuple[int, int]:
        """(maxFeePerGas, maxPriorityFeePerGas). Sous 20 Gwei, Arc jette la transaction sans erreur."""
        base = max(self.w3.eth.get_block("latest")["baseFeePerGas"], self.min_base_fee)
        priorite = self.w3.eth.max_priority_fee
        return 2 * base + priorite, priorite

    def cout_max_wei(self, valeur_wei: int) -> int:
        max_fee, _ = self.frais_max()
        return valeur_wei + GAS_TRANSFERT * max_fee

    def envoyer(self, cle_privee: str, destinataire: str, valeur_wei: int) -> str:
        compte = Account.from_key(cle_privee)
        max_fee, priorite = self.frais_max()
        tx = {
            "type": 2,
            "chainId": self.chain_id,
            "nonce": self.w3.eth.get_transaction_count(compte.address, "pending"),
            "to": Web3.to_checksum_address(destinataire),
            "value": valeur_wei,
            "gas": GAS_TRANSFERT,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priorite,
        }
        signee = compte.sign_transaction(tx)
        return self.w3.eth.send_raw_transaction(signee.raw_transaction).to_0x_hex()

    def attendre(self, tx_hash: str, timeout: int = 60) -> tuple[bool, int, int]:
        """(succès, frais réels en wei, numéro de bloc)."""
        recu = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return recu["status"] == 1, recu["gasUsed"] * recu["effectiveGasPrice"], recu["blockNumber"]
