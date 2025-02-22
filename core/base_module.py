from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.wallet_manager import Wallet, Chain, TransactionResult
from core.nonce_manager import NonceManager
from config.settings import SETTINGS


class BaseModule(ABC):
    def __init__(self, nonce_manager: NonceManager):
        self.settings = SETTINGS
        self.module_name = self.__class__.__name__
        self.nonce_manager = nonce_manager

    def prepare_transaction(self, wallet: Wallet, tx: dict) -> dict:
        """Подготовка транзакции с безопасным получением nonce"""
        try:
            # Получаем следующий доступный nonce
            nonce = self.nonce_manager.get_next_nonce(wallet.address)
            tx["nonce"] = nonce
            return tx
        except Exception as e:
            # В случае ошибки освобождаем nonce
            if "nonce" in tx:
                self.nonce_manager.release_nonce(wallet.address, tx["nonce"])
            raise e

    def handle_failed_transaction(self, wallet: Wallet, tx: dict):
        """Обработка неудачной транзакции"""
        if "nonce" in tx:
            self.nonce_manager.release_nonce(wallet.address, tx["nonce"])

    @abstractmethod
    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict, wallet_number: int) -> TransactionResult:
        """Process a transaction using the module's specific logic"""
        pass

    @abstractmethod
    def get_available_chains(self, wallet_number: int = None, proxy: dict = None) -> List[Chain]:
        """Get list of chains supported by this module"""
        pass