# IMPORT DEPENDENCIES
import asyncio
import datetime
import os
import discord
import hashlib
import logging
import pytz
import calendar

from discord.utils import sleep_until
from discord.ext import commands
from discord import app_commands

import parsedatetime as pdt

from tinydb import TinyDB, Query, where

log = logging.getLogger('auby')
query = Query()

#### NEW REMINDER SYSTEM ####
class Reminder():
    ## DO NOT SPECIFY
    task: asyncio.Future
    db = TinyDB(os.path.join(os.getcwd(), "auby/data/remind_db.json"))

    def __init__(self, user: discord.User, channel: discord.TextChannel, r_name: str, end_time: datetime, bot: discord.Client, r_id: str):
        self.r_id = r_id
        self.user = user
        self.channel = channel
        self.r_name = r_name
        self.end_time = end_time
        self.r_id = r_id

        self.bot = bot

        log.info(f"Initializing Reminder {self.r_id}, due {self.end_time}")
        self.task = asyncio.ensure_future(self.await_reminder())
    
    async def await_reminder(self):
        reminder = {"user": self.user.id, "channel_id": self.channel.id, "name": self.r_name, "end": self.end_time.timestamp(), "id": self.r_id}
        if not self.db.contains(Query().id == self.r_id):
            self.db.insert(reminder)

        await sleep_until(self.end_time)
        await self.send_reminder()

    async def send_reminder(self):
        log.debug(f"Sending reminder with ID {self.r_id}, named {self.r_name}")
        try:
            log.info(f"Sending Reminder: {self.r_id}")
            await self.channel.send(f"<@{self.user.id}>, <t:{int(self.end_time.timestamp())}:R>: {self.r_name}")
            del self.bot.reminders[self.r_id]
            self.db.remove(query['id'] == self.r_id)
        except (discord.Forbidden, discord.NotFound):
            log.warning(f"Error sending reminder with ID {self.r_id} due to the bot not having permissions to send messages, or the channel doesn't exist. Attempting to send to DM with user.")
            dm = await self.user.create_dm()
            await dm.send(f"<@{self.user.id}>, Error sending reminder in requested channel, <t:{int(self.end_time.timestamp())}:R>: {self.r_name}")
        except Exception as e:
            log.exception(f"An error occurred while trying to send reminder with ID {self.r_id}.", exc_info=e)

    async def stop(self):
        log.info(f"Stopping reminder {self.r_id}, named {self.r_name}")
        self.task.cancel()

class ReminderTools():
    def __init__(self, bot=discord.Client):
        self.bot = bot
        self.rdb: TinyDB = bot.remind_conf

    async def load(self):
        self.bot.reminders = {}
        if len(self.rdb.all()) > 0:
            log.info(f"Loading {len(self.rdb.all())} reminders.")
            for row in self.rdb.all():
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
                    user=user,
                    channel=channel,
                    r_name=r_name,
                    end_time=end_time,
                    r_id=r_id,
                    bot=bot
                )

                self.bot.reminders[r_id] = _reminder
        else:
            log.info("No reminders to load.")

    async def stopall(self):
        loaded_reminders = dict(self.bot.reminders)
        for rem in loaded_reminders.values():
            await rem.stop()

class ReminderCmds(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.remind_db = TinyDB(os.path.join(os.getcwd(), "auby/data/remind_db.json"))

    @app_commands.command(name="remind", description="BETA: Reminds you something.")
    @app_commands.describe(
        name="What do you want me to remind you for? (ex: pet a fox)",
        date="When do you want to be reminded? (most date formats work)"
    )
    async def remind(self, interaction: discord.Interaction, name: str, date: str):
        cal = pdt.Calendar()
        now = datetime.datetime.now(pytz.utc)
        start_date = interaction.created_at
        end_date = cal.parseDT(datetimeString=date,
                               sourceTime=now, tzinfo=pytz.utc)[0]

        if end_date > start_date:
            data = str(interaction.user.id)+str(name)+str(end_date.timestamp())
            r_id = hashlib.blake2s(data.encode('utf-8'), digest_size=8).hexdigest()

            _reminder = Reminder(
                user=interaction.user,
                channel=interaction.channel,
                r_name=name,
                end_time=end_date,
                r_id=r_id,
                bot=self.bot
            )

            self.bot.reminders[r_id] = _reminder
            await interaction.response.send_message(f"<@{interaction.user.id}>, I will remind you <t:{int(calendar.timegm(end_date.utctimetuple()))}:R>: {name}")
        else:
            await interaction.response.send_message("That time is not valid!", ephemeral=True)

    @app_commands.command(name="remindlist", description="BETA: See a list of the reminders you have set.")
    async def remindlist(self, interaction: discord.Interaction):
        embed = discord.Embed(
            color=discord.Color.orange(),
            description="A list of your set reminders.",
            title=f"Reminder list for {interaction.user.name}"
        )
        r_list = self.remind_db.search(where('user') == interaction.user.id)
        r_list.sort(key=lambda r: r["end"], reverse=False)

        body1 = "\n".join(str(r["id"]) for r in r_list)
        body2 = "\n".join(r["name"] for r in r_list)
        body3 = "\n".join(f"<t:{int(r['end'])}:R>" for r in r_list)

        embed.add_field(name="Reminder ID", value=body1)
        embed.insert_field_at(1, name="Name", value=body2)
        embed.insert_field_at(2, name="Due Date", value=body3)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="deletereminder", description="BETA: Delete a reminder you have set.")
    @app_commands.describe(
        id="What is the ID of the reminder?"
    )
    async def deletereminder(self, interaction: discord.Interaction, id: str):
        await interaction.response.send_message(f"I have deleted your reminder with ID: ``{id}``.", ephemeral=True)
        self.bot.reminders[id].task.cancel()
        del self.bot.reminders[id]
        self.remind_db.remove(query.id == str(id))


async def setup(bot: commands.Bot):
    # sourcery skip: instance-method-first-arg-name
    await bot.add_cog(ReminderCmds(bot=bot))
    bot.remindertools = ReminderTools(bot=bot)
    await bot.remindertools.load()

async def teardown(bot: commands.Bot):
    log.info(f"Unloading Reminders Extension")
    await bot.remindertools.stopall()


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