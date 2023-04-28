### IMPORT LIBRARIES
import discord
import os
import datetime

from tinydb import TinyDB

from auby.extensions.reminder import Reminder

class LoadReminders():
    def __init__(self, bot=discord.Client, db=None):
        self.bot = bot
        self.rdb = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))

    async def load(self):
        async with self.rdb() as stored_reminders:
            for row in stored_reminders:
                message_id: int = row['message_id']
                try:
                    user: discord.User = await self.bot.fetch_user(row['user'])
                except discord.NotFound:
                    user: None = None
                try:
                    channel: discord.TextChannel = await self.bot.fetch_channel(row['channel_id'])
                except discord.NotFound:
                    channel: None = None
                r_name = row['name']
                end_time = datetime.datetime.fromtimestamp(int(row['end']))
                r_id = row['id']
                bot = self.bot

                _reminder = Reminder(
                    message_id=message_id,
                    user=user,
                    channel=channel,
                    r_name=r_name,
                    end_time=end_time,
                    r_id=r_id,
                    bot=bot
                )