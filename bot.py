import os
import discord
import asyncio #More time
from datetime import datetime, timedelta #Time  
from dotenv import load_dotenv #Enviromental Variable
import pytz #Timezone
import json #Stores event data
import uuid #Unique IDs

#Invite Link
#https://discord.com/oauth2/authorize?client_id=1289305831489147063&scope=bot+applications.commands&permissions=268435456


load_dotenv()

TOKEN = os.environ.get("TOKEN_KEY")
JSON_FILE_PATH = "events.json"

intents = discord.Intents.default()
bot = discord.Bot(intents = intents)

events = {}
def load_events():
    print("starting load") 
    try:
        with open(JSON_FILE_PATH, "r") as f:
            loaded_events = json.load(f)
            #event_details takes in dictionary of the details
            for event_id, event_details in loaded_events.items():
                #Converts iso formatted date back into datetime object with timezone
                event_details["time"] = datetime.fromisoformat(event_details["time"]).replace(tzinfo=pytz.timezone("America/New_York"))
            print("finished load")
            return loaded_events
    except(FileNotFoundError, json.JSONDecodeError):
        print ("Error Decoding Saved Events JSON")
        return {}
    

events = load_events()


def save_events():
    print(f"Saving, {events}")
    saved_events = {
        event_id: {
            "time": event_details["time"].isoformat(),
            "channel": event_details["channel"],
            "user": event_details["user"],
            "message": event_details["message"],
            "roles": event_details.get("roles", []),
            "repeat": event_details.get("repeat", False)
        }
        for event_id, event_details in events.items()

    }
    
    try:
        with open(JSON_FILE_PATH, "w+") as f:
            json.dump(saved_events, f, indent=4)
    except Exception as e:
        print(f"Error saving events: {e}") 


def calculate_reminders(event_time):
    return {
        "two_hours": event_time-timedelta(hours=2),
        "twenty_minutes": event_time-timedelta(minutes=20),
        "five_minutes": event_time-timedelta(minutes=5)
    }

async def send_reminder(channel, message):
    await channel.send(message)


async def schedule_reminder(event_time, channel, message, role_ids, repeat):
    reminders = calculate_reminders(event_time)

    now = datetime.now(pytz.timezone('America/New_York'))

    role_mentions = " "
    formatted_role_mentions = []
    for role_id in role_ids:
        mention_string = f"<@&{role_id}>"
        formatted_role_mentions.append(mention_string)
    role_mentions = ", ".join(formatted_role_mentions)

    #Two hour announcement
    two_hour_announcement = (reminders['two_hours'] - now).total_seconds()
    if two_hour_announcement > 0:
        await asyncio.sleep(two_hour_announcement)
        await send_reminder(channel, f"{message} {role_mentions}")

    #Twenty minute announcement
    twenty_minute_announcement = (reminders['twenty_minutes'] - now).total_seconds()
    if twenty_minute_announcement > 0:
        await asyncio.sleep(twenty_minute_announcement)
        await send_reminder(channel, f"{message} {role_mentions}")

    #Five minute announcement
    five_minute_announcement = (reminders['five_minutes'] - now).total_seconds()
    if five_minute_announcement > 0:
        await asyncio.sleep(five_minute_announcement)
        await send_reminder(channel, f"{message} {role_mentions}")

    if repeat:
        next_event_time = event_time + timedelta(weeks=1) #Gets the time for next week
        event_id = f"{channel.id}_{next_event_time.timestamp()}_{uuid.uuid4()}" #Makes new id for event

        events[event_id] = {
            "time": next_event_time,
            "channel": channel.id,
            "user": "bot",
            "message": message,
            "roles": role_ids,
            "repeat": repeat
        }
        save_events()
        
        print(f"Repeating event scheduled for {next_event_time.strftime('%Y-%m-%d %H:%M %Z')}") ##FIX

        


@bot.slash_command(name="announce", description="Schedule an event and get reminders periodically before event occurs.")
async def announce(ctx, day: int, month: int, time: str, message: str, roles: str, channel: discord.TextChannel = None, repeat: bool = False):
    #print(events)
    await ctx.respond("Processing your request...")
    try:
        hour, minute = map(int, time.split(":"))
        timezone = pytz.timezone('America/New_York')
        now = datetime.now(timezone)
        
        event_time = timezone.localize(datetime(year=now.year, month=month, day=day, hour=hour, minute=minute))

        if event_time < now:
            await ctx.send("Event time has already passed.")
            return
        
        event_id = f"{ctx.user.id}_{event_time.timestamp()}_{uuid.uuid4()}"

        #Stores all roles/mentions
        role_ids = []
        role_mentions = roles.split(",")
        for role in role_mentions:
            stripped_role = role.strip()
            if stripped_role and stripped_role.startswith("<@&") and stripped_role.endswith(">"):
                role_ids.append(stripped_role[3:-1])

        target_channel = channel if channel else ctx.channel

        events[event_id] = {
            "time": event_time,
            "channel": target_channel.id,   
            "user": ctx.user.name,
            "message": message,
            "roles": role_ids,
            "repeat": repeat
        }

        save_events()
        
        await ctx.send(f"Event **[{event_id}]** scheduled for *{event_time.strftime('%Y-%m-%d %H:%M %Z')}*.")
        
        await schedule_reminder(event_time, ctx.channel, message, role_ids, repeat)

    except ValueError:
        await ctx.send("Invalid input. Please use the format: `/announce day month hour:minute`")
    

@bot.slash_command(description="Deletes event.")
async def deleteannouncement(ctx, event_id: str):
    await ctx.respond("Processing your request...")
    if event_id in events:
        del events[event_id]
        save_events()
        await ctx.send(f"Event **{event_id}** has been deleted.")
    else:
        await ctx.send(f"Event **{event_id}** does not exist.")


@bot.slash_command(description="Edits event.")
async def editannouncement(ctx, event_id: str, day: int, month: int, time: str, message: str, roles: str="none", channel_id: str = None, repeat: bool = False):
    await ctx.respond("Processing your request...")

    if event_id in events:
        try:
            hour, minute = map(int, time.split(":"))
            timezone = pytz.timezone("America/New_York")
            now = datetime.now(timezone)
            event_time = timezone.localize(datetime(year=now.year, month=month, day=day, hour=hour, minute=minute))

            if event_time < now:
                await ctx.send("Updated event time has already passed.")
                return

            events[event_id]["time"] = event_time
            events[event_id]["message"] = message
            events[event_id]["repeat"] = repeat

            if roles:
                role_ids = []
                role_mentions = roles.split(",")
                for role in role_mentions:
                    stripped_role = role.strip()
                    if stripped_role.startswith("<@&") and stripped_role.endswith(">"):
                        role_ids.append(stripped_role[3:-1])  # Extract role ID from <@&roleID>
                events[event_id]["roles"] = role_ids


            if channel_id:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    events[event_id]["channel"] = channel.id
                else:
                    await ctx.send(f"Channel with ID {channel_id} does not exist. Defaulting to previous channel.")


            await ctx.send(f"Event **{event_id}** has been updated to *{event_time.strftime('%Y-%m-%d %H:%M %Z')}*")
        except:
            await ctx.send(f"Invalid input. Please use the format: `hour:minute` in military time.")

        save_events()
    else:
        await ctx.send(f"Event {event_id} does not exist")


@bot.slash_command(description="Lists all upcoming events.")
async def listannouncements(ctx):
    await ctx.respond("Processing your request...")
    if not events:
        await ctx.send("There are no scheduled events.")
        return
    
    event_list = []
    for event_id, event_details in events.items():
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

        event_list.append(f"Event ID: **{event_id}**, Time: {event_time}, Channel: {channel_name}, User: {event_details['user']}, Message: '{custom_message}', Roles: {roles_string}.")

    message = "\n".join(event_list)
    await ctx.send(f"Scheduled Events:\n {message}")


@bot.event
async def on_ready():
    print(f'{bot.user} is now running.')

    asyncio.create_task(periodic_cleanup())

    for event_id, event_details in events.items():
        event_time = event_details["time"]
        now = datetime.now(pytz.timezone('America/New_York'))

        if event_time > now:
            channel = bot.get_channel(event_details["channel"])
            role_ids = event_details.get("roles", [])
            asyncio.create_task(schedule_reminder(event_time, channel, event_details["message"], role_ids, event_details.get("repeat", False)))
        else:
            print(f"Event {event_id} has passed.")


async def cleanup_past_events():
    now = datetime.now(pytz.timezone('America/New_York'))
    events_to_remove = []
    
    for event_id, event_details in events.items():
        if event_details["time"] < now:
            events_to_remove.append(event_id)

    for event_id in events_to_remove:
        del events[event_id]
        print(f"Deleted past event {event_id}.")

    save_events()


async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  #Wait for one hour
        await cleanup_past_events()



@bot.command(description="Gives bot ping.")
async def ping(ctx):
    await ctx.respond(f"Latency is {bot.latency}")


@bot.command(description="Gives time.")
async def time(ctx):
    await ctx.respond(datetime.now(pytz.timezone('America/New_York')))


bot.run(TOKEN)