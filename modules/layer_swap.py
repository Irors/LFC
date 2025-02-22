from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import requests
import random
from config.constants import *


class LayerSwapModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.settings = SETTINGS["LAYERSWAP"]
        self.headers = {"X-LS-APIKEY": self.settings["API_KEY"]}
        self.networks = self.settings["TO_CHAIN"]

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            log_transaction_start(wallet_number, "Checking Layerswap bridge availability")

            balance = self.w3.eth.get_balance(wallet.address)
            balance_eth = float(Web3.from_wei(balance, 'ether'))

            # Определяем сумму для бриджа
            min_amount = balance_eth * self.settings["AMOUNT_PERCENTAGE"]["MIN"]
            max_amount = balance_eth * self.settings["AMOUNT_PERCENTAGE"]["MAX"]

            amount_to_bridge = random.uniform(min_amount, max_amount)

            # Проверяем возможность бриджа
            if not self.check_swap_rate(
                    self.settings["FROM_NETWORK"],
                    destination_chain.name.lower(),
                    amount_to_bridge
            ):
                raise Exception("Bridge amount out of limits")

            log_status(wallet_number, "Getting Layerswap transaction data")

            # Получаем данные для транзакции
            tx_data = self.create_swap(
                wallet,
                self.settings["FROM_NETWORK"],
                destination_chain.name.lower(),
                amount_to_bridge
            )

            # Создаем транзакцию
            transaction = {
                "from": wallet.address,
                "to": self.w3.to_checksum_address(tx_data["to_address"]),
                "value": Web3.to_wei(amount_to_bridge, 'ether'),
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id
            }

            # Получаем nonce через NonceManager
            transaction = self.prepare_transaction(wallet, transaction)

            # Оценка газа
            estimated_gas = self.w3.eth.estimate_gas(transaction)
            transaction["gas"] = int(estimated_gas * 1.5)

            log_status(
                wallet_number,
                f"Bridging {amount_to_bridge:.6f} ETH to {destination_chain.name}"
            )

            try:
                # Подписываем и отправляем транзакцию
                signed_tx = self.w3.eth.account.sign_transaction(transaction, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                # Ждем подтверждения
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    log_transaction_success(wallet_number, tx_hash.hex(), "Layerswap bridge transaction")
                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash.hex(),
                        module_name=self.module_name
                    )
                else:
                    self.handle_failed_transaction(wallet, transaction)
                    log_transaction_error(wallet_number, "Transaction failed", "Layerswap bridge transaction")
                    return TransactionResult(
                        success=False,
                        tx_hash=tx_hash.hex(),
                        error_message="Transaction failed",
                        module_name=self.module_name
                    )

            except Exception as e:
                self.handle_failed_transaction(wallet, transaction)
                raise e

        except Exception as e:
            error_message = str(e)
            log_transaction_error(wallet_number, error_message, "Layerswap bridge transaction")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )

    # Остальные методы остаются без изменений
    def get_available_chains(self, wallet_number: int = None, proxy: dict = None):
        available_chains = []
        source = self.networks.get(self.settings["FROM_NETWORK"].lower())

        if not source:
            log_transaction_error(wallet_number or 0, f"Network {self.settings['FROM_NETWORK']} not supported")
            return []

        for network_name in self.networks:
            if network_name == self.settings["FROM_NETWORK"].lower():
                continue

            params = {
                "source": source,
                "destination": self.networks[network_name],
                "sourceAsset": "ETH",
                "destinationAsset": "ETH",
            }

            try:
                response = requests.get(
                    "https://api.layerswap.io/api/available_routes",
                    params=params,
                    proxies=proxy
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("data"):
                        available_chains.append(
                            Chain(
                                id=self.get_chain_id(network_name),
                                name=network_name.capitalize(),
                                rpc_url=self.get_rpc_url(network_name),
                                currency_address=TOKENS["ETH"],
                                is_enabled=True,
                                supports_deposits=True
                            )
                        )

            except Exception as e:
                log_transaction_error(wallet_number or 0, f"Error checking route for {network_name}: {str(e)}")

        return available_chains

    def check_swap_rate(self, from_network: str, to_network: str, amount: float) -> bool:
        """Проверка лимитов для суммы бриджа"""
        params = {
            "source": self.networks[from_network.lower()],
            "source_asset": "ETH",
            "destination": self.networks[to_network.lower()],
            "destination_asset": "ETH",
            "refuel": False
        }

        try:
            response = requests.post(
                "https://api.layerswap.io/api/swap_rate",
                json=params
            )

            if response.status_code == 200:
                data = response.json().get("data", {})
                return data.get("min_amount", 0) <= amount <= data.get("max_amount", float("inf"))
            return False

        except Exception as e:
            log_transaction_error(0, f"Error checking swap rate: {str(e)}")
            return False

    def create_swap(self, wallet: Wallet, from_network: str, to_network: str, amount: float) -> dict:
        """Создание свапа и получение данных для транзакции"""
        params = {
            "source": self.networks[from_network.lower()],
            "source_asset": "ETH",
            "destination": self.networks[to_network.lower()],
            "destination_asset": "ETH",
            "refuel": False,
            "amount": amount,
            "destination_address": wallet.address
        }

        response = requests.post(
            "https://api.layerswap.io/api/swaps",
            headers=self.headers,
            json=params
        )

        if response.status_code != 200:
            raise Exception("Failed to create swap")

        swap_id = response.json()["data"]["swap_id"]

        params = {"from_address": wallet.address}
        response = requests.get(
            f"https://api.layerswap.io/api/swaps/{swap_id}/prepare_src_transaction",
            headers=self.headers,
            params=params
        )

        if response.status_code != 200:
            raise Exception("Failed to prepare transaction")

        return response.json()["data"]

    def get_chain_id(self, network: str) -> int:
        """Получение chain_id по имени сети"""
        chain_ids = {
            "ethereum": 1,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "polygon": 137,
            "base": 8453,
            "zksync": 324,
            "scroll": 534352
        }
        return chain_ids.get(network.lower())

    def get_rpc_url(self, network: str) -> str:
        """Получение RPC URL по имени сети"""
        return SETTINGS["RPC_URL"]  # Временное решение