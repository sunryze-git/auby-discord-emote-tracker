# IMPORT DEPENDENCIES
import asyncio
import datetime
import pytz
import os
import discord

from resources import log

from datetime import timezone
from tinydb import TinyDB, Query, where

query = Query()

#### REMINDER SYSTEM ####
class Reminder():
    def __init__(self, bot):
        self.bot = bot
        self.db = TinyDB(os.path.join(os.getcwd(), "remind_db.json"))
        self.next_due = None
        self.task = None

        asyncio.ensure_future(self.start())

    def in_range(self, timestamp, target):
        return abs(timestamp - target) <= 1

    async def send_reminder(self, r):
        log.debug("Sending Reminder to User!")
        channel = await self.bot.fetch_channel(int(r['channel']))
        try:
            await channel.send(f"<@{r['user']}>, <t:{int(r['end'])}:R>: {r['name']}")
            self.db.remove(query.id == r['id'])
        except discord.Forbidden:
            log.debug(f"Error sending reminder with ID {r['id']} due to the bot not having permissions to send messages. (TODO: Redirect reminder to the users DMs.)")
        except Exception as e:
            log.exception(f"An error occurred while trying to send reminder with ID {r['id']}.", exc_info=e)

    async def handle_old_reminders(self, db, now):
        past_reminders = db.search(query.end < now.timestamp())
        for r in past_reminders:
            await self.send_reminder(r=r)

    async def handle_new_reminders(self):
        log.debug(f"There are {len(self.db)} reminders due.")
        now = datetime.datetime.now(timezone.utc)
        immediate_reminders = self.db.search(query.end <= now.timestamp())
        for r in immediate_reminders:
            await self.send_reminder(r=r)
            self.db.remove(query.id == r['id'])
        future_reminders = self.db.search(query.end > now.timestamp())
        future_reminders.sort(key=lambda x: x["end"])
        if future_reminders:
            self.next_due = datetime.datetime.fromtimestamp(future_reminders[0]["end"], tz=pytz.utc)
        for r in future_reminders:
            if r["end"] <= now.timestamp():
                await self.send_reminder(r=r)
                self.db.remove(query.id == r['id'])
            else:
                break
    
    async def schedule_next_reminder(self):
        if self.next_due is None:
            return
        delta = self.next_due - datetime.datetime.now(timezone.utc)
        seconds_until_due = max(delta.total_seconds(), 0)
        log.debug(f"Next reminder is due in {seconds_until_due} seconds.")
        await asyncio.sleep(seconds_until_due)
        self.task = asyncio.create_task(self.handle_new_reminders())
    
    async def inject(self, reminder):
        log.debug(f"Reminder {reminder['name']} added to queue.")
        self.db.insert(reminder)
        if self.task is not None and not self.task.done():
            self.task.cancel()
        await self.handle_new_reminders()
        await self.schedule_next_reminder()

    async def start(self):
        await self.handle_old_reminders(db=self.db, now=datetime.datetime.now(timezone.utc))
        await self.handle_new_reminders()
        await self.schedule_next_reminder()

    async def delete_reminder(self, id):
        self.db.remove(query.id == str(id))
        asyncio.ensure_future(self.start())