import yt_dlp
import asyncio
import discord
from discord import app_commands, WebhookMessage
from discord.ext import commands

# Suppress noise about console usage from errors
# yt_dlp.utils.bug_reports_message = lambda: ''

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
# TODO Handle age restricted videos
# TODO Queue max 25 fields/paging
# TODO leave on pause timeout


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.url = data.get('url')
        self.title = data.get('title')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.original_url = data.get('original_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class MusicView(discord.ui.View):
    def __init__(self, bot, cog, embed_message=None, button_styles=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.embed_message = embed_message
        self.button_styles = button_styles or {}
        for name, button in self.__dict__.items():
            if isinstance(button, discord.ui.Button):
                button.style = self._get_button_style(button.custom_id)

    def _get_button_style(self, custom_id):
        return self.button_styles.get(custom_id, discord.ButtonStyle.primary)

    @discord.ui.button(emoji='📝', label='Queue', style=discord.ButtonStyle.primary, custom_id='queue_button', row=0)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('queue button')
        await self.cog.queue_command(interaction, button)

    @discord.ui.button(emoji='⏯️', label='(Un)pause', style=discord.ButtonStyle.primary, custom_id='pause_button', row=0)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('pause button')
        await self.cog.pause(interaction, button)

    @discord.ui.button(emoji='⏭️', label='Skip', style=discord.ButtonStyle.primary, custom_id='skip_button', row=0)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('skip button')
        await self.cog.skip(interaction, button)

    @discord.ui.button(emoji='🔄', label='Loop', style=discord.ButtonStyle.primary, custom_id='loop_button', row=0)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.loop(interaction, button)

    @discord.ui.button(emoji='🔁', label='Repeat', style=discord.ButtonStyle.primary, custom_id='repeat_button', row=1)
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.repeat(interaction, button)

    @discord.ui.button(emoji='❎', label='Remove from queue', style=discord.ButtonStyle.primary, custom_id='remove_button', row=1)
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.remove_from_queue(interaction, button)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.loop_state = {}
        self.embed_messages = {}
        self.playlist_state = {}
        self.currently_playing = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        guild_id = guild.id
        voice_client = guild.voice_client
        voice_channel_members_len = len(voice_client.channel.members)
        if member == self.bot.user or (voice_channel_members_len == 1 and voice_client.channel.members[0] == self.bot.user):
            # Check if the bot is the one being disconnected
            if before.channel is not None and after.channel is None:
                await self._clear_guild_info(guild_id)
                print(f'[{member.guild.name}|{before.channel.name}] Bot has been disconnected from {before.channel}')
            # Check if the bot was 1 left in channel
            elif before.channel is not None and after.channel is not None:
                await voice_client.disconnect()
                await self._clear_guild_info(guild_id)

    async def _clear_guild_info(self, guild_id):
        self.loop_state.pop(guild_id, None)
        self.queue.pop(guild_id, None)
        self.embed_messages.pop(guild_id, None)
        self.currently_playing.pop(guild_id, None)

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
            await interaction.response.send_message('Left voice channel', ephemeral=True)
        else:
            await interaction.response.send_message('Bot is not in a voice channel', ephemeral=True)

    def _prepare_button_styles_dict_for_guild(self, guild_id):
        if self.loop_state.get(guild_id):
            return {"loop_button": discord.ButtonStyle.secondary}
        return None

    @staticmethod
    async def parse_duration(duration):
        min, sec = divmod(duration, 60)
        return f'{min}:{sec} min' if min else f'{sec} sec'

    async def edit_embed_message(self, interaction, player):
        print("edit_embed_message", interaction, player)
        guild_id = interaction.guild.id
        duration = await self.parse_duration(player.duration)
        embed = discord.Embed(
            title='Playing',
            description=f'[{player.title}]({player.original_url})\n'
                        f'Duration: {duration}',
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=player.thumbnail)
        button_styles = self._prepare_button_styles_dict_for_guild(guild_id)
        view = MusicView(self.bot, self, button_styles=button_styles)
        if guild_id in self.embed_messages:
            await self.embed_messages.get(guild_id).edit(embed=embed, view=view)
        else:
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
    async def _change_button_style(button: discord.ui.Button, change_to_secondary_style=False):
        print("_change_button_style", button)
        if button.style == discord.ButtonStyle.primary or change_to_secondary_style:
            button.style = discord.ButtonStyle.secondary
        else:
            button.style = discord.ButtonStyle.primary
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
    async def _pause_state_control(interaction: discord.Interaction):
        print("_pause_state_control")
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
        if not await self._pause_state_control(interaction):
            return False
        await interaction.response.defer()
        queue = self.queue.get(guild_id)
        print("queue", queue)
        print("self.loop_state.get(guild_id)", self.loop_state.get(guild_id))
        if not queue and not self.loop_state.get(guild_id):
            await voice_client.disconnect(force=True)
            await interaction.followup.send(f'Nothing to play, disconnecting', ephemeral=True)
            return None
        elif not queue and self.loop_state.get(guild_id):
            self.queue[guild_id] = [self.currently_playing.get(guild_id)]
        print('in', self.queue.get(guild_id))
        player = await YTDLSource.from_url(self.queue.get(guild_id).pop(0), loop=self.bot.loop)
        print('player in skip called')
        await self._play(player, interaction)
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)
        # else:


    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        if not await self._pause_state_control(interaction):
            return False
        await interaction.response.defer()
        print('in', self.queue.get(guild_id))
        player = await YTDLSource.from_url(self.currently_playing.get(guild_id), loop=self.bot.loop)
        print('player in repeat called')
        await self._play(player, interaction)
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)

    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        self.loop_state[guild_id] = False if self.loop_state.get(guild_id) else True
        print('loop called', self.loop_state)
        print(self.embed_messages.get(interaction.guild.id).id)
        print(self.embed_messages.get(interaction.guild.id).channel)
        print(dir(self.embed_messages.get(interaction.guild.id)))
        button = await self._change_button_style(button)
        print(button)
        await interaction.response.edit_message(view=button.view)
        await interaction.message.send(f'Loop {"enabled" if self.loop_state[interaction.guild.id] else "disabled"}', delete_after=10)

    async def queue_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('queue command')
        try:
            button = await self._change_button_style(button)
            print('button', button, dir(button), button.view, dir(button.view))
            await interaction.response.edit_message(view=button.view)
            print('edited')
            if button.style == discord.ButtonStyle.primary:
                embed = interaction.message.embeds[0].clear_fields()
            else:
                for index, music in enumerate(self.queue.get(interaction.guild.id)):
                    interaction.message.embeds[0].add_field(name=f'{index}: {music}', value='', inline=False)
                embed = interaction.message.embeds[0]
            print('q embed', embed, dir(embed))
            await interaction.followup.edit_message(message_id=self.embed_messages.get(interaction.guild.id).id, embed=embed)
            print('qc done')
        except Exception as e:
            print(f'Error: {e}')
            # await interaction.response.send_message(e)

    async def remove_from_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('remove_from_queue')
        button = await self._change_button_style(button)
        view = button.view
        await interaction.response.edit_message(view=view)
        guild_id = interaction.guild.id
        guild_queue = self.queue.get(guild_id)
        print(view.to_components())
        print('view.queue_button', view.queue_button)
        print('view.queue_button, dir', dir(view.queue_button))

        # if view.queue_button.style == discord.ButtonStyle.primary:
        #     print('queue style primary')
        #     await self.queue_command(interaction, view.queue_button)

        async def button_callback(interaction):
            # Add selected field information
            selected_field_index = int(interaction.data['custom_id'])
            embed = interaction.message.embeds[0]
            print('view', dir(view))
            print('embed', dir(embed))
            guild_queue.pop(selected_field_index)
            embed = embed.remove_field(selected_field_index)
            print(view.children)
            view.children.pop(selected_field_index)
            print(view.children)
            # embed = discord.Embed(title=f'Selected {selected_field}')
            # embed.add_field(name=f'{selected_field}', value=f'Details about {selected_field}', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)

        try:
            embed = interaction.message.embeds[0]
            # if button.style == discord.ButtonStyle.primary:
            #     await self.queue_command(interaction, view.queue_button)
                # embed = embed.clear_fields()
            # else:
            for index, music in enumerate(guild_queue):
                # embed.add_field(name=music, value='', inline=False)
                button = discord.ui.Button(label=f'{index}: {music}', custom_id=f'{index}')
                button.callback = button_callback
                view.add_item(button)
            print('else view', view, dir(view))
            # embed = interaction.message.embeds[0]
            print('remove edited')
            await interaction.followup.edit_message(message_id=self.embed_messages.get(guild_id).id, embed=embed, view=view)
        except Exception as e:
            print(f'Remove from queue error: {e}')

    async def skip_to(self, interaction: discord.Interaction, button: discord.ui.Button):
        button = await self._change_button_style(button)
        await interaction.response.edit_message(view=button.view)


async def setup(bot):
    music_cog = Music(bot)
    await bot.add_cog(music_cog)
