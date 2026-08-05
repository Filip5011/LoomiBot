import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import json
import math
import random
from datetime import datetime, timedelta
import os
from database import *
from tables import *

with open("loomian_data.json", "r", encoding="utf-8") as file:
    loomian_data = json.load(file)

loomian_names = {
    data["id"]: name
    for name, data in loomian_data.items()
}

Base.metadata.create_all(engine)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

MIN_MESSAGES = 5
MAX_MESSAGES = 10

MESSAGE_COOLDOWN = 2
HINT_COOLDOWN = 10

message_counts = {}
last_counted_messages = {}
next_spawn_intervals = {}
current_spawns = {}
last_hints = {}

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready and running.")

@bot.event
async def on_message(message):
    global message_counts, next_spawn_intervals, current_spawns, last_counted_messages

    if message.author == bot.user:
        return

    if message.guild is None:
        return

    server_id = message.guild.id

    now = datetime.now()

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
        current_spawns[server_id] = random.choice(list(loomian_data.keys()))
        current_spawn = current_spawns[server_id]

        image_path = loomian_data[current_spawn]["image"]
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

        await channel.send(embed=embed, file=file)

        message_counts[server_id] = 0
        next_spawn_intervals[server_id] = random.randint(MIN_MESSAGES, MAX_MESSAGES)

    await bot.process_commands(message)

@bot.command(aliases=["w"])
async def wiki(ctx, *, query=None):
    if query is None:
        await ctx.send("Here is the Official Loomian Legacy Wiki:\nhttps://loomian-legacy.fandom.com/wiki/Loomian_Legacy_Wiki")
        return

    query = query.title()

    if query in loomian_data:
        await ctx.send(f"Here is the Wiki page for {query}:\nhttps://loomian-legacy.fandom.com/wiki/{query}")
    else:
        await ctx.send("Invalid Loomian query.")


@bot.command(aliases=["c"])
async def catch(ctx, *, loomian):
    global current_spawns

    server_id = ctx.guild.id

    if server_id not in current_spawns:
        await ctx.send("There is no Loomian spawned...")
        return

    current_spawn = current_spawns[server_id]

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

        captured = Loomian(
            owner=user,
            species_id=loomian_data[current_spawn]["id"],
            level=level
        )

        session.add(captured)
        session.commit()

    await ctx.send(f"{ctx.author.mention} caught a wild level {level} {current_spawn}!")

    current_spawns.pop(server_id)

@bot.command(aliases=["h"])
async def hint(ctx):
    global current_spawns, last_hints

    server_id = ctx.guild.id

    if server_id not in current_spawns:
        await ctx.send("There is no Loomian spawned...")
        return

    current_spawn = current_spawns[server_id]

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

@bot.command(aliases=["l"])
async def loomians(ctx):
    with Session() as session:
        user = session.query(User).filter_by(
            discord_id=str(ctx.author.id)
        ).first()

        if user is None:
            user = User(discord_id=str(ctx.author.id))
            session.add(user)
            session.flush()

        embed = discord.Embed(title=f"{ctx.author.name}'s Loomians")

        loomian_list = ""

        for loomian in user.loomians:
            name = loomian_names[loomian.species_id]
            level = loomian.level

            loomian_list += f"- {name} - Lv.{level}\n"

        embed.add_field(
            name="Loomian - Level",
            value=loomian_list,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("Provide the Channel ID you want Loomians to spawn in.")

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    response = await bot.wait_for("message", check=check)

    try:
        spawn_channel_id = int(response.content)
    except ValueError:
        await ctx.send("Please provide a valid channel ID.")
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

    await ctx.send("Setup complete!")



bot.run(token, log_handler=handler, log_level=logging.DEBUG)
