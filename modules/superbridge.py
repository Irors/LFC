from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import requests
import random
from config.constants import *


class SuperBridgeModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.settings = SETTINGS["SUPERBRIDGE"]
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': 'https://superbridge.app',
            'referer': 'https://superbridge.app/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_chain_info(self, wallet_number: int, proxy: dict) -> dict:
        try:
            log_status(wallet_number, "Getting chain information for SuperBridge")
            response = requests.get('https://chainid.network/chains.json', proxies=proxy)
            if response.status_code == 200:
                chains_data = response.json()
                return {
                    chain['chainId']: {
                        'rpc': chain.get('rpc', [])[0] if chain.get('rpc') else None,
                        'name': chain.get('name'),
                        'currency': chain.get('nativeCurrency', {}).get('symbol')
                    }
                    for chain in chains_data
                }
            return {}
        except Exception as e:
            log_transaction_error(wallet_number, f"Failed to get chains info: {e}", "SuperBridge initialization")
            return {}

    def get_gas_price(self, chain_id: int, wallet_number: int, proxy: dict) -> str:
        """Получение gas price в сети назначения"""
        try:
            chains_info = self.get_chain_info(wallet_number, proxy)
            if chain_id in chains_info and chains_info[chain_id]['rpc']:
                w3 = Web3(Web3.HTTPProvider(chains_info[chain_id]['rpc']))
                gas_price = w3.eth.gas_price
                return str(gas_price)
        except Exception as e:
            log_transaction_error(wallet_number, f"Failed to get gas price for chain {chain_id}: {e}", "SuperBridge gas check")

        return "3294362"  # дефолтное значение

    def get_bridge_data(self, wallet: str, destination_chain_id: int, amount_wei: int, wallet_number: int,
                        proxy: dict) -> dict:
        """Получение данных для бриджа"""
        log_status(wallet_number, f"Getting SuperBridge route data for chain ID {destination_chain_id}")

        payload = {
            "host": "superbridge.app",
            "amount": str(amount_wei),
            "fromChainId": str(SETTINGS["CHAIN_ID"]),
            "toChainId": str(destination_chain_id),
            "fromTokenAddress": TOKENS["ETH"],
            "toTokenAddress": TOKENS["ETH"],
            "fromTokenDecimals": 18,
            "toTokenDecimals": 18,
            "fromGasPrice": str(self.w3.eth.gas_price),
            "toGasPrice": self.get_gas_price(destination_chain_id, wallet_number, proxy),
            "graffiti": "superbridge",
            "recipient": wallet,
            "sender": wallet,
            "forceViaL1": False
        }

        response = requests.post(
            'https://api.superbridge.app/api/v2/bridge/routes',
            headers=self.headers,
            json=payload,
            proxies=proxy
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get bridge routes: {response.text}")

        data = response.json()

        # Проверяем на ошибку AmountTooSmall
        if "AmountTooSmall" in str(data):
            amount_eth = Web3.from_wei(amount_wei, 'ether')
            raise Exception(f"Amount too small: {amount_eth} ETH")

        if not data.get("results"):
            raise Exception("No bridge routes available")

        return data["results"][0]["result"]

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            # Создаем прокси для запросов
            proxy = None
            if wallet.proxy:
                proxy = {
                    'http': wallet.proxy.as_url(),
                    'https': wallet.proxy.as_url()
                }

            log_transaction_start(wallet_number, f"Starting SuperBridge transaction to {destination_chain.name}")

            # Проверяем баланс
            balance = self.w3.eth.get_balance(wallet.address)
            balance_eth = float(Web3.from_wei(balance, 'ether'))

            # Определяем сумму для бриджа
            amount_to_bridge = random.uniform(
                balance_eth * (self.settings["AMOUNT_PERCENTAGE"]["MIN"]),
                balance_eth * (self.settings["AMOUNT_PERCENTAGE"]["MAX"])
            )

            amount_in_wei = Web3.to_wei(amount_to_bridge, 'ether')

            log_status(
                wallet_number,
                f"Getting SuperBridge route for {amount_to_bridge:.6f} ETH to {destination_chain.name}"
            )

            # Получаем данные для транзакции
            bridge_data = self.get_bridge_data(wallet.address, destination_chain.id, amount_in_wei, wallet_number,
                                               proxy)
            tx_data = bridge_data["initiatingTransaction"]

            log_status(wallet_number, "Preparing SuperBridge transaction")

            # Создаем транзакцию
            transaction = {
                "from": wallet.address,
                "to": self.w3.to_checksum_address(tx_data["to"]),
                "data": tx_data["data"],
                "value": int(tx_data["value"]),
                "gasPrice": self.w3.eth.gas_price,
                "chainId": self.w3.eth.chain_id
            }

            # Получаем nonce через NonceManager
            transaction = self.prepare_transaction(wallet, transaction)

            # Оценка газа
            estimated_gas = bridge_data["steps"][0]["estimatedGasLimit"]
            transaction["gas"] = int(estimated_gas * 1.5)  # Добавляем множитель для надежности

            log_status(wallet_number, "Signing and sending SuperBridge transaction")

            try:
                # Подписываем и отправляем транзакцию
                signed_tx = self.w3.eth.account.sign_transaction(transaction, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                log_status(
                    wallet_number,
                    f"Bridging {amount_to_bridge:.6f} ETH to {destination_chain.name}"
                )

                # Ждем подтверждения
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    log_transaction_success(wallet_number, tx_hash.hex(), "SuperBridge transaction")
                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash.hex(),
                        module_name=self.module_name
                    )
                else:
                    self.handle_failed_transaction(wallet, transaction)
                    log_transaction_error(wallet_number, "Transaction failed", "SuperBridge transaction")
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
            log_transaction_error(wallet_number, error_message, "SuperBridge transaction")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None):
        """Получение списка доступных сетей для бриджа"""
        log_status(wallet_number or 0, "Getting available chains for SuperBridge")
        supported_chains = [8453, 10, 34443, 7777777, 130]  # ID поддерживаемых сетей
        chains_info = self.get_chain_info(wallet_number, proxy)

        available_chains = []
        for chain_id in supported_chains:
            if chain_id in chains_info:
                chain_data = chains_info[chain_id]
                available_chains.append(
                    Chain(
                        id=chain_id,
                        name=chain_data['name'],
                        rpc_url=chain_data['rpc'],
                        currency_address=TOKENS["ETH"],
                        is_enabled=True,
                        supports_deposits=True
                    )
                )

        return available_chains