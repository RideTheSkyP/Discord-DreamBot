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
    # 'bitrate': 320000,
    'encoding': 'utf-8',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'socket_timeout': 5,
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
    'before_options': f'-reconnect 1 -reconnect_at_eof 1 '
                      f'-reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -sn -dn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# TODO ADD SEARCH BUTTON
# TODO DISCONNECT IF CHANNEL IS EMPTY


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.original_url = data.get('original_url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class MusicView(discord.ui.View):
    def __init__(self, bot, cog, embed_message=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.embed_message = embed_message

    @discord.ui.button(emoji='📝', label='Queue', style=discord.ButtonStyle.primary, custom_id='queue_button')
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('queue button')
        await self.cog.queue_command(interaction, button)

    @discord.ui.button(emoji='⏯️', label='(Un)pause', style=discord.ButtonStyle.primary, custom_id='pause_button')
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('pause button')
        await self.cog.pause(interaction, button)

    @discord.ui.button(emoji='⏭️', label='Skip', style=discord.ButtonStyle.primary, custom_id='skip_button')
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('skip button')
        await self.cog.skip(interaction, button)

    @discord.ui.button(emoji='🔄', label='Loop', style=discord.ButtonStyle.primary, custom_id='loop_button')
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.loop(interaction, button)

    @discord.ui.button(emoji='🔁', label='Repeat', style=discord.ButtonStyle.primary, custom_id='repeat_button')
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.repeat(interaction, button)

    @discord.ui.button(emoji='❎', label='Remove from queue', style=discord.ButtonStyle.primary, custom_id='remove_button')
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.remove_from_queue(interaction, button)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.loop_state = {}
        self.embed_messages = {}
        self.currently_playing = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if the bot is the one being disconnected
        if member == self.bot.user:
            if before.channel is not None and after.channel is None:
                guild_id = member.guild.id
                self.loop_state.pop(guild_id, None)
                self.queue.pop(guild_id, None)
                self.embed_messages.pop(guild_id, None)
                self.currently_playing.pop(guild_id, None)
                print(f'[{member.guild.name}|{before.channel.name}] Bot has been disconnected from {before.channel}')

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
            await interaction.response.send_message(f'Joined **{interaction.user.voice.channel.name}** voice channel', ephemeral=True)

    @app_commands.command(name='leave', description='Make the bot leave the voice channel it is in')
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
            del self.queue[interaction.guild.id]
            await interaction.response.send_message('Left voice channel', ephemeral=True)
        else:
            await interaction.response.send_message('Bot is not in a voice channel', ephemeral=True)

    @staticmethod
    async def parse_duration(duration):
        min, sec = divmod(duration, 60)
        return f'{min}:{sec} min' if min else f'{sec} sec'

    async def edit_embed_message(self, interaction, player):
        print('create_player_embed', player.data.keys())
        duration = await self.parse_duration(player.duration)
        embed = discord.Embed(
            title='Playing',
            description=f'[{player.title}]({player.original_url})\n'
                        f'Duration: {duration}',
            color=discord.Color.blurple()
        )
        print('embed', embed)
        embed.set_thumbnail(url=player.thumbnail)
        print('set_thumbnail', embed)
        view = MusicView(self.bot, self)
        print('view', view)
        guild_id = interaction.guild.id
        if guild_id in self.embed_messages:
            print('Already exist message')
            await self.embed_messages.get(guild_id).edit(embed=embed, view=view)
        else:
            print('Create new message')
            self.embed_messages[guild_id] = await interaction.followup.send(embed=embed, view=view)

    async def _add_to_song_queue(self, guild_id, player):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        self.queue.get(guild_id).append(player)
        print('_add_to_song_queue', self.queue)

    async def play_next(self, voice_client, interaction):
        print('Play next called')
        guild_id = voice_client.guild.id
        if self.loop_state.get(guild_id):
            await self._add_to_song_queue(guild_id, self.currently_playing.get(guild_id))
        if guild_id in self.queue and self.queue.get(guild_id):
            player = await YTDLSource.from_url(self.queue.get(guild_id).pop(0), loop=self.bot.loop)
            voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(voice_client, interaction)) if e is None else print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Player error: {e}'))
            await self.edit_embed_message(interaction, player)
            print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Now playing next song in queue: {player.title}')
        else:
            if voice_client.is_connected() and not (voice_client.is_playing() or voice_client.is_paused()):
                await voice_client.disconnect()
            else:
                await asyncio.sleep(150)

    async def _play(self, player, interaction: discord.Interaction):
        print('_play', player.title)
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        try:
            if self.loop_state.get(guild_id):
                await self._add_to_song_queue(guild_id, self.currently_playing.get(guild_id))
            print('play', [player for player in self.queue.get(interaction.guild.id)])
            voice_client.play(player, after=lambda e: self.bot.loop.create_task(self.play_next(voice_client, interaction)))
            self.currently_playing[interaction.guild.id] = player.title
            await self.edit_embed_message(interaction, player)
            print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Playing: {player.title}')
        except Exception as e:
            print(f'Exception: {e}')
            await interaction.followup.send(f'Error occurred: {e}')

    @app_commands.command(name='play', description='Play music from query or url')
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        await self._join(interaction)
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        player = await YTDLSource.from_url(query, loop=self.bot.loop)
        await self._add_to_song_queue(guild_id, player.title)
        if voice_client.is_playing() or voice_client.is_paused():
            print('connected', player.title)
            # await interaction.followup.send(f'Added {player.title} to the queue', ephemeral=True)
            await interaction.delete_original_response()
            print(f'[{voice_client.guild.name}|{voice_client.channel.name}] Added {player.title} to the queue')
        else:
            current_music_title = self.queue.get(guild_id).pop(0)
            self.currently_playing[guild_id] = current_music_title
            await self._play(player, interaction)

    @staticmethod
    async def _change_button_style(button: discord.ui.Button):
        if button.style == discord.ButtonStyle.primary:
            button.style = discord.ButtonStyle.secondary
        else:
            button.style = discord.ButtonStyle.primary
        print('_change_button_style', button.style)
        return button

    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('pause called')
        voice_client = interaction.guild.voice_client
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)
        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message('Paused', delete_after=5)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message('Resumed', delete_after=5)

    @staticmethod
    async def _pause_if_playing(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message('Bot is not connected to the voice channel', delete_after=5)
            return False
        if voice_client.is_playing():
            print('is playing')
            voice_client.pause()
        return True

    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('skip called')
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if not await self._pause_if_playing(interaction):
            return False
        print('self.queue.get(guild_id)', [player for player in self.queue.get(guild_id)])
        await interaction.response.defer()
        if self.queue.get(guild_id):
            print('in', self.queue.get(guild_id))
            player = await YTDLSource.from_url(self.queue.get(guild_id).pop(0), loop=self.bot.loop)
            print('player in skip called')
            await self._play(player, interaction)
        else:
            await voice_client.disconnect(force=True)
            await interaction.followup.send(f'Nothing to play, disconnecting', ephemeral=True)

    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        if not await self._pause_if_playing(interaction):
            return False
        await interaction.response.defer()
        print('in', self.queue.get(guild_id))
        player = await YTDLSource.from_url(self.currently_playing.get(guild_id), loop=self.bot.loop)
        print('player in repeat called')
        await self._play(player, interaction)
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)

    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.loop_state[interaction.guild.id] = False if self.loop_state.get(interaction.guild.id) else True
        print('loop called', self.loop_state)
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)
        await interaction.response.send_message(f'Loop {"enabled" if self.loop_state[interaction.guild.id] else "disabled"}', delete_after=10)

    async def queue_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)
        if button.style == discord.ButtonStyle.primary:
            embed = interaction.message.embeds[0].clear_fields()
        else:
            for index, music in enumerate(self.queue.get(interaction.guild.id)):
                interaction.message.embeds[0].add_field(name=music, value='', inline=False)
            embed = interaction.message.embeds[0]
        await interaction.message.edit(embed=embed)
        print('Done')

    async def remove_from_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)

    async def skip_to(self, interaction: discord.Interaction, button: discord.ui.Button):
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)


async def setup(bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
