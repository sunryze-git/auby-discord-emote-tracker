# Import Libraries
import discord
from discord.ext import commands
from discord import app_commands

from tinydb import TinyDB, Query
from tinydb import where

import re
import os
import time
import emoji

#### SECRET TOKEN #####
token = os.environ.get('TOKEN')
#### ##### ###### #####

# Setup our Intents
intents = discord.Intents.default()
intents.message_content = True

db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))

User = Query()

bot = commands.Bot(command_prefix='$', intents=intents)

latest_pk = ""

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="OMORI"))

    for guild in bot.guilds:
        if not conf.contains(User.guild == guild.id):
            print(f"Guild with ID {guild.id} was not in the config database. Applying default configuration.")
            conf.insert({'guild': guild.id, 'logging': False, 'bots': False}) 

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

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
    await handle_emoji(message)

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

@bot.tree.command(name="index")
@app_commands.describe(history = "How many messages should I look back?")
async def index(interaction: discord.Interaction, history: int):
    await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have started indexing. The index may take a while depending on the specified message history!", ephemeral=True)
    await index_emoji(guild=interaction.guild, limit=history)

@bot.tree.command(name="statistics", description="Reports the statistics of either the global server, or just your user.")
@app_commands.describe(type = "Do you want user stats or global server stats?")
@app_commands.describe(sort_order = "Which order do you want to sort by?")
@app_commands.describe(emoji_types = "What emojis would you like to see in the report?")
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
async def statistics(interaction: discord.Interaction, type: discord.app_commands.Choice[int], sort_order: discord.app_commands.Choice[int], emoji_types: discord.app_commands.Choice[int]):
    embed = discord.Embed(
        color=discord.Color.blue(),
        description="Below are the current stats of your server. Aubrey Neutral is always watching.",
        title=f"Statistics in {interaction.guild.name}"
    )

    embed.set_thumbnail(url="https://media.tenor.com/wmVr2zAeufoAAAAC/omori-aubrey.gif")
    if type.value == 1:
        ephemeral = True
        user_id = interaction.user.id
        stats = await userstats_generator(interaction.guild.id,int(user_id))
    elif type.value == 2:
        ephemeral = False
        stats = await stats_generator(interaction.guild.id)

    counter = 0
    sort_order = sort_order.value != 1
    stats_sorted = sorted(stats.items(), reverse=sort_order, key=lambda entry: len(entry[1]))
    total = 0

    total_body = ""
    user_body = ""
    for k,v in stats_sorted:
        if isinstance(k, int):
            emoji_name = await interaction.guild.fetch_emoji(k)
        elif emoji_types == 2:
            emoji_name = k
        else:
            continue
        emoji_count = len(v)
        total = emoji_count + total

        top_user_id = max(set(v), key = v.count)

        try:
            top_user = await bot.fetch_user(int(top_user_id))
            top_user = f"{top_user.name}#{top_user.discriminator}"
        except Exception as e:
            top_user = "unknown#0000"
            print(e)

        total_body = f"{total_body}\n{emoji_name} ({emoji_count})"
        user_body = f"{user_body}\n{top_user}"

        counter += 1
        if counter > 10:
            break

    embed.set_footer(text="This data only includes indexed messages. Non-indexed messages will not appear.")
    embed.add_field(name="POPULARITY BY TOTAL", value=total_body)
    embed.insert_field_at(1,name="EMOJI BY USER", value=user_body)

    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    ping_results = os.popen('ping -c1 1.1.1.1 | grep -E time').read()
    ping_results = re.findall('.*time=(.*\d)', ping_results)
    await interaction.response.send_message(f"```The ping to 1.1.1.1 is {ping_results[0]} ms```")


@bot.tree.command(name="snuggle")
@app_commands.describe(snuggle_target = "Who do you want me to snuggle? :3")
async def snuggle(interaction: discord.Interaction, snuggle_target: str):
    await interaction.response.send_message(f":3 Sure thing! {snuggle_target} is such a cutie, ima snuggle them so much >w< *snuggles close to my bot body*")


# @bot.tree.command(name="run_command")
# @app_commands.describe(command = "What Python-based command would you like me to run?")
# async def run_command(interaction: discord.Integration, command: str):
#     print("Command Attempted")
#     if interaction.user.id != 229709025824997377:
#         await interaction.response.send_message("Sorry! This command is reserved for developers!", ephemeral=True)
#     try:
#         command_output = await eval(command)
#     except Exception as e:
#         command_output = e
#     await interaction.response.send_message(f" ```{command_output}``` ", ephemeral=True)

@bot.tree.command(name="logging")
@app_commands.describe(set_logging_state = "When True, the bot will log emotes in this server. If False, stored data is deleted, and logging stops.")
@app_commands.describe(bot_logging = "Do you want to log bots?")
@app_commands.describe(unicode_logging = "Do you want to log unicode emotes?")
async def logging(interaction: discord.Interaction, set_logging_state: bool, bot_logging: bool, unicode_logging: bool):
    try:
        await interaction.response.send_message(f"Hello, {interaction.user.mention}, I have updated the configuration for your server.", ephemeral=True)
        if conf.contains(User.guild == interaction.guild_id):
            conf.update({'logging': set_logging_state}, User.guild == interaction.guild_id)
            conf.update({'bots': bot_logging}, User.guild == interaction.guild_id)
            conf.update({'unicode': unicode_logging}, User.guild == interaction.guild_id)
    except Exception as e:
        print(e)

async def index_emoji(guild, limit):
    for channel in guild.text_channels:
        try:
            print(guild.name, channel.name)
            async for message in channel.history(limit=limit):
                if message.author != bot.user:
                    await handle_emoji(message)
        except Exception as e:
            print(e)
    print(f"Indexing finished for {guild.name}")

async def stats_generator(guild):
    stats = {}
    for row in db:
        if row['guild'] == guild:
            if row['emoji'] not in stats.keys():
                stats[row['emoji']] = []
            stats[row['emoji']].append(row['user'])
    return stats

async def userstats_generator(guild,user_id):
    user_rows = db.search((User.user == user_id) & (User.guild == guild))
    stats = {}
    for row in user_rows:
        if row['emoji'] not in stats.keys():
            stats[row['emoji']] = []
        stats[row['emoji']].append(row['user'])
    return stats

async def handle_emoji(message):
    content = message.content
    guild_id = message.guild.id
    guild = message.guild
    user_id = message.author.id
    user_name = str(message.author)
    message_id = message.id
    sent_time = discord.utils.snowflake_time(int(message_id))
    emoji_id = re.findall('<.*:\w+:(\d+)>', content)
    emoji_name = re.findall('<.*:(\w+):\d+>', content)
    author_is_bot = message.author.bot

    # Do not handle the emoji if the guild has chosen to disable logging
    guild_config = conf.get(User.guild == guild_id)
    if not guild_config['logging']:
        return

    # If the author of the message is a bot, ignore it if specified in the config
    if author_is_bot and not guild_config['bots']:
        return

    # Ignore the message if there are no emojis in it
    if len(db.search(User.message_id == message_id)) >= 1:
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
    
bot.run(token)