from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS
from config.constants import *
from faker import Faker
from hashlib import sha256
import random
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
from web3 import Web3


class DmailModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.settings = SETTINGS["DMAIL"]
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACT_ADDRESSES["DMAIL"]['contract']),
            abi=CONTRACT_ADDRESSES["DMAIL"]['abi']
        )

    @staticmethod
    def generate_email():
        return f"{Faker().word()}{random.randint(1, 999999)}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com'])}"

    @staticmethod
    def generate_text():
        fake = Faker()
        return fake.text()

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None):
        return [
            Chain(
                id=SETTINGS["CHAIN_ID"],
                name="Lisk",
                rpc_url=SETTINGS["RPC_URL"],
                currency_address=TOKENS['ETH'],
                is_enabled=True,
                supports_deposits=True
            )
        ]

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            message_count = random.randint(self.settings["MESSAGE_COUNT"]["MIN"],
                                           self.settings["MESSAGE_COUNT"]["MAX"])

            tx_hash = None
            for i in range(message_count):
                log_transaction_start(wallet_number, f"Processing Dmail message {i + 1}/{message_count}")

                email = self.generate_email()
                text = self.generate_text()

                transaction = {
                    "from": wallet.address,
                    "gasPrice": self.w3.eth.gas_price,
                    "chainId": self.w3.eth.chain_id
                }

                log_status(wallet_number, "Preparing Dmail transaction data")

                tx = self.contract.functions.send_mail(
                    sha256(f"{email}".encode()).hexdigest(),
                    sha256(f"{text}".encode()).hexdigest()
                ).build_transaction(transaction)

                # Получаем nonce через NonceManager
                tx = self.prepare_transaction(wallet, tx)

                # Оценка газа
                tx["gas"] = self.w3.eth.estimate_gas(tx)

                log_status(wallet_number, "Signing and sending Dmail transaction")

                try:
                    # Подпись и отправка
                    signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
                    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                    if receipt["status"] != 1:
                        self.handle_failed_transaction(wallet, tx)
                        raise Exception("Transaction failed")

                    log_transaction_success(wallet_number, tx_hash.hex(), "Dmail transaction")

                except Exception as e:
                    self.handle_failed_transaction(wallet, tx)
                    raise e

            return TransactionResult(
                success=True,
                tx_hash=tx_hash.hex() if tx_hash else "",
                module_name=self.module_name
            )

        except Exception as e:
            error_message = str(e)
            log_transaction_error(wallet_number, error_message, "Dmail transaction")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )