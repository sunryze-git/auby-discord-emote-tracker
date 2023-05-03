from discord.ext import commands
from tinydb import where
import logging
log = logging.getLogger('auby')

class GuildListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.server_conf

    @commands.Cog.listener()
    async def on_ready(self):
        required_keys = ['bot_logging', 'unicode_logging']

        for guild in self.bot.guilds:
            if not self.db.contains(where('guild') == guild.id):
                log.info(f"Guild with ID {guild.id} was not in the config database.")
                self.db.insert({
            'guild': guild.id,
            'bot_logging': False,
            'unicode_logging': False
            })
        
        for document in self.db:
            if all(key in document for key in required_keys):
                pass
            else:
                for key in required_keys:
                    if key not in document:
                        document[key] = False
                self.db.update(document, doc_ids=[document.doc_id])

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"Bot has joined new server: {guild.name}")
        self.db.insert({
            'guild': guild.id,
            'bot_logging': False,
            'unicode_logging': False
            }) 

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.info(f"Bot has been removed from server: {guild.name}")
        if self.db.contains(where('guild') == guild.id):
            self.db.remove(where('guild') == guild.id)

async def setup(bot):
    await bot.add_cog(GuildListener(bot=bot))