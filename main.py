### IMPORT LIBRARIES
import discord
import os

from discord.ext import commands
from discord.ext import tasks
from tinydb import TinyDB, Query

from resources.tools import Tools
from resources.reminder import Reminder
from resources.emoji import EmojiHandler
from resources import log

processemote = EmojiHandler()

#### SECRET TOKEN #####
token = os.environ.get('TOKEN')
#### ##### ###### #####

# Setup our Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Setup the databases
db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))
User = Query()

# Define a global variable which stores the latest PluralKit-detected message
latest_pk = ""

# Initialize our Tools class
tools = Tools(bot=bot, db=db)

# Sync Commands with Discord
async def sync_tree():
    try:
        await bot.tree.sync()
        log.info("Commands Synced")
    except Exception as e:
        log.warning(f"Failed to sync commands: {e}")

# Function that runs when the bot is loaded
@bot.event
async def on_ready():
    await bot.load_extension('commands')

    log.info(f'Bot Login Successful as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="OMORI"))

    for guild in bot.guilds:
        if not conf.contains(User.guild == guild.id):
            log.info(f"Guild with ID {guild.id} was not in the config database. Applying default configuration.")
            conf.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

    

    await sync_tree()

# Runs when the bot detects a new guild
@bot.event
async def on_guild_join(guild):
    log.info(f"Bot has joined new server: {guild.name}")
    conf.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

# Runs when the bot detects a removal from a guild
@bot.event
async def on_guild_remove(guild):
    log.info(f"Bot has been removed from server: {guild.name}")
    if conf.contains(User.guild == guild.id):
        conf.remove(User.guild == guild.id)

# Runs when the bot detects a new message
@bot.event
async def on_message(message):
    global latest_pk
    if message.author == bot.user:
        return

    if message.webhook_id is not None:
        latest_pk = message.content
        return
            
    #log.debug(f"IN {message.guild.id} FROM {message.author}-{message.webhook_id}: {message.content}")
    await processemote.process(message=message)

# Runs when the bot detects a message deletion, regardless if it is in the cache or not
@bot.event
async def on_raw_message_delete(message):
    if message.cached_message is not None:
        c_message = message.cached_message
        if latest_pk in c_message.content:
            return
    try:
        db.remove(User.message_id == message.message_id)
    except Exception as e:
        log.error(e)

# Command which reloads the commands module, WIP: reload resources
@bot.tree.command(name="reload")
async def reload(interaction: discord.Interaction):
    global rc
    log.info("Reloading Commands!")
    await bot.reload_extension('commands')
    await interaction.response.send_message("Bot has been reloaded", ephemeral=True)
    await sync_tree()

# Starts the bot
bot.run(token, root_logger=False)