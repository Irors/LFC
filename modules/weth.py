from core.base_module import BaseModule
from core.wallet_manager import Wallet, Chain, TransactionResult
from config.settings import SETTINGS
from web3 import Web3
from utils.logger import log_transaction_start, log_transaction_success, log_transaction_error, log_status


class WethModule(BaseModule):
    def __init__(self):
        super().__init__()
        self.w3 = Web3(Web3.HTTPProvider(SETTINGS["RPC_URL"]))
        self.contract_address = "0x4200000000000000000000000000000000000006"
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
                'nonce': self.w3.eth.get_transaction_count(wallet.address),
                'chainId': self.w3.eth.chain_id
            })

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
                log_transaction_error(wallet_number, "Transaction failed", "WETH withdrawal")
                return TransactionResult(
                    success=False,
                    tx_hash=tx_hash.hex(),
                    error_message="Transaction failed",
                    module_name=self.module_name
                )

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