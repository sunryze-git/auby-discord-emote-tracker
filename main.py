# IMPORT LIBRARIES
import discord
import os
import logging
import colorlog

from discord.ext import commands

from tinydb import TinyDB

#### SECRET TOKEN #####
token = os.environ.get('TOKEN')
#### ##### ###### #####

# Setup our Intents
intents = discord.Intents.default()
intents.message_content = True

# Setup Logging
def setup_logging(logging_level):
    log = logging.getLogger('auby')
    log.setLevel(logging_level)
    format_str = '%(bold_black)s%(asctime)s %(log_color)s%(levelname)-8s %(purple)s%(filename)s%(reset)s %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    cformat = f'{format_str}'
    colors = {
        'DEBUG': 'green',
        'INFO': 'cyan',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    formatter = colorlog.ColoredFormatter(
        cformat, date_format, log_colors=colors)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)
    return log

log = setup_logging(logging_level=logging.DEBUG)

class CustomBot(commands.Bot):
    async def setup_hook(self):
        self.reminders = {}
        self.logger = log

        self.server_conf    = TinyDB(os.path.join(os.getcwd(), "auby/data/server_conf.json"))
        self.emoji_conf     = TinyDB(os.path.join(os.getcwd(), "auby/data/emoji_db.json"))
        self.remind_conf    = TinyDB(os.path.join(os.getcwd(), "auby/data/remind_db.json"))

        self.logger.info(f"Logging in as {self.user}")

        # Load Extensions
        for file in os.listdir(os.path.join(os.getcwd(),'auby/extensions')):
            if not file.startswith("__"):
                self.logger.info(f"Loaded Extension: {file}")
                await self.load_extension(f"auby.extensions.{file[:-3]}")

        # Load Listeners
        for file in os.listdir(os.path.join(os.getcwd(),'auby/listeners')):
            if not file.startswith("__"):
                self.logger.info(f"Loaded Extension: {file}")
                await self.load_extension(f"auby.listeners.{file[:-3]}")

activity = discord.Game(name="OMORI")
bot = CustomBot(command_prefix='$', intents=intents, activity=activity)

# On_Ready function
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        bot.logger.info("Commands Synced")
    except Exception as e:
        bot.logger.warning(f"Failed to sync commands: {e}")

# Start bot
bot.run(token)