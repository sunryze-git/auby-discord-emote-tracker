# Import Libraries
import discord
import logging

from discord.ext import commands
from discord import app_commands

log = logging.getLogger('auby')

# General multipurpose cog for handling other commands
class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.confi_db = bot.server_conf

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        ping_results = round(self.bot.latency * 1000, 1)
        await interaction.response.send_message(f"Websocket Ping: ```{ping_results} ms```")

    @app_commands.command(name="reload")
    async def reload(self, interaction: discord.Interaction):
        extensions = [i for i in self.bot.extensions]
        for ext in extensions:
            self.bot.logger.info(f"Reloading Extension {ext}")
            await self.bot.reload_extension(ext)
        await interaction.response.send_message(f"Finished reloading {len(self.bot.extensions)} extension(s).", ephemeral=True)

# Add the cog classes to our bot - this function runs when commands.py is loaded by main.py
async def setup(bot: commands.Bot):
    # sourcery skip: instance-method-first-arg-name
    await bot.add_cog(Cmds(bot))