from discord.utils import get
from timeManager import TimeManager


class Player:
	def __init__(self):
		pass

	@staticmethod
	async def play(voice, song):
		voice.play(discord.FFmpegPCMAudio(executable=ffmpegPathUrl, source=song, **ffmpegOptions),
		           after=lambda e: playNext(ctx))
		voice.is_playing()

	async def wait(self):
		pass

	# async def playNext(ctx):
	# 	global skipToTime, songStartTime, loop
	# 	endTime = songStartTime - datetime.now()
	# 	end = skipToTime
	# 	ffmpegOptions["before_options"] = f"-ss {skipToTime} -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 " \
	# 	                                  f"-reconnect_delay_max 5"
	# 	voice = get(bot.voice_clients, guild=ctx.guild)
	#
	# 	voice.is_paused()
	#
	# 	if loop is True:
	# 		songQueue[ctx.guild].append(songQueue[ctx.guild][0])
	# 		musicTitles[ctx.guild].append(musicTitles[ctx.guild][0])
	# 	else:
	# 		pass
	#
	# 	end += abs(int(endTime.total_seconds()))
	#
	# 	if len(songQueue[ctx.guild]) > 1 and len(musicTitles[ctx.guild]) > 1:
	# 		del songQueue[ctx.guild][0], musicTitles[ctx.guild][0]
	#
	# 		if TimeManager.timeParse(songQueue[ctx.guild][0]["duration"]) <= end:
	# 			skipToTime = 0
	# 			voice.stop()
	#
	# 		song = search(ctx.author.mention, musicTitles[ctx.guild][0])
	# 		songQueue[ctx.guild][0] = song
	# 		asyncio.run_coroutine_threadsafe(edit_message(ctx), bot.loop)
	# 		songStartTime = datetime.now()
	# 		await play(ctx)
	# 		# voice.play(discord.FFmpegPCMAudio(executable=ffmpegPathUrl, source=songQueue[ctx.guild][0]["source"],
	# 		#                                   **ffmpegOptions), after=lambda e: playNext(ctx))
	# 		# voice.is_playing()
	# 	else:
	# 		asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)
	# 		asyncio.run_coroutine_threadsafe(message[ctx.guild].delete(), bot.loop)
	# 		loop = False