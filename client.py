import asyncio

from aioconsole import ainput

from messages_templates import help_message


class ChatClient:
    def __init__(self, host='127.0.0.1', port=8000):
        self.host = host
        self.port = port

    async def run(self):
        try:
            reader, writer = (
                await asyncio.open_connection(self.host, self.port)
            )
        except ConnectionRefusedError:
            raise SystemExit('Не получилось подключиться к серверу')

        print(help_message)
        await asyncio.gather(self.listen_to_server(reader), self.write_to_server(writer))
            
    async def write_to_server(self, writer):
        while True:
            try:
                if command := await ainput():
                    print(f'Отправлена команда: {command}')
                    writer.write(f'{command}\n'.encode())
                    await writer.drain()
            except (ConnectionResetError, ConnectionRefusedError):
                raise SystemExit('Соединение потеряно')
            except KeyboardInterrupt:
                raise SystemExit('Соединение закрыто')
    
    async def listen_to_server(self, reader):
        while True:
            try:
                data = await reader.read(4096)
                message = data.decode().strip()
                print(f'Получено сообщение: {message}')
            except asyncio.IncompleteReadError:
                raise SystemExit('Сервер отключился')

if __name__ == "__main__":
    client = ChatClient()
    asyncio.run(client.run())
