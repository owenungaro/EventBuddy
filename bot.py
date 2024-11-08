import os
import discord
import asyncio #More time
from datetime import datetime, timedelta #Time  
from dotenv import load_dotenv #Enviromental Variable
import pytz #Timezone
import json #Stores event data
import uuid #Unique IDs
import sys #For restarting

import pdb

#TODO
#Remake repo to get rid of .vscode and __pycashe_
#Change the repeat announcement when an repeatable event passes (it makes a new ID from the old ID system)
#Update list announcements, it should also show repeat and skip(only if repeat is active)
#Make randomized id for the end of the name
#Finish create task 
#Fix space in front of the first event in listevents
#Make editannouncement parameters, non mandatory
#Make all commands have editing. Processing your request will be edited to the actual output

#Recreate repo at blueprint github
#Change announcement times: 1hr, 30m, morning: 9 AM


load_dotenv()

TOKEN = os.environ.get("TOKEN_KEY")
JSON_FILE_PATH = os.environ.get("JSON_FILE", "events.json")
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")

intents = discord.Intents.default()
bot = discord.Bot(intents = intents)

events = {}
scheduled_tasks = {}
def load_events():
    print("starting load") 
    try:
        with open(JSON_FILE_PATH, "r") as f:
            loaded_events = json.load(f)
            #event_details takes in dictionary of the details
            for event_id, event_details in loaded_events.items():
                #Converts iso formatted date back into datetime object with timezone
                event_details["time"] = datetime.fromisoformat(event_details["time"]).replace(tzinfo=pytz.timezone(TIMEZONE))
            print("finished load")
            return loaded_events
    except(FileNotFoundError, json.JSONDecodeError):
        print ("Error Decoding Saved Events JSON")
        return {}
    

events = load_events()


def save_events():
    print(f"Saving, {events.keys()}")
    saved_events = {
        event_name: {
            "time": event_details["time"].isoformat(),
            "channel": event_details["channel"],
            "user": event_details["user"],
            "message": event_details["message"],
            "roles": event_details.get("roles", []),
            "repeat": event_details.get("repeat", False),
            "skip": event_details.get("skip", False)
        }
        for event_name, event_details in events.items()

    }
    
    try:
        with open(JSON_FILE_PATH, "w+") as f:
            json.dump(saved_events, f, indent=4)
    except Exception as e:
        print(f"Error saving events: {e}") 


def calculate_reminders(event_time):
    return {
        "first_announcement": event_time-timedelta(minutes=3),
        "second_announcement": event_time-timedelta(minutes=2),
        "third_announcement": event_time-timedelta(minutes=1)
    }


async def send_reminder(channel, message, eventID):
    if eventID in events:
        await channel.send(message)
    else:
        print(f"Event with id {eventID} was called into send_reminder but doesn't exist.")


def schedule_reminder(event_name, event_time, channel, message, role_ids, repeat):
    cancel_existing_reminders(event_name)

    reminders = calculate_reminders(event_time)
    now = datetime.now(pytz.timezone(TIMEZONE))

    if event_time < now:
        events[event_name]["time"] = event_time + timedelta(weeks=1)
        events[event_name]["skip"] = False
        save_events()
        asyncio.run(channel.send(f"Event **{event_name}** is canceled for this week. It will occur next on {events[event_name]['time'].strftime('%Y-%m-%d %H:%M %Z')}."))
        return

    role_mentions = " "
    formatted_role_mentions = []
    for role_id in role_ids:
        mention_string = f"<@&{role_id}>"
        formatted_role_mentions.append(mention_string)
    role_mentions = ", ".join(formatted_role_mentions)

    asyncLoop = asyncio.get_event_loop()
    if not asyncLoop.is_running():
        asyncLoop.run_forever()

    #Two hour announcement
    first_announcement = (reminders['first_announcement'] - now).total_seconds()
    if first_announcement > 0:
        asyncLoop.call_later(first_announcement, lambda: asyncio.create_task(send_reminder(channel, f"{message} {role_mentions}", event_name)))

    # Twenty minute announcement
    second_announcement = (reminders['second_announcement'] - now).total_seconds()
    if second_announcement > 0:
        asyncLoop.call_later(second_announcement, lambda: asyncio.create_task(send_reminder(channel, f"{message} {role_mentions}", event_name)))

    # Five minute announcement
    third_announcement = (reminders['third_announcement'] - now).total_seconds()
    if third_announcement > 0:
        asyncLoop.call_later(third_announcement, lambda: asyncio.create_task(send_reminder(channel, f"{message} {role_mentions}", event_name)))

    if repeat:
        asyncLoop.call_later(third_announcement, lambda: reschedule_announcement(event_name, event_time))

    

def reschedule_announcement(event_name, event_time):
    next_event_time = event_time + timedelta(weeks=1) #Gets the time for next week
    events[event_name]["time"] = next_event_time

    events[event_name]["skip"] = False

    save_events()
    
    print(f"Repeating event scheduled for {next_event_time.strftime('%Y-%m-%d %H:%M %Z')}")

    channel = bot.get_channel(events[event_name]["channel"])
    if channel:
        schedule_reminder(event_name, event_time, channel, events[event_name]["message"], events[event_name]["roles"], events[event_name]["repeat"])


# Add this function to cancel existing reminders for an event
def cancel_existing_reminders(event_name):
    for task_key in list(scheduled_tasks.keys()):
        if task_key.startswith(event_name):
            scheduled_tasks[task_key].cancel()
            del scheduled_tasks[task_key]


@bot.slash_command(name="makeannouncement", description="Schedule an event and get reminders periodically before event occurs.")
async def makeannouncement(ctx, name: str, day: int, month: int, time: str, message: str, roles: str = "none", channel: discord.TextChannel = None, repeat: bool = False):
    #print(events)
    await ctx.respond("Processing your request...")
    try:
        timezone = pytz.timezone(TIMEZONE)
        now = datetime.now(timezone)
        hour, minute = map(int, time.split(":"))
        event_time = timezone.localize(datetime(year=now.year, month=month, day=day, hour=hour, minute=minute))

        if event_time < now:
            await ctx.send("Event time has already passed.")
            return
        

        #Stores all roles/mentions
        role_ids = [role_id[3:-1] for role_id in roles.split() if role_id.startswith("<@&") and role_id.endswith(">")] if roles != "none" else []
        target_channel = channel if channel else ctx.channel

        events[name] = {
            "time": event_time,
            "channel": target_channel.id,
            "user": ctx.user.name,
            "message": message,
            "roles": role_ids,
            "repeat": repeat,
            "skip": False
        }

        save_events()
        
        await ctx.send(f"Event **{name}** scheduled for *{event_time.strftime('%Y-%m-%d %H:%M %Z')}*.")
        
        schedule_reminder(name, event_time, ctx.channel, message, role_ids, repeat)

    except ValueError:
        await ctx.send(
            "Invalid input! Please ensure you are using the correct format:\n"
            "/makeannouncement name day month hour:minute message roles(optional) channel(optional) repeat(optional)\n"
            "For example: /makeannouncement Meeting 25 12 14:30 'Team update' @role #general True.")


@bot.slash_command(description="Deletes event.")
async def deleteannouncement(ctx, event_name: str):
    await ctx.respond("Processing your request...")
    if event_name in events:
        del events[event_name]
        save_events()
        await ctx.send(f"Event **{event_name}** has been deleted.")
    else:
        await ctx.send(f"Event **{event_name}** does not exist.")


@bot.slash_command(description="Edits event.")
async def editannouncement(ctx, name: str, day: int = None, month: int = None, time: str = None, message: str = None, roles: str = "none", channel_id: str = None, repeat: bool = None):
    await ctx.respond("Processing your request...")

    if name in events:
        try:
            # Cancel existing reminders for the event being edited
            cancel_existing_reminders(name)

            # Proceed with event editing
            if day is not None and month is not None and time is not None:
                hour, minute = map(int, time.split(":"))
                timezone = pytz.timezone(TIMEZONE)
                now = datetime.now(timezone)
                event_time = timezone.localize(datetime(year=now.year, month=month, day=day, hour=hour, minute=minute))

                if event_time < now:
                    await ctx.send("Updated event time has already passed.")
                    return

                events[name]["time"] = event_time

            if message is not None:
                events[name]["message"] = message

            role_ids = [role_id[3:-1] for role_id in roles.split() if role_id.startswith("<@&") and role_id.endswith(">")] if roles != "none" else []
            events[name]["roles"] = role_ids

            if channel_id:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    events[name]["channel"] = channel.id
                else:
                    await ctx.send(f"Channel with ID {channel_id} does not exist. Defaulting to previous channel.")

            if repeat is not None:
                events[name]["repeat"] = repeat

            # Reschedule the reminder after updating event details
            schedule_reminder(name, events[name]["time"], bot.get_channel(events[name]["channel"]), events[name]["message"], events[name]["roles"], events[name].get("repeat", False))

            updated_time = events[name].get("time")
            if updated_time:
                await ctx.send(f"Event **{name}** has been updated to *{updated_time.strftime('%Y-%m-%d %H:%M %Z')}*")
            else:
                await ctx.send(f"Event **{name}** has been updated.")
            
            save_events()

        except ValueError:
            await ctx.send(
                "Invalid input! Please use the correct format:\n"
                "`/editannouncement name day month hour:minute message roles channel repeat`\n"
                "- Time should be in 24-hour military time (e.g., `14:30` for 2:30 PM).\n"
                "- Ensure the `roles` field is correctly formatted if you are including roles."
            )
    else:
        await ctx.send(f"Event {name} does not exist")



@bot.slash_command(description="Lists all upcoming events.")
async def listannouncements(ctx):
    await ctx.respond("Processing your request...")
    if not events:
        await ctx.send("There are no scheduled events.")
        return
    
    cleanup_past_events()
    event_list = []
    for event_name, event_details in events.items():
        event_time = event_details["time"].strftime('%Y-%m-%d %H:%M %Z')
        custom_message = event_details.get("message", "No Message Found")
        channel_id = event_details.get("channel")
        channel = bot.get_channel(channel_id)

        channel_name = channel.name if channel else "Unknown Channel"
        
        roles = []
        for role_id in event_details.get("roles", []):
            role_mention = f"<@&{role_id}>"
            roles.append(role_mention)
        
        roles_string = " ,".join(roles)

        event_list.append(f"Event ID: **{event_name}**, Time: {event_time}, Channel: {channel_name}, User: {event_details['user']}, Message: '{custom_message}', Roles: {roles_string}.")

    message = "\n".join(event_list)
    await ctx.send(f"Scheduled Events:\n {message}")


@bot.slash_command(description="Cancels schedueled announcement for a week")
async def cancelannouncement(ctx, name: str):
    await ctx.respond("Processing your request...")
    if name in events:
        try:
            if events[name]["repeat"] == False:
                await ctx.send(f"Event **{name}** is not a repeating event.")
                return
            
            if events[name]["skip"] == True:
                await ctx.send(f"Event **{name}** has already been canceled for this week.")
                return


            
            events[name]["skip"] = True
            save_events()
            await ctx.send(f"Event **{name}** will be skipped for this week.")

        except KeyError as error:
            await ctx.send(f"Error: {error}")
        except Exception as e:
            await ctx.send(f"Unexpected error: {e}")
    else:
        await ctx.send(f"Event **{name}** does not exist")

@bot.slash_command(name="time", description="Get the current time in the specified timezone.")
async def time(ctx, timezone: str = TIMEZONE):
    await ctx.respond("Fetching current time...")
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        current_time = now.strftime('%Y-%m-%d %H:%M %Z')
        
        await ctx.send(f"The current time in {timezone} is {current_time}.")
    except pytz.UnknownTimeZoneError:
        await ctx.send(f"Error: '{timezone}' is not a recognized timezone. Please provide a valid timezone.")


@bot.event
async def on_ready():
    print(f'{bot.user} is now running.')

    # asyncio.loop
    asyncio.create_task(periodic_cleanup())

    for event_id, event_details in events.items():
        event_time = event_details["time"]
        now = datetime.now(pytz.timezone(TIMEZONE))

        # Check if the event time has already passed for this week
        if event_time < now:
            # Update event time to the next week
            events[event_id]["time"] = event_time + timedelta(weeks=1)
            save_events()  # Save the updated event details
            print(f"Event {event_id} has passed. Rescheduled to {events[event_id]['time'].strftime('%Y-%m-%d %H:%M %Z')}.")
            continue  # Skip to the next event

        # Proceed to schedule reminders for future events
        channel = bot.get_channel(event_details["channel"])
        if channel: 
            schedule_reminder(event_id, event_time, channel, event_details["message"], event_details["roles"], event_details.get("repeat", False))
        else:
            print(f"Channel with ID {event_details['channel']} not found for event {event_id}.")


def cleanup_past_events():
    now = datetime.now(pytz.timezone(TIMEZONE))
    events_to_remove = []
    
    for event_id, event_details in events.items():
        if event_details["time"] < now:
            events_to_remove.append(event_id)

    for event_id in events_to_remove:
        del events[event_id]
        print(f"Deleted past event {event_id}.")


async def periodic_cleanup():
    while True:
        cleanup_past_events()
        save_events()
        await asyncio.sleep(1800)  #Wait for 30 minutes



@bot.command(description="Gives bot ping.")
async def ping(ctx):
    await ctx.respond(f"Latency is {bot.latency}")


bot.run(TOKEN)
