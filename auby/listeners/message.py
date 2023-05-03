from discord.ext import commands

from auby.extensions.emoji import EmojiHandler

class MessageListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pk = ""
        self.emojihandler = EmojiHandler(bot=bot)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if message.webhook_id is not None:
            self.pk = message.content
            return
                
        #log.debug(f"IN {message.guild.id} FROM {message.author}-{message.webhook_id}: {message.content}")
        await self.emojihandler.process(message=message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, message):
        if message.cached_message is not None:
            c_message = message.cached_message
            if self.pk in c_message.content:
                 return

        await self.emojihandler.remove(message=message)

async def setup(bot):
    await bot.add_cog(MessageListener(bot=bot))