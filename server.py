import asyncio
from asyncio import Task
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional

from custom_logger import logger
from constants import BAN_TIME, MAX_REPORTS, IP_ADDR, PORT
from constants import Status
from messages_templates import (
    ban,
    sign_in_required,
    unknown_command,
    success_registration,
    already_signed_in,
    success_sign_in,
    no_username,
    empty_message,
    no_username_or_empty_msg,
    message_sended,
    user_isnt_registered,
    new_messages,
    no_messages_with_target_user,
    user_statuses,
    not_all_params_given,
    server_initialized,
    banned_user_message,
    user_disconnected,
    get_command,
    new_registration,
    signed_in,
    send_message,
    send_private_message,
    get_private_chat,
    get_status,
    report_user,
    new_connection,
    server_started,
    server_stopped,
    private,
    successfully_sended,
    no_such_user,
    already_reported,
    report,
    user_banned,
    user_already_banned,
    time_error,
    added_scheduled_message,
    no_id_given,
    wrong_id_format,
    no_such_delayed_message,
    succefully_cancel_delayed_message,
    create_scheduled_message,
    sending_delayed_message,
    cancel_scheduled_message
)


class ChatServer:
    """
    Класс ChatServer предназначен для управления
    серверной частью чат-приложения.

    - Структура данных для self.users:
    {
        'username': {
            'status': 'online',
            'client_addr': client_addr,
            # Непрочитанные сообщения из общего чата.
            'unread_messages': [],
            # Индексы последних прочитанных сообщений для каждого чата.
            'last_read': {},
            'reports': {'reported_by': [], 'end_of_ban': 0}
        }
    }

    - Структура данных для self.general_chat:
    [(username, message), ...]

    - Структура данных для self.private_chats:
    {(username1, username2): [(username, message), ...]}

    - Структура данных для self.scheduled_messages:
    {username: {task_id: asyncio.Task, task_id: asyncio.Task}...}
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 8000) -> None:
        """Инициализация сервера."""
        self.host: str = host
        self.port: int = port
        self.users: dict[str, dict] = {}
        self.general_chat: list[tuple[str, str]] = []
        self.private_chats: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self.scheduled_messages: dict[str, dict[int, Task]] = {}
        self.auth_handlers = {
            '/sign_in': self.handle_sign_in,
        }
        self.command_handlers = {
            '/send_all': self.handle_send_all,
            '/send': self.handle_send,
            '/get_chat_with': self.handle_get_chat_with,
            '/status': self.handle_status,
            '/report': self.handle_report,
            '/send_delayed': self.handle_send_delayed,
        }
        logger.info(server_initialized, host, port)

    def _check_ban(
            self,
            username: Optional[str],
            writer: StreamWriter
    ) -> bool:
        """Проверка, забанен ли пользователь."""
        loop = asyncio.get_running_loop()
        current_time = loop.time()
        end_of_ban = self.users[username]['reports'].get('end_of_ban', 0)

        if current_time < end_of_ban:
            logger.warning(banned_user_message, username)
            remaining_time = end_of_ban - loop.time()
            writer.write(ban.format(remaining_time).encode())
            return True

        if current_time > end_of_ban and end_of_ban:
            self.users[username]['reports']['reported_by'].clear()
            self.users[username]['reports']['end_of_ban'] = 0
        return False

    def _logout_user(
            self,
            client_addr: tuple[str, int],
            username: Optional[str]
    ) -> None:
        """Обработка выхода пользователя из системы."""
        logger.info(user_disconnected, username, client_addr)
        if username:
            self.users[username]['status'] = Status.OFFLINE

    def _require_sign_in(self, writer: StreamWriter) -> None:
        """Требование входа в систему, если пользователь не авторизован."""
        writer.write(sign_in_required.encode())

    async def handle_command(
            self,
            command: str,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str],
            client_addr: tuple[str, int]
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

    async def handle_sign_in(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str],
            client_addr: tuple[str, int]
    ) -> Optional[str]:
        """Обработчик команды входа пользователя."""
        if not command_args:
            writer.write(no_username.encode())
            return

        username = command_args[0]
        if username not in self.users:
            logger.info(new_registration, username)
            self.users[username] = {
                'status': Status.ONLINE,
                'client_addr': client_addr,
                'unread_messages': [],
                'last_read': {},
                'reports': {'reported_by': [], 'end_of_ban': 0}
            }
            chat_log = self.general_chat[-20:]
            writer.write(success_registration.format(chat_log).encode())
            return username

        if self.users[username]['status'] == Status.ONLINE:
            writer.write(already_signed_in.encode())
            return

        logger.info(signed_in, username)
        self.users[username].update(
            {'status': Status.ONLINE, 'client_addr': client_addr}
        )
        chat_log = self.users[username]['unread_messages']
        writer.write(success_sign_in.format(chat_log).encode())
        self.users[username]['unread_messages'].clear()
        return username

    async def handle_send_all(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str]
    ) -> None:
        """Обработчик команды отправки сообщения всем пользователям."""
        if not username:
            self._require_sign_in(writer)
            return

        if self._check_ban(username, writer):
            return

        if not command_args:
            writer.write(empty_message.encode())
            return

        logger.info(send_message, username)
        self.general_chat.append((username, ' '.join(command_args)))
        writer.write(successfully_sended.encode())
        for user in self.users:
            self.users[user]['unread_messages'].append(
                (username, ' '.join(command_args))
            )

    async def handle_send(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str]
    ) -> None:
        """Обработчик команды отправки личного сообщения."""
        if not username:
            self._require_sign_in(writer)
            return

        if self._check_ban(username, writer):
            return

        if len(command_args) < 2:
            writer.write(no_username_or_empty_msg.encode())
            return

        target_username = command_args[0]
        if target_username in self.users:
            chat_id = tuple(sorted([username, target_username]))

            if chat_id not in self.private_chats:
                self.private_chats[chat_id] = []

            self.private_chats[chat_id].append(
                (username, ' '.join(command_args[1:]))
            )
            logger.info(send_private_message, username, target_username)
            writer.write(message_sended.format(target_username).encode())
        else:
            writer.write(user_isnt_registered.format(target_username).encode())

    async def handle_get_chat_with(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str]
    ) -> None:
        """Обработчик команды получения личного чата с пользователем."""
        if not username:
            self._require_sign_in(writer)
            return

        if not command_args:
            writer.write(no_username.encode())
            return

        target_username = command_args[0]

        chat_id = tuple(sorted([username, target_username]))

        if chat_id in self.private_chats:
            logger.info(get_private_chat, username, target_username)
            # Получаем индекс последнего прочитанного сообщения для этого чата.
            last_read_index = (
                self.users[username]['last_read'].get(chat_id, -1)
            )

            # Отправляем все сообщения начиная с последнего прочитанного.
            unread_messages = self.private_chats[chat_id][last_read_index + 1:]
            writer.write(new_messages.format(unread_messages).encode())

            # Обновляем индекс последнего прочитанного сообщения.
            self.users[username]['last_read'][chat_id] = (
                len(self.private_chats[chat_id]) - 1
            )

        else:
            writer.write(no_messages_with_target_user.encode())

    async def handle_status(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str]
    ) -> None:
        """Обработчик команды проверки статуса пользователя."""
        if not username:
            self._require_sign_in(writer)
            return

        logger.info(get_status, username)
        users_info = (
            [(username, user_info['status'])
             for username, user_info in self.users.items()]
        )
        writer.write(user_statuses.format(users_info).encode())
        writer.write(private.format(list(self.private_chats.keys())).encode())

    async def handle_report(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str]
    ) -> None:
        """Обработчик команды отправки жалобы на пользователя."""
        if not username:
            self._require_sign_in(writer)
            return

        if not command_args:
            writer.write(no_username.encode())
            return

        target_username = command_args[0]

        if target_username not in self.users:
            writer.write(no_such_user.encode())
            return

        if username in self.users[target_username]['reports']['reported_by']:
            writer.write(already_reported.format(target_username).encode())
            return

        logger.warning(report_user, username, target_username)
        self.users[target_username]['reports']['reported_by'].append(username)
        number_of_reports = (
            len(self.users[target_username]['reports']['reported_by'])
        )

        if number_of_reports < MAX_REPORTS:
            writer.write(report.format(target_username).encode())
        elif number_of_reports == MAX_REPORTS:
            loop = asyncio.get_running_loop()
            self.users[target_username]['reports']['end_of_ban'] = (
                loop.time() + BAN_TIME
            )
            writer.write(user_banned.format(target_username).encode())
        else:
            writer.write(user_already_banned.format(target_username).encode())

    async def handle_send_delayed(
        self,
        command_args: list[str],
        writer: StreamWriter,
        username: Optional[str]
    ) -> None:
        """Обработчик команды отправки отложенного сообщения."""
        if not username:
            self._require_sign_in(writer)
            return

        if len(command_args) < 3:
            writer.write(not_all_params_given.encode())
            return

        target_username, delay, *message = command_args

        if target_username not in self.users:
            writer.write(user_isnt_registered.encode())
            return

        try:
            delay = int(delay)
        except ValueError:
            writer.write(time_error.encode())
            return

        logger.info(create_scheduled_message, username, target_username, delay)
        # Создание отложенной задачи
        task = asyncio.create_task(
            self.send_scheduled_message(
                username,
                target_username,
                ' '.join(message),
                delay,
                writer
            )
        )

        if username not in self.scheduled_messages:
            self.scheduled_messages[username] = {}

        message_id = len(self.scheduled_messages[username])

        self.scheduled_messages[username][message_id] = task

        writer.write(
            added_scheduled_message.format(message_id, delay).encode()
        )

    async def send_scheduled_message(
        self,
        username: str,
        target_username: str,
        message: str,
        delay: int,
        writer: StreamWriter
    ) -> None:
        """Отправка отложенного сообщения."""
        await asyncio.sleep(delay)
        logger.info(sending_delayed_message, username, target_username)
        await self.handle_send([target_username, message], writer, username)

    async def handle_cancel_scheduled(
        self,
        command_args: list[str],
        writer: StreamWriter,
        username: Optional[str]
    ) -> None:
        """Обработчик команды для отмены отложенного сообщения."""
        if not username:
            self._require_sign_in(writer)
            return

        if len(command_args) != 1:
            writer.write(no_id_given.encode())
            return

        try:
            message_id = int(command_args[0])
        except ValueError:
            writer.write(wrong_id_format.encode())
            return

        if (username in self.scheduled_messages
                and message_id in self.scheduled_messages[username]):

            logger.info(cancel_scheduled_message, username)
            self.scheduled_messages[username][message_id].cancel()
            del self.scheduled_messages[username][message_id]
            writer.write(
                succefully_cancel_delayed_message.format(message_id).encode()
            )

        else:
            writer.write(no_such_delayed_message.format(message_id).encode())

    async def handle_client(
            self,
            reader: StreamReader,
            writer: StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info('peername')
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


if __name__ == "__main__":
    server = ChatServer(IP_ADDR, PORT)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(server.run())
    except KeyboardInterrupt:
        logger.info(server_stopped)
    finally:
        # Закрываем незавершённые задачи
        pending_tasks = asyncio.all_tasks(loop)
        tasks = asyncio.gather(*pending_tasks, return_exceptions=True)
        loop.run_until_complete(tasks)
        loop.close()
        raise SystemExit('Завершено администратором')
