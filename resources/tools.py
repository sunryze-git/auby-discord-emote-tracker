### IMPORT LIBRARIES
import discord
import os
import datetime
import pytz

from tinydb import TinyDB, Query, where
from resources import log
from resources.emoji import EmojiHandler

from discord.ext import tasks

query = Query()
processemote = EmojiHandler()

#### TOOLS ####
class Tools():
    def __init__(self, bot=discord.Client, db=None):
        self.bot = bot
        self.rdb = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))
        self.db = TinyDB(os.path.join(os.getcwd(), "db.json"))
        self.confdb = TinyDB(os.path.join(os.getcwd(), "config.json"))

    async def gen_srv_stats(self, guild_id):
        log.debug(f"Sorting through server statistics for {guild_id}")
        stats = {}
        for item in self.db:
            if item['guild'] == guild_id:
                if item['emoji'] not in stats.keys():
                    stats[item['emoji']] = []
                stats[item['emoji']].append(item['user'])
        return stats
    
    async def gen_usr_stats(self, guild_id, user_id):
        log.debug(f"Sorting through user statistics for {user_id} in {guild_id}")
        stats = {}
        for row in self.db.search((query.user == user_id) & (query.guild == guild_id)):
            if row['emoji'] not in stats.keys():
                stats[row['emoji']] = []
            stats[row['emoji']].append(row['user'])
        return stats

    async def index_emoji(self, guild, limit):
        log.debug(f"Started Indexing {guild.name}, limit of {limit} messages")
        for channel in guild.text_channels:
            try:
                log.debug(f"Indexing: {guild.name}--->{channel.name}")
                async for message in channel.history(limit=limit):
                    if message.author != self.bot.user:
                        await processemote.process(message=message)
            except discord.Forbidden:
                log.debug(f"The bot does not have permissions to view {channel.name}.")
            except Exception as e:
                log.error(e)
        log.debug(f"Indexing finished for {guild.name}")