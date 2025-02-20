from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.wallet_manager import Wallet, Chain, TransactionResult
from config.settings import SETTINGS


class BaseModule(ABC):
    def __init__(self):
        self.settings = SETTINGS
        self.module_name = self.__class__.__name__

    @abstractmethod
    def process_transaction(self, wallet: Wallet, destination_chain: Chain, amount: dict, wallet_number: int) -> TransactionResult:
        """Process a transaction using the module's specific logic"""
        pass

    @abstractmethod
    def get_available_chains(self, wallet_number: int = None, proxy: dict = None) -> List[Chain]:
        """Get list of chains supported by this module"""
        pass
