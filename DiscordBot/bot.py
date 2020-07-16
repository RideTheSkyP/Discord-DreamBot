import discord
import datetime
import asyncio
import os
import shutil
import youtube_dl
import requests
from discord.ext import commands
from discord.utils import get

joined, messages, guildId, songQueue, message = 0, 0, 0, {}, {}
token = open("token.txt", "r").read()
bot = commands.Bot(command_prefix="!")
bot.remove_command("help")
ffmpegPath = ""

ydlOptions = {
    "format": "bestaudio",
    "noplaylist": True,
    # "postprocessors": [{
    #                 "key": "FFmpegExtractAudio",
    #                 "preferredcodec": "mp3",
    #                 "preferredquality": "192"
    #             }],
    # "postprocessor_args": [
    #     "-ar", "16000"
    # ],
    "prefer_ffmpeg": True,
    "ffmpeg_location": ffmpegPath
}

ffmpegOptions = {
    "options": "-vn"
}


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
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()
    await ctx.send("Joined {}".format(channel))


@bot.command(pass_context=True)
async def leave(ctx):
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients)
    if voice and voice.is_connected():
        await voice.disconnect()
        await ctx.send("Left {}".format(channel))


def parse_duration(duration):
    m, s = divmod(duration, 60)
    h, m = divmod(m, 60)
    return f'{h:d}:{m:02d}:{s:02d}'


async def edit_message(ctx):
    embed = songQueue[ctx.guild][0]["embed"]
    content = "\n".join([f"({songQueue[ctx.guild].index(i)}) {i['title']}" for i in songQueue[ctx.guild][1:]]) \
        if len(songQueue[ctx.guild]) > 1 else "No song queued"
    embed.set_field_at(index=3, name="File: ", value=content, inline=False)
    await message[ctx.guild].edit(embed=embed)


def search(author, arg):
    try:
        with youtube_dl.YoutubeDL(ydlOptions) as ydl:
            try:
                requests.get(arg)
            except:
                info = ydl.extract_info(f"ytsearch:{arg}", download=False)["entries"][0]
            else:
                info = ydl.extract_info(arg, download=False)

            embed = (discord.Embed(title="Currently playing: ", description=f"[{info['title']}]({info['webpage_url']})",
                                   color=discord.Color.purple())
                     .add_field(name="Duration", value=parse_duration(info["duration"]))
                     .add_field(name="Requested by", value=author)
                     .add_field(name="Uploader", value=f"[{info['uploader']}]({info['channel_url']})")
                     .add_field(name="Queue", value="No song queued")
                     .set_thumbnail(url=info["thumbnail"]))
    except discord.HTTPException:
        pass

    return {"embed": embed, "source": info["formats"][0]["url"], "title": info["title"]}


def playNext(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)
    if len(songQueue[ctx.guild]) > 1:
        del songQueue[ctx.guild][0]
        asyncio.run_coroutine_threadsafe(edit_message(ctx), bot.loop)
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=songQueue[ctx.guild][0]["source"],
                                          **ffmpegOptions), after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)


@bot.command(pass_context=True, aliases=["p"])
async def play(ctx, video: str):
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    song = search(ctx.author.mention, video)
    await ctx.channel.purge(limit=1)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    if not voice.is_playing():
        songQueue[ctx.guild] = [song]
        print(songQueue, song)
        message[ctx.guild] = await ctx.send(embed=song["embed"])
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=song["source"], **ffmpegOptions),
                   after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        f"Queued"
        songQueue[ctx.guild].append(song)
        f"{songQueue}"
        await edit_message(ctx)


@bot.command(pass_context=True)
async def pause(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)
    if voice.is_connected():
        await ctx.channel.purge(limit=1)
        if voice.is_playing():
            await ctx.send("Music paused", delete_after=5)
            voice.pause()
        else:
            await ctx.send("Music resumed", delete_after=5)
            voice.resume()


@bot.command(pass_context=True)
async def hello(ctx):
    await ctx.send("Hi {}".format(ctx.author))


@bot.command(pass_context=True)
async def help(ctx):
    embed = discord.Embed(title="Help", description="Commands")
    embed.add_field(name="!hello", value="Greets the user")
    embed.add_field(name="!users", value="Prints number of users")
    await ctx.send(embed=embed)


@bot.command(pass_context=True)
async def skip(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)
    if voice.is_playing():
        await ctx.channel.purge(limit=1)
        await ctx.send("Music skipped", delete_after=5)
        voice.stop()


@bot.command(pass_context=True)
async def users(ctx):
    await ctx.send(ctx.member_count)


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