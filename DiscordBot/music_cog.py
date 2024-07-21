import yt_dlp
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
#
# # Suppress noise about console usage from errors
# # yt_dlp.utils.bug_reports_message = lambda: ''
#
# print('music_cog')
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'bitrate': 320000,
    'encoding': 'utf-8',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'socket_timeout': 10,
    'ignoreerrors': False,
    'logtostderr': False,
    'extract_flat': False,
    # 'simulate': True,
    'prefer_ffmpeg': True,
    'quiet': True,
    # 'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

# yt_opts = { 'format': 'best[ext=mp4]', 'download_ranges': download_range_func(None, [(start_time, end_time)]), 'force_keyframes_at_cuts': True, }
#         self.ffmpegOptions = {
#             "before_options": f"-ss {self.skipToTime} "
#                               f"-reconnect 1 -reconnect_at_eof 1 "
#                               f"-reconnect_streamed 1 -reconnect_delay_max 5",
#             "options": "-vn"
#         }

ffmpeg_options = {
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.embed_messages = {}

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     print("Syncing Bot Tree")
    #     await self.bot.tree.sync()

    @staticmethod
    async def _join(interaction: discord.Interaction):
        voice = interaction.user.voice
        if voice is None or voice.channel is None:
            await interaction.response.send_message('You are not connected to a voice channel.', ephemeral=True)
            return None
        channel = voice.channel
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        return True

    @app_commands.command(name='join', description='Make the bot join the voice channel you are in')
    async def join(self, interaction: discord.Interaction):
        if await self._join(interaction):
            await interaction.response.send_message(f'Joined **{interaction.user.voice.channel.name}** voice channel',
                                                    ephemeral=True)

    @app_commands.command(name='leave', description='Make the bot leave the voice channel it is in')
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
            del self.queue[interaction.guild.id]
            await interaction.response.send_message('Left voice channel', ephemeral=True)
        else:
            await interaction.response.send_message('Bot is not in a voice channel', ephemeral=True)

    def edit_embed_message(self):
        pass

    def _add_to_song_queue(self, guild_id, player):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        self.queue[guild_id].append(player)

    async def play_next(self, voice_client):
        guild_id = voice_client.guild.id
        if guild_id in self.queue and self.queue[guild_id]:
            player = self.queue[guild_id].pop(0)
            voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(voice_client)) if e is None else print(f'[{voice_client.guild.name}/{voice_client.channel.name}] Player error: {e}'))
            print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Now playing next song in queue: {player.title}')
            # await self.update_player_embed(guild_id, player)
        else:
            if not voice_client.is_connected() and not (voice_client.is_playing() or voice_client.is_paused()):
                await asyncio.sleep(150)
                if not self.queue.get(guild_id) and voice_client.is_connected() and not (voice_client.is_playing() or voice_client.is_paused()):
                    # if guild_id in self.current_embed_messages:
                    #     try:
                    #         await self.current_embed_messages[guild_id].delete()
                    #     except discord.errors.NotFound:
                    #         pass  # Handle case where message is already deleted or doesn't exist
                    await voice_client.disconnect()

    async def _play(self, player, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        try:
            if voice_client.is_playing() or voice_client.is_paused():
                print('connected')
                await interaction.followup.send(f'Added {player.title} to the queue')
                print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Added {player.title} to the queue')
            else:
                print('play')
                voice_client.play(self.queue[guild_id].pop(0), after=lambda e: self.bot.loop.create_task(self.play_next(voice_client)))
                print('created', dir(interaction.followup))
                await interaction.followup.send(f'Playing: {player.title}')
                print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Playing: {player.title}')
        except Exception as e:
            print(f'Exception: {e}')
            await interaction.followup.send(f'Error occurred: {e}')

    @app_commands.command(name='play', description='Play music from query or url')
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._join(interaction)
        guild_id = interaction.guild.id
        player = await YTDLSource.from_url(query, loop=self.bot.loop)
        self._add_to_song_queue(guild_id, player)
        await self._play(player, interaction)

    @app_commands.command(name='pause', description='Pause or unpause current music')
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message('Paused', delete_after=5)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message('Resumed', delete_after=5)

    @app_commands.command(name='skip', description='Skip current music')
    async def skip(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name='loop', description='Loop current queue')
    async def loop(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name='remove', description='Removes chosen music from queue')
    async def remove_from_queue(self, interaction: discord.Interaction):
        pass


async def setup(bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
