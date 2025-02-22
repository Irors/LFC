from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import random
import requests
from config.constants import *
from core.nonce_manager import NonceManager


class JumperModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.settings = SETTINGS["JUMPER"]
        self.headers = {
            'x-lifi-integrator': 'jumper.exchange',
            'x-lifi-sdk': '3.1.3',
            'x-lifi-widget': '3.2.2',
        }

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None) -> list[Chain]:
        try:
            log_status(wallet_number or 0, "Getting available chains for Jumper")
            headers = {
                'Referer': 'https://jumper.exchange/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            routes_response = requests.get('https://api.jumper.exchange/p/lifi/tools', headers=headers, proxies=proxy)
            routes_data = routes_response.json()

            # Собираем chain_ids
            available_chain_ids = set()
            for bridge in routes_data["bridges"]:
                for route in bridge["supportedChains"]:
                    if route["fromChainId"] == 1135:
                        available_chain_ids.add(route["toChainId"])
                    elif route["toChainId"] == 1135:
                        available_chain_ids.add(route["fromChainId"])

            available_chains = []
            for chain_id in available_chain_ids:
                if chain_id != 1:
                    chain_info_response = requests.get(f'https://chainid.network/chains.json', proxies=proxy)
                    chains_data = chain_info_response.json()

                    chain_info = next((chain for chain in chains_data if chain["chainId"] == chain_id), None)

                    if chain_info and chain_info['nativeCurrency']['symbol'] == 'ETH':
                        available_chains.append(
                            Chain(
                                id=chain_id,
                                name=chain_info["name"],
                                rpc_url=chain_info["rpc"][0] if chain_info.get("rpc") else "",
                                currency_address=self.settings["TO_TOKEN"],
                                is_enabled=True,
                                supports_deposits=True
                            )
                        )

            return available_chains

        except Exception as e:
            log_transaction_error(wallet_number or 0, f"Error getting available chains: {str(e)}",
                                  "Jumper initialization")
            return []

    def validate_balance(self, wallet: Wallet, wallet_number: int):
        """Проверка баланса и апрув токена"""
        log_status(wallet_number, "Validating balance for Jumper")

        if self.settings["FROM_TOKEN"] != '0x0000000000000000000000000000000000000000':
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(self.settings["FROM_TOKEN"]),
                abi=self.settings["TOKEN_ABI"]
            )

            balance = token_contract.functions.balanceOf(wallet.address).call()

            # Проверяем апрув
            allowance = token_contract.functions.allowance(
                wallet.address,
                self.settings["SPENDER_ADDRESS"]
            ).call()

            if allowance < balance:
                log_transaction_start(wallet_number, "Approving token for Jumper")

                approve_tx = token_contract.functions.approve(
                    self.settings["SPENDER_ADDRESS"],
                    2 ** 256 - 1
                ).build_transaction({
                    "from": wallet.address,
                    "nonce": self.w3.eth.get_transaction_count(wallet.address),
                    "gasPrice": self.w3.eth.gas_price,
                    "chainId": self.w3.eth.chain_id
                })

                approve_tx["gas"] = int(self.w3.eth.estimate_gas(approve_tx) * 1.5)
                signed_tx = self.w3.eth.account.sign_transaction(approve_tx, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

                log_transaction_success(wallet_number, tx_hash.hex(), "Token approval for Jumper")
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            self.value = int(balance * (random.randint(
                self.settings["AMOUNT_PERCENTAGE"]["MIN"],
                self.settings["AMOUNT_PERCENTAGE"]["MAX"]
            ) / 100))
        else:
            balance = self.w3.eth.get_balance(wallet.address)
            self.value = int(balance * (random.uniform(
                self.settings["AMOUNT_PERCENTAGE"]["MIN"],
                self.settings["AMOUNT_PERCENTAGE"]["MAX"]
            )))

    def check_bridge(self, wallet: Wallet, destination_chain: Chain, wallet_number: int) -> dict:
        """Проверка доступности бриджа и получение маршрута"""
        log_status(wallet_number, f"Checking Jumper bridge route to {destination_chain.name}")

        json_data = {
            'fromAddress': wallet.address,
            'fromAmount': str(self.value),
            'fromChainId': CHAIN_ID_LISK,
            'fromTokenAddress': self.settings["FROM_TOKEN"],
            'toChainId': destination_chain.id,
            'toTokenAddress': self.settings["TO_TOKEN"],
            'options': {
                'integrator': 'jumper.exchange',
                'order': 'CHEAPEST',
                'slippage': 0.005,
                'maxPriceImpact': 0.4,
                'allowSwitchChain': True,
            },
        }

        response = requests.post(
            'https://li.quest/v1/advanced/routes',
            headers=self.headers,
            json=json_data
        ).json()

        if not response.get("routes"):
            raise Exception(f'No available routes for {destination_chain.name}')

        return response["routes"][0]

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            log_transaction_start(wallet_number, "Starting Jumper bridge transaction")

            # Проверяем баланс и делаем апрув
            self.validate_balance(wallet, wallet_number)

            # Получаем маршрут
            route = self.check_bridge(wallet, destination_chain, wallet_number)

            log_status(wallet_number, "Preparing Jumper transaction data")

            # Получаем данные для транзакции
            tx_data = requests.post(
                'https://li.quest/v1/advanced/stepTransaction',
                json=route["steps"][0]
            ).json()["transactionRequest"]["data"]

            # Создаем транзакцию
            tx = {
                "to": self.w3.to_checksum_address(self.settings["SPENDER_ADDRESS"]),
                "data": tx_data,
                "value": self.value if self.settings[
                                           "FROM_TOKEN"] == '0x0000000000000000000000000000000000000000' else 0,
                "chainId": self.w3.eth.chain_id,
                "nonce": self.w3.eth.get_transaction_count(wallet.address),
                "gasPrice": self.w3.eth.gas_price,
                "from": wallet.address
            }

            # Оценка газа
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.5)

            log_status(wallet_number, "Signing and sending Jumper transaction")

            # Подписываем и отправляем транзакцию
            signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            log_status(wallet_number, "Waiting for Jumper transaction confirmation")

            # Ждем подтверждения
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                log_transaction_success(wallet_number, tx_hash.hex(), "Jumper bridge transaction")
                return TransactionResult(
                    success=True,
                    tx_hash=tx_hash.hex(),
                    module_name=self.module_name
                )
            else:
                log_transaction_error(wallet_number, "Transaction failed", "Jumper bridge transaction")
                return TransactionResult(
                    success=False,
                    tx_hash=tx_hash.hex(),
                    error_message="Transaction failed",
                    module_name=self.module_name
                )

        except Exception as e:
            error_message = str(e)
            log_transaction_error(wallet_number, error_message, "Jumper bridge transaction")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )