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
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    # 'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}
# # yt_opts = { 'format': 'best[ext=mp4]', 'download_ranges': download_range_func(None, [(start_time, end_time)]), 'force_keyframes_at_cuts': True, }
# #         self.ffmpegOptions = {
# #             "before_options": f"-ss {self.skipToTime} "
# #                               f"-reconnect 1 -reconnect_at_eof 1 "
# #                               f"-reconnect_streamed 1 -reconnect_delay_max 5",
# #             "options": "-vn"
# #         }

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
        print('loop', loop)
        print('data', data)
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        print('filename', filename)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     print("Syncing Bot Tree")
    #     await self.bot.tree.sync()

    async def _join(self, interaction: discord.Interaction):
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
            await interaction.response.send_message('Disconnected from the voice channel.', ephemeral=True)
        else:
            await interaction.response.send_message('I am not in a voice channel.', ephemeral=True)

    @app_commands.command(name='play', description='Make the bot play music from query or url')
    async def play(self, interaction: discord.Interaction, query: str):
        """Plays from a url (almost anything youtube_dl supports)"""
        await interaction.response.defer()
        await self._join(interaction)
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        print('query', query)
        player = await YTDLSource.from_url(query, loop=self.bot.loop)
        print('player', player)
        print('voice_client', dir(voice_client))
        print('vars', voice_client)
        try:
            if voice_client or self.queue.get(guild_id):
                if guild_id not in self.queue:
                    self.queue[guild_id] = []
                self.queue[guild_id].append(player)
                await interaction.followup.send(f'Added {player.title} to the queue', ephemeral=False)
            else:
                # if guild_id not in self.played_songs:
                #     self.played_songs[guild_id] = deque()
                voice_client.play(player)
            print('player', player)
        except Exception as e:
            print(f'Exception: {e}')
            await interaction.response.send_message(f'Error occurred: {e}')

        # voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        await interaction.response.send_message(f'Now playing: {player.title}')


async def setup(bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
