import discord
from discord.ext import commands, tasks
import asyncio
import logging
from dotenv import load_dotenv
import json
import math
import random
from datetime import datetime, timedelta
import os
from database import *
from tables import *

with open("wiki_queries.json", "r", encoding="utf-8") as file:
    wiki_queries = json.load(file)

with open("loomian_data.json", "r", encoding="utf-8") as file:
    loomian_data = json.load(file)

loomian_names = {
    data["id"]: name
    for rarity in loomian_data.values()
    for name, data in rarity.items()
}

loomian_rarities = {
    name: rarity
    for rarity, loomians in loomian_data.items()
    for name in loomians
}

Base.metadata.create_all(engine)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

OWNER_ID = 613290473620242453

MIN_MESSAGES = 15
MAX_MESSAGES = 25

VOICE_XP = 20
MESSAGE_XP = 50
MESSAGE_XP_COOLDOWN = 5

MESSAGE_COOLDOWN = 3
HINT_COOLDOWN = 10

WEATHERS = {
    "Clear": ":sunny:",
    "Heavy Rainfall": ":cloud_rain:",
    "Strong Gusts": ":dash:",
    "Dense Fog": ":fog:",
    "Smoldering Heat": ":fire:",
    "Severe Thunderstorm": ":cloud_lightning:",
    "Blistering Blizzard": ":cloud_snow:"
}

message_counts = {}
last_counted_messages = {}
last_message_xp = {}
next_spawn_intervals = {}
current_spawns = {}
last_hints = {}
rarities = {
    "Common": 60,
    "Uncommon": 35.8,
    "Rare": 2,
    "Very_Rare": 1.3,
    "Roamer": 0.8
}

def admin_or_owner():
    async def predicate(ctx):
        return (
            ctx.author.id == OWNER_ID or
            ctx.author.guild_permissions.administrator
        )
    return commands.check(predicate)

bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=intents,
    help_command=None
)

def get_time():
    current_minute = datetime.now().minute

    if current_minute // 15 % 2 == 0:
        current_time = "day"
    else:
        current_time = "night"

    minutes_until_change = 15 - (current_minute % 15)

    return current_time, minutes_until_change

def get_weather():
    now = datetime.now()

    weather_period = (
        now.year,
        now.month,
        now.day,
        now.hour,
        now.minute // 30
    )

    random_weather = random.Random(str(weather_period))

    current_weather = random_weather.choice(list(WEATHERS))
    emoji = WEATHERS[current_weather]

    minutes_until_change = 30 - (now.minute % 30)

    return current_weather, emoji, minutes_until_change

def experience_gain(session, loomian, experience):
    if loomian.level >= 50:
        loomian.level = 50
        loomian.experience = 0
        return 0

    loomian.experience += experience
    old_level = loomian.level
    xp_req = 500 + loomian.level * 90

    while loomian.experience >= xp_req:
        loomian.experience -= xp_req
        loomian.level += 1
        xp_req = 500 + loomian.level * 90

    levels_gained = loomian.level - old_level

    return levels_gained

def check_evolution(loomian):
    species_name = loomian_names[loomian.species_id]

    current_time, _ = get_time()
    current_weather, _, _ = get_weather()

    for rarity, loomians in loomian_data.items():
        if species_name not in loomians:
            continue

        data = loomians[species_name]
        requirements = data["requirements"]

        if not isinstance(requirements, list):
            return None

        for requirement in requirements:
            if "evolution" not in requirement:
                continue

            if "level" not in requirement:
                continue

            evolution = requirement["evolution"]
            level = requirement["level"]

            if loomian.item == "Drop of Youth":
                continue

            if loomian.level < level:
                continue            

            if "time" in requirement:
                if current_time != requirement["time"]:
                    continue

            if "weather" in requirement:
                if current_weather != requirement["weather"]:
                    continue

            if "item" in requirement:
                if loomian.item != requirement["item"]:
                    continue

            if "move" in requirement:
                continue

            if "condition" in requirement:
                continue

            return evolution

        return None

    return None

def evolve_loomian(loomian, new_species_id):
    old_name = loomian_names[loomian.species_id]
    new_name = loomian_names[new_species_id]

    loomian.species_id = new_species_id

    return old_name, new_name
  
@bot.event
async def on_ready():
    if not voice_xp_gain.is_running():
        voice_xp_gain.start()

    print(f"Logged in as {bot.user}")
    print(f"{bot.user.name} is ready and running.")

@tasks.loop(minutes=1)
async def voice_xp_gain():
    for guild in bot.guilds:

        for member in guild.members:

            if member.bot:
                continue

            if member.voice is None:
                continue

            with Session() as session:
                user = session.query(User).filter_by(
                    discord_id=str(member.id)
                ).first()

                if user is None:
                    continue

                if user.selected_loomian_id is None:
                    continue

                loomian = session.query(Loomian).filter_by(
                    id=user.selected_loomian_id
                ).first()

                if loomian is None:
                    continue

                levels_gained = experience_gain(
                    session,
                    loomian,
                    VOICE_XP
                )

                old_name = loomian_names[loomian.species_id]
                new_species_id = None
                new_name = None

                if levels_gained > 0:
                    new_species_id = check_evolution(loomian)

                    if new_species_id:
                        old_name, new_name = evolve_loomian(
                            loomian,
                            new_species_id
                        )

                session.commit()

                if levels_gained > 0:
                    server = session.query(Server).filter_by(
                        server_id=guild.id
                    ).first()

                    if server is not None:
                        channel = bot.get_channel(
                            server.spawn_channel_id
                        )

                        if channel is not None:

                            if new_species_id:
                                await channel.send(
                                    f"{member.mention}'s {old_name} "
                                    f"evolved into {new_name} at "
                                    f"level {loomian.level}! :tada:",
                                    silent=True
                                )

                            else:
                                await channel.send(
                                    f"{member.mention}'s {old_name} "
                                    f"reached level {loomian.level}!",
                                    silent=True
                                )

@bot.event
async def on_message(message):
    global message_counts, next_spawn_intervals, current_spawns, last_counted_messages

    if message.author == bot.user:
        return

    if message.author.bot:
        return

    if message.guild is None:
        return

    server_id = message.guild.id
    user_id = str(message.author.id)

    now = datetime.now()

    # ========== XP GAIN ==========

    if user_id not in last_message_xp or (now - last_message_xp[user_id]).total_seconds() >= MESSAGE_XP_COOLDOWN:
        with Session() as session:
            user = session.query(User).filter_by(
                discord_id=user_id
            ).first()

            if user is not None and user.selected_loomian_id is not None:
                loomian = session.query(Loomian).filter_by(
                    id=user.selected_loomian_id
                ).first()

                if loomian is not None:
                    levels_gained = experience_gain(
                        session,
                        loomian,
                        MESSAGE_XP
                    )

                session.commit()

                if levels_gained > 0:
                    new_species_id = check_evolution(loomian)

                    if new_species_id:
                        old_name, new_name = evolve_loomian(
                            loomian,
                            new_species_id
                        )

                        await message.channel.send(
                            f"{message.author.mention}."
                            f"{old_name} has reached level {loomian.level}!"
                            f":tada: Your {old_name} evolved into {new_name}!"
                        )

                    else:
                        loomian_name = loomian_names[loomian.species_id]
                        await message.channel.send(
                            f"{message.author.mention}."
                            f"{loomian_name} has reached level {loomian.level}!"
                        )

        last_message_xp[user_id] = now

    # ========== SPAWNING ==========

    if server_id in last_counted_messages:
        if (now - last_counted_messages[server_id]).total_seconds() < MESSAGE_COOLDOWN:
            await bot.process_commands(message)
            return

    last_counted_messages[server_id] = now

    if server_id not in message_counts:
        message_counts[server_id] = 0
        next_spawn_intervals[server_id] = random.randint(MIN_MESSAGES, MAX_MESSAGES)

    message_counts[server_id] += 1

    if message_counts[server_id] >= next_spawn_intervals[server_id]:

        rarity = random.choices(
            list(rarities.keys()),
            weights=list(rarities.values()),
            k=1
        )[0]

        current_spawn = random.choice(
            list(loomian_data[rarity].keys())
        )

        current_spawns[server_id] = {
            "name": current_spawn,
            "rarity": rarity
        }

        image_path = loomian_data[rarity][current_spawn]["image"]
        file = discord.File(image_path, filename=f"{current_spawn}.webp")
        embed = discord.Embed(title=f"A new Loomian has spawned!", description="Use \"@LoomiBot catch <Loomian>\" to catch it!")
        embed.set_image(url=f"attachment://{current_spawn}.webp")

        with Session() as session:
            server = session.query(Server).filter_by(
                server_id=message.guild.id
            ).first()

            if server is None:
                return

            spawn_channel_id = server.spawn_channel_id

        channel = bot.get_channel(spawn_channel_id)

        if channel is None:
            channel = await bot.fetch_channel(spawn_channel_id)

        print(current_spawn)

        await channel.send(embed=embed, file=file)

        message_counts[server_id] = 0
        next_spawn_intervals[server_id] = random.randint(MIN_MESSAGES, MAX_MESSAGES)

    await bot.process_commands(message)

@bot.command(aliases=["commands"])
async def help(ctx):
    embed = discord.Embed(title="__LoomiBot's Commands__",
                          description="- **help** - View commands.\n" \
                                      "- **changelog** - View the most recent updates.\n" \
                                      "- **wiki** <optional: query> - Displays the corresponding Wiki page.\n" \
                                      "- **abilities** <loomian> - Displays the corresponding loomian's abilities.\n " \
                                      "- **catch** <loomian> - Attempt to catch the current loomian.\n" \
                                      "- **hint** - Gives a hint on the current loomian's name.\n" \
                                      "- **stats** - View your statistics.\n"
                                      "- **loomians** - Shows your loomian inventory.\n" \
                                      "- **setup** - (Admin only) Setup the bot.\n" \
                                      "\n" \
                                      "If you find any bugs or errors, DM @filip5011"
                                      )
    await ctx.send(embed=embed)
    return

@bot.command(aliases=["log", "cl"])
async def changelog(ctx):
    embed = discord.Embed(title="__Changelog__",
                          description=
                          "v0.5.1\n" \
                          " - Added direct ability searching\n" \
                          "v0.4.3\n" \
                          "- Added majority of wiki into search\n" \
                          "- Added User stats and Loomicoins\n" \
                          "v0.3.1\n" \
                          "- Added rarities to spawns\n" \
                          "- Improved Wiki searching\n" \
                          "- Bug fixes and improvements"
                          )
    await ctx.send(embed=embed)
    return

@bot.command(aliases=["w"])
async def wiki(ctx, *, query=None):
    if query is None:
        await ctx.send(
            "Here is the Official Loomian Legacy Wiki:\n"
            "https://loomian-legacy.fandom.com/wiki/Loomian_Legacy_Wiki"
        )
        return

    query = query.lower().replace("'", "").replace("_", " ")

    for name, data in wiki_queries.items():
        if query == name.lower() or query in [alias.lower() for alias in data["aliases"]]:
            wiki_url = data["url"]
            name = name.replace("_", " ")
            await ctx.send(
                f"Here is the Wiki page for {name}:\n{wiki_url}"
            )
            return

    await ctx.send("Invalid Wiki query.")

@bot.command(aliases=["a", "ability", "sa", "secret ability"])
async def abilities(ctx, *, loomian=None):
    if loomian is None:
        await ctx.send(
                    "Here is a list of all abilities:\n"
                    "https://loomian-legacy.fandom.com/wiki/Ability"
                )
        return
    
    loomian = loomian.strip().lower()

    for rarity, loomians in loomian_data.items():
        for name, data in loomians.items():
            if name.lower() == loomian:
                abilities = ", ".join(data["abilities"])
                secret_ability = data["secret ability"] or "None"

                embed = discord.Embed(
                    title=f"{name}'s Abilities"
                )

                embed.add_field(
                    name="Abilities:",
                    value=abilities,
                    inline=False
                )

                embed.add_field(
                    name="Secret Ability:",
                    value=secret_ability,
                    inline=False
                )

                await ctx.send(embed=embed)
                return

    await ctx.send("Invalid loomian.")

@bot.command()
@admin_or_owner()
async def bam(ctx, *, message):
    await ctx.send(f"{message} has been bammed.")

@bot.command()
@commands.is_owner()
async def spawn(ctx, *, loomian):
    global current_spawns

    server_id = ctx.guild.id

    current_spawn = loomian.title()

    for rarity, loomians in loomian_data.items():
        if current_spawn in loomians:
            current_spawns[server_id] = {
                "name": current_spawn,
                "rarity": rarity
            }
            break
    else:
        await ctx.send("Invalid Loomian.")
        return

    image_path = loomian_data[rarity][current_spawn]["image"]
    file = discord.File(image_path, filename=f"{current_spawn}.webp")
    embed = discord.Embed(title=f"A new Loomian has spawned!", description="Use \"@LoomiBot catch <Loomian>\" to catch it!")
    embed.set_image(url=f"attachment://{current_spawn}.webp")

    with Session() as session:
        server = session.query(Server).filter_by(
            server_id=server_id
        ).first()

        if server is None:
            return

        spawn_channel_id = server.spawn_channel_id

    channel = bot.get_channel(spawn_channel_id)

    if channel is None:
        channel = await bot.fetch_channel(spawn_channel_id)

    await channel.send(embed=embed, file=file)

    message_counts[server_id] = 0
    next_spawn_intervals[server_id] = random.randint(MIN_MESSAGES, MAX_MESSAGES)

@bot.command()
@commands.is_owner()
async def give_exp(ctx, *, amount):
    try:
        amount = int(amount)
    except ValueError:
        await ctx.send("Please enter a valid amount of experience.")
        return

    if amount <= 0:
        await ctx.send("Please enter a positive amount of experience.")
        return

    with Session() as session:
        user_id = str(ctx.author.id)

        user = session.query(User).filter_by(
            discord_id=user_id
        ).first()

        if user is None or user.selected_loomian_id is None:
            await ctx.send("You don't have a selected Loomian.")
            return

        loomian = session.query(Loomian).filter_by(
            id=user.selected_loomian_id
        ).first()

        if loomian is None:
            await ctx.send("Your selected Loomian could not be found.")
            return

        levels_gained = experience_gain(
            session,
            loomian,
            amount
        )

        if levels_gained > 0:
            new_species_id = check_evolution(loomian)

            if new_species_id:
                old_name, new_name = evolve_loomian(
                    loomian,
                    new_species_id
                )

                await ctx.channel.send(
                    f"{ctx.author.mention}\n"
                    f"{old_name} has reached level {loomian.level}!\n"
                    f":tada: Your {old_name} evolved into {new_name}!"
                )

            else:
                loomian_name = loomian_names[loomian.species_id]

                await ctx.channel.send(
                    f"{ctx.author.mention}\n"
                    f"{loomian_name} has reached level {loomian.level}!"
                )

        session.commit()

@bot.command()
async def time(ctx):
    current_time, change = get_time()

    next_time = "night" if current_time == "day" else "day"
    emoji = ":sunny:" if current_time == "day" else ":stars:"

    await ctx.send(
        f"{emoji} It is currently **{current_time}**!\n"
        f"-# It will be **{next_time}** in **{change} minutes**."
    )

@bot.command()
async def weather(ctx):
    current_weather, emoji, change = get_weather()

    change_msg = f"-# The weather is forecast to change in **{change} minutes**"

    if current_weather == "Clear":
        await ctx.send(
            f"{emoji} The weather in Roria is currently **clear**.\n"
            + change_msg
        )

    elif current_weather == "Severe Thunderstorm" or current_weather == "Blistering Blizzard":
        await ctx.send(
            f"{emoji} Roria is currently experiencing a **{current_weather}**.\n"
            + change_msg
        )

    else:
        await ctx.send(
            f"{emoji} Roria is currently experiencing **{current_weather}**.\n"
            + change_msg
        )

@bot.command(aliases=["c"])
async def catch(ctx, *, loomian):
    global current_spawns

    server_id = ctx.guild.id

    if ctx.guild is None:
        return

    if server_id not in current_spawns:
        await ctx.send("There is no Loomian spawned...")
        return

    current_spawn = current_spawns[server_id]["name"]
    rarity = current_spawns[server_id]["rarity"]

    if loomian.lower() != current_spawn.lower():
        await ctx.send("Incorrect Loomian, try again!")
        return

    with Session() as session:

        user = session.query(User).filter_by(
            discord_id=str(ctx.author.id)
        ).first()

        if user is None:
            user = User(discord_id=str(ctx.author.id))
            session.add(user)
            session.flush()

        level = random.randint(3, 25)
        species_id = loomian_data[rarity][current_spawn]["id"]

        last_loomian = (
            session.query(Loomian)
            .filter_by(owner_id=user.id)
            .order_by(Loomian.instance_number.desc())
            .first()
        )

        if last_loomian:
            instance_number = last_loomian.instance_number + 1
        else:
            instance_number = 1

        existing_loomian = session.query(Loomian).filter_by(
            owner_id=user.id,
            species_id=species_id
        ).first()

        first_capture = existing_loomian is None

        captured = Loomian(
            owner=user,
            species_id=species_id,
            instance_number=instance_number,
            level=level
        )

        user.captured += 1

        session.add(captured)

        if first_capture:
            user.loomicoins += 100
            user.loomipedia += 1

        session.commit()

        msg = f"{ctx.author.mention} caught a wild level {level} {current_spawn}!"

        if first_capture:
            await ctx.send(msg + "\nFirst capture bonus! Obtained 100 Loomicoins.")
        else:
            await ctx.send(msg)

    current_spawns.pop(server_id)

@bot.command(aliases=["h"])
async def hint(ctx):
    global current_spawns, last_hints

    server_id = ctx.guild.id

    if server_id not in current_spawns:
        await ctx.send("There is no Loomian spawned...")
        return

    current_spawn = current_spawns[server_id]["name"]

    now = datetime.now()

    if server_id in last_hints:
        remaining = HINT_COOLDOWN - (now - last_hints[server_id]).total_seconds()

        if remaining > 0:
            await ctx.send(f"You can use another hint in {int(remaining)} seconds.")
            return

    last_hints[server_id] = now

    name_len = len(current_spawn)
    hint = ["\\_"] * name_len
    clues = max(1, math.ceil(name_len / 3))
    revealed = random.sample(range(name_len), clues)

    for i in revealed:
        hint[i] = current_spawn[i]

    await ctx.send("".join(hint))

@bot.command()
async def stats(ctx):
    with Session() as session:
        user = session.query(User).filter_by(
            discord_id=str(ctx.author.id)
        ).first()

        if user is None:
            user = User(discord_id=str(ctx.author.id))
            session.add(user)
            session.flush()

        embed = discord.Embed(
            title=f"{ctx.author.name}'s stats",
            description=f"Loomicoins: Ł{user.loomicoins}\n" \
                        f"Loomipedia: {user.loomipedia}/300\n" \
                        f"Captured loomians: {user.captured} "
            )
        
    await ctx.send(embed=embed)

@bot.command(aliases=["l"])
async def loomians(ctx):
    with Session() as session:
        user = session.query(User).filter_by(
            discord_id=str(ctx.author.id)
        ).first()

        if user is None or not user.loomians:
            await ctx.send("You don't have any Loomians.")
            return

        embed = discord.Embed(title=f"{ctx.author.name}'s Loomians")

        loomian_list = ""

        for loomian in sorted(
            user.loomians,
            key=lambda loomian: loomian.instance_number
        ):
            name = loomian_names[loomian.species_id]
            level = loomian.level
            number = loomian.instance_number

            if loomian.id == user.selected_loomian_id:
                loomian_list += f"- :star: **#{number} - {name}** - Lv.{level}\n"
            else:
                loomian_list += f"- #{number} - {name} - Lv.{level}\n"

        embed.add_field(
            name="ID - Loomian - Level",
            value=loomian_list,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(aliases=["s"])
async def select(ctx, *, selected_number):
    selected_number = selected_number.strip()

    try:
        selected_number = int(selected_number)
    except ValueError:
        await ctx.send("Please enter a number.")
        return

    if selected_number < 1:
        await ctx.send("Please enter a valid ID.")
        return

    with Session() as session:
        user = session.query(User).filter_by(
            discord_id=str(ctx.author.id)
        ).first()

        if user is None:
            await ctx.send("You don't have any Loomians.")
            return

        selected_loomian = session.query(Loomian).filter_by(
            owner_id=user.id,
            instance_number=selected_number
        ).first()

        if selected_loomian is None:
            await ctx.send("Please enter a valid ID")
            return
        
        user.selected_loomian_id = selected_loomian.id

        session.commit()

        loomian_name = loomian_names[selected_loomian.species_id]

        await ctx.send(f"Successfully selected #{user.selected_loomian_id} - {loomian_name}")

@bot.command()
@admin_or_owner()
async def setup(ctx):
    await ctx.send("Provide the channel ID or mention the channel.")

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    response = await bot.wait_for("message", check=check)

    channel_input = response.content.strip()

    if channel_input.startswith("<#") and channel_input.endswith(">"):
        channel_input = channel_input[2:-1]

    try:
        spawn_channel_id = int(channel_input)
    except ValueError:
        await ctx.send("Please provide a valid channel ID or channel mention.")
        return

    channel = bot.get_channel(spawn_channel_id)

    if channel is None:
        await ctx.send("That channel does not exist.")
        return

    with Session() as session:
        server = session.query(Server).filter_by(
            server_id=ctx.guild.id
        ).first()

        if server is None:
            server = Server(
                server_id=ctx.guild.id,
                spawn_channel_id=spawn_channel_id
            )
            session.add(server)
        else:
            server.spawn_channel_id = spawn_channel_id

        session.commit()

    await ctx.send(f"Setup complete! Loomians will spawn in {channel.mention}.")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
