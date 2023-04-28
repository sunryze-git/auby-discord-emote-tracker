# Import Libraries
import discord
from discord.ext import commands
from discord import app_commands
from pythonping import ping
from asyncstdlib import map as amap
from asyncstdlib import list as alist
from datetime import timezone
from tinydb import TinyDB, where, Query

import datetime
import parsedatetime as pdt
import calendar
import re
import os
import pytz
import logging
log = logging.getLogger()

# General multipurpose cog for handling other commands
class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.confi_db = TinyDB(os.path.join(os.getcwd(), "config.json"))

    @app_commands.command(name="index")
    @app_commands.describe(
        history = "How many messages should I look back?"
    )
    async def index(self, interaction: discord.Interaction, history: int):
        await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have started indexing. The index may take a while depending on the specified message history!", ephemeral=True)
        await self.bot.emojihandler.index(guild=interaction.guild, limit=history)

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        ping_results = re.findall('.* (.*\d..)', str(ping('1.1.1.1')))
        await interaction.response.send_message(f"```The ping of the server is {ping_results[0]}```")

    @app_commands.command(name="logging")
    @app_commands.describe(
        set_logging_state = "When True, the bot will log emotes in this server. If False, stored data is deleted, and logging stops.",
        bot_logging = "Do you want to log bots?",
        unicode_logging = "Do you want to log unicode emotes?"
    )
    async def logging(self, interaction: discord.Interaction, set_logging_state: bool, bot_logging: bool, unicode_logging: bool):
        try:
            await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have updated the configuration for your server.", ephemeral=True)
            if self.confi_db.contains(where('guild') == interaction.guild_id):
                self.confi_db.update({'logging': set_logging_state, 'bots': bot_logging, 'unicode': unicode_logging}, Query().guild == interaction.guild_id)
        except Exception as e:
            log.warning(e)

# Seperate cog for handling statistics
class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.confi_db = TinyDB(os.path.join(os.getcwd(), "config.json"))
    
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
        sort_order = sort_order.value != 1

        ephemeral, stats, g_logging = await self.stats_init(type=type, interaction=interaction, sort_order=sort_order)
        stats_converted = await self.stats_convert(stats=stats, interaction=interaction, emoji_type=emoji_types.value)
        emoji_list, user_list = await self.stats_textify(stats=stats_converted)

        embed = discord.Embed(
            color=discord.Color.blue(),
            description=f"Below are the current stats of your server.\nGUILD LOGGING: **{str(g_logging)}**",
            title=f"Statistics in {interaction.guild.name}"
        )
        embed.set_thumbnail(url="https://media.tenor.com/wmVr2zAeufoAAAAC/omori-aubrey.gif")

        embed.set_footer(text="This data only includes indexed messages. Non-indexed messages will not appear.")
        embed.add_field(name="POPULARITY BY TOTAL", value=emoji_list)
        embed.insert_field_at(1,name="WHO SAID MOST", value=user_list)
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
 
    async def stats_init(self, type, interaction, sort_order):
        if type.value == 1:
            stats = await self.bot.emojihandler.gen_usr_stats(guild_id=interaction.guild.id, user_id = int(interaction.user.id))
            stats_sorted = sorted(stats.items(), reverse=sort_order, key=lambda entry: len(entry[1]))
            guild_logging = bool(self.confi_db.get(where('guild') == interaction.guild.id)['logging'])
            return True, stats_sorted[:10], guild_logging
        elif type.value == 2:
            stats = await self.bot.emojihandler.gen_srv_stats(guild_id=interaction.guild.id)
            stats_sorted = sorted(stats.items(), reverse=sort_order, key=lambda entry: len(entry[1]))
            guild_logging = bool(self.confi_db.get(where('guild') == interaction.guild.id)['logging'])
            return False, stats_sorted[:10], guild_logging

    async def stats_convert(self, stats, interaction, emoji_type):
        async def process_tuple(tup):
            if emoji_type == 1 and not isinstance(tup[0], int):
                return

            if isinstance(tup[0], int):
                try:
                    emoji_object = await interaction.guild.fetch_emoji(tup[0])
                except (discord.NotFound):
                    log.error(f"Error fetching emoji with ID {tup[0]}.")
                    emoji_object = "Error Fetching"
            else:
                emoji_object = tup[0]
                
            emoji_count = len(tup[1])
            most_common_id = max(set(tup[1]), key = tup[1].count)

            try:
                top_user = await self.bot.fetch_user(int(most_common_id))
                top_user_name = f"{top_user.name}#{top_user.discriminator}"
            except Exception as e:
                top_user_name = "unknown#0000"
                log.warning(e)
            return (emoji_object, emoji_count, top_user_name)
        
        result = await alist(amap(process_tuple, stats))
        return result

    async def stats_textify(self, stats):
        return "\n".join([f"{tup[0]} ({tup[1]})" for tup in stats if tup is not None]), "\n".join(tup[2] for tup in stats if tup is not None)

# New Cog for handling reminders
class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.remind_db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))


    @app_commands.command(name="remind", description="BETA: Reminds you something.")
    @app_commands.describe(
        name = "What do you want me to remind you for? (ex: pet a fox)",
        date = "When do you want to be reminded? (most date formats work)"
    )
    async def remind(self, interaction: discord.Interaction, name: str, date: str):
        cal = pdt.Calendar()
        now = datetime.datetime.now(timezone.utc)
        start_date = interaction.created_at
        end_date = cal.parseDT(datetimeString=date, sourceTime=now, tzinfo=pytz.utc)[0]

        if end_date > start_date:
            await interaction.response.send_message(f"<@{interaction.user.id}>, I will remind you <t:{int(calendar.timegm(end_date.utctimetuple()))}:R>: {name}")
        else:
            await interaction.response.send_message("That time is not valid!", ephemeral=True)

    @app_commands.command(name="remindlist", description="BETA: See a list of the reminders you have set.")
    async def remindlist(self, interaction: discord.Interaction):
        embed = discord.Embed(
            color=discord.Color.orange(),
            description="A list of your set reminders.",
            title=f"Reminder list for {interaction.user.name}"
        )
        r_list = self.remind_db.search(where('user') == interaction.user.id)
        r_list.sort(key=lambda r: r["end"], reverse=False)

        body1 = "\n".join(str(r["id"]) for r in r_list)
        body2 = "\n".join(r["name"] for r in r_list)
        body3 = "\n".join(f"<t:{int(r['end'])}:R>" for r in r_list)

        embed.add_field(name="Reminder ID", value=body1)
        embed.insert_field_at(1,name="Name", value=body2)
        embed.insert_field_at(2,name="Due Date", value=body3)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="deletereminder", description="BETA: Delete a reminder you have set.")
    @app_commands.describe(
        id = "What is the ID of the reminder?"
    )
    async def deletereminder(self, interaction: discord.Interaction, id: str):
        await interaction.response.send_message(f"I have deleted your reminder with ID: ``{id}``.", ephemeral=True)
        await self.reminder.rem

# Add the cog classes to our bot - this function runs when commands.py is loaded by main.py
async def setup(bot: commands.Bot):
    # sourcery skip: instance-method-first-arg-name
    await bot.add_cog(Cmds(bot))
    await bot.add_cog(StatsCog(bot))
    await bot.add_cog(Reminders(bot))