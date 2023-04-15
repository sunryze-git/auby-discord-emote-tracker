# Import Libraries
import discord
from discord.ext import commands
from discord import app_commands

from tinydb import TinyDB, Query
from tinydb import where

from pythonping import ping

from asyncstdlib import map as amap
from asyncstdlib import list as alist

import re
import os

from resources import *

db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))

User = Query()

class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="index")
    @app_commands.describe(history = "How many messages should I look back?")
    async def index(self, interaction: discord.Interaction, history: int):
        await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have started indexing. The index may take a while depending on the specified message history!", ephemeral=True)
        await index_emoji(guild=interaction.guild, limit=history, bot = commands.Bot)

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        ping_results = ping('1.1.1.1')
        ping_results = re.findall('.* (.*\d..)', str(ping_results))
        await interaction.response.send_message(f"```The ping of the server is {ping_results[0]}```")

    @app_commands.command(name="logging")
    @app_commands.describe(set_logging_state = "When True, the bot will log emotes in this server. If False, stored data is deleted, and logging stops.")
    @app_commands.describe(bot_logging = "Do you want to log bots?")
    @app_commands.describe(unicode_logging = "Do you want to log unicode emotes?")
    async def logging(self, interaction: discord.Interaction, set_logging_state: bool, bot_logging: bool, unicode_logging: bool):
        try:
            await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have updated the configuration for your server.", ephemeral=True)
            if conf.contains(User.guild == interaction.guild_id):
                conf.update({'logging': set_logging_state}, User.guild == interaction.guild_id)
                conf.update({'bots': bot_logging}, User.guild == interaction.guild_id)
                conf.update({'unicode': unicode_logging}, User.guild == interaction.guild_id)
        except Exception as e:
            print(e)

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="statistics", description="Reports emoji statistics.")
    @app_commands.describe(
        type = "Do you want user stats or global server stats?",
        sort_order = "Which order do you want to sort by?",
        emoji_types = "What emojis would you like to see in the report?"
    )
    @app_commands.choices(type=[
        discord.app_commands.Choice(name='User Statistics', value=1),
        discord.app_commands.Choice(name='Server Statistics', value=2),
    ])
    @app_commands.choices(sort_order=[
        discord.app_commands.Choice(name='Least To Greatest', value=1),
        discord.app_commands.Choice(name='Greatest to Least', value=2)
    ])
    @app_commands.choices(emoji_types=[
        discord.app_commands.Choice(name='Custom Only', value=1),
        discord.app_commands.Choice(name='Custom and Unicode', value=2)
    ])
    async def statistics(self, interaction: discord.Interaction, type: discord.app_commands.Choice[int], sort_order: discord.app_commands.Choice[int], emoji_types: discord.app_commands.Choice[int]):
        embed = discord.Embed(
            color=discord.Color.blue(),
            description="Below are the current stats of your server.",
            title=f"Statistics in {interaction.guild.name}"
        )
        embed.set_thumbnail(url="https://media.tenor.com/wmVr2zAeufoAAAAC/omori-aubrey.gif")
        sort_order = sort_order.value != 1

        ephemeral, stats = await self.stats_init(type=type, interaction=interaction, sort_order=sort_order)
        stats_converted = await self.stats_convert(stats=stats, interaction=interaction, emoji_type=emoji_types.value)
        emoji_list, user_list = await self.stats_textify(stats=stats_converted)

        embed.set_footer(text="This data only includes indexed messages. Non-indexed messages will not appear.")
        embed.add_field(name="POPULARITY BY TOTAL", value=emoji_list)
        embed.insert_field_at(1,name="WHO SAID MOST", value=user_list)
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
 
    async def stats_init(self, type, interaction, sort_order):
        if type.value == 1:
            stats = await userstats_generator(guild=interaction.guild.id, user_id = int(interaction.user.id))
            stats_sorted = sorted(stats.items(), reverse=sort_order, key=lambda entry: len(entry[1]))
            return True, stats_sorted[:10]
        elif type.value == 2:
            stats = await stats_generator(guild=interaction.guild.id)
            stats_sorted = sorted(stats.items(), reverse=sort_order, key=lambda entry: len(entry[1]))
            return False, stats_sorted[:10]

    async def stats_convert(self, stats, interaction, emoji_type):
        async def process_tuple(tup):
            if emoji_type == 1 and not isinstance(tup[0], int):
                return

            if isinstance(tup[0], int):
                emoji_object = await interaction.guild.fetch_emoji(tup[0])
            else:
                emoji_object = tup[0]
                
            emoji_count = len(tup[1])
            most_common_id = max(set(tup[1]), key = tup[1].count)

            try:
                top_user = await self.bot.fetch_user(int(most_common_id))
                top_user_name = f"{top_user.name}#{top_user.discriminator}"
            except Exception as e:
                top_user_name = "unknown#0000"
                print(e)
            return (emoji_object, emoji_count, top_user_name)
        
        result = await alist(amap(process_tuple, stats))
        return result

    async def stats_textify(self, stats):
        return "\n".join([f"{tup[0]} ({tup[1]})" for tup in stats if tup != None]), "\n".join(tup[2] for tup in stats if tup != None)

async def setup(bot: commands.Bot):
    await bot.add_cog(Cmds(bot))
    await bot.add_cog(StatsCog(bot))