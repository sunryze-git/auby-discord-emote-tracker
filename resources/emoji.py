### IMPORT LIBRARIES
import re
import os
import emoji
import discord
from tinydb import Query, TinyDB

from resources import log

class EmojiHandler():
    def __init__(self):
        # Create a database instance for configurations and a database instance for emojis
        self.confdb = TinyDB(os.path.join(os.getcwd(), "config.json"))
        self.db     = TinyDB(os.path.join(os.getcwd(), "db.json"))

    async def process(self, message):
        # Find all custom emojis and their names in the message content
        emoji_id = re.findall(r'<.*:\w+:(\d+)>', message.content)
        emoji_name = re.findall(r'<.*:(\w+):\d+>', message.content)

        # Check if the guild has enabled emoji logging
        if not self._should_log(message.guild):
            log.debug("Message should not be logged, as the configuration for this guild doesn't allow it.")
            return
        
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
            log.debug(f"Processing {len(emoji_id)} custom emoji(s) in this message.")
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

    def _should_log(self, guild):
        guild_config = self.confdb.get(Query().guild == guild.id)
        return bool(guild_config and guild_config['logging'])

    def _should_ignore_bot(self, is_bot, guild):
        guild_config = self.confdb.get(Query().guild == guild.id)
        return bool(guild_config and guild_config['bots'] and is_bot)
    
    def _should_ignore_message(self, message):
        message_id = message.id
        return len(self.db.search(Query().message_id == message_id)) > 0

    async def _process_custom_emojis(self, emoji_id, emoji_name, message):
        for counter, i in enumerate(emoji_id):
            try:
                await message.guild.fetch_emoji(i)
            except discord.NotFound:
                log.debug(f"Custom emoji {emoji_name}:{emoji_id} not found.")
            except Exception as e:
                log.exception(f"An error occurred while fetching custom emoji {i}.", exc_info=e)
                return
            self.db.insert({'guild': message.guild.id, 'user': message.author.id, 'emoji': int(i), 'emoji_name': emoji_name[counter], 'message_id': message.id})

    async def _process_unicode_emojis(self, message):
        guild_config = self.confdb.get(Query().guild == message.guild.id)
        if guild_config and guild_config['unicode']:
            for i in emoji.distinct_emoji_list(message.content):
                emoji_name = emoji.demojize(i)
                self.db.insert({'guild': message.guild.id, 'user': message.author.id, 'emoji': i, 'emoji_name': emoji_name, 'message_id': message.id})