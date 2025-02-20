import time
import random
import requests
from web3 import Web3
from typing import List
from core.wallet_manager import Chain, Wallet, TransactionResult
from core.base_module import BaseModule
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
from config.settings import SETTINGS
from config.constants import *


class RelayBridge(BaseModule):
    def __init__(self):
        super().__init__()
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.settings = SETTINGS["RELAY_BRIDGE"]
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None) -> List[Chain]:
        response = self.session.get(API_ENDPOINTS["RELAY"]["CHAINS"], proxies=proxy)
        data = response.json()

        chains = []
        for chain_data in data["chains"]:
            if not chain_data.get("disabled", False):
                chain = Chain(
                    id=int(chain_data["id"]),
                    name=chain_data["name"],
                    rpc_url=chain_data["httpRpcUrl"],
                    currency_address=chain_data["currency"]["address"],
                    is_enabled=not chain_data.get("disabled", False),
                    supports_deposits=chain_data.get("depositEnabled", True)
                )
                chains.append(chain)

        return [chain for chain in chains
                if chain.is_enabled
                and chain.supports_deposits
                and chain.id != API_ENDPOINTS["RELAY"]["ORIGIN_CHAIN_ID"]]

    def _prepare_transaction_data(self, quote_data: dict, wallet: Wallet) -> dict:
        """Подготовка данных транзакции"""
        tx_data = quote_data["steps"][0]["items"][0]["data"]
        tx_data.update({
            'value': int(tx_data['value']),
            'to': self.w3.to_checksum_address(tx_data['to']),
            'maxFeePerGas': int(tx_data['maxFeePerGas']),
            'maxPriorityFeePerGas': int(tx_data['maxPriorityFeePerGas']),
            'nonce': self.w3.eth.get_transaction_count(wallet.address)
        })
        return tx_data

    def _monitor_transaction(self, tx_hash: str, request_id: str, wallet_number: int) -> bool:
        """Мониторинг статуса транзакции"""
        for attempt in range(self.settings["MAX_STATUS_CHECKS"]):
            log_status(wallet_number, f"Checking Relay transaction status (attempt {attempt + 1}/{self.settings['MAX_STATUS_CHECKS']})")
            status_data = self._check_transaction_status(request_id)

            if status_data["status"] == "success":
                log_transaction_success(wallet_number, tx_hash, "Relay bridge transaction")
                return True
            elif status_data["status"] == "failed":
                log_transaction_error(wallet_number, f"Transaction failed: {tx_hash}", "Relay bridge transaction")
                return False
            else:
                log_status(wallet_number, f"Current status: {status_data['status']}. Waiting...")

            time.sleep(self.settings["STATUS_CHECK_DELAY"])

        log_transaction_error(wallet_number, f"Transaction status check timeout after {self.settings['MAX_STATUS_CHECKS']} attempts: {tx_hash}")
        return False

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        try:
            proxy = None
            if wallet.proxy:
                proxy = {
                    'http': wallet.proxy.as_url(),
                    'https': wallet.proxy.as_url()
                }

            log_transaction_start(wallet_number, f"Checking Relay bridge availability for {destination_chain.name}")

            if not self._check_chain_config(destination_chain.id, wallet_number, proxy):
                log_transaction_error(wallet_number, f"Bridge to {destination_chain.name} unavailable", "Relay bridge")
                return TransactionResult(False, error_message=f"Bridge to {destination_chain.name} unavailable")

            log_status(wallet_number, f"Getting quote for {destination_chain.name}")

            quote_data = self._get_quote(wallet.address, destination_chain, wallet_number, proxy)

            if "errorCode" in quote_data:
                error_msg = quote_data.get("message", "Unknown error")
                log_transaction_error(wallet_number, f"Quote error: {error_msg}", "Relay bridge")
                return TransactionResult(False, error_message=error_msg)

            log_status(wallet_number, "Preparing Relay transaction data")
            tx_data = self._prepare_transaction_data(quote_data, wallet)
            request_id = quote_data["steps"][0]["requestId"]

            log_status(wallet_number, "Signing and sending Relay transaction")
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, wallet.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            log_status(wallet_number, "Monitoring transaction status")
            success = self._monitor_transaction(tx_hash.hex(), request_id, wallet_number)

            return TransactionResult(
                success=success,
                tx_hash=tx_hash.hex(),
                module_name=self.module_name
            )

        except Exception as e:
            error_message = str(e)
            log_transaction_error(wallet_number, error_message, "Relay bridge transaction")
            return TransactionResult(False, error_message=error_message, module_name=self.module_name)

    def _check_transaction_status(self, request_id: str, wallet_number: int = None, proxy: dict = None) -> dict:
        """Проверка статуса транзакции"""
        params = {"requestId": request_id}
        response = self.session.get(API_ENDPOINTS["RELAY"]["STATUS"], params=params, proxies=proxy)
        return response.json()

    def _check_chain_config(self, destination_chain_id: int, wallet_number: int = None, proxy: dict = None) -> bool:
        params = {
            "originChainId": str(API_ENDPOINTS["RELAY"]["ORIGIN_CHAIN_ID"]),
            "destinationChainId": str(destination_chain_id)
        }
        response = self.session.get(API_ENDPOINTS["RELAY"]["CONFIG"], params=params, proxies=proxy)
        return response.json().get("enabled", False)

    def _get_quote(self, wallet_address: str, destination_chain: Chain, wallet_number: int = None,
                   proxy: dict = None) -> dict:
        balance = self.w3.eth.get_balance(wallet_address)

        min_amount = balance * self.settings["AMOUNT_PERCENTAGE"]["MIN"]
        max_amount = balance * self.settings["AMOUNT_PERCENTAGE"]["MAX"]
        amount_to_bridge = random.uniform(min_amount, max_amount)

        payload = {
            "user": wallet_address,
            "originChainId": API_ENDPOINTS["RELAY"]["ORIGIN_CHAIN_ID"],
            "destinationChainId": destination_chain.id,
            "originCurrency": TOKENS['ETH'],
            "destinationCurrency": destination_chain.currency_address,
            "recipient": wallet_address,
            "tradeType": "EXACT_INPUT",
            "amount": int(amount_to_bridge),
            "slippageTolerance": self.settings["SLIPPAGE"],
            "useExternalLiquidity": False
        }
        response = self.session.post(API_ENDPOINTS["RELAY"]["QUOTE"], json=payload, proxies=None)
        return response.json()
