import discord
import datetime
import asyncio
from discord.ext import commands
from discord.utils import get


joined, messages, guildId = 0, 0, 0
token = open("token.txt", "r").read()

bot = commands.Bot(command_prefix="!")
bot.remove_command("help")


# todo redo with using a database || reading previous messages (preferred to read)
# async def update_stats():
#     await bot.wait_until_ready()
#     global messages, joined
#     while not bot.is_closed():
#         try:
#             with open("stats.txt", "a") as file:
#                 timestr = datetime.datetime.now()
#                 file.write("Time: {}; Messages: {}; Members joined: {}\n".format(timestr, messages, joined))
#                 messages, joined = 0, 0
#                 await asyncio.sleep(5)
#         except Exception as e:
#             print(e)
#             await asyncio.sleep(5)


@bot.command(pass_context=True)
async def join(ctx):
    channel = ctx.author.voice.channel
    await channel.connect()


@bot.command(pass_context=True)
async def leave(ctx):
    await ctx.voice_client.disconnect()


@bot.command(pass_context=True)
async def hello(ctx):
    await ctx.send("Hi {}".format(ctx.author))


@bot.command(pass_context=True)
async def help(ctx):
    embed = discord.Embed(title="Help", description="Commands")
    embed.add_field(name="!hello", value="Greets the user")
    embed.add_field(name="!users", value="Prints number of users")
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    perms = discord.Permissions(permissions=506719280)
    invite_link = discord.utils.oauth_url(bot.user, permissions=perms)
    print(f"Use this link to add the bot to your server: {invite_link}")
    global guildId
    for guild in bot.guilds:
        print("{} is connected to the following guild: {}".format(bot.user, guild.name))
        guildId = guild.id
        print("Guild id", guild.id)


# @bot.event
# async def on_message(message):
#     global messages
#     messages += 1
#     print(f"{message.channel}: {message.author}; {message.author.name}: {message.content}")
#     id = bot.get_guild(guildId)
#
#     if message.author == bot.user:
#         return

    # if message.content == "!hello":
    #     await message.channel.send("Hi {}".format(message.author))
    # elif message.content == "!help":
    #     embed = discord.Embed(title="Help", description="Commands")
    #     embed.add_field(name="!hello", value="Greets the user")
    #     embed.add_field(name="!users", value="Prints number of users")
#         await message.channel.send(content=None, embed=embed)
#     elif message.content == "!users":
#         await message.channel.send(f"""Number of Members: {id.member_count}""")
#
#     # if str(message.channel) == "general":
#     #     print(message.channel)
#
#
# # todo join, rejoin, wait after everyone leaves, leave after no one mentions for some time || task ended
# @bot.event
# async def on_voice_state_update(member, before, after):
#     print("Channel {}\n {}\n {}\n".format(member, before, after))
#     # if after.channel is None:
#     #     asyncio.sleep(2)


@bot.event
async def on_member_join(member):
    global joined
    joined += 1
    for channel in member.guild.channels:
        if str(channel) == "general":
            print("Someone connected")
    await member.create_dm()
    await member.dm_channel.send(f'Hi {member.name}, welcome to my Discord server!')


@bot.event
async def on_member_update(before, after):
    nickname = after.nick
    print(before.nick, after.nick)
    if nickname:
        if nickname.lower().count("dream") > 0:
            lastNickname = before.nick
            if lastNickname:
                await after.edit(nick=lastNickname)
            else:
                await after.edit(nick="Nickname dream is reserved by bot, please change yours role or nickname")


# bot.loop.create_task(update_stats())
bot.run(token)
