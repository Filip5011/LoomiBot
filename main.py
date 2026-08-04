import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import json
import math
import random
from datetime import datetime, timedelta
with open("loomian_data.json", "r", encoding="utf-8") as file:
    loomian_data = json.load(file)
import os

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

message_count = 0
last_counted_message = None
next_spawn_interval = random.randint(MIN_MESSAGES, MAX_MESSAGES)
current_spawn = None
last_hint = None

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready and running.")

@bot.event
async def on_message(message):
    global message_count, next_spawn_interval, current_spawn, last_counted_message

    if message.author == bot.user:
        return

    now = datetime.now()

    if last_counted_message is not None:
        if (now - last_counted_message).total_seconds() < MESSAGE_COOLDOWN:
            await bot.process_commands(message)
            return

    last_counted_message = now
    message_count += 1

    if message_count >= next_spawn_interval:
        current_spawn = random.choice(list(loomian_data.keys()))

        image_path = loomian_data[current_spawn]["image"]
        file = discord.File(image_path, filename=f"{current_spawn}.webp")
        embed = discord.Embed(title=f"A new Loomian has spawned!", description="Use \"@LoomiBot catch <Loomian>\" to catch it!")
        embed.set_image(url=f"attachment://{current_spawn}.webp")

        await message.channel.send(embed=embed, file=file)

        message_count = 0
        next_spawn_interval = random.randint(MIN_MESSAGES, MAX_MESSAGES)

    await bot.process_commands(message)

@bot.command()
async def wiki(ctx):
    await ctx.send("Here is the Official Loomian Legacy Wiki:\nhttps://loomian-legacy.fandom.com/wiki/Loomian_Legacy_Wiki")

@bot.command(aliases=["c"])
async def catch(ctx, *, loomian):
    global current_spawn

    if current_spawn is None:
        await ctx.send("There is no Loomian spawned...")

    if loomian.lower() == current_spawn.lower():
        await ctx.send(f"{ctx.author.mention} caught a wild {current_spawn}!")
        current_spawn = None

    else:
        await ctx.send("Incorrect Loomian, try again!")

@bot.command(aliases=["h"])
async def hint(ctx):
    global current_spawn, last_hint

    if current_spawn is None:
        await ctx.send("There is no Loomian spawned...")
        return

    now = datetime.now()

    if last_hint is not None:
        remaining = HINT_COOLDOWN - (now - last_hint).total_seconds()

        if remaining > 0:
            await ctx.send(f"You can use another hint in {int(remaining)} seconds.")
            return

    last_hint = now

    name_len = len(current_spawn)
    hint = ["\\_"] * name_len
    clues = max(1, math.ceil(name_len / 3))
    revealed = random.sample(range(name_len), clues)

    for i in revealed:
        hint[i] = current_spawn[i]

    await ctx.send("".join(hint))

# @bot.command()
# @commands.has_permissions(administrator=True)
# async def setup(ctx):


bot.run(token, log_handler=handler, log_level=logging.DEBUG)
