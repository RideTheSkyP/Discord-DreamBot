import discord
import asyncio
# from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands


# Load environment variables from .env file
# load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

with open('token.txt', 'r') as f:
    token = f.read()


bot = commands.Bot(
    command_prefix=commands.when_mentioned_or('.'),
    description='Music bot',
    case_insensitive=True,
    intents=intents
)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    clear = bot.tree.clear_commands(guild=discord.Object(GUILD_ID))
    print('clear', clear)
    synced = await bot.tree.sync(guild=discord.Object(GUILD_ID))
    print('synced', synced)
    print('tree', bot.tree, vars(bot.tree))
    print('comms', bot.tree.get_commands())
    print('comms guild', bot.tree.get_commands(guild=discord.Object(GUILD_ID)))


@bot.command(name='sync')
async def sync(ctx):
    print('sync ctx', ctx, ctx.guild, ctx.guild.id)
    synced = await bot.tree.sync(guild=ctx.guild)
    print('synced', synced)


async def load():
    await bot.load_extension('music_cog')


async def main():
    async with bot:
        await load()
        await bot.start(token)

# async def main():
#
#     async with bot:
#         # await client.load_extension('music_cog')
#         await bot.run(token)

# bot.run(token)
asyncio.run(main())
