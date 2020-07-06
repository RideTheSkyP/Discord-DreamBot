import discord
import datetime
import asyncio

joined, messages, guildId = 0, 0, 0
client = discord.Client()
token = open("token.txt", "r").read()


# todo redo with using a database || reading previous messages (preferred to read)
# async def update_stats():
#     await client.wait_until_ready()
#     global messages, joined
#     while not client.is_closed():
#         try:
#             with open("stats.txt", "a") as file:
#                 timestr = datetime.datetime.now()
#                 file.write("Time: {}; Messages: {}; Members joined: {}\n".format(timestr, messages, joined))
#                 messages, joined = 0, 0
#                 await asyncio.sleep(5)
#         except Exception as e:
#             print(e)
#             await asyncio.sleep(5)


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    perms = discord.Permissions(permissions=8)
    invite_link = discord.utils.oauth_url(client.user, permissions=perms)
    print(f"Use this link to add the bot to your server: {invite_link}")
    # global guildId
    # for guild in client.guilds:
    #     print("{} is connected to the following guild: {}".format(client.user, guild.name))
    #     guildId = guild.id
    #     print("Guild id", guild.id)


@client.event
async def on_message(message):
    global messages
    messages += 1
    print(f"{message.channel}: {message.author}; {message.author.name}: {message.content}")
    # id = client.get_guild(guildId)
    # print(id)
    if message.content.find("!hello") != -1:
        await message.channel.send("Hi {}".format(message.author))
    # elif message.content == "!users":
    #     await message.channel.send(f"""Number of Members: {id.member_count}""")

    # if str(message.channel) == "general":
    #     print(message.channel)


# todo join, rejoin, wait after everyone leaves, leave after no one mentions for some time || task ended
@client.event
async def on_voice_state_update(member, before, after):
    print("Channel {}\n {}\n {}\n".format(member, before, after))
    # if after.channel is None:
    #     asyncio.sleep(2)


@client.event
async def on_member_join(member):
    global joined
    joined += 1
    for channel in member.guild.channels:
        if str(channel) == "general":
            await channel.send_message("Welcome to the server {}. I hope you'll like to spend time here:)"
                                       .format(member.mention))


@client.event
async def on_member_update(before, after):
    nickname = after.nick
    print(before.nick, after.nick, nickname)
    if nickname:
        if nickname.lower().count("dream") > 0:
            lastNickname = before.nick
            if lastNickname:
                await after.edit(nick=lastNickname)
            else:
                await after.edit(nick="STOP")


# client.loop.create_task(update_stats())
client.run(token)

