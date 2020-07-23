import discord
from datetime import datetime
import asyncio
import os
import shutil
import youtube_dl
import requests
from discord.ext import commands
from discord.utils import get

joined, messages, guildId, songIterator, skipToTime, skipTime, songStartTime = 0, 0, 0, 0, 0, 0, 0
loop = False
songQueue, musicTitles, message = {}, {}, {}
token = open("token.txt", "r").read()
ffmpegPath = open("ffmpegPath.txt", "r").read()
commandPrefix = "."

# todo add playlists
# todo add spotify player
# todo add volume command
# todo add "" and font to help and extended help (done)
# todo make pages in queue
# todo check if guild still exist (for database solutions)
# todo fix 404 exception in play (when requesting more then one song together)
# todo loop (done) -> need to avoid global variable loop
# todo extract direct url to youtube from [query] and link it with music title
# todo add skip to [time] (done) and skip [time] (done) functions (done)
# todo list a youtube playlist with choice indices on play command
# todo fix url with youtube playlists (currently playing 1st song in playlist, need to play exact one)
# todo create channel
# todo create settings command
# todo set delete time for play command in settings
# todo set pause timer in settings
# todo set color of embed message and queue in settings
# todo set command_prefix in settings
bot = commands.Bot(command_prefix=commandPrefix)
bot.remove_command("help")
musicPath = "data/audio/cache/"
playlistPath = "data/audio/playlist/"

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
    "before_options": f"-ss {skipToTime}",
    "options": "-vn"
}


# todo redo with using a database || reading previous messages (preferred to read)
# add nickname changes tracking
# async def update_stats():
#     await bot.wait_until_ready()
#     global messages, joined
#     while not bot.is_closed():
#         try:
#             with open("stats.txt", "a") as file:
#                 timestr = datetime.datetime.now()
#                 file.write("Time: {}; Messages: {}; Members joined: {}\n".format(timestr, messages, joined))
#                 messages, joined = 0,6 0
#                 await asyncio.sleep(5)
#         except Exception as e:
#             print(e)
#             await asyncio.sleep(5)


@bot.command(pass_context=True)
async def join(ctx):
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients, guild=ctx.guild)
    deleteFiles()

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    await ctx.send("Joined {}".format(channel), delete_after=5)


@bot.command(pass_context=True, aliases=["LEAVE"])
async def leave(ctx):
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients)

    if voice and voice.is_connected():
        await voice.disconnect()
        deleteFiles()
        await ctx.send("Left {}".format(channel), delete_after=5)


def parseDuration(duration):
    m, s = divmod(duration, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# Queue or queued
async def edit_message(ctx):
    embed = songQueue[ctx.guild][0]["embed"]
    content = "\n".join([f"**{songQueue[ctx.guild].index(i)}:**"
                         f"[{i['title']}]({i['webpage_url']}) **Requested by:**{ctx.author.mention} "
                         f"**Duration:** {i['duration']}"
                         for i in songQueue[ctx.guild][1:]]) \
        if len(songQueue[ctx.guild]) > 1 \
        else "No songs are queued"

    embed.set_field_at(index=3, name="Queue", value=content, inline=False)
    await message[ctx.guild].edit(embed=embed)


def search(author, url):
    with youtube_dl.YoutubeDL(ydlOptions) as ydl:
        try:
            requests.get(url)
        except:
            info = ydl.extract_info(f"ytsearch:{url}", download=False)["entries"][0]
        else:
            info = ydl.extract_info(url, download=False)

        embed = (discord.Embed(title="Currently playing: ", description=f"[{info['title']}]({info['webpage_url']})",
                               color=discord.Color.purple())
                 .add_field(name="Duration", value=parseDuration(info["duration"]))
                 .add_field(name="Requested by", value=author)
                 .add_field(name="Uploader", value=f"[{info['uploader']}]({info['channel_url']})")
                 .add_field(name="Queue", value="No song queued")
                 .set_thumbnail(url=info["thumbnail"]))

        return {"embed": embed, "source": info["formats"][0]["url"], "title": info["title"],
                "webpage_url": info['webpage_url'], "thumbnail": info["thumbnail"],
                "duration": parseDuration(info["duration"])}


def playNext(ctx, played):
    global skipToTime
    ffmpegOptions["before_options"] = f"-ss {skipToTime}"
    voice = get(bot.voice_clients, guild=ctx.guild)
    video = musicTitles[ctx.guild][0]

    if loop is True:
        songQueue[ctx.guild].append(songQueue[ctx.guild][0])
        musicTitles[ctx.guild].append(musicTitles[ctx.guild][0])
    else:
        pass

    del songQueue[ctx.guild][0], musicTitles[ctx.guild][0]
    os.remove(played)

    if len(songQueue[ctx.guild]) > 0 and len(musicTitles[ctx.guild]) > 0:
        song = download(video)
        asyncio.run_coroutine_threadsafe(edit_message(ctx), bot.loop)
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=song, **ffmpegOptions),
                   after=lambda e: playNext(ctx, song))
        voice.is_playing()
    else:
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)
        deleteFiles()

    skipToTime = 0


def download(url):
    global songIterator
    with youtube_dl.YoutubeDL(ydlOptions) as ydl:
        try:
            requests.get(url)
        except:
            info = ydl.extract_info(f"ytsearch:{url}", download=True)["entries"][0]
        else:
            info = ydl.extract_info(url, download=True)

        filename = ydl.prepare_filename(info)
        songIterator += 1
        songTitle = os.path.splitext(filename)[0]
        os.rename(songTitle + ".mp3", songTitle + f"{songIterator}.mp3")
        file = os.path.join(songTitle + f"{songIterator}.mp3")

        try:
            if os.path.exists(os.path.join(musicPath + filename)):
                os.remove(os.path.join(musicPath + filename))
            else:
                pass
        except Exception as e:
            print("Download exception", e)
    return file


@bot.command(pass_context=True, aliases=["PLAY", "p", "P"])
async def play(ctx, *video: str):
    global songStartTime

    try:
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)
        song = search(ctx.author.mention, video)
        await ctx.channel.purge(limit=1)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

        if not voice.is_playing():
            file = download(video)
            songQueue[ctx.guild] = [song]
            musicTitles[ctx.guild] = [video]
            message[ctx.guild] = await ctx.send(embed=song["embed"])
            songStartTime = datetime.now()
            print(songStartTime)
            voice.play(discord.FFmpegPCMAudio(executable=ffmpegPath, source=file, **ffmpegOptions),
                       after=lambda e: playNext(ctx, file))
            voice.is_playing()
        else:
            songQueue[ctx.guild].append(song)
            musicTitles[ctx.guild].append(video)
            await edit_message(ctx)
    except Exception as e:
        print("Play exc:", e)
        await ctx.send("You're not connected to the voice channel or the video you requested isn't supported by player",
                       delete_after=5)


@bot.command(pass_context=True, aliases=["REPEAT", "r", "R", "again", "AGAIN", "replay", "REPLAY"])
async def repeat(ctx):
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    await ctx.channel.purge(limit=1)

    try:
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect

        if voice.is_playing():
            songQueue[ctx.guild].insert(1, songQueue[ctx.guild][0])
            musicTitles[ctx.guild].insert(1, musicTitles[ctx.guild][0])
            voice.stop()
        else:
            ctx.send("Nothing to repeat", delete_after=5)

        await ctx.send("Repeat requested by: {}".format(ctx.message.author), delete_after=5)
        await edit_message(ctx)
    except Exception as e:
        print("Repeat exc:", e)
        await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)


# redo this completely
@bot.command(pass_context=True, aliases=["LOOP", "l", "L"])
async def loop(ctx):
    global loop
    await ctx.channel.purge(limit=1)

    if loop is True:
        loop = False
    else:
        loop = True


@bot.command(pass_context=True, aliases=["PAUSE", "stop", "STOP", "resume", "RESUME"])
async def pause(ctx):
    voice = get(bot.voice_clients, guild=ctx.guild)
    await ctx.channel.purge(limit=1)

    try:
        if voice.is_connected():
            if voice.is_playing():
                await ctx.send("Music paused", delete_after=5)
                voice.pause()
            else:
                await ctx.send("Music resumed", delete_after=5)
                voice.resume()
    except Exception as e:
        print("Pause exception", e)
        await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)


def timeParse(time):
    try:
        seconds = 0
        parts = time.split(":")
        for i in range(len(parts)):
            try:
                seconds += int(parts[-i - 1]) * (60 ** i)
            except Exception as e:
                print("timeParse parts to int exception", e)
        return seconds
    except Exception as e:
        print("Time parse exception:", e)


@bot.command(pass_context=True, aliases=["SKIP", "s", "S"])
async def skip(ctx, time="0"):
    endtime = songStartTime - datetime.now()
    print(abs(int(endtime.total_seconds())))
    voice = get(bot.voice_clients, guild=ctx.guild)
    await ctx.channel.purge(limit=1)

    try:
        if int(time) is 0:
            if voice.is_playing():
                await ctx.send("Track skipped", delete_after=5)
                voice.stop()
            else:
                await ctx.send("Nothing is playing", delete_after=5)
        elif int(time):
            raise Exception
    except:
        await skipto(ctx, timeParse(time) + abs(int(endtime.total_seconds())))
    else:
        await ctx.send("You're not connected to the voice channel or queue is empty", delete_after=5)


@bot.command(pass_context=True)
async def skipto(ctx, time):
    global skipToTime
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    await ctx.channel.purge(limit=1)

    try:
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect

        if voice.is_playing():
            songQueue[ctx.guild].insert(1, songQueue[ctx.guild][0])
            musicTitles[ctx.guild].insert(1, musicTitles[ctx.guild][0])
            skipToTime = time
            voice.stop()
        else:
            ctx.send("Nothing to skip", delete_after=5)

        await ctx.send(f"**Skipped to:** {parseDuration(time)}, **Requested by:** {ctx.message.author}", delete_after=5)
        await edit_message(ctx)
    except Exception as e:
        print("Skipto exception:", e)
        await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)


@bot.command(pass_context=True, aliases=["HELP", "h", "H"])
async def help(ctx):
    await ctx.channel.purge(limit=1)
    embed = discord.Embed(title="Help", description="Commands", color=discord.Color.purple()) \
        .add_field(name=f"*{commandPrefix}hello*", value="Greets the user", inline=True) \
        .add_field(name=f"*{commandPrefix}users*", value="Prints number of users", inline=True) \
        .add_field(name=f"*{commandPrefix}join*", value="Bot will join voice channel", inline=True) \
        .add_field(name=f"*{commandPrefix}leave*", value="Bot will leave voice channel", inline=False) \
        .add_field(name=f"*{commandPrefix}play*", value="Request music with url or song title", inline=False) \
        .add_field(name=f"*{commandPrefix}skip*", value="Plays next track", inline=True) \
        .add_field(name=f"*{commandPrefix}skip 1:20 or 20*", value="Skips next amount of time for 20 skips 20 seconds, "
                                                                   "for 1:20 skips 1 minute 20 seconds", inline=True) \
        .add_field(name=f"*{commandPrefix}replay*", value="Repeat the track", inline=True) \
        .add_field(name=f"*{commandPrefix}pause*", value="Pause music", inline=True) \
        .add_field(name=f"*{commandPrefix}queue*", value="Shows queue", inline=False) \
        .add_field(name=f"*{commandPrefix}extendedhelp*\t\t\t*{commandPrefix}aliases*",
                   value="Shows all aliases and some useful information", inline=True) \
        .add_field(name="CAPS LOCK", value="You can ignore register and use bot with enabled CAPS LOCK", inline=False) \
        .add_field(name="Playlists",
                   value=f"Playlist are disabled, if you want to enable them, type {commandPrefix}settings",
                   inline=True)
    await ctx.send(embed=embed)


@bot.command(pass_context=True, aliases=["EXTENDEDHELP", "eh", "Eh", "aliases", "ALIASES"])
async def extendedhelp(ctx):
    await ctx.channel.purge(limit=1)
    embed = discord.Embed(title="Help", description="Extended help commands and aliases", color=discord.Color.purple()) \
        .add_field(name=f"*{commandPrefix}play*",
                   value=f'Aliases are: **"{commandPrefix}PLAY", "{commandPrefix}p", "{commandPrefix}P"**',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}pause*",
                   value=f'Aliases are: **"{commandPrefix}PAUSE", "{commandPrefix}stop", "{commandPrefix}STOP"**',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}help*",
                   value=f'Aliases are: **"{commandPrefix}HELP", "{commandPrefix}h", "{commandPrefix}H"**',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}repeat*",
                   value=f'Aliases are: **"{commandPrefix}REPEAT", "{commandPrefix}r", "{commandPrefix}R", '
                         f'"{commandPrefix}again", "{commandPrefix}AGAIN", "{commandPrefix}replay", '
                         f'"{commandPrefix}REPLAY"**', inline=False) \
        .add_field(name=f"*{commandPrefix}skip*",
                   value=f'Aliases are:** "{commandPrefix}SKIP", "{commandPrefix}s", "{commandPrefix}S"**',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}extendedhelp*",
                   value=f'Aliases are: **"{commandPrefix}EXTENDEDHELP", "{commandPrefix}eh", '
                         f'"{commandPrefix}EH", "{commandPrefix}aliases", "{commandPrefix}ALIASES"**',
                   inline=False) \
        .add_field(name="Issues", value=f'If bot stacked at voice channel use command "*{commandPrefix}leave*" it will '
                                        f'clear cache also you can disconnect him from voice chat and then test with '
                                        f'"*{commandPrefix}join*" command', inline=False)
    await ctx.send(embed=embed)


@bot.command(pass_context=True)
async def hello(ctx):
    await ctx.send("Hi {}".format(ctx.author))


@bot.command(pass_context=True)
async def users(ctx):
    await ctx.send("Number of users on server: {}".format(ctx.guild.member_count))


@bot.command(pass_context=True, aliases=["QUEUE", "q", "Q"])
async def queue(ctx):
    await ctx.channel.purge(limit=1)
    try:
        playing = f"[{songQueue[ctx.guild][0]['title']}]({songQueue[ctx.guild][0]['webpage_url']})"
        content = "\n".join([f"{songQueue[ctx.guild].index(i)}: [{i['title']}]({i['webpage_url']}) "
                             f"Requested by:{ctx.author.mention} Duration: {i['duration']}"
                             for i in songQueue[ctx.guild][1:]]) if len(songQueue[ctx.guild]) > 1 else "No song queued"

        embed = (discord.Embed(title="Music queue", color=discord.Color.purple())
                 .add_field(name="Playing now: ", value=playing, inline=False)
                 .add_field(name="Requested by", value=f"{ctx.author.mention}", inline=True)
                 .add_field(name="Duration", value=songQueue[ctx.guild][0]['duration'], inline=True)
                 .add_field(name="Queued: ", value=content, inline=False)
                 .set_thumbnail(url=songQueue[ctx.guild][0]["thumbnail"]))

        await ctx.send(embed=embed)
    except Exception as e:
        print("Queue exception: ", e)
        await ctx.send("You're not connected to the voice channel or queue is empty", delete_after=5)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    perms = discord.Permissions(permissions=8)
    invite_link = discord.utils.oauth_url(bot.user.id, permissions=perms)
    print(f"Use this link to add the bot to your server: {invite_link}")
    deleteFiles()

    activity = discord.Game(name=f"{commandPrefix}help", type=3)
    await bot.change_presence(activity=activity)

    for guild in bot.guilds:
        print("{} is connected to the following guild: {}. Guild id: {}".format(bot.user, guild.name, guild.id))


# # todo join, rejoin, wait after everyone leaves, leave after no one mentions for some time || task ended
# @bot.event
# async def on_voice_state_update(member, before, after):
#     print("Channel {}\n {}\n {}\n".format(member, before, after))
#     # if after.channel is None:
#     #     asyncio.sleep(2)


# @bot.event
# async def on_member_join(member):
#     global joined
#     joined += 1
#     # for channel in member.guild.channels:
#     #     if str(channel) == "general":
#     #         print("Someone connected")
#     await member.create_dm()
#     await member.dm_channel.send(f'Hi {member.name}, welcome to my Discord server!')


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
    global songIterator
    for files in os.listdir(musicPath):
        os.remove(os.path.join(musicPath + files))
    songIterator = 0


# bot.loop.create_task(update_stats())
bot.run(token)
