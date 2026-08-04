import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import json
import random
from loomian_dict import loomian_dict
from loomians import loomians
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

MIN_MESSAGES = 3
MAX_MESSAGES = 10

message_count = 0
next_spawn_interval = random.randint(MIN_MESSAGES, MAX_MESSAGES)

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready and running.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    message_count += 1

    if message_count >= next_spawn_interval:
        await message.channel.send(random.choice(loomians))
        message_count = 0
        next_spawn_interval = random.randint(MIN_MESSAGES, MAX_MESSAGES)

    await bot.process_commands(message)

@bot.command()
async def wiki(ctx):
    await ctx.send("Here is the Official Loomian Legacy Wiki:\nhttps://loomian-legacy.fandom.com/wiki/Loomian_Legacy_Wiki")

# @bot.command()
# @commands.has_permissions(administrator=True)
# async def setup(ctx):


bot.run(token, log_handler=handler, log_level=logging.DEBUG)
