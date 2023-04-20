# Import Libraries
import discord
import os

from discord.ext import commands
from tinydb import TinyDB, Query

from resources import Tools
from resources import Reminder

#### SECRET TOKEN #####
token = os.environ.get('TOKEN')
#### ##### ###### #####

# Setup our Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))
User = Query()

latest_pk = ""

async def sync_tree():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.event
async def on_ready():
    global tools
    global rc
    
    await bot.load_extension('commands')

    print(f'We have logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="OMORI"))

    for guild in bot.guilds:
        if not conf.contains(User.guild == guild.id):
            print(f"Guild with ID {guild.id} was not in the config database. Applying default configuration.")
            conf.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

    tools = Tools(bot=bot, db=db)
    rc = Reminder(bot=bot)

    print("Syncing Commands")
    await sync_tree()

@bot.event
async def on_guild_join(guild):
    print(f"Bot has joined new server: {guild.name}")
    conf.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

@bot.event
async def on_guild_remove(guild):
    print(f"Bot has been removed from server: {guild.name}")
    if conf.contains(User.guild == guild.id):
        conf.remove(User.guild == guild.id)

@bot.event
async def on_message(message):
    global latest_pk
    if message.author == bot.user:
        return

    if message.webhook_id is not None:
        latest_pk = message.content
        return
            
    #print(f"IN {message.guild.id} FROM {message.author}-{message.webhook_id}: {message.content}")
    await tools.process_emoji(message = message)

@bot.event
async def on_raw_message_delete(message):
    if message.cached_message is not None:
        c_message = message.cached_message
        if latest_pk in c_message.content:
            return
    try:
        db.remove(User.message_id == message.message_id)
    except Exception as e:
        print(e)

@bot.tree.command(name="reload")
async def reload(interaction: discord.Interaction):
    print("Reloading Commands!")
    await bot.reload_extension('commands')
    await interaction.response.send_message("Commands Reloaded", ephemeral=True)
    await sync_tree()

bot.run(token)