import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from pathlib import Path

from config.settings import SETTINGS
from core.wallet_manager import WalletManager
from modules.lisk_dmail import DmailModule
from modules.relay_bridge import RelayBridge
from modules.ionic import IonicModule
from modules.safe import SafeModule
from modules.jumper import JumperModule
from modules.layer_swap import LayerSwapModule
from modules.superbridge import SuperBridgeModule
from modules.weth import WethModule

from utils.logger import setup_logging, log_module_start
from utils.results_tracker import ResultsTracker


class DeFiBot:
    def __init__(self, excel_path: str = "wallets.xlsx"):
        self.excel_path = excel_path
        self.wallet_counter = 0
        self.wallet_count_lock = threading.Lock()
        self.results_tracker = ResultsTracker()
        self.weth_module = WethModule()

        # Инициализация модулей
        self.modules = [
            DmailModule(),
            RelayBridge(),
            IonicModule(),
            SafeModule(),
            JumperModule(),
            LayerSwapModule(),
            SuperBridgeModule()
        ]

    def get_wallet_number(self) -> int:
        with self.wallet_count_lock:
            self.wallet_counter += 1
            return self.wallet_counter

    def process_wallet(self, wallet):
        try:
            time.sleep(
               random.randint(SETTINGS['BETWEEN_START_WALLETS']['MIN'], SETTINGS['BETWEEN_START_WALLETS']['MAX']))

            wallet_number = self.get_wallet_number()
            contracts_to_process = wallet.contracts_count

            logger.info(f"[Account #{wallet_number}] Planning to process {contracts_to_process} contracts")

            # Проверяем и выводим WETH если есть
            weth_result = self.weth_module.check_and_withdraw_weth(wallet, wallet_number)
            if not weth_result.success:
                logger.warning(f"[Account #{wallet_number}] Failed to process WETH: {weth_result.error_message}")

            # Добавляем задержку после обработки WETH
            if weth_result.tx_hash:
                delay = random.uniform(
                    SETTINGS["DELAYS"]["BETWEEN_MODULES"]["MIN"],
                    SETTINGS["DELAYS"]["BETWEEN_MODULES"]["MAX"]
                )
                logger.info(f"[Account #{wallet_number}] Waiting {delay:.2f} seconds after WETH processing")
                time.sleep(delay)

            # Добавляем задержку между кошельками
            if wallet_number > 1:
                delay = random.uniform(
                    SETTINGS["DELAYS"]["BETWEEN_WALLETS"]["MIN"],
                    SETTINGS["DELAYS"]["BETWEEN_WALLETS"]["MAX"]
                )
                logger.info(f"[Account #{wallet_number}] Waiting {delay:.2f} seconds before processing")
                time.sleep(delay)

            # Обрабатываем указанное количество контрактов
            contracts_processed = 0
            while contracts_processed < contracts_to_process:
                # Перемешиваем модули для случайного порядка
                random.shuffle(self.modules)

                for module in self.modules:
                    if contracts_processed >= contracts_to_process:
                        break

                    # Логируем начало работы модуля
                    log_module_start(module.module_name, wallet_number)

                    available_chains = module.get_available_chains()

                    if not available_chains:
                        logger.error(f"[Account #{wallet_number}] No available chains for {module.module_name}")
                        continue

                    # Проверяем bridge_chain_id только для бридж модулей
                    is_bridge_module = isinstance(module,
                                                  (RelayBridge, JumperModule, LayerSwapModule, SuperBridgeModule))

                    # Выбор сети на основе bridge_chain_id только для бриджей
                    if is_bridge_module and wallet.bridge_chain_id is not None:
                        # Ищем указанную сеть среди доступных
                        destination_chain = next(
                            (chain for chain in available_chains if chain.id == wallet.bridge_chain_id),
                            None
                        )
                        # Если указанная сеть недоступна для бриджа, пропускаем этот модуль
                        if destination_chain is None:
                            logger.warning(
                                f"[Account #{wallet_number}] Specified chain {wallet.bridge_chain_id} not available for {module.module_name}, skipping")
                            continue
                    else:
                        # Для не-бридж модулей или если bridge_chain_id не указан
                        destination_chain = random.choice(available_chains)

                    # Добавляем задержку между транзакциями
                    delay = random.uniform(
                        SETTINGS["DELAYS"]["BETWEEN_TRANSACTIONS"]["MIN"],
                        SETTINGS["DELAYS"]["BETWEEN_TRANSACTIONS"]["MAX"]
                    )
                    logger.info(f"[Account #{wallet_number}] Waiting {delay:.2f} seconds before transaction")
                    time.sleep(delay)

                    # Обработка транзакции
                    logger.info(f"[Account #{wallet_number}] Selected chain: {destination_chain.name}")
                    result = module.process_transaction(
                        wallet,
                        destination_chain,
                        SETTINGS["RELAY_BRIDGE"]["AMOUNT_PERCENTAGE"],
                        wallet_number
                    )

                    # Обновление результатов
                    self.results_tracker.update_results(wallet, destination_chain, result)
                    contracts_processed += 1
                    logger.info(
                        f"[Account #{wallet_number}] Processed {contracts_processed}/{contracts_to_process} contracts")

                    # Добавляем задержку между модулями
                    if contracts_processed < contracts_to_process:
                        delay = random.uniform(
                            SETTINGS["DELAYS"]["BETWEEN_MODULES"]["MIN"],
                            SETTINGS["DELAYS"]["BETWEEN_MODULES"]["MAX"]
                        )
                        logger.info(f"[Account #{wallet_number}] Waiting {delay:.2f} seconds before next module")
                        time.sleep(delay)

        except Exception as e:
           logger.error(f"[Account #{wallet_number}] Error processing wallet {wallet.address}: {str(e)}")

    def run(self):
        try:
            setup_logging()
            wallets = WalletManager.load_wallets(self.excel_path)

            if not wallets:
                logger.error("No wallets loaded")
                return

            logger.info(f"Starting process with {len(wallets)} wallets. Wait...")

            with ThreadPoolExecutor(max_workers=SETTINGS["MAX_THREADS"]) as executor:
                futures = [
                    executor.submit(self.process_wallet, wallet)
                    for wallet in wallets
                ]

                for future in as_completed(futures):
                    future.result()

        except Exception as e:
            logger.error(f"Critical error in run(): {str(e)}")
            raise


if __name__ == "__main__":
    try:
        Path("logs").mkdir(exist_ok=True)
        bot = DeFiBot("wallets.xlsx")
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
    finally:
        logger.info("Bot finished working")
