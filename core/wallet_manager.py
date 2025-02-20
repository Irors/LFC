from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd
from loguru import logger
from eth_account import Account


@dataclass
class Chain:
    id: int
    name: str
    rpc_url: str
    currency_address: str
    is_enabled: bool = True
    supports_deposits: bool = True


@dataclass
class ProxyConfig:
    login: str
    password: str
    ip: str
    port: str

    def as_url(self) -> str:
        return f"http://{self.login}:{self.password}@{self.ip}:{self.port}"


@dataclass
class Wallet:
    address: str
    private_key: str
    proxy: Optional[ProxyConfig] = None
    contracts_count: int = 1
    bridge_chain_id: Optional[int] = None


@dataclass
class TransactionResult:
    success: bool
    tx_hash: str = ""
    error_message: str = ""
    module_name: str = ""


class WalletManager:
    @staticmethod
    def _parse_proxy(proxy_string: str) -> Optional[ProxyConfig]:
        """Парсинг строки прокси в объект ProxyConfig"""
        try:
            if not proxy_string or pd.isna(proxy_string):
                return None

            # Удаляем http:// если есть
            proxy_string = proxy_string.replace('http://', '')

            # Разбиваем на компоненты
            auth, address = proxy_string.split('@')
            login, password = auth.split(':')
            ip, port = address.split(':')

            return ProxyConfig(
                login=login.strip(),
                password=password.strip(),
                ip=ip.strip(),
                port=port.strip()
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга прокси '{proxy_string}': {str(e)}")
            return None

    @staticmethod
    def load_wallets(excel_path: str) -> list[Wallet]:
        try:
            # Читаем Excel файл
            df = pd.read_excel(excel_path)
            wallets = []

            for index, row in df.iterrows():
                try:
                    # Проверяем обязательные данные
                    if pd.isna(row['Private Key']) or pd.isna(row['Wallet Address']):
                        continue

                    # Парсим прокси
                    proxy_config = WalletManager._parse_proxy(row['Proxy']) if pd.notna(row['Proxy']) else None

                    # Получаем количество контрактов
                    contracts_count = int(row['Contracts count']) if pd.notna(row['Contracts count']) else 1

                    # Получаем chain_id для бриджа
                    bridge_chain_id = int(row['Bridge Chain Id']) if pd.notna(row['Bridge Chain Id']) else None

                    # Создаем объект Wallet
                    wallet = Wallet(
                        address=str(row['Wallet Address']),
                        private_key=str(row['Private Key']),
                        proxy=proxy_config,
                        contracts_count=contracts_count,
                        bridge_chain_id=bridge_chain_id
                    )
                    wallets.append(wallet)
                    logger.debug(
                        f"Loaded wallet {wallet.address} with contracts_count: {wallet.contracts_count}, bridge_chain_id: {bridge_chain_id}")
                except Exception as e:
                    logger.error(f"Error processing row {index + 1}: {str(e)}")
                    continue

            if not wallets:
                logger.error("No valid wallets found in Excel file")
            else:
                logger.info(f"Successfully loaded {len(wallets)} wallets")

            return wallets
        except Exception as e:
            logger.error(f"Error loading wallets from Excel: {str(e)}")
            return []