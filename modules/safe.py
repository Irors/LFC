from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import random
from config.constants import *


class SafeModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.settings = SETTINGS
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACT_ADDRESSES["SAFE"]['contract']),
            abi=CONTRACT_ADDRESSES['SAFE']['ABI']
        )

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None):
        return [
            Chain(
                id=CHAIN_ID_LISK,
                name="Lisk",
                rpc_url=RPC_URL,
                currency_address=TOKENS['ETH'],
                is_enabled=True,
                supports_deposits=True
            )
        ]

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict, wallet_number: int) -> TransactionResult:
        # try:
            log_transaction_start(wallet_number, "Creating Safe transaction")

            # Генерируем случайный nonce
            random_nonce = random.randint(
                self.settings["SAFE"]["NONCE_RANGE"]["MIN"],
                self.settings["SAFE"]["NONCE_RANGE"]["MAX"]
            )

            log_status(wallet_number, "Preparing Safe contract interaction")

            # Создаем транзакцию через метод контракта
            tx = self.contract.functions.createProxyWithNonce(
                self.w3.to_checksum_address(CONTRACT_ADDRESSES["SAFE"]["IMPLEMENTATION"]),
                CONTRACT_ADDRESSES["SAFE"]["ENCODED_PARAMS"],
                random_nonce
            ).build_transaction({
                "from": wallet.address,
                "nonce": self.w3.eth.get_transaction_count(wallet.address),
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id
            })

            # Оценка газа
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.5)

            log_status(wallet_number, "Signing and sending Safe transaction")

            # Подписываем и отправляем транзакцию
            signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Ждем подтверждения
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                log_transaction_success(wallet_number, tx_hash.hex(), "Safe deployment")
                return TransactionResult(
                    success=True,
                    tx_hash=tx_hash.hex(),
                    module_name=self.module_name
                )
            else:
                log_transaction_error(wallet_number, "Transaction failed", "Safe deployment")
                return TransactionResult(
                    success=False,
                    tx_hash=tx_hash.hex(),
                    error_message="Transaction failed",
                    module_name=self.module_name
                )

        # except Exception as e:
        #     error_message = str(e)
        #     log_transaction_error(wallet_number, error_message, "Safe deployment")
        #     return TransactionResult(
        #         success=False,
        #         error_message=error_message,
        #         module_name=self.module_name
        #     )