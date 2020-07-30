import discord
from datetime import datetime
import asyncio
import shutil
import youtube_dl
import requests
from discord.ext import commands
from discord.utils import get

joined, messages, guildId, songIterator, skipToTime, songStartTime, pauseTime = 0, 0, 0, 0, 0, 0, 0
loop = False
songQueue, musicTitles, message = {}, {}, {}
embedColor = discord.Color.purple()
token = open("token.txt", "r").read()
ffmpegPathUrl = open("ffmpegPathUrl.txt", "r").read()
commandPrefix = "."

# todo launch on_message with asyncio coroutine that can notify functions when event(command invoked)
# todo Track command messages with on_message to remove rubbish
# todo add playlists
# todo redo 2 tries in skip command
# todo add spotify player
# todo add volume command
# todo check if guild still exist (for database solutions)
# todo loop (done) -> need to avoid global boolean variable loop
# todo extract direct url to youtube from [query] and link it with music title
# todo list a youtube playlist with choice indices on play command
# todo fix url with youtube playlists (currently playing 1st song in playlist, need to play exact one)
# todo create channel
# todo create settings command (done)
# todo set delete time for play command in settings
# todo add to settings deleting all other commands which are unnecessary
# todo set pause timer in settings
# todo set color of embed message and queue in settings (done)
# todo set command_prefix in settings (done)

bot = commands.Bot(command_prefix=commandPrefix)
bot.remove_command("help")
musicPath = "data/audio/cache/"
playlistPath = "data/audio/playlist/"

ydlOptions = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "encoding": "utf-8",
    "default_search": "auto",
    "ignoreerrors": False,
    "no-check-certificate": True,
    "socket_timeout": 5,
    "source_address": "0.0.0.0",
    "extractaudio": True,
    "audioformat": "mp3",
    # "extract_flat": True,
    "simulate": True,
    "prefer_ffmpeg": True,
    "ffmpeg_location": ffmpegPathUrl
}

ffmpegOptions = {
    "before_options": f"-ss {skipToTime} -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 5",
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
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    await ctx.send("Joined {}".format(channel), delete_after=5)


@bot.command(pass_context=True, aliases=["LEAVE", "disconnect", "DISCONNECT"])
async def leave(ctx):
    global loop
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(ctx.bot.voice_clients)
    songQueue[ctx.guild], musicTitles[ctx.guild] = [], []

    if voice and voice.is_connected():
        # await voice.disconnect()
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        # asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)
        loop = False
        await ctx.send("Left {}".format(channel), delete_after=5)


def parseDuration(duration: int):
    m, s = divmod(duration, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# Queue or queued
async def edit_message(ctx):
    embed = songQueue[ctx.guild][0]["embed"]
    content = "\n".join([f"**{songQueue[ctx.guild].index(i)}:**"
                         f"[{i['title']}]({i['webpage_url']})\n**Requested by:** {ctx.author.mention} "
                         f"**Duration:** {i['duration']}"
                         for i in songQueue[ctx.guild][1:]]) if len(songQueue[ctx.guild]) > 1 else "No songs are queued"

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
                               color=embedColor)
                 .add_field(name="Duration", value=parseDuration(info["duration"]))
                 .add_field(name="Requested by", value=author)
                 .add_field(name="Uploader", value=f"[{info['uploader']}]({info['channel_url']})")
                 .add_field(name="Queue", value="No song queued")
                 .set_thumbnail(url=info["thumbnail"]))

        return {"embed": embed, "source": info["formats"][0]["url"], "title": info["title"],
                "webpage_url": info['webpage_url'], "thumbnail": info["thumbnail"],
                "duration": parseDuration(info["duration"])}


def playNext(ctx):
    global skipToTime, songStartTime, loop
    endTime = songStartTime - datetime.now()
    end = skipToTime
    ffmpegOptions["before_options"] = f"-ss {skipToTime}"
    voice = get(bot.voice_clients, guild=ctx.guild)
    voice.is_paused()

    if loop is True:
        songQueue[ctx.guild].append(songQueue[ctx.guild][0])
        musicTitles[ctx.guild].append(musicTitles[ctx.guild][0])
    else:
        pass

    end += abs(int(endTime.total_seconds()))

    if len(songQueue[ctx.guild]) > 1 and len(musicTitles[ctx.guild]) > 1:
        del songQueue[ctx.guild][0], musicTitles[ctx.guild][0]

        if timeParse(songQueue[ctx.guild][0]["duration"]) <= end:
            skipToTime = 0
            voice.stop()

        song = search(ctx.author.mention, musicTitles[ctx.guild][0])
        songQueue[ctx.guild][0] = song
        asyncio.run_coroutine_threadsafe(edit_message(ctx), bot.loop)
        songStartTime = datetime.now()

        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPathUrl, source=songQueue[ctx.guild][0]["source"],
                                          before_options=f"-ss {skipToTime} -reconnect 1 -reconnect_streamed 1 -reconnect_at_eof 1 -reconnect_delay_max 5",
                                          options="-vn"),
                   after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        # asyncio.sleep(pauseTime)
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
        asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)
        loop = False


@bot.command(pass_context=True, aliases=["PLAY", "p", "P"])
async def play(ctx, *video: str):
    global songStartTime

    # await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)
    song = search(ctx.author.mention, video)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect()

    if not voice.is_playing():
        songQueue[ctx.guild] = [song]
        musicTitles[ctx.guild] = [video]
        message[ctx.guild] = await ctx.send(embed=song["embed"])
        songStartTime = datetime.now()
        voice.play(discord.FFmpegPCMAudio(executable=ffmpegPathUrl,
                                          source=songQueue[ctx.guild][0]["source"], **ffmpegOptions),
                   after=lambda e: playNext(ctx))
        voice.is_playing()
    else:
        songQueue[ctx.guild].append(song)
        musicTitles[ctx.guild].append(video)
        await edit_message(ctx)


@bot.command(pass_context=True, aliases=["REPEAT", "r", "R", "again", "AGAIN", "replay", "REPLAY"])
async def repeat(ctx):
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)

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
    await ctx.channel.purge(limit=1)
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice.is_connected():
        if voice.is_playing():
            await ctx.send("Music paused", delete_after=5)
            voice.pause()
            voice.is_paused()
        else:
            await ctx.send("Music resumed", delete_after=5)
            voice.resume()


def timeParse(time):
    seconds = 0
    parts = time.split(":")
    for i in range(len(parts)):
        seconds += int(parts[-i - 1]) * (60 ** i)
    return seconds


@bot.command(pass_context=True, aliases=["SKIP", "s", "S"])
async def skip(ctx, time="0"):
    global skipToTime
    skipped = 0
    requestTime = songStartTime - datetime.now()
    voice = get(bot.voice_clients, guild=ctx.guild)

    try:
        try:
            if int(time) is 0:
                await ctx.channel.purge(limit=1)
                if voice.is_playing():
                    await ctx.send("Track skipped", delete_after=5)
                    skipToTime = 0
                    voice.stop()
                else:
                    await ctx.send("Nothing is playing", delete_after=5)
            else:
                skipped += timeParse(time) + abs(int(requestTime.total_seconds()))
                await skipto(ctx, skipped)
        except:
            skipped += timeParse(time) + abs(int(requestTime.total_seconds()))
            await skipto(ctx, skipped)
    except Exception as e:
        print("Skip exc: ", e)
        await ctx.send("Please enter time in correct format", delete_after=5)


@bot.command(pass_context=True, aliases=["SKIPTO", "st", "ST"])
async def skipto(ctx, time):
    global skipToTime
    await ctx.channel.purge(limit=1)
    channel = ctx.message.author.voice.channel
    voice = get(bot.voice_clients, guild=ctx.guild)

    if voice and voice.is_connected():
        await voice.move_to(channel)
    else:
        voice = await channel.connect

    if voice.is_playing():
        songQueue[ctx.guild].insert(1, songQueue[ctx.guild][0])
        musicTitles[ctx.guild].insert(1, musicTitles[ctx.guild][0])
        skipToTime += timeParse(time)
        voice.stop()
    else:
        await ctx.send("Nothing to skip", delete_after=5)

    await ctx.send(f"**Skipped to:** {parseDuration(skipToTime)}, **Requested by:** {ctx.message.author}",
                   delete_after=25)
    await edit_message(ctx)


def chooseEmbedColor(color):
    global embedColor
    embedTitle = f"Your new discord embeds color is *{color}*"

    if color == "blue":
        embedColor = discord.Color.blue()
    elif color == "purple":
        embedColor = discord.Color.purple()
    elif color == "blue-purple":
        embedColor = discord.Color.blurple()
    elif color == "dark-blue":
        embedColor = discord.Color.dark_blue()
    elif color == "dark-gold":
        embedColor = discord.Color.dark_gold()
    elif color == "dark-green":
        embedColor = discord.Color.dark_green()
    elif color == "dark-grey":
        embedColor = discord.Color.dark_grey()
    elif color == "dark-magenta":
        embedColor = discord.Color.dark_magenta()
    elif color == "dark-orange":
        embedColor = discord.Color.dark_orange()
    elif color == "dark-purple":
        embedColor = discord.Color.dark_purple()
    elif color == "dark-red":
        embedColor = discord.Color.dark_red()
    elif color == "dark-teal":
        embedColor = discord.Color.dark_teal()
    elif color == "gold":
        embedColor = discord.Color.gold()
    elif color == "green":
        embedColor = discord.Color.green()
    elif color == "light-grey":
        embedColor = discord.Color.light_grey()
    elif color == "magenta":
        embedColor = discord.Color.magenta()
    elif color == "orange":
        embedColor = discord.Color.orange()
    elif color == "red":
        embedColor = discord.Color.red()
    elif color == "teal":
        embedColor = discord.Color.teal()
    else:
        embedTitle = f"No such color is presented, please choose something from *{commandPrefix}settings " \
                       f"embedColor*\nYour current embed color wasn't changed"
    return embedTitle


@bot.command(pass_context=True, aliases=["SETTINGS", "set", "SET"])
async def settings(ctx, task=None, *args):
    await ctx.channel.purge(limit=1)
    global pauseTime, commandPrefix, embedColor

    if task is None:
        await ctx.send(f"Your new ")
    elif task == "commandPrefix":
        if not args:
            await ctx.send("Please give a prefix after [commandPrefix]", delete_after=5)
        else:
            commandPrefix = args[0]
            bot.command_prefix = commandPrefix
            await ctx.send(f"Your new command prefix is {args[0]}")
    elif task == "embedColor":
        if not args:
            await ctx.send(f"**Possible colors are**\n*blue\npurple\nred\norange\ngreen\nmagenta\nteal\ngold*\n"
                           f"*blue-purple\nlight-grey\ndark-blue\ndark-gold\ndark-green\ndark-purple\ndark-grey*\n"
                           f"*dark-magenta\ndark-orange\ndark-red\ndark-teal*\nUse command "
                           f"__*{commandPrefix}settings embedColor dark-purple*__ to set embeds color")
        else:
            embedTitle = chooseEmbedColor(args[0])
            embed = discord.Embed(title=embedTitle, color=embedColor)
            await ctx.send(embed=embed)


@bot.command(pass_context=True, aliases=["HELP", "h", "H"])
async def help(ctx):
    await ctx.channel.purge(limit=1)
    embed = discord.Embed(title="Help", description="Commands", color=embedColor) \
        .add_field(name=f"*{commandPrefix}hello*", value="Greets the user", inline=True) \
        .add_field(name=f"*{commandPrefix}users*", value="Prints number of users", inline=True) \
        .add_field(name=f"*{commandPrefix}join*", value="Bot will join voice channel", inline=True) \
        .add_field(name=f"*{commandPrefix}leave*", value="Bot will leave voice channel", inline=False) \
        .add_field(name=f"*{commandPrefix}play*", value="Request music with url or song title", inline=False) \
        .add_field(name=f"*{commandPrefix}skip*", value="Plays next track", inline=True) \
        .add_field(name=f"*{commandPrefix}skip 1:20 or 20*", value="Skips next amount of time for 20 skips 20 seconds, "
                                                                   "for 1:20 skips 1 minute 20 seconds, hh:mm:ss format"
                   , inline=True) \
        .add_field(name=f"*{commandPrefix}replay*", value="Repeat the track", inline=True) \
        .add_field(name=f"*{commandPrefix}pause*", value="Pause music", inline=True) \
        .add_field(name=f"*{commandPrefix}queue*", value="Shows queue", inline=False) \
        .add_field(name=f"*{commandPrefix}extendedhelp*\t\t\t*{commandPrefix}aliases*",
                   value="Shows all aliases and some useful information", inline=True) \
        .add_field(name="CAPS LOCK", value="You can ignore register and use bot with enabled CAPS LOCK", inline=False) \
        .add_field(name="Playlists",
                   value=f'Playlist are disabled, if you want to enable them, type "*{commandPrefix}settings*"',
                   inline=True)
    await ctx.send(embed=embed)


@bot.command(pass_context=True, aliases=["EXTENDEDHELP", "eh", "Eh", "aliases", "ALIASES"])
async def extendedhelp(ctx):
    await ctx.channel.purge(limit=1)
    embed = discord.Embed(title="Help", description="Extended help commands and aliases", color=embedColor) \
        .add_field(name=f"*{commandPrefix}play*",
                   value=f'Aliases are: "**{commandPrefix}PLAY**", "**{commandPrefix}p**", "**{commandPrefix}P**"',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}pause*",
                   value=f'Aliases are: "**{commandPrefix}PAUSE**", "**{commandPrefix}stop**", '
                         f'"**{commandPrefix}STOP**"', inline=False) \
        .add_field(name=f"*{commandPrefix}help*",
                   value=f'Aliases are: "**{commandPrefix}HELP**", "**{commandPrefix}h**", "**{commandPrefix}H**"',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}repeat*",
                   value=f'Aliases are: "**{commandPrefix}REPEAT**", "**{commandPrefix}r**", "**{commandPrefix}R**", '
                         f'"**{commandPrefix}again**", "**{commandPrefix}AGAIN**", "**{commandPrefix}replay**", '
                         f'"**{commandPrefix}REPLAY**"', inline=False) \
        .add_field(name=f"*{commandPrefix}skip*",
                   value=f'Aliases are: "**{commandPrefix}SKIP**", "**{commandPrefix}s**", "**{commandPrefix}S**"',
                   inline=False) \
        .add_field(name=f"*{commandPrefix}extendedhelp*",
                   value=f'Aliases are: "**{commandPrefix}EXTENDEDHELP**", "**{commandPrefix}eh**", '
                         f'"**{commandPrefix}EH**", "**{commandPrefix}aliases**", "**{commandPrefix}ALIASES**"',
                   inline=False) \
        .add_field(name="Issues", value=f'If bot stacked at voice channel use command "**{commandPrefix}leave**" it '
                                        f'will clear cache also you can disconnect him from voice chat and then test '
                                        f'with "**{commandPrefix}join**" command', inline=False)
    await ctx.send(embed=embed)


@bot.command(pass_context=True)
async def hello(ctx):
    await ctx.send("Hi {}".format(ctx.author))


@bot.command(pass_context=True)
async def users(ctx):
    await ctx.send("Number of users on server: {}".format(ctx.guild.member_count))


@bot.command(pass_context=True, aliases=["QUEUE", "q", "Q"])
async def queue(ctx, page=1):
    await ctx.channel.purge(limit=1)
    voice = get(bot.voice_clients, guild=ctx.guild)
    playing, content, pg, iterator, queueSize = "", "", 0, 0, 5
    page = page - 1

    if voice and voice.is_playing:
        playing = f"[{songQueue[ctx.guild][0]['title']}]({songQueue[ctx.guild][0]['webpage_url']})"
    else:
        await ctx.send("Nothing playing now", delete_after=10)

    if len(songQueue[ctx.guild]) > 1:
        for i in songQueue[ctx.guild][1:]:
            iterator += 1
            pg = iterator // queueSize + 1

            if page == iterator // queueSize:
                content += "\n".join([f" **{songQueue[ctx.guild].index(i)}:** [{i['title']}]({i['webpage_url']})\n"
                                      f"**Requested by:** {ctx.author.mention}   **Duration:** {i['duration']}\n"])
        if pg > 1:
            content += "\n".join([f"**Page:** {page + 1}/{pg}"])
    else:
        content = "No queued songs"

    embed = (discord.Embed(title="Music queue", color=embedColor)
             .add_field(name="Playing now: ", value=playing, inline=False)
             .add_field(name="Requested by", value=f"{ctx.author.mention}", inline=True)
             .add_field(name="Duration", value=songQueue[ctx.guild][0]['duration'], inline=True)
             .add_field(name="Queued: ", value=content, inline=False)
             .set_thumbnail(url=songQueue[ctx.guild][0]["thumbnail"]))

    await ctx.send(embed=embed)


# @bot.command(pass_context=True)
# async def volume(ctx, volume: int):
#     await ctx.channel.purge(limit=1)
#     voice = get(bot.voice_clients, guild=ctx.guild)
#     voice.volume = volume / 100
#     await ctx.send(f"Volume changed to {volume}%", delete_after=5)


@play.error
@repeat.error
@leave.error
@pause.error
@skip.error
@skipto.error
@queue.error
@settings.error
# @volume.error
async def errorHandler(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        print(error)
        await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Command requires argument", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("No such command", delete_after=5)
    elif isinstance(error, commands.ConversionError):
        await ctx.send("Sorry requested video can't be decoded, try one more time please", delete_after=5)
    elif isinstance(error, commands.TooManyArguments):
        await ctx.send("To many arguments, please check if everything is okey", delete_after=5)
    else:
        print("Error handler:", error)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    perms = discord.Permissions(permissions=8)
    invite_link = discord.utils.oauth_url(bot.user.id, permissions=perms)
    print(f"Use this link to add bot to your server: {invite_link}")

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


# bot.loop.create_task(update_stats())
bot.run(token)
