import discord

from tinydb import TinyDB, Query
from tinydb import where

import re
import os
import emoji

db = TinyDB(os.path.join(os.getcwd(), "db.json"))
conf = TinyDB(os.path.join(os.getcwd(), "config.json"))

User = Query()

async def stats_generator(guild):
    stats = {}
    for row in db:
        if row['guild'] == guild:
            if row['emoji'] not in stats.keys():
                stats[row['emoji']] = []
            stats[row['emoji']].append(row['user'])
    return stats
async def userstats_generator(guild, user_id):
    user_rows = db.search((User.user == user_id) & (User.guild == guild))
    stats = {}
    for row in user_rows:
        if row['emoji'] not in stats.keys():
            stats[row['emoji']] = []
        stats[row['emoji']].append(row['user'])
    return stats
async def index_emoji(guild, limit, bot):
    for channel in guild.text_channels:
        try:
            print(guild.name, channel.name)
            async for message in channel.history(limit=limit):
                if message.author != bot.user:
                    await handle_emoji(message = message)
        except Exception as e:
            print(e)
    print(f"Indexing finished for {guild.name}")
async def handle_emoji(message):
    content = message.content
    guild_id = message.guild.id
    guild = message.guild
    user_id = message.author.id
    message_id = message.id
    sent_time = discord.utils.snowflake_time(int(message_id))
    emoji_id = re.findall('<.*:\w+:(\d+)>', content)
    emoji_name = re.findall('<.*:(\w+):\d+>', content)
    # Do not handle the emoji if the guild has chosen to disable logging
    guild_config = conf.get(User.guild == guild_id)
    if not guild_config['logging']:
        return
    # If the author of the message is a bot, ignore it if specified in the config
    if message.author.bot and not guild_config['bots']:
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