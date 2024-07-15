import yt_dlp
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
#
# # Suppress noise about console usage from errors
# # yt_dlp.utils.bug_reports_message = lambda: ''


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print('init')

    # @client.tree.command(name="join", description="Adds a user to the list of usernames to query")
    @app_commands.command(name='join', description='Make the bot join the voice channel you are in')
    async def join(self, interaction: discord.Interaction):
        print('join')
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.response.send_message(f'Joined {channel.name} voice channel', ephemeral=True)
        else:
            await interaction.response.send_message('You are not in a voice channel.', ephemeral=True)

    @app_commands.command(name='leave', description='Make the bot leave the voice channel it is in')
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message('Disconnected from the voice channel.', ephemeral=True)
        else:
            await interaction.response.send_message('I am not in a voice channel.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(Music(bot))
