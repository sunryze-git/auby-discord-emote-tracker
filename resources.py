# IMPORT DEPENDENCIES
import discord
import re
import os
import emoji
import datetime
import pytz
import logging
import colorlog
import asyncio
import uuid

from tinydb import TinyDB, Query, where
from datetime import timezone

# Setup our databases
db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))
remind_db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))
query = Query()

### INITIALIZE LOGGING ###
def setup_logging(logging_level=logging.INFO):
    log = logging.getLogger(__file__)
    log.setLevel(logging_level)
    format_str = '%(bold_black)s%(asctime)s %(log_color)s%(levelname)-8s %(purple)s%(filename)s%(reset)s %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    cformat = f'{format_str}'
    colors={
            'DEBUG': 'green',
            'INFO': 'cyan',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    formatter = colorlog.ColoredFormatter(cformat, date_format, log_colors=colors)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    return log
log = setup_logging(logging_level=logging.DEBUG)

#### TOOLS ####
class Tools():
    def __init__(self, bot=discord.Client, db=None):
        self.bot = bot
        self.db = db
        
    async def gen_srv_stats(self, guild_id):
        stats = {}
        for item in self.db:
            if item['guild'] == guild_id:
                if item['emoji'] not in stats.keys():
                    stats[item['emoji']] = []
                stats[item['emoji']].append(item['user'])
        return stats
    
    async def gen_usr_stats(self, guild_id, user_id):
        stats = {}
        for row in self.db.search((query.user == user_id) & (query.guild == guild_id)):
            if row['emoji'] not in stats.keys():
                stats[row['emoji']] = []
            stats[row['emoji']].append(row['user'])
        return stats

    async def index_emoji(self, guild, limit):
        for channel in guild.text_channels:
            try:
                log.debug(guild.name, channel.name)
                async for message in channel.history(limit=limit):
                    if message.author != self.bot.user:
                        await self.process_emoji(message = message)
            except Exception as e:
                log.error(e)
        log.debug(f"Indexing finished for {guild.name}")

    async def process_emoji(self, message):
        content = message.content
        guild_id = message.guild.id
        guild = message.guild
        user_id = message.author.id
        message_id = message.id
        sent_time = discord.utils.snowflake_time(int(message_id))
        emoji_id = re.findall('<.*:\w+:(\d+)>', content)
        emoji_name = re.findall('<.*:(\w+):\d+>', content)
        # Do not handle the emoji if the guild has chosen to disable logging
        guild_config = conf.get(query.guild == guild_id)
        if not guild_config['logging']:
            return
        # If the author of the message is a bot, ignore it if specified in the config
        if message.author.bot and not guild_config['bots']:
            return
        # Ignore the message if there are no emojis in it
        if len(db.search(query.message_id == message_id)) >= 1:
            return
        # If there are emojis in the message, for every emoji detected, try to get its id. 
        # Insert that emoji into the database as its id. If there is not a normally detected emoji, but the emoji library detects more than 0,
        # get the emount of amojis and their names in the content. Then get their name, and insert them into the database, if the guild has enabled unicode logging.
        if len(emoji_id) > 0:
            for counter, i in enumerate(emoji_id):
                try:
                    await guild.fetch_emoji(i)
                except Exception as e:
                    return
                db.insert({'guild': guild_id, 'user': user_id, 'emoji': int(i), 'emoji_name': emoji_name[counter], 'message_id': message_id})
        elif emoji.emoji_count(content) > 0:
            if guild_config['unicode']:
                for i in emoji.distinct_emoji_list(content):
                    emoji_name = emoji.demojize(i)
                    db.insert({'guild': guild_id, 'user': user_id, 'emoji': i, 'emoji_name': emoji_name, 'message_id': message_id})

#### REMINDER SYSTEM ####
class Reminder():
    def __init__(self, bot):
        self.bot = bot
        self.db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))
        self.next_due = None
        self.task = None

        asyncio.ensure_future(self.start())

    def in_range(self, timestamp, target):
        return abs(timestamp - target) <= 1

    async def send_reminder(self, r):
        log.debug("Sending Reminder to User!")
        channel = await self.bot.fetch_channel(int(r['channel']))
        try:
            await channel.send(f"<@{r['user']}>, <t:{int(r['end'])}:R>: {r['name']}")
            self.db.remove(query.id == r['id'])
        except Exception as e:
            log.error(e)

    async def handle_old_reminders(self, db, now):
        past_reminders = db.search(query.end < now.timestamp())
        for r in past_reminders:
            await self.send_reminder(r=r)

    async def handle_new_reminders(self):
        log.debug(f"There are {len(self.db)} reminders due.")
        now = datetime.datetime.now(timezone.utc)
        immediate_reminders = self.db.search(query.end <= now.timestamp())
        for r in immediate_reminders:
            await self.send_reminder(r=r)
            self.db.remove(query.id == r['id'])
        future_reminders = self.db.search(query.end > now.timestamp())
        future_reminders.sort(key=lambda x: x["end"])
        if future_reminders:
            self.next_due = datetime.datetime.fromtimestamp(future_reminders[0]["end"], tz=pytz.utc)
        for r in future_reminders:
            if r["end"] <= now.timestamp():
                await self.send_reminder(r=r)
                self.db.remove(query.id == r['id'])
            else:
                break
    
    async def schedule_next_reminder(self):
        if self.next_due is None:
            return
        delta = self.next_due - datetime.datetime.now(timezone.utc)
        seconds_until_due = max(delta.total_seconds(), 0)
        log.debug(f"Next reminder is due in {seconds_until_due} seconds.")
        await asyncio.sleep(seconds_until_due)
        self.task = asyncio.create_task(self.handle_new_reminders())
    
    async def inject(self, reminder):
        log.debug(f"Reminder {reminder['name']} added to queue.")
        self.db.insert(reminder)
        if self.task is not None and not self.task.done():
            self.task.cancel()
        await self.handle_new_reminders()
        await self.schedule_next_reminder()

    async def start(self):
        await self.handle_old_reminders(db=self.db, now=datetime.datetime.now(timezone.utc))
        await self.handle_new_reminders()
        await self.schedule_next_reminder()

    async def delete_reminder(self, id):
        self.db.remove(query.id == str(id))
        asyncio.ensure_future(self.start())