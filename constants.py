from enum import Enum

# Время бана в секундах.
BAN_TIME = 4 * 3600
# Максимальное количетсво репортов,
# которое должен получить пользователь,чтобы быть забанненым.
MAX_REPORTS = 3
# IP адрес, на котором необходимо запустить сервер.
IP_ADDR = '127.0.0.1'
# Порт, на котором необходимо запустить сервер.
PORT = 8000

class Status(Enum):
    """
    Перечисление, представляющее статусы пользователей.

    Атрибуты:
        ONLINE: Пользователь онлайн.
        OFFLINE: Пользователь оффлайн.
    """
    ONLINE = 'online'
    OFFLINE = 'offline'
