import asyncio
from asyncio.streams import StreamWriter
from typing import Optional

from custom_logger import logger
from config import BAN_TIME, MAX_REPORTS
from config import Status, ClientAddress, Message, ChatID, Report, UserInfo
from messages_templates import (
    ban,
    sign_in_required,
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
    banned_user_message,
    new_registration,
    signed_in,
    send_message,
    send_private_message,
    get_private_chat,
    get_status,
    report_user,
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


class AuthHandlers:
    def __init__(self, server_instance):
        # Экземпляр основного серверного класса
        self.server = server_instance

    async def handle_sign_in(
            self,
            command_args: list[str],
            writer: StreamWriter,
            username: Optional[str],
            client_addr: ClientAddress
    ) -> Optional[str]:
        """Обработчик команды входа пользователя."""
        if not command_args:
            writer.write(no_username.encode())
            return

        username = command_args[0]
        if username not in self.users:
            logger.info(new_registration, username)
            user_info = UserInfo(
                status=Status.ONLINE,
                client_addr=client_addr,
                reports=Report()
            )
            self.server.users[username] = user_info
            chat_log = self.server.general_chat[-20:]
            writer.write(success_registration.format(chat_log).encode())
            return username

        user_info = self.server.users[username]
        if user_info.status == Status.ONLINE:
            writer.write(already_signed_in.encode())
            return

        logger.info(signed_in, username)
        new_user_info = UserInfo(
            **user_info.model_dump(),
            status=Status.ONLINE,
            client_addr=client_addr
        )
        self.server.users[username] = new_user_info
        chat_log = new_user_info.unread_messages
        writer.write(success_sign_in.format(chat_log).encode())
        new_user_info.unread_messages.clear()
        self.server.users[username] = new_user_info
        return username


class MessageHandlers:
    def __init__(self, server_instance):
        self.server = server_instance

    def _check_ban(
            self,
            username: Optional[str],
            writer: StreamWriter
    ) -> bool:
        """Проверка, забанен ли пользователь."""
        loop = asyncio.get_running_loop()
        current_time = loop.time()
        user_info = self.server.users[username]
        end_of_ban = user_info.reports.end_of_ban

        if current_time < end_of_ban:
            logger.warning(banned_user_message, username)
            remaining_time = end_of_ban - loop.time()
            writer.write(ban.format(remaining_time).encode())
            return True

        if current_time > end_of_ban and end_of_ban:
            base_report = Report()
            self.server.users[username].reports = base_report
        return False

    def _require_sign_in(self, writer: StreamWriter) -> None:
        """Требование входа в систему, если пользователь не авторизован."""
        writer.write(sign_in_required.encode())

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
        self.server.general_chat.append(
            Message(sender=username, text=' '.join(command_args))
        )
        writer.write(successfully_sended.encode())
        for user in self.server.users:
            user_info = self.server.users[user]
            user_info.unread_messages.append(
                Message(sender=username, text=' '.join(command_args))
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
        if target_username in self.server.users:
            chat_id = ChatID(id=tuple(sorted([username, target_username])))

            if chat_id not in self.server.private_chats:
                self.server.private_chats[chat_id] = []

            self.server.private_chats[chat_id].append(
                Message(sender=username, text=' '.join(command_args[1:]))
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

        chat_id = ChatID(id=tuple(sorted([username, target_username])))

        if chat_id in self.server.private_chats:
            logger.info(get_private_chat, username, target_username)
            # Получаем индекс последнего прочитанного сообщения для этого чата.
            user_info = self.server.users[username]
            last_read_index = user_info.last_read.get(chat_id, -1)

            # Отправляем все сообщения начиная с последнего прочитанного.
            unread_messages = (
                self.server.private_chats[chat_id][last_read_index + 1:]
            )
            writer.write(new_messages.format(unread_messages).encode())

            # Обновляем индекс последнего прочитанного сообщения.
            user_info.last_read[chat_id] = (
                len(self.server.private_chats[chat_id]) - 1
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
            [(username, user_info.status)
             for username, user_info in self.server.users.items()]
        )
        writer.write(user_statuses.format(users_info).encode())
        writer.write(
            private.format(list(self.server.private_chats.keys())).encode()
        )

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

        target_user_info = self.server.users[target_username]
        users_who_reported_target_user = target_user_info.reports.reported_by
        if username in users_who_reported_target_user:
            writer.write(already_reported.format(target_username).encode())
            return

        logger.warning(report_user, username, target_username)
        users_who_reported_target_user.append(username)
        number_of_reports = (
            len(target_user_info.reports.reported_by)
        )

        if number_of_reports < MAX_REPORTS:
            writer.write(report.format(target_username).encode())
        elif number_of_reports == MAX_REPORTS:
            time_now = asyncio.get_running_loop().time()
            target_user_info.reports.end_of_ban = (time_now + BAN_TIME)
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

        target_username, delay, *message_text = command_args

        if target_username not in self.server.users:
            writer.write(user_isnt_registered.encode())
            return

        try:
            delay = int(delay)
        except ValueError:
            writer.write(time_error.encode())
            return

        logger.info(create_scheduled_message, username, target_username, delay)
        # Создание отложенной задачи
        message = Message(sender=username, text=' '.join(message_text))
        task = asyncio.create_task(
            self.send_scheduled_message(
                message,
                target_username,
                delay,
                writer
            )
        )

        if username not in self.server.scheduled_messages:
            self.server.scheduled_messages[username] = {}

        message_id = len(self.server.scheduled_messages[username])

        self.server.scheduled_messages[username][message_id] = task

        writer.write(
            added_scheduled_message.format(message_id, delay).encode()
        )

    async def send_scheduled_message(
            self,
            message: Message,
            target_username: str,
            delay: int,
            writer: StreamWriter
    ) -> None:
        """Отправка отложенного сообщения."""
        await asyncio.sleep(delay)
        logger.info(sending_delayed_message, message.sender, target_username)
        await self.handle_send(
            [target_username, message.text],
            writer,
            message.sender
        )

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

        if (username in self.server.scheduled_messages
                and message_id in self.server.scheduled_messages[username]):

            logger.info(cancel_scheduled_message, username)
            self.server.scheduled_messages[username][message_id].cancel()
            del self.server.scheduled_messages[username][message_id]
            writer.write(
                succefully_cancel_delayed_message.format(message_id).encode()
            )

        else:
            writer.write(no_such_delayed_message.format(message_id).encode())
