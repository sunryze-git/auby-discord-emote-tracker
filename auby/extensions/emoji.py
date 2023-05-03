### IMPORT LIBRARIES
import re
import emoji
import discord
import logging

from tinydb import Query, where

from discord.ext import commands
from discord import app_commands

from asyncstdlib import map as amap
from asyncstdlib import list as alist

log = logging.getLogger('auby')

class EmojiHandler():
    def __init__(self, bot: commands.Bot):
        # Create a database instance for configurations and a database instance for emojis
        self.confdb = bot.server_conf
        self.db     = bot.emoji_conf
        self.bot    = bot

    async def process(self, message):
        # Find all custom emojis and their names in the message content
        emoji_id = re.findall(r'<.*:\w+:(\d+)>', message.content)
        emoji_name = re.findall(r'<.*:(\w+):\d+>', message.content)
        
        # Check if bot messages should be ignored based on the guild's configuration
        if self._should_ignore_bot(message.author.bot, message.guild):
            log.debug(f"Message from {message.author.name} is a bot, and the configuration doesn't allow it.")
            return
        
        # Check if the message has already been logged
        if self._should_ignore_message(message):
            log.debug("Message ID has already been logged. Ignoring.")
            return

        # If there are custom emojis in the message content, process them
        if len(emoji_id) > 0:
            try:
                await self._process_custom_emojis(emoji_id, emoji_name, message)
            except Exception as e:
                log.exception("An error occurred while processing custom emojis.", exc_info=e)
        # If there are no custom emojis, and / or there are unicode emojis in the message content, process those as well
        elif emoji.emoji_count(message.content) > 0:
            log.debug(f"Processing {emoji.emoji_count(message.content)} custom emoji(s) in this message.")
            try:
                await self._process_unicode_emojis(message)
            except Exception as e:
                log.exception("An error occurred while processing unicode emojis.", exc_info=e)

    def _should_ignore_bot(self, is_bot, guild):
        guild_config = self.confdb.get(Query().guild == guild.id)
        return bool(guild_config and guild_config['bot_logging'] and is_bot)
    
    def _should_ignore_message(self, message):
        message_id = message.id
        return len(self.db.search(Query().message_id == message_id)) > 0

    async def _process_custom_emojis(self, emoji_id, emoji_name, message):
        for counter, i in enumerate(emoji_id):
            try:
                await message.guild.fetch_emoji(i)
                log.debug(f"Custom emoji {emoji_name}:{emoji_id} was found in {message.guild.name}")
            except discord.NotFound:
                log.debug(f"Custom emoji {emoji_name}:{emoji_id} not found in {message.guild.name}")
            except Exception as e:
                log.exception(f"An error occurred while fetching custom emoji {i}.", exc_info=e)
                return
            self.db.insert({'guild': message.guild.id, 'user': message.author.id, 'emoji': int(i), 'emoji_name': emoji_name[counter], 'message_id': message.id})

    async def _process_unicode_emojis(self, message):
        guild_config = self.confdb.get(Query().guild == message.guild.id)
        if guild_config and guild_config['unicode_logging']:
            for i in emoji.distinct_emoji_list(message.content):
                emoji_name = emoji.demojize(i)
                self.db.insert({'guild': message.guild.id, 'user': message.author.id, 'emoji': i, 'emoji_name': emoji_name, 'message_id': message.id})

    async def server_stats(self, guild_id):
        log.debug(f"Sorting server statistics for {guild_id}")
        stats = {}
        for item in self.db:
            if item['guild'] == guild_id:
                if item['emoji'] not in stats.keys():
                    stats[item['emoji']] = []
                stats[item['emoji']].append(item['user'])
        return stats

    async def user_stats(self, guild_id, user_id):
        log.debug(f"Sorting user statistics for {user_id} in {guild_id}")
        stats = {}
        for row in self.db.search((Query().user == user_id) & (Query().guild == guild_id)):
            if row['emoji'] not in stats.keys():
                stats[row['emoji']] = []
            stats[row['emoji']].append(row['user'])
        return stats

    async def index(self, guild: discord.Guild, limit: int):
        log.debug(f"Started index for {guild.name} --> {limit} messages")
        for channel in guild.text_channels:
            try:
                log.debug(f"Indexing: {guild.name} ---> {channel.name}")
                async for message in channel.history(limit=limit):
                    if message.author != self.bot.user:
                        await self.process(message=message)
            except discord.Forbidden:
                log.debug(f"The bot does not have permissions to view {channel.name}.")
            except Exception as e:
                log.error(e)
        log.debug(f"Indexing finished for {guild.name} ({guild.id})")

    async def remove(self, message):
        try:
            self.db.remove(Query().message_id == message.message_id)
        except Exception as e:
            log.error(e)

class EmojiCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.confi_db = bot.server_conf
        self.emojihandler = EmojiHandler(bot=bot)

    @app_commands.command(name="statistics", description="Reports emoji statistics.")
    @app_commands.describe(
        type="Do you want user stats or global server stats?",
        emoji_types="What emojis would you like to see in the report?"
    )
    @app_commands.choices(type=[
        discord.app_commands.Choice(name='User Statistics', value=1),
        discord.app_commands.Choice(name='Server Statistics', value=2),
    ])
    @app_commands.choices(emoji_types=[
        discord.app_commands.Choice(name='Custom Only', value=1),
        discord.app_commands.Choice(name='Custom and Unicode', value=2)
    ])
    async def statistics(self, interaction: discord.Interaction, type: discord.app_commands.Choice[int], emoji_types: discord.app_commands.Choice[int]):
        ephemeral, stats, g_logging = await self.stats_init(type=type, interaction=interaction)
        stats_converted = await self.stats_convert(stats=stats, interaction=interaction, emoji_type=emoji_types.value)
        emoji_list, user_list = await self.stats_textify(stats=stats_converted)

        embed = discord.Embed(
            color=discord.Color.blue(),
            description=f"Below are the current stats of your server.\nGUILD LOGGING: **{str(g_logging)}**",
            title=f"Statistics in {interaction.guild.name}"
        )
        embed.set_thumbnail(
            url="https://media.tenor.com/wmVr2zAeufoAAAAC/omori-aubrey.gif")

        embed.set_footer(
            text="This data only includes indexed messages. Non-indexed messages will not appear.")
        embed.add_field(name="POPULARITY BY TOTAL", value=emoji_list)
        embed.insert_field_at(1, name="WHO SAID MOST", value=user_list)
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    async def stats_init(self, type, interaction):
        if type.value == 1:
            stats = await self.bot.emojihandler.user_stats(guild_id=interaction.guild.id, user_id=int(interaction.user.id))
            stats_sorted = sorted(
                stats.items(),reverse=True, key=lambda entry: len(entry[1]))
            guild_logging = bool(self.confi_db.get(
                where('guild') == interaction.guild.id)['logging'])
            return True, stats_sorted[:10], guild_logging
        elif type.value == 2:
            stats = await self.bot.emojihandler.server_stats(guild_id=interaction.guild.id)
            stats_sorted = sorted(
                stats.items(),reverse=True, key=lambda entry: len(entry[1]))
            guild_logging = bool(self.confi_db.get(
                where('guild') == interaction.guild.id)['logging'])
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
            most_common_id = max(set(tup[1]), key=tup[1].count)

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

    @app_commands.command(name="index")
    @app_commands.describe(
        history="How many messages should I look back?"
    )
    async def index(self, interaction: discord.Interaction, history: int):
        await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have started indexing. The index may take a while depending on the specified message history!", ephemeral=True)
        await self.bot.emojihandler.index(guild=interaction.guild, limit=history)

    @app_commands.command(name="logging")
    @app_commands.describe(
        bot_logging="Do you want to log bots?",
        unicode_logging="Do you want to log unicode emotes?"
    )
    async def logging(self, interaction: discord.Interaction, bot_logging: bool, unicode_logging: bool):
        try:
            await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have updated the configuration for your server.", ephemeral=True)
            if self.confi_db.contains(where('guild') == interaction.guild_id):
                self.confi_db.update({
                    'bots': bot_logging,
                    'unicode': unicode_logging
                    }, Query().guild == interaction.guild_id)
        except Exception as e:
            log.warning(e)

async def setup(bot: commands.Bot):
    bot.emojihandler = EmojiHandler(bot=bot)
    await bot.add_cog(EmojiCmds(bot=bot))