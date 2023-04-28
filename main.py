### IMPORT LIBRARIES
import discord
import os
import logging
import colorlog

from discord.ext import commands

#### SECRET TOKEN #####
token = os.environ.get('TOKEN')
#### ##### ###### #####

# Setup our Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Setup Logging
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

# On_Ready function
@bot.event
async def on_ready():
    await bot.load_extension('auby.listeners.guild')
    await bot.load_extension('auby.listeners.message')
    await bot.load_extension('auby.commands.commands')
    await bot.load_extension('auby.extensions.emoji')

    log.info(f'Bot Login Successful as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="OMORI"))

    try:
        await bot.tree.sync()
        log.info("Commands Synced")
    except Exception as e:
        log.warning(f"Failed to sync commands: {e}")

# Start bot
bot.run(token)