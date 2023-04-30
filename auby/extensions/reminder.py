# IMPORT DEPENDENCIES
import asyncio
import datetime
import os
import discord
from discord.utils import sleep_until
import hashlib

from tinydb import TinyDB, Query
import logging
log = logging.getLogger('auby')
query = Query()

#### NEW REMINDER SYSTEM ####
class Reminder():
    message_id: str
    user: discord.User
    channel: discord.TextChannel
    r_name: str
    end_time: datetime
    bot: discord.Client
    r_id: str
    task: asyncio.Future
    db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))

    def __init__(self):
        if self.r_id is None:
            data = str(self.message_id)+str(self.name)
            self.r_id = hashlib.blake2s(data.encode('utf-8'), digest_size=8).hexdigest()
        self.task = asyncio.ensure_future(self.await_reminder())
    
    async def await_reminder(self):
        reminder = {"user": self.user.id, "channel_id": self.channel.id, "message_id": self.message_id, "name": self.r_name, "end": self.end_time.timestamp(), "id": self.r_id}
        self.db.insert(reminder)

        await sleep_until(self.end_time)
        await self.send_reminder(reminder=reminder)

    async def send_reminder(self):
        log.debug(f"Sending reminder with ID {self.r_id}, named {self.r_name}")
        try:
            await self.channel.send(f"<@{self.user.id}>, <t:{int(self.end_time.timestamp())}:R>: {self.r_name}")
        except (discord.Forbidden, discord.NotFound):
            log.warning(f"Error sending reminder with ID {self.r_id} due to the bot not having permissions to send messages, or the channel doesn't exist. Attempting to send to DM with user.")
            dm = await self.user.create_dm()
            await dm.send(f"<@{self.user.id}>, Error sending reminder in requested channel, <t:{int(self.end_time.timestamp())}:R>: {self.r_name}")
        except Exception as e:
            log.exception(f"An error occurred while trying to send reminder with ID {self.r_id}.", exc_info=e)

    async def remove(self):
        self.db.remove(query.id == str(self.r_id))
        self.task.cancel()


#### REMINDER SYSTEM ####
# class Reminder():
#     def __init__(self, bot: discord.Client):
#         self.bot = bot
#         self.db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))
#         self.next_due = None
#         self.task = None

#         asyncio.ensure_future(self.start())

#     def in_range(self, timestamp, target):
#         return abs(timestamp - target) <= 1

#     async def send_reminder(self, r):
#         log.debug("Sending Reminder to User!")
#         try:
#             channel = await self.bot.fetch_channel(int(r['channel']))
#             await channel.send(f"<@{r['user']}>, <t:{int(r['end'])}:R>: {r['name']}")
#             self.db.remove(query.id == r['id'])
#         except (discord.Forbidden, discord.NotFound):
#             log.debug(f"Error sending reminder with ID {r['id']} due to the bot not having permissions to send messages, or the channel doesn't exist. Attempting to send to DM with user.")
#             user = await self.bot.fetch_user(int(r['user']))
#             dm_channel = await user.create_dm()
#             await dm_channel.send(f"<@{r['user']}> I couldn't send in the channel you requested, <t:{int(r['end'])}:R>: {r['name']}")
#             self.db.remove(query.id == r['id'])
#         except Exception as e:
#             log.exception(f"An error occurred while trying to send reminder with ID {r['id']}.", exc_info=e)

#     async def handle_old_reminders(self, db, now):
#         past_reminders = db.search(query.end < now.timestamp())
#         for r in past_reminders:
#             await self.send_reminder(r=r)

#     async def handle_new_reminders(self):
#         log.debug(f"There are {len(self.db)} reminders due.")
#         now = datetime.datetime.now(timezone.utc)
#         immediate_reminders = self.db.search(query.end <= now.timestamp())
#         for r in immediate_reminders:
#             await self.send_reminder(r=r)
#             self.db.remove(query.id == r['id'])
#         future_reminders = self.db.search(query.end > now.timestamp())
#         future_reminders.sort(key=lambda x: x["end"])
#         if future_reminders:
#             self.next_due = datetime.datetime.fromtimestamp(future_reminders[0]["end"], tz=pytz.utc)
#         for r in future_reminders:
#             if r["end"] <= now.timestamp():
#                 await self.send_reminder(r=r)
#                 self.db.remove(query.id == r['id'])
#             else:
#                 break
    
#     async def schedule_next_reminder(self):
#         if self.next_due is None:
#             return
#         delta = self.next_due - datetime.datetime.now(timezone.utc)
#         seconds_until_due = max(delta.total_seconds(), 0)
#         log.debug(f"Next reminder is due in {seconds_until_due} seconds.")
#         await asyncio.sleep(seconds_until_due)
#         self.task = asyncio.create_task(self.handle_new_reminders())
    
#     async def inject(self, reminder):
#         log.debug(f"Reminder {reminder['name']} added to queue.")
#         self.db.insert(reminder)
#         if self.task is not None and not self.task.done():
#             self.task.cancel()
#         await self.handle_new_reminders()
#         await self.schedule_next_reminder()

#     async def start(self):
#         await self.handle_old_reminders(db=self.db, now=datetime.datetime.now(timezone.utc))
#         await self.handle_new_reminders()
#         await self.schedule_next_reminder()

#     async def delete_reminder(self, id):
#         next_reminder = self.db.search(query.end > datetime.datetime.now(timezone.utc).timestamp())[0]
#         is_next_due = next_reminder['id'] == id if next_reminder else False
#         self.db.remove(query.id == str(id))
#         await self.handle_new_reminders()
#         if is_next_due:
#             if self.task is not None and not self.task.done():
#                 self.task.cancel()
#             await self.schedule_next_reminder()