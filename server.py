import asyncio
from asyncio import Task
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional

from custom_logger import logger
from config import Status, ClientAddress, Message, ChatID, UserInfo
from services import AuthHandlers, MessageHandlers
from messages_templates import (
    unknown_command,
    server_initialized,
    user_disconnected,
    get_command,
    new_connection,
    server_started,
)


class ChatServer:
    """
    Класс ChatServer предназначен для управления
    серверной частью чат-приложения.

    - Структура данных для self.scheduled_messages:
    {username: {task_id: asyncio.Task, task_id: asyncio.Task}...}
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 8000) -> None:
        """Инициализация сервера."""
        self.host: str = host
        self.port: int = port
        self.users: dict[str, UserInfo] = {}
        self.general_chat: list[Message] = []
        self.private_chats: dict[ChatID, list[Message]] = {}
        self.scheduled_messages: dict[str, dict[int, Task]] = {}
        self.auth_handler = AuthHandlers(self)
        self.message_handler = MessageHandlers(self)
        self.auth_handlers = {
            '/sign_in': self.auth_handler.handle_sign_in,
        }
        self.command_handlers = {
            '/send_all': self.message_handler.handle_send_all,
            '/send': self.message_handler.handle_send,
            '/get_chat_with': self.message_handler.handle_get_chat_with,
            '/status': self.message_handler.handle_status,
            '/report': self.message_handler.handle_report,
            '/send_delayed': self.message_handler.handle_send_delayed,
        }
        logger.info(server_initialized, host, port)

    def _logout_user(
            self,
            client_addr: ClientAddress,
            username: Optional[str]
    ) -> None:
        """Обработка выхода пользователя из системы."""
        logger.info(user_disconnected, username, client_addr)
        if username:
            # self.users[username]['status'] = Status.OFFLINE
            user_info = self.users[username]
            user_info.status = Status.OFFLINE

    async def handle_command(
            self,
            command: str,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str],
            client_addr: ClientAddress
    ) -> Optional[str]:
        """Обработчик команд от клиентов."""
        logger.info(get_command, command, username)
        if command in self.auth_handlers:
            return await self.auth_handlers[command](
                command_args, writer, username, client_addr
            )
        elif command in self.command_handlers:
            return await self.command_handlers[command](
                command_args, writer, username
            )
        else:
            writer.write(unknown_command.format(command).encode())

    async def handle_client(
            self,
            reader: StreamReader,
            writer: StreamWriter
    ) -> None:
        ip, port = writer.get_extra_info('peername')
        client_addr = ClientAddress(ip=ip, port=port)
        logger.info(new_connection, client_addr)
        username = None

        while True:
            data = await reader.read(4096)

            if not data:
                self._logout_user(client_addr, username)
                break

            message = data.decode().strip()
            command, *command_args = message.split()

            new_username = await self.handle_command(
                command, command_args, writer, username, client_addr
            )

            if new_username:
                username = new_username

            await writer.drain()

        writer.close()

    async def run(self) -> None:
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(server_started, self.host, self.port)
        await server.serve_forever()
        # Функция asyncio.run() создает новый цикл событий,
        # запускает переданную сопрограмму coro и в конце закрывает
        # цикл событий. Если в программе используются асинхронные
        # генераторы или пул потоков, то функция завершит их работу.
        # Поэтому даже не обязательно:
        # pending_tasks = asyncio.all_tasks()
        # await asyncio.gather(*pending_tasks, return_exceptions=True)
