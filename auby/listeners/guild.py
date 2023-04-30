import os

from discord.ext import commands
from tinydb import TinyDB, where
import logging
log = logging.getLogger('auby')

class GuildListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TinyDB(os.path.join(os.getcwd(), "config.json"))

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            if not self.db.contains(where('guild') == guild.id):
                log.info(f"Guild with ID {guild.id} was not in the config database.")
                self.db.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"Bot has joined new server: {guild.name}")
        self.db.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.info(f"Bot has been removed from server: {guild.name}")
        if self.db.contains(where('guild') == guild.id):
            self.db.remove(where('guild') == guild.id)

async def setup(bot):
    await bot.add_cog(GuildListener(bot=bot))