from loguru import logger
from pathlib import Path
from config.settings import SETTINGS


def format_url(url: str) -> str:
    """Форматирование URL для вывода в консоль"""
    return f"<{SETTINGS['LOGGING']['COLORS']['URL']}>{url}</{SETTINGS['LOGGING']['COLORS']['URL']}>"


def format_module_name(module_name: str) -> str:
    """Форматирование имени модуля для вывода в консоль"""
    return f"<{SETTINGS['LOGGING']['COLORS']['MODULE']}>{module_name}</{SETTINGS['LOGGING']['COLORS']['MODULE']}>"


def setup_logging():
    logger.remove()

    # Создаем директорию для логов
    Path("logs").mkdir(exist_ok=True)

    # Настройка логирования в файл
    logger.add(
        "logs/defi_bot_{time}.log",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{function}</cyan> | <white>{message}</white>",
        level="INFO",
        rotation="1 day"
    )

    # Кастомный форматтер для консоли
    def formatter(record):
        # Форматирование времени
        time_str = f"<green>{record['time'].strftime('%H:%M:%S')}</green>"

        # Базовый разделитель
        separator = f"<white>|</white>"

        # Форматирование уровня логирования
        level_str = f"{separator} <level>{record['level']}</level> {separator}"

        # Получаем сообщение
        message = record["message"]

        # Определяем цвет сообщения на основе содержимого
        if "https://" in message or "http://" in message:
            # Находим URL в сообщении и оборачиваем его в теги цвета
            for word in message.split():
                if word.startswith(("http://", "https://")):
                    message = message.replace(word, format_url(word))

        if "[MODULE]" in message:
            message = message.replace("[MODULE]", "")
            colored_message = f"<{SETTINGS['LOGGING']['COLORS']['MODULE']}>{message}</{SETTINGS['LOGGING']['COLORS']['MODULE']}>"
        elif any(text in message for text in ["Transaction confirmed", "Success", "Confirmed"]):
            colored_message = f"<{SETTINGS['LOGGING']['COLORS']['SUCCESS']}>{message}</{SETTINGS['LOGGING']['COLORS']['SUCCESS']}>"
        elif any(text in message for text in ["Error", "Failed", "error"]):
            colored_message = f"<{SETTINGS['LOGGING']['COLORS']['ERROR']}>{message}</{SETTINGS['LOGGING']['COLORS']['ERROR']}>"
        else:
            colored_message = f"<{SETTINGS['LOGGING']['COLORS']['INFO']}>{message}</{SETTINGS['LOGGING']['COLORS']['INFO']}>"

        return f"{time_str} {level_str} {colored_message}\n"

    # Добавляем логирование в консоль
    logger.add(
        lambda msg: print(msg, end=""),
        format=formatter,
        colorize=True
    )


# Добавляем вспомогательные функции для стандартизации вывода
def log_module_start(module_name: str, wallet_number: int):
    """Логирование начала работы модуля"""
    logger.info(f"[MODULE] Starting {module_name} module for Account #{wallet_number}")


def log_transaction_start(wallet_number: int, action: str, details: str = ""):
    """Логирование начала транзакции"""
    message = f"[Account #{wallet_number}] {action}"
    if details:
        message += f": {details}"
    logger.info(message)


def log_transaction_success(wallet_number: int, tx_hash: str, action: str = "Transaction"):
    """Логирование успешной транзакции"""
    logger.success(
        f"[Account #{wallet_number}] {action} confirmed: "
        f"https://blockscout.lisk.com/tx/0x{tx_hash}"
    )


def log_transaction_error(wallet_number: int, error: str, action: str = "Transaction"):
    """Логирование ошибки транзакции"""
    logger.error(f"[Account #{wallet_number}] {action} error: {error}")


def log_status(wallet_number: int, message: str):
    """Логирование статуса"""
    logger.info(f"[Account #{wallet_number}] {message}")