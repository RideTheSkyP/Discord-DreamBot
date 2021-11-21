import asyncio
from datetime import datetime
import requests
import youtube_dl
import discord
from discord.ext import commands
from discord.utils import get
import mysql.connector
import validators
from timeManager import TimeManager

# from player import Player

token = open("token.txt", "r").read()


# @commands.guild_only()
# @commands.check(audio_playing)
# @commands.check(in_voice_channel)

# Create class method
# def readCreds():
#     token = open("token.txt", "r").read()
#     ffmpegPathUrl = open("ffmpegPathUrl.txt", "r").read()
#     dbCreds = open("dbCreds.txt", "r").read().split(";")

# todo Write to database playlist states, etc
# todo launch player in threads [???]
# todo launch on_message with asyncio coroutine that can notify functions when event (command invoked)
# todo track command messages with on_message to remove rubbish
# todo add spotify player [???]
# todo extract direct url to youtube from [query] and link it with music title
# todo list a youtube playlist with choice indices on play command
# todo create channel [???]
# todo fix when music looped, bot must leave after everyone leaves channel
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


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.joined = 0
        self.messages = 0
        self.guildId = 0
        self.songIterator = 0
        self.skipToTime = 0
        self.songStartTime = datetime.now()
        self.repeatDeleteAfter, self.pauseDeleteAfter, self.skipDeleteAfter, self.volumeDeleteAfter = 5, 5, 25, 15
        self.loop = False
        self.playlistDisabled = False
        self.songQueue = {}
        self.musicTitles = {}
        self.message = {}
        self.embedColor = discord.Color.purple()
        self.ffmpegPathUrl = open("ffmpegPath.txt", "r").read()
        self.dbCreds = open("dbCreds.txt", "r").read().split(";")
        self.ydlOptions = {
            "format": "bestaudio",
            "noplaylist": self.playlistDisabled,
            "bitrate": 320000,
            # "quite": True,
            "encoding": "utf-8",
            "default_search": "auto",
            "ignoreerrors": False,
            "no-check-certificate": True,
            "socket_timeout": 10,
            "source_address": "0.0.0.0",
            "extractaudio": True,
            # "audioformat": "mp3",
            "extract_flat": False,
            "simulate": True,
            "prefer_ffmpeg": True,
            "ffmpeg_location": self.ffmpegPathUrl
        }
        self.ffmpegOptions = {
            "before_options": f"-ss {self.skipToTime} "
                              f"-reconnect 1 -reconnect_at_eof 1 "
                              f"-reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

    @commands.command(pass_context=True)
    async def join(self, ctx):
        await ctx.channel.purge(limit=1)
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            await channel.connect()

        await ctx.send(f"Joined {channel}", delete_after=5)

    @commands.command(pass_context=True, aliases=["LEAVE", "disconnect", "DISCONNECT"])
    async def leave(self, ctx):
        await ctx.channel.purge(limit=1)
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)
        self.songQueue[ctx.guild.id], self.musicTitles[ctx.guild.id] = [], []

        if voice and voice.is_connected():
            self.skipToTime = 0
            asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
            asyncio.run_coroutine_threadsafe(self.message[ctx.guild.id].delete(), bot.loop)
            self.loop = False
            await ctx.send(f"Left {channel}", delete_after=5)

    async def edit_message(self, ctx):
        currentSong = self.songQueue[ctx.guild.id][0]
        embed = (discord.Embed(title="Currently playing",
                               description=f"[{currentSong['title']}]({currentSong['webpage_url']})",
                               color=self.embedColor)
                 .add_field(name="Duration", value=TimeManager.parseDuration(currentSong["duration"]))
                 .add_field(name="Requested by", value=ctx.author.mention)
                 .add_field(name="Uploader", value=f"[{currentSong['uploader']}]({currentSong['channel_url']})")
                 .add_field(name="Queue", value="No song queued")
                 .set_thumbnail(url=currentSong["thumbnail"]))
        content = "\n".join([f"**{self.songQueue[ctx.guild.id].index(i)}:**"
                             f"[{i['title']}]({i['webpage_url']})\n**Requested by:** {ctx.author.mention} "
                             f"**Duration:** {TimeManager.parseDuration(i['duration'])}"
                             for i in self.songQueue[ctx.guild.id][1:5]]) if len(self.songQueue[ctx.guild.id]) > 1 \
            else "No songs are queued"
        embed.set_field_at(index=3, name="Queue", value=content, inline=False)

        if ctx.guild.id in self.message:
            await self.message[ctx.guild.id].edit(embed=embed)
        else:
            self.message[ctx.guild.id] = await ctx.send(embed=embed)

    async def search(self, ctx, url):
        with youtube_dl.YoutubeDL(self.ydlOptions) as ydl:
            try:
                requests.get(url)
            except:
                if len(url) > 0:
                    if validators.url(url[0]):
                        info = ydl.extract_info(url[0], download=False)
                    else:
                        info = ydl.extract_info(f"ytsearch:{' '.join(url)}", download=False)

            entries = enumerate(info["entries"]) if "_type" in info else [(0, info)]
            for i, entry in entries:
                if ctx.guild.id not in self.songQueue:
                    self.songQueue[ctx.guild.id] = [entry]
                    self.musicTitles[ctx.guild.id] = [entry["formats"][0]["url"]]
                    continue
                self.songQueue[ctx.guild.id].append(entry)
                self.musicTitles[ctx.guild.id].append(entry["formats"][0]["url"])

    @commands.command(pass_context=True, aliases=["PLAY", "p", "P"])
    async def play(self, ctx, *video: str):
        await self.search(ctx, video)
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

        if not voice.is_playing():
            self.songStartTime = datetime.now()
            self._playMusic(ctx, self.ffmpegPathUrl, self.musicTitles[ctx.guild.id][0])
            voice.is_playing()
            self.skipToTime = 0
        await self.edit_message(ctx)

    def playNext(self, ctx):
        voice = get(bot.voice_clients, guild=ctx.guild)
        if voice is None:
            del self.songQueue[ctx.guild.id]
            del self.musicTitles[ctx.guild.id]
            del self.message[ctx.guild.id]
        elif voice.is_connected():
            endTime = self.songStartTime - datetime.now()
            end = self.skipToTime
            self.ffmpegOptions["before_options"] = f"-ss {self.skipToTime} -reconnect 1 " \
                                                   f"-reconnect_at_eof 1 -reconnect_streamed 1 " \
                                                   f"-reconnect_delay_max 5"
            voice = get(bot.voice_clients, guild=ctx.guild)
            voice.is_paused()

            if self.loop is True:
                self.songQueue[ctx.guild.id].append(self.songQueue[ctx.guild.id][0])
                self.musicTitles[ctx.guild.id].append(self.musicTitles[ctx.guild.id][0])

            end += abs(int(endTime.total_seconds()))

            if len(self.songQueue[ctx.guild.id]) > 1 and len(self.musicTitles[ctx.guild.id]) > 1:
                del self.songQueue[ctx.guild.id][0], self.musicTitles[ctx.guild.id][0]

                if TimeManager.timeParse(self.songQueue[ctx.guild.id][0]["duration"]) <= end:
                    self.skipToTime = 0
                    voice.stop()

                asyncio.run_coroutine_threadsafe(self.edit_message(ctx), bot.loop)
                self.songStartTime = datetime.now()
                self._playMusic(ctx, self.ffmpegPathUrl, self.musicTitles[ctx.guild.id][0])
                voice.is_playing()
            else:
                del self.songQueue[ctx.guild.id]
                del self.musicTitles[ctx.guild.id]
                del self.message[ctx.guild.id]
                asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
                asyncio.run_coroutine_threadsafe(self.message[ctx.guild.id].delete(), bot.loop)
                self.loop = False

    def _playMusic(self, ctx, executable, source):
        voice = get(bot.voice_clients, guild=ctx.guild)
        voice.play(discord.FFmpegPCMAudio(executable=executable, source=source, **self.ffmpegOptions),
                   after=lambda e: self.playNext(ctx))

    @commands.command(pass_context=True, aliases=["REPEAT", "r", "R", "again", "AGAIN", "replay", "REPLAY"])
    async def repeat(self, ctx):
        await ctx.channel.purge(limit=1)
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)

        try:
            if voice and voice.is_connected():
                await voice.move_to(channel)
            else:
                voice = await channel.connect

            if voice.is_playing():
                self.songQueue[ctx.guild.id].insert(1, self.songQueue[ctx.guild.id][0])
                self.musicTitles[ctx.guild.id].insert(1, self.musicTitles[ctx.guild.id][0])
                voice.stop()
            else:
                await ctx.send("Nothing to repeat", delete_after=5)

            await ctx.send(f"Repeat requested by: {ctx.message.author}", delete_after=self.repeatDeleteAfter)
            await self.edit_message(ctx)
        except Exception as e:
            print("Repeat exc:", e)
            await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)

    @commands.command(pass_context=True, aliases=["LOOP", "l", "L"])
    async def loop(self, ctx):
        await ctx.channel.purge(limit=1)
        self.loop = False if self.loop else True
        await ctx.send(f"**Loop {'enabled' if self.loop else 'disabled'}**")

    @commands.command(pass_context=True, aliases=["PAUSE", "stop", "STOP", "resume", "RESUME", "shutup", "SHUTUP"])
    async def pause(self, ctx):
        await ctx.channel.purge(limit=1)
        voice = get(bot.voice_clients, guild=ctx.guild)

        if voice.is_connected():
            if voice.is_playing():
                await ctx.send("**Music paused**", delete_after=self.pauseDeleteAfter)
                voice.pause()
                voice.is_paused()
            else:
                await ctx.send("**Music resumed**", delete_after=self.pauseDeleteAfter)
                voice.resume()

    @commands.command(pass_context=True, aliases=["enableYTPlaylists", "EYTP", "eytp"])
    async def changeYoutubePlaylistsState(self, ctx):
        self.playlistDisabled = False if self.playlistDisabled else True
        self.ydlOptions["noplaylist"] = self.playlistDisabled
        await ctx.send(f"**Youtube playlists {'disabled' if self.playlistDisabled else 'enabled'}**",
                       delete_after=self.pauseDeleteAfter)

    @commands.command(pass_context=True, aliases=["SKIP", "s", "S"])
    async def skip(self, ctx, time="0"):
        skipped = 0
        requestTime = self.songStartTime - datetime.now()
        voice = get(bot.voice_clients, guild=ctx.guild)

        try:
            if int(time) == 0:
                await ctx.channel.purge(limit=1)
                if voice.is_playing():
                    await ctx.send("Track skipped", delete_after=self.skipDeleteAfter)
                    self.skipToTime = 0
                    voice.stop()
                else:
                    await ctx.send("Nothing is playing", delete_after=self.skipDeleteAfter)
            else:
                skipped += int(time) + abs(int(requestTime.total_seconds()))
                self.skipToTime += skipped
                await self.skipto(ctx, self.skipToTime)
        except:
            skipped += TimeManager.timeParse(time) + abs(int(requestTime.total_seconds()))
            self.skipToTime += skipped
            await self.skipto(ctx, self.skipToTime)

    @commands.command(pass_context=True, aliases=["SKIPTO", "st", "ST"])
    async def skipto(self, ctx, time):
        await ctx.channel.purge(limit=1)
        channel = ctx.message.author.voice.channel
        voice = get(bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect

        if voice.is_playing():
            self.songQueue[ctx.guild.id].insert(1, self.songQueue[ctx.guild.id][0])
            self.musicTitles[ctx.guild.id].insert(1, self.musicTitles[ctx.guild.id][0])
            self.skipToTime = TimeManager.timeParse(time)
            voice.stop()
        else:
            await ctx.send("Nothing to skip", delete_after=self.skipDeleteAfter)

        await ctx.send(
            f"**Skipped to:** {TimeManager.parseDuration(self.skipToTime)} **Requested by:** {ctx.message.author}",
            delete_after=self.skipDeleteAfter)
        await self.edit_message(ctx)

    @commands.command(pass_contex=True, aliases=["REMOVE", "rm", "RM"])
    async def remove(self, ctx, position: int):
        if self.songQueue[ctx.guild.id][position] and self.musicTitles[ctx.guild.id][position]:
            del self.songQueue[ctx.guild.id][position], self.musicTitles[ctx.guild.id][position]
        else:
            await ctx.send("No such music position in queue", delete_after=5)
        asyncio.run_coroutine_threadsafe(self.edit_message(ctx), bot.loop)

    def chooseEmbedColor(self, color):
        color = color.lower()
        embedTitle = f"Your new discord embeds color is *{color}*"
        colorDict = {"blue": discord.Color.blue(), "purple": discord.Color.purple(),
                     "blue-purple": discord.Color.blurple(),
                     "dark-blue": discord.Color.dark_blue(), "dark-gold": discord.Color.dark_gold(),
                     "dark-green": discord.Color.dark_green(), "dark-grey": discord.Color.dark_grey(),
                     "dark-magenta": discord.Color.dark_magenta(), "dark-orange": discord.Color.dark_orange(),
                     "dark-purple": discord.Color.dark_purple(), "dark-red": discord.Color.dark_red(),
                     "dark-teal": discord.Color.dark_teal(), "gold": discord.Color.gold(),
                     "green": discord.Color.green(),
                     "light-grey": discord.Color.light_grey(), "magenta": discord.Color.magenta(),
                     "orange": discord.Color.orange(), "red": discord.Color.red(), "teal": discord.Color.teal(),
                     "dark-theme": discord.Color.dark_theme()}

        if color in colorDict:
            self.embedColor = colorDict[color]
        else:
            embedTitle = f"No such color is presented, please choose something from *{commandPrefix}settings " \
                         f"embedColor*\nYour current embed color wasn't changed"
        return embedTitle

    @commands.command(pass_context=True, aliases=["SETTINGS", "set", "SET"])
    async def settings(self, ctx, task=None, *args):
        await ctx.channel.purge(limit=1)
        global commandPrefix

        if task is None:
            embed = discord.Embed(title=f"Settings command description", description=f"Command pattern is\n"
                                                                                     f"**{commandPrefix}settings "
                                                                                     f"[task]**"
                                                                                     f" **[argument]**",
                                  color=self.embedColor) \
                .add_field(name=f"{commandPrefix}settings commandPrefix [symbol]", value="Sets given symbol as command "
                                                                                         "prefix") \
                .add_field(name=f"{commandPrefix}settings embedColor", value=f"Prints all possible embed colors",
                           inline=False) \
                .add_field(name=f"{commandPrefix}settings embedColor [color]", value=f"Sets given color as embed color")
            await ctx.send(embed=embed)
        else:
            task = task.lower()
            match task:
                case "commandprefix":
                    if not args:
                        await ctx.send("Please give a prefix after [commandPrefix]", delete_after=5)
                    else:
                        commandPrefix = args[0]
                        bot.command_prefix = commandPrefix
                        await ctx.send(f"Your new command prefix is {args[0]}")
                case "embedcolor":
                    if not args:
                        await ctx.send(embed=discord.Embed(title=f"Possible colors are",
                                                           description=f"*blue\npurple\nred\norange\ngreen\nmagenta\n"
                                                                       f"teal\ngold\nblue-purple\nlight-grey\n"
                                                                       f"dark-blue\ndark-gold\ndark-green\n"
                                                                       f"dark-purple\ndark-grey\ndark-magenta\n"
                                                                       f"dark-orange\ndark-red\ndark-teal\n"
                                                                       f"dark-theme*\nUse command "
                                                                       f"__{commandPrefix}settings "
                                                                       f"embedColor dark-purple__ to set embeds "
                                                                       f"color",
                                                           color=self.embedColor))
                    else:
                        color = args[0].lower()
                        embedTitle = self.chooseEmbedColor(color)
                        embed = discord.Embed(title=embedTitle, color=self.embedColor)
                        await ctx.send(embed=embed)
                case "deleteafter":
                    if not args:
                        await ctx.send(embed=discord.Embed(title="Possible to set time in this commands",
                                                           description=f"Command pattern is "
                                                                       f"**{commandPrefix}settings** "
                                                                       f"**deleteAfter [command to set delete after "
                                                                       f"time] ** [seconds]**")
                                       .add_field(name="repeat", value="delete repeat command message")
                                       .add_field(name="pause", value="delete pause command message")
                                       .add_field(name="skip", value="delete skip command message")
                                       .add_field(name="volume", value="delete volume command message"))
                    else:
                        arg = args[0].lower()
                        match arg:
                            case "repeat":
                                try:
                                    self.repeatDeleteAfter = int(args[1])
                                except Exception as e:
                                    print(f"Settings repeat delete after exc: {e}")
                                    await ctx.send(f"Could not convert given value [{args[1]}] to the integer")
                                await ctx.send(f"Repeat command delete time had been set to "
                                               f"{self.repeatDeleteAfter} seconds")
                            case "pause":
                                try:
                                    self.repeatDeleteAfter = int(args[1])
                                except Exception as e:
                                    print(f"Settings pause delete after exc: {e}")
                                    await ctx.send(f"Could not convert given value [{args[1]}] to the integer")
                                await ctx.send(f"Pause command delete time had been set to "
                                               f"{self.pauseDeleteAfter} seconds")
                            case "skip":
                                try:
                                    self.repeatDeleteAfter = int(args[1])
                                except Exception as e:
                                    print(f"Settings skip delete after exc: {e}")
                                    await ctx.send(f"Could not convert given value [{args[1]}] to the integer")
                                await ctx.send(f"Skip command delete time had been set to "
                                               f"{self.skipDeleteAfter} seconds")
                            case "volume":
                                try:
                                    self.repeatDeleteAfter = int(args[1])
                                except Exception as e:
                                    print(f"Settings volume delete after exc: {e}")
                                    await ctx.send(f"Could not convert given value [{args[1]}] to the integer")
                                await ctx.send(f"Volume command delete time had been set to "
                                               f"{self.volumeDeleteAfter} seconds")
                            case _:
                                await ctx.send("No such command for delete after")

    def getInfo(self, query):
        with youtube_dl.YoutubeDL(self.ydlOptions) as ydl:
            try:
                requests.get(query)
                # async with aiohttp.ClientSession() as session:
                #     async with session.get(query) as r:
                #         info = r
            except:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
            else:
                info = ydl.extract_info(query, download=False)
        return info

    @commands.command(pass_context=True, aliases=["PLAYLIST", "pl", "PL"])
    async def playlist(self, ctx, task=None, title=None, *musicTitle):
        query = ""

        if task:
            task = task.lower()

        mySqlDB = mysql.connector.connect(
            host=self.dbCreds[0],
            user=self.dbCreds[1],
            password=self.dbCreds[2],
            database=self.dbCreds[3]
        )

        myCursor = mySqlDB.cursor()

        for word in musicTitle:
            query += f"{word} "

        if not task:
            embed = discord.Embed(title="Playlist commands description",
                                  description=f"The pattern of command is\n**{commandPrefix}playlist [task] "
                                              f"[playlist title] [music title]**", color=self.embedColor) \
                .add_field(name=f"{commandPrefix}playlist show", value=f"Shows server playlists", inline=False) \
                .add_field(name=f"{commandPrefix}playlist show [playlist title]",
                           value=f"Shows all tracks from playlist") \
                .add_field(name=f"{commandPrefix}playlist play [playlist title]",
                           value=f"Plays all tracks from playlist",
                           inline=False) \
                .add_field(name=f"{commandPrefix}playlist add [playlist title] [music]",
                           value=f"Adds music to playlist") \
                .add_field(name=f"{commandPrefix}playlist delete [playlist title]", value=f"Deletes playlist",
                           inline=False) \
                .add_field(name=f"{commandPrefix}playlist delete [playlist title] [music]",
                           value=f"Deletes song from playlist")
            await ctx.send(embed=embed)
        elif task == "play":
            if title:
                sqlQuery = "SELECT DISTINCT query FROM playlists WHERE guildId=%s AND playlistTitle=%s"
                values = (ctx.guild.id, title)
                myCursor.execute(sqlQuery, values)
                records = myCursor.fetchall()
                for row in records:
                    await self.play(ctx, row[0])
            else:
                await ctx.send("Please decide which playlist to play")
                await self.playlist(ctx, "show")
        elif task == "show":
            if not title:
                playlists = ""
                sqlQuery = "SELECT DISTINCT playlistTitle FROM playlists WHERE guildId=%s"
                values = (ctx.guild.id,)
                myCursor.execute(sqlQuery, values)
                records = myCursor.fetchall()
                for row in records:
                    playlists += f"*{row[0]}*\n"
                embed = discord.Embed(title="Server playlists", description=f"{playlists}", color=self.embedColor)
                await ctx.send(embed=embed)
            else:
                songs = ""
                sqlQuery = "SELECT DISTINCT query FROM playlists WHERE guildId=%s AND playlistTitle=%s"
                values = (ctx.guild.id, title)
                myCursor.execute(sqlQuery, values)
                records = myCursor.fetchall()
                for row in records:
                    songs += f"{row[0]}\n"
                embed = discord.Embed(title=f"*{title}* playlist music", description=f"{songs}", color=self.embedColor)
                await ctx.send(embed=embed)
        elif task == "add":
            tags = ""
            sqlQuery = "SELECT DISTINCT playlistTitle FROM playlists WHERE guildId=%s"
            values = (ctx.guild.id,)
            myCursor.execute(sqlQuery, values)
            playlistsAmount = myCursor.fetchall()

            if len(playlistsAmount) < 3:
                sqlQuery = "SELECT DISTINCT query FROM playlists WHERE guildId=%s AND playlistTitle=%s"
                values = (ctx.guild.id, title)
                myCursor.execute(sqlQuery, values)
                songsAmount = myCursor.fetchall()

                if len(songsAmount) < 20:
                    info = self.getInfo(query)

                    if info["tags"] is not None:
                        for tag in info["tags"]:
                            if len(tags) < 200:
                                tags += f"{tag} "

                    sqlQuery = "INSERT INTO playlists (guildId, playlistTitle, query, genre) VALUES (%s, %s, %s, %s)"
                    values = (ctx.guild.id, title, query, tags)
                    myCursor.execute(sqlQuery, values)
                    mySqlDB.commit()
                    await ctx.send(f"Song {query} has been added to playlist {title}")
                else:
                    await ctx.send(f"Max amount of songs is 20")
            else:
                await ctx.send("Max amount of playlists is 3")
        elif task == "delete":
            if not music:
                sqlQuery = "DELETE FROM playlists WHERE guildId=%s AND playlistTitle=%s LIMIT 1"
                values = (ctx.guild.id, title)
                myCursor.execute(sqlQuery, values)
                mySqlDB.commit()
                await ctx.send(f"Playlist *{title}* is deleted")
            else:
                sqlQuery = "DELETE FROM playlists WHERE guildId=%s AND playlistTitle=%s AND query=%s LIMIT 1"
                values = (ctx.guild.id, title, query)
                myCursor.execute(sqlQuery, values)
                mySqlDB.commit()
                await ctx.send(f"From playlist *{title}* is deleted {query}")
        else:
            await ctx.send("No such command")

    @commands.command(pass_context=True, aliases=["HELP", "h", "H"])
    async def help(self, ctx):
        await ctx.channel.purge(limit=1)
        embed = discord.Embed(title="Help", description="Commands", color=self.embedColor) \
            .add_field(name=f"*{commandPrefix}hello*", value="Greets the user", inline=True) \
            .add_field(name=f"*{commandPrefix}users*", value="Prints number of users on server", inline=True) \
            .add_field(name=f"*{commandPrefix}join*", value="Bot will join voice channel", inline=True) \
            .add_field(name=f"*{commandPrefix}leave*", value="Bot will leave voice channel", inline=True) \
            .add_field(name=f"*{commandPrefix}skip*", value="Plays next track", inline=True) \
            .add_field(name=f"*{commandPrefix}play*", value="Request music with url or song title", inline=True) \
            .add_field(name=f"*{commandPrefix}skip 1:20 or 20*", value="Skips 1 minute 20 seconds of the song or 20 "
                                                                       "seconds, hh:mm:ss format", inline=False) \
            .add_field(name=f"*{commandPrefix}skipto 1:20 or 20*",
                       value="Song starts playing at this exact time, e.g at 1 "
                             "minute 20 seconds or 20 seconds, hh:mm:ss format"
                       , inline=False) \
            .add_field(name=f"*{commandPrefix}pause*", value="Pauses music", inline=True) \
            .add_field(name=f"*{commandPrefix}replay*", value="Repeats the track", inline=True) \
            .add_field(name=f"*{commandPrefix}queue*", value="Shows queue", inline=True) \
            .add_field(name=f"*{commandPrefix}settings*", value=f"Shows all settings commands") \
            .add_field(name=f"*{commandPrefix}playlist*", value=f"Shows all playlist commands") \
            .add_field(name=f"*{commandPrefix}extendedhelp*\t\t\t\t\t\t*{commandPrefix}aliases*",
                       value="Shows all aliases and some useful information", inline=False) \
            .add_field(name=f"*{commandPrefix}remove*", value=f"Removes song from queue, with given position",
                       inline=False) \
            .add_field(name="CAPS LOCK", value="You can ignore register and use bot with enabled CAPS LOCK",
                       inline=False) \
            .add_field(name=f"*{commandPrefix}enableYTPlaylists*",
                       value=f"Enables/Disables youtube playlists",
                       inline=True)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, aliases=["EXTENDEDHELP", "eh", "Eh", "aliases", "ALIASES"])
    async def extendedhelp(self, ctx):
        await ctx.channel.purge(limit=1)
        embed = discord.Embed(title="Help", description="Extended help commands and aliases", color=self.embedColor) \
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
                       value=f'Aliases are: "**{commandPrefix}REPEAT**", "**{commandPrefix}r**", '
                             f'"**{commandPrefix}R**", "**{commandPrefix}again**", "**{commandPrefix}AGAIN**", '
                             f'"**{commandPrefix}replay**", "**{commandPrefix}REPLAY**"', inline=False) \
            .add_field(name=f"*{commandPrefix}remove*",
                       value=f'Aliases are: "**{commandPrefix}REMOVE**", "**{commandPrefix}rm**", '
                             f'"**{commandPrefix}RM**"',
                       inline=False) \
            .add_field(name=f"*{commandPrefix}skip*",
                       value=f'Aliases are: "**{commandPrefix}SKIP**", "**{commandPrefix}s**", "**{commandPrefix}S**"',
                       inline=False) \
            .add_field(name=f"*{commandPrefix}skipto*",
                       value=f'Aliases are: "**{commandPrefix}SKIPTO**", "**{commandPrefix}st**", '
                             f'"**{commandPrefix}ST**"',
                       inline=False) \
            .add_field(name=f"*{commandPrefix}settings*",
                       value=f'Aliases are: "**{commandPrefix}SETTINGS**", "**{commandPrefix}set**", '
                             f'"**{commandPrefix}SET**"', inline=False) \
            .add_field(name=f"*{commandPrefix}playlist*",
                       value=f'Aliases are: "**{commandPrefix}PLAYLIST**", "**{commandPrefix}pl**", '
                             f'"**{commandPrefix}PL**"', inline=False) \
            .add_field(name=f"*{commandPrefix}enableYTPlaylists*",
                       value=f'Aliases are: "**{commandPrefix}EYTP**", "**{commandPrefix}eytp**"',
                       inline=False) \
            .add_field(name=f"*{commandPrefix}extendedhelp*",
                       value=f'Aliases are: "**{commandPrefix}EXTENDEDHELP**", "**{commandPrefix}eh**", '
                             f'"**{commandPrefix}EH**", "**{commandPrefix}aliases**", "**{commandPrefix}ALIASES**"',
                       inline=False) \
            .add_field(name="Issues", value=f'If bot stuck at voice channel, use command "**{commandPrefix}leave**" it '
                                            f'will clear cache also you can disconnect bot from voice chat and then '
                                            f'test with "**{commandPrefix}join**" command', inline=False)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True)
    async def hello(self, ctx):
        await ctx.send(f"Hi {ctx.author}. Your server id is {ctx.guild.id}")

    @commands.command(pass_context=True)
    async def users(self, ctx):
        await ctx.send(f"Number of users on server: {ctx.guild.member_count}")

    @commands.command(pass_context=True, aliases=["QUEUE", "q", "Q"])
    async def queue(self, ctx, page=1):
        await ctx.channel.purge(limit=1)
        voice = get(bot.voice_clients, guild=ctx.guild)
        playing, content, pg, iterator, queueSize = "", "", 0, 0, 5
        page = page - 1

        if voice and voice.is_playing:
            playing = f"[{self.songQueue[ctx.guild.id][0]['title']}]({self.songQueue[ctx.guild.id][0]['webpage_url']})"
        else:
            await ctx.send("Nothing playing", delete_after=10)

        if len(self.songQueue[ctx.guild.id]) > 1:
            for i in self.songQueue[ctx.guild.id][1:]:
                iterator += 1
                pg = iterator // queueSize + 1

                if page == iterator // queueSize:
                    content += "\n".join(
                        [f" **{self.songQueue[ctx.guild.id].index(i)}:** [{i['title']}]({i['webpage_url']})\n"
                         f"**Requested by:** {ctx.author.mention}   "
                         f"**Duration:** {TimeManager.parseDuration(i['duration'])}\n"])
            if pg > 1:
                content += "\n".join([f"**Page:** {page + 1}/{pg}"])
        else:
            content = "No queued songs"

        embed = (discord.Embed(title="Music queue", color=self.embedColor)
                 .add_field(name="Playing now: ", value=playing, inline=False)
                 .add_field(name="Requested by", value=f"{ctx.author.mention}", inline=True)
                 .add_field(name="Duration",
                            value=TimeManager.parseDuration(self.songQueue[ctx.guild.id][0]['duration']),
                            inline=True)
                 .add_field(name="Queued: ", value=content, inline=False)
                 .set_thumbnail(url=self.songQueue[ctx.guild.id][0]["thumbnail"]))
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, aliases=["VOLUME", "vol", "VOL"])
    async def volume(self, ctx, volume: int):
        await ctx.channel.purge(limit=1)
        voice = get(bot.voice_clients, guild=ctx.guild)
        voice.source = discord.PCMVolumeTransformer(voice.source)
        voice.source.volume = volume / 100
        await ctx.send(f"Volume changed to {volume}%", delete_after=self.volumeDeleteAfter)

    @play.error
    @repeat.error
    @leave.error
    @pause.error
    @skip.error
    @skipto.error
    @queue.error
    @settings.error
    @playlist.error
    @remove.error
    @volume.error
    async def errorHandler(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send("You're not connected to the voice channel or nothing playing now", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Command requires additional info", delete_after=5)
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send("No such command", delete_after=5)
        elif isinstance(error, commands.ConversionError):
            await ctx.send("Sorry, requested video can't be decoded, try one more time please", delete_after=5)
        elif isinstance(error, commands.TooManyArguments):
            await ctx.send("Too many arguments, please check if everything is okay", delete_after=5)
        elif isinstance(error, ValueError):
            await ctx.send("Please enter correct value", delete_after=5)
        else:
            print("Error handler:", error)

    async def clearDatabase(self):
        guilds = []
        await bot.wait_until_ready()

        for guildId in bot.guilds:
            guilds.append(guildId.id)

        while not bot.is_closed():
            try:
                mySqlDB = mysql.connector.connect(
                    host=self.dbCreds[0],
                    user=self.dbCreds[1],
                    password=self.dbCreds[2],
                    database=self.dbCreds[3]
                )

                myCursor = mySqlDB.cursor()
                sqlQuery = "SELECT DISTINCT guildId FROM playlists"
                myCursor.execute(sqlQuery)
                records = myCursor.fetchall()
                for guild in records:
                    if int(guild[0]) not in guilds:
                        sqlQuery = "DELETE FROM playlists WHERE guildId=%s"
                        values = (guild[0],)
                        myCursor.execute(sqlQuery, values)
                        mySqlDB.commit()
                await asyncio.sleep(86400)
            except Exception as e:
                print("Clear database exc: ", e)


commandPrefix = "."
bot = commands.Bot(command_prefix=commands.when_mentioned_or(commandPrefix))
bot.remove_command("help")


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}.")
    perms = discord.Permissions(permissions=8)
    inviteLink = discord.utils.oauth_url(bot.user.id, permissions=perms)
    print(f"Use this link to add bot to your server: {inviteLink}")

    activity = discord.Game(name=f"{commandPrefix}help", type=3)
    await bot.change_presence(activity=activity)

    for guild in bot.guilds:
        print(f"{bot.user} is connected to the following guild: {guild.name}. Guild id: {guild.id}")


# @bot.event
# async def on_member_update(before, after):
#     nickname = after.nick
#     if nickname:
#         if nickname.lower().count("dream") > 0:
#             lastNickname = before.nick
#             if lastNickname:
#                 await after.edit(nick=lastNickname)
#             else:
#                 await after.edit(nick="Nickname dream is reserved by bot, please change your role or nickname")


# todo join, rejoin, wait after everyone leaves, leave after no one mentions for some time || task ended
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

# @bot.event
# async def on_server_join():
#     pass

if __name__ == "__main__":
    bot.add_cog(Music(bot))
    music = Music(bot)
    bot.loop.create_task(music.clearDatabase())
    # bot.loop.create_task(update_stats())
    bot.run(token)
