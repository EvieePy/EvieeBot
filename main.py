import aiohttp
import asyncpg

import utils


async def get_prefix(bot_, msg):
    defaults = ('eviee ', 'eviee pls ', 'e>')

    if not msg.guild:
        return defaults


class Botto(utils.Bot):

    def __init__(self):
        super().__init__(command_prefix=get_prefix)

    @utils.evieeloads
    async def async_init(self):
        """Async Initializer"""
        self.remove_command('help')
        self.pool = await asyncpg.create_pool(
            f'postgres://postgres:{utils.config.get("DB", "token")}@localhost:5432/eviee2')
        self.session = aiohttp.ClientSession(loop=self.loop)
