# IMPORT DEPENDENCIES
import discord
import re
import os
import emoji
import datetime
import pytz
import logging
import colorlog

from tinydb import TinyDB, Query
from datetime import timezone
from discord.ext import tasks

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
        self.cache = []
        self.rlist = []
        self.main.start()
        self.db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))

    def in_range(self, timestamp, target):
        return abs(timestamp - target) <= 1

    @tasks.loop(seconds=300)
    async def main(self):
        self.cache = []
        self.list = []

        # Set time buffer to be within the next 5 minutes from now
        log.info("Checking for reminders within the next 300 seconds.")
        now = datetime.datetime.now(timezone.utc)
        buffer = now+datetime.timedelta(seconds=300)

        # Get a list of reminders within the next 5 minutes
        self.rlist = self.db.search((query.end < buffer.timestamp()) & (query.end > now.timestamp()))

        # Handle reminders that are in the past
        if len(self.db.search(query.end < now.timestamp())):
            log.warning("Found reminders in the past.")
            await self.handle_old_reminders(db=self.db, now=now)

        # Handle found reminders within the next 5 minutes, sync the queue
        if len(self.rlist) > 0:
            await self.handle_new_reminders()
            await self.sync_queue()

    @tasks.loop(time=[datetime.datetime.now().time()])
    async def r_queue(self):
        now = round(datetime.datetime.now(tz=pytz.utc).timestamp(),1)
        r = self.db.search(query.end.test(lambda x: self.in_range(x, now)))[0]
        log.debug(f"Reminder time has been reached for {r}.")
        await self.send_reminder(r=r)

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
        log.debug(f"There are {len(self.rlist)} reminders within the next 5 minutes. Adding them to the reminder cache.")
        for r in self.rlist:
            log.debug(f"Appending timer named {r['name']}, due {datetime.datetime.fromtimestamp(r['end'], tz=pytz.utc)}")
            self.cache.append(datetime.datetime.fromtimestamp(r["end"], tz=pytz.utc).time())

    async def sync_queue(self):
        self.r_queue.change_interval(time=self.cache)
        self.r_queue.start()
    
    async def inject(self, reminder):
        log.debug(f"Items before the append: {self.cache} {self.rlist}")
        time = datetime.datetime.fromtimestamp(reminder['end'], tz=pytz.utc).time()
        self.cache.append(time)
        self.rlist.append(reminder)
        log.debug(f"I have appended the items to the lists. The new lists are: {self.cache} {self.rlist}")
        self.main.stop()
        self.main.change_interval(time=time)
        self.main.restart()

    async def get_nextiteration(self):
        return self.main.next_iteration

async def Init_Class(bot):
    return Reminder(bot=bot)