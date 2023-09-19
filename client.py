import asyncio


class ChatClient:
    def __init__(self, host='127.0.0.1', port=8000):
        self.host = host
        self.port = port

    async def send_command(self, writer, reader, command):
        print(f'Отправлена команда: {command}')
        writer.write(f'{command}\n'.encode())
        await writer.drain()
        await self.read_message(reader)

    async def read_message(self, reader):
        try:
            data = await reader.read(4096)
            message = data.decode().strip()
            print(f'Получено сообщение: {message}')
        except asyncio.IncompleteReadError:
            raise SystemExit('Сервер отключился')

    async def run(self):
        try:
            reader, writer = (
                await asyncio.open_connection(self.host, self.port)
            )
        except ConnectionRefusedError:
            raise SystemExit('Не получилось подключиться к серверу')

        while True:
            try:
                message = input("> ")
                if message:
                    await self.send_command(writer, reader, message)
            except (ConnectionResetError, ConnectionRefusedError):
                raise SystemExit('Соединение потеряно')
            except KeyboardInterrupt:
                raise SystemExit('Соединение закрыто')

if __name__ == "__main__":
    client = ChatClient()
    asyncio.run(client.run())
