from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import random
from config.constants import *


class IonicModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.settings = SETTINGS["IONIC"]

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

    def check_token_balance(self, wallet: Wallet, token_address: str, token_contract) -> float:
        """Проверка баланса токена"""
        balance = token_contract.functions.balanceOf(wallet.address).call()
        decimals = token_contract.functions.decimals().call()
        return float(balance) / (10 ** decimals)  # Конвертация из wei

    def get_available_tokens(self, wallet: Wallet, wallet_number: int) -> list:
        """Получение списка доступных токенов с достаточным балансом"""
        log_status(wallet_number, "Checking available tokens for Ionic")
        available_tokens = []

        for token_symbol, token_data in self.settings["TOKENS"].items():
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_data["ADDRESS"]),
                abi=self.settings["ABI"]["TOKEN"]
            )

            balance = self.check_token_balance(wallet, token_data["ADDRESS"], token_contract)
            log_status(wallet_number, f"Token {token_symbol} balance: {balance:.6f}")

            if balance >= token_data["MIN_AMOUNT"]:
                available_tokens.append({
                    "symbol": token_symbol,
                    "address": token_data["ADDRESS"],
                    "balance": balance,
                    "contract": token_contract,
                    "data": token_data
                })

        return available_tokens

    def approve_token(self, wallet: Wallet, token_contract, spender_address: str, amount: int,
                      wallet_number: int) -> bool:
        try:
            log_transaction_start(wallet_number, "Approving token for Ionic supply")

            tx = token_contract.functions.approve(
                spender_address,
                amount * 18**10
            ).build_transaction({
                "from": wallet.address,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id
            })

            # Получаем nonce через NonceManager
            tx = self.prepare_transaction(wallet, tx)

            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.5)

            try:
                signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    log_transaction_success(wallet_number, tx_hash.hex(), "Token approval for Ionic")
                    return True
                else:
                    self.handle_failed_transaction(wallet, tx)
                    log_transaction_error(wallet_number, "Token approval failed", "Ionic approval")
                    return False

            except Exception as e:
                self.handle_failed_transaction(wallet, tx)
                raise e

        except Exception as e:
            log_transaction_error(wallet_number, str(e), "Ionic approval")
            return False

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            # Получаем доступные токены
            available_tokens = self.get_available_tokens(wallet, wallet_number)
            if not available_tokens:
                return TransactionResult(
                    success=False,
                    error_message="No tokens available for supply",
                    module_name=self.module_name
                )

            # Выбираем случайный токен
            token = random.choice(available_tokens)
            log_status(wallet_number, f"Selected token for Ionic supply: {token['symbol']}")

            # Создаем контракт для supply
            supply_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token["data"]["SUPPLY_CONTRACT"]),
                abi=self.settings["ABI"]["SUPPLY"]
            )

            # Определяем сумму для supply
            balance = token["balance"]
            supply_amount = int(random.uniform(
                balance * token["data"]["MIN_AMOUNT"],
                balance * min(token["data"]["MAX_AMOUNT"], token["balance"])
            ) * (10 ** token["contract"].functions.decimals().call()))

            # Делаем approve
            if not self.approve_token(
                    wallet,
                    token["contract"],
                    token["data"]["SUPPLY_CONTRACT"],
                    supply_amount * 2,  # Апрувим с запасом
                    wallet_number
            ):
                return TransactionResult(
                    success=False,
                    error_message="Token approval failed",
                    module_name=self.module_name
                )

            log_status(
                wallet_number,
                f"Supplying {supply_amount / (10 ** token['contract'].functions.decimals().call())} {token['symbol']} to Ionic"
            )

            # Делаем supply
            tx = supply_contract.functions.mint(
                supply_amount
            ).build_transaction({
                "from": wallet.address,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id
            })

            # Получаем nonce через NonceManager
            tx = self.prepare_transaction(wallet, tx)

            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.5)

            try:
                signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                log_status(wallet_number, "Waiting for Ionic supply transaction confirmation")

                # Ждем подтверждения транзакции
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    log_transaction_success(wallet_number, tx_hash.hex(), "Ionic supply")
                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash.hex(),
                        module_name=self.module_name
                    )
                else:
                    self.handle_failed_transaction(wallet, tx)
                    log_transaction_error(wallet_number, "Transaction failed", "Ionic supply")
                    return TransactionResult(
                        success=False,
                        tx_hash=tx_hash.hex(),
                        error_message="Transaction failed",
                        module_name=self.module_name
                    )

            except Exception as e:
                self.handle_failed_transaction(wallet, tx)
                raise e

        except Exception as e:
            error_message = str(e)
            log_transaction_error(wallet_number, error_message, "Ionic supply")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )