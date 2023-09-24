from asyncio import StreamWriter
from enum import Enum

from pydantic import BaseModel

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


class ClientAddress(BaseModel):
    ip: str
    port: int


class Message(BaseModel):
    sender: str
    text: str


class ChatID(BaseModel):
    # ID включает в себя отсортированный кортеж из
    # двух username'ов пользователей, между которыми ведётся чат.
    id: tuple[str, str]


class Report(BaseModel):
    reported_by: list[str] = []
    end_of_ban: int = 0


class UserInfo(BaseModel):
    status: Status
    client_addr: ClientAddress
    # Непрочитанные сообщения из общего чата.
    unread_messages: list[Message] = []
    # Индексы последних прочитанных сообщений для каждого чата.
    last_read: dict[ChatID, int] = {}
    reports: Report
    writer: StreamWriter

    class Config:
        # arbitrary_types_allowed=True в конфигурации модели,
        # разрешает использовать произвольные (нестандартные) типы 
        # в вашей модели. 
        # Это означает, что Pydantic не будет пытаться валидировать или 
        # преобразовывать эти типы, а просто принимать их как есть.

        # Настройка arbitrary_types_allowed = True влияет только на те поля, 
        # которые используют нестандартные типы, которые Pydantic не может 
        # обработать автоматически. 
        # Это не отключает валидацию и преобразование для стандартных полей, 
        # которые Pydantic может обрабатывать. 
        arbitrary_types_allowed = True

