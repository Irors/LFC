from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status
import random
import requests
import time


class WethModule(BaseModule):
    def __init__(self, nonce_manager: NonceManager):
        super().__init__(nonce_manager)
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.contract_address = "0x4200000000000000000000000000000000000006"
        self.eth_price = None
        self.last_price_update = 0
        self.price_update_interval = 60  # обновляем цену раз в минуту
        self.abi = [
            {
                "constant": True,
                "inputs": [{"name": "", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "wad", "type": "uint256"}],
                "name": "withdraw",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        self.contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(self.contract_address),
            abi=self.abi
        )

    def get_eth_price(self) -> float:
        """Получает актуальную цену ETH с CoinGecko API с кэшированием"""
        current_time = time.time()

        # Если цена не получена или прошло больше минуты с последнего обновления
        if self.eth_price is None or (current_time - self.last_price_update) > self.price_update_interval:
            try:
                # Делаем запрос к CoinGecko API
                response = requests.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": "ethereum",
                        "vs_currencies": "usd"
                    },
                    timeout=10
                )
                response.raise_for_status()
                self.eth_price = float(response.json()["ethereum"]["usd"])
                self.last_price_update = current_time
            except (requests.RequestException, KeyError, ValueError) as e:
                # В случае ошибки используем резервное значение
                if self.eth_price is None:
                    self.eth_price = SETTINGS['PRICE_ETH']  # резервное значение
                log_status(None, f"Error fetching ETH price, using cached/default price: {str(e)}")

        return self.eth_price

    def get_eth_balance_in_usd(self, address: str) -> float:
        """Получает баланс ETH и конвертирует его в USD"""
        balance_wei = self.w3.eth.get_balance(address)
        balance_eth = Web3.from_wei(balance_wei, 'ether')
        return float(balance_eth) * self.get_eth_price()

    def ensure_minimum_eth_balance(self, wallet: Wallet, wallet_number: int) -> TransactionResult:
        """
        Проверяет баланс ETH и при необходимости конвертирует WETH в ETH
        чтобы обеспечить минимальный баланс от 6.25$ до 8.75$
        """
        try:
            log_transaction_start(wallet_number, "Checking ETH balance before bridge")

            # Получаем актуальную цену ETH
            eth_price = self.get_eth_price()

            # Проверяем текущий баланс ETH в USD
            current_eth_balance_usd = self.get_eth_balance_in_usd(wallet.address)
            log_status(wallet_number, f"Current ETH balance: ${current_eth_balance_usd:.2f} (ETH price: ${eth_price})")

            if current_eth_balance_usd >= 5:
                log_status(wallet_number, f"Sufficient ETH balance: ${current_eth_balance_usd:.2f}")
                return TransactionResult(success=True, module_name=self.module_name)

            # Определяем необходимую сумму в USD (случайно от 6.25$ до 8.75$)
            target_usd_amount = random.uniform(6.25, 8.75)
            needed_eth = target_usd_amount / eth_price

            log_status(wallet_number, f"Target ETH balance: ${target_usd_amount:.2f} ({needed_eth:.6f} ETH)")

            # Проверяем баланс WETH
            weth_balance = self.contract.functions.balanceOf(wallet.address).call()
            weth_balance_eth = Web3.from_wei(weth_balance, 'ether')
            weth_balance_usd = float(weth_balance_eth) * eth_price

            # Определяем сколько WETH конвертировать
            if weth_balance_usd < (target_usd_amount - current_eth_balance_usd):
                # Если не хватает WETH, конвертируем всё
                amount_to_withdraw = weth_balance
                log_status(wallet_number,
                           f"Not enough WETH (${weth_balance_usd:.2f}), converting all available: {weth_balance_eth:.6f} WETH")
            else:
                # Конвертируем только необходимое количество
                needed_additional_eth = needed_eth - (current_eth_balance_usd / eth_price)
                amount_to_withdraw = Web3.to_wei(needed_additional_eth, 'ether')
                log_status(wallet_number,
                           f"Converting {Web3.from_wei(amount_to_withdraw, 'ether'):.6f} WETH to reach target")

            if amount_to_withdraw == 0:
                log_status(wallet_number, "No WETH to convert")
                return TransactionResult(success=True, module_name=self.module_name)

            # Создаем транзакцию для withdraw
            transaction = self.contract.functions.withdraw(amount_to_withdraw).build_transaction({
                'from': wallet.address,
                'gas': 54110,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })

            # Получаем nonce через NonceManager
            transaction = self.prepare_transaction(wallet, transaction)

            try:
                # Подписываем и отправляем транзакцию
                signed_tx = self.w3.eth.account.sign_transaction(transaction, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                # Ждем подтверждения
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    new_eth_balance_usd = self.get_eth_balance_in_usd(wallet.address)
                    log_transaction_success(wallet_number,
                                          f"{tx_hash.hex()} (New ETH balance: ${new_eth_balance_usd:.2f})",
                                          "WETH to ETH conversion")
                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash.hex(),
                        module_name=self.module_name
                    )
                else:
                    self.handle_failed_transaction(wallet, transaction)
                    log_transaction_error(wallet_number, "Transaction failed", "WETH to ETH conversion")
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
            log_transaction_error(wallet_number, error_message, "WETH to ETH conversion")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )

    def get_available_chains(self, wallet_number: int = None, proxy: dict = None):
        return [
            Chain(
                id=SETTINGS["CHAIN_ID"],
                name="Lisk",
                rpc_url=SETTINGS["RPC_URL"],
                currency_address=TOKENS["ETH"],
                is_enabled=True,
                supports_deposits=True
            )
        ]

    def check_and_withdraw_weth(self, wallet: Wallet, wallet_number: int) -> TransactionResult:
        """Проверяет баланс WETH и если есть, делает withdraw всей суммы"""
        try:
            log_transaction_start(wallet_number, "Checking WETH balance")

            # Проверяем баланс WETH
            weth_balance = self.contract.functions.balanceOf(wallet.address).call()

            if weth_balance == 0:
                log_status(wallet_number, "No WETH balance found, skipping")
                return TransactionResult(
                    success=True,
                    module_name=self.module_name
                )

            log_status(wallet_number, f"Found {Web3.from_wei(weth_balance, 'ether')} WETH, initiating withdrawal")

            # Создаем транзакцию для withdraw
            transaction = self.contract.functions.withdraw(weth_balance).build_transaction({
                'from': wallet.address,
                'gas': 54110,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })

            # Получаем nonce через NonceManager
            transaction = self.prepare_transaction(wallet, transaction)

            try:
                # Подписываем и отправляем транзакцию
                signed_tx = self.w3.eth.account.sign_transaction(transaction, wallet.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

                # Ждем подтверждения
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    log_transaction_success(wallet_number, tx_hash.hex(), "WETH withdrawal")
                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash.hex(),
                        module_name=self.module_name
                    )
                else:
                    self.handle_failed_transaction(wallet, transaction)
                    log_transaction_error(wallet_number, "Transaction failed", "WETH withdrawal")
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
            log_transaction_error(wallet_number, error_message, "WETH withdrawal")
            return TransactionResult(
                success=False,
                error_message=error_message,
                module_name=self.module_name
            )

    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict,
                            wallet_number: int) -> TransactionResult:
        """
        Основной метод для обработки транзакций. В данном случае он просто вызывает check_and_withdraw_weth
        """
        return self.check_and_withdraw_weth(wallet, wallet_number)