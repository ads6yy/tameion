"""Arc testnet access: reading the native balance, sending native USDC (18 decimals)."""
from eth_account import Account
from web3 import Web3

TRANSFER_GAS = 21_000
GWEI = 10**9


class Chain:
    def __init__(self, rpc_url: str, chain_id: int, min_base_fee_gwei: int):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.min_base_fee = min_base_fee_gwei * GWEI
        if self.w3.eth.chain_id != chain_id:
            raise SystemExit(f"The RPC does not serve chain {chain_id}")

    def balance_wei(self, address: str) -> int:
        return self.w3.eth.get_balance(Web3.to_checksum_address(address))

    def balance_at_latest_block(self, address: str) -> tuple[int, int]:
        """(block number, balance in wei at that block): the record is tied to a precise block."""
        block = self.w3.eth.block_number
        return block, self.w3.eth.get_balance(Web3.to_checksum_address(address), block_identifier=block)

    def max_fees(self) -> tuple[int, int]:
        """(maxFeePerGas, maxPriorityFeePerGas). Below 20 Gwei, Arc silently drops the transaction."""
        base = max(self.w3.eth.get_block("latest")["baseFeePerGas"], self.min_base_fee)
        priority = self.w3.eth.max_priority_fee
        return 2 * base + priority, priority

    def max_cost_wei(self, value_wei: int) -> int:
        max_fee, _ = self.max_fees()
        return value_wei + TRANSFER_GAS * max_fee

    def send(self, private_key: str, recipient: str, value_wei: int) -> str:
        account = Account.from_key(private_key)
        max_fee, priority = self.max_fees()
        tx = {
            "type": 2,
            "chainId": self.chain_id,
            "nonce": self.w3.eth.get_transaction_count(account.address, "pending"),
            "to": Web3.to_checksum_address(recipient),
            "value": value_wei,
            "gas": TRANSFER_GAS,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
        }
        signed = account.sign_transaction(tx)
        return self.w3.eth.send_raw_transaction(signed.raw_transaction).to_0x_hex()

    def wait(self, tx_hash: str, timeout: int = 60) -> tuple[bool, int, int]:
        """(success, actual fee in wei, block number)."""
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt["status"] == 1, receipt["gasUsed"] * receipt["effectiveGasPrice"], receipt["blockNumber"]
