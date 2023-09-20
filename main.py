import asyncio
from config import IP_ADDR, PORT

from server import ChatServer
from custom_logger import logger
from messages_templates import server_stopped


if __name__ == "__main__":
    try:
        server = ChatServer(IP_ADDR, PORT)
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info(server_stopped)
        raise SystemExit('Завершено администратором')
