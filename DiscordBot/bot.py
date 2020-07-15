import discord
import datetime
import asyncio
import os
import shutil
import youtube_dl
import requests
from discord.ext import commands
from discord.utils import get

joined, messages, guildId, songQueue, message, musicTitles, repeat, i = 0, 0, 0, {}, {}, {}, False, 0
token = open("token.txt", "r").read()

bot = commands.Bot(command_prefix="!")
bot.remove_command("help")
musicPath = "data/audio/cache/"
ffmpegPath = ""

# check what happen if remove socket timeout
ydlOptions = {
    "socket_timeout": 5,
    "source_address": "0.0.0.0",
    "extractaudio": True,
    "audioformat": "mp3",
    "no-check-certificate": True,
    "ignoreerrors": False,
    "default_search": "auto",
    "outtmpl": "data/audio/cache/%(id)s.%(ext)s",
    "encoding": "utf-8",
    "format": "bestaudio/best",
    "noplaylist": True,
    "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }],
    "postprocessor_args": [
        "-ar", "16000"
    ],
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
    await ctx.send("Joined {}".format(channel), delete_after=5)


@bot.command(pass_context=True)
async def leave(ctx):
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients)
    if voice and voice.is_connected():
        await voice.disconnect()
        await ctx.send("Left {}".format(channel), delete_after=5)


def parse_duration(duration):
    m, s = divmod(duration, 60)
    h, m = divmod(m, 60)
    return f'{h:d}:{m:02d}:{s:02d}'


async def edit_message(ctx):
    embed = songQueue[ctx.guild][0]["embed"]
    content = "\n".join([f"({songQueue[ctx.guild].index(i)}) {i['title']}" for i in songQueue[ctx.guild][1:]]) \
        if len(songQueue[ctx.guild]) > 1 else "No song queued"
    embed.set_field_at(index=3, name="Queue: ", value=content, inline=False)
    await message[ctx.guild].edit(embed=embed)


def search(author, arg):
    global i

    with youtube_dl.YoutubeDL(ydlOptions) as ydl:
        try:
            requests.get(arg)
        except:
            info = ydl.extract_info(f"ytsearch:{arg}", download=True)["entries"][0]
        else:
            info = ydl.extract_info(arg, download=True)

        filename = ydl.prepare_filename(info)
        i += 1
        songTitle = os.path.splitext(filename)[0]
        os.rename(songTitle + ".mp3", songTitle + f"{i}.mp3")
        f = os.path.join(songTitle + f"{i}.mp3")

        try:
            if os.path.exists(os.path.join(musicPath+filename)):
                os.remove(os.path.join(musicPath+filename))
            else:
                pass
        except Exception as e:
            print(e)

        embed = (discord.Embed(title="Currently playing: ", description=f"[{info['title']}]({info['webpage_url']})",
                               color=discord.Color.purple())
                 .add_field(name="Duration", value=parse_duration(info["duration"]))
                 .add_field(name="Requested by", value=author)
                 .add_field(name="Uploader", value=f"[{info['uploader']}]({info['channel_url']})")
                 .add_field(name="Queue", value="No song queued")
                 .set_thumbnail(url=info["thumbnail"]))

        return {"embed": embed, "source": info["formats"][0]["url"], "title": info["title"]}, f


def playNext(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)
    global repeat

    song = musicTitles[ctx.guild][0]
    if not repeat:
        del songQueue[ctx.guild][0], musicTitles[ctx.guild][0]
        os.remove(song)
    else:
        await ctx.send("Repeat requested by: {}".format(ctx.message.author.voice.channel), delete_after=5)
        repeat = False

    if len(songQueue[ctx.guild]) > 0 and len(musicTitles[ctx.guild]) > 0:
        asyncio.run_coroutine_threadsafe(edit_message(ctx), bot.loop)
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=musicTitles[ctx.guild][0]),
                   after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)
        deleteFiles()
        repeat = False


@bot.command(pass_context=True, aliases=["p", "PLAY", "P"])
async def play(ctx, video: str):
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    song, file = search(ctx.author.mention, video)
    await ctx.channel.purge(limit=1)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    if not voice.is_playing():
        songQueue[ctx.guild] = [song]
        musicTitles[ctx.guild] = [file]
        message[ctx.guild] = await ctx.send(embed=song["embed"])
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=file), after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        songQueue[ctx.guild].append(song)
        musicTitles[ctx.guild].append(file)
        await edit_message(ctx)


@bot.command(pass_context=True, aliases=["REPEAT", "r", "R", "omt", "OMT", "again", "AGAIN", "replay", "REPLAY"])
async def repeat(ctx):
    global repeat

    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    await ctx.channel.purge(limit=1)

    repeat = True

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect

    if voice.is_playing():
        voice.stop()
    else:
        ctx.send("Nothing to repeat", delete_after=5)

    await edit_message(ctx)


@bot.command(pass_context=True, aliases=["stop", "STOP", "s", "S"])
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
    deleteFiles()

    for guild in bot.guilds:
        print("{} is connected to the following guild: {}.Guild id: {}".format(bot.user, guild.name, guild.id))


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
    # for channel in member.guild.channels:
    #     if str(channel) == "general":
    #         print("Someone connected")
    await member.create_dm()
    await member.dm_channel.send(f'Hi {member.name}, welcome to my Discord server!')


@bot.event
async def on_member_update(before, after):
    nickname = after.nick
    if nickname:
        if nickname.lower().count("dream") > 0:
            lastNickname = before.nick
            if lastNickname:
                await after.edit(nick=lastNickname)
            else:
                await after.edit(nick="Nickname dream is reserved by bot, please change yours role or nickname")


def deleteFiles():
    for files in os.listdir(musicPath):
        os.remove(os.path.join(musicPath + files))


# bot.loop.create_task(update_stats())
bot.run(token)
