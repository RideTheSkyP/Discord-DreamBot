import discord

client = discord.Client()
token = open("token.txt", "r").read()


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")


@client.event
async def on_message(message):
    print(f"{message.channel}: {message.author}: {message.author.name}: {message.content}")
    # print(message.author, message.content)
    id = client.get_guild(728056581312479352)

    if message.content.find("!hello") != -1:
        await message.channel.send("Hi {}".format(message.author))
    elif message.content == "!users":
        await message.channel.send(f"""Number of Members: {id.member_count}""")

    # if str(message.channel) == "general":
    #     print(message.channel)


@client.event
async def on_voice_state_update(member, before, after):
    print("Channel {}\n {}\n {}\n".format(member, before, after))


@client.event
async def on_member_join(member):
    for channel in member.guild.channels:
        if str(channel) == "general":
            await channel.send_message(f"""Welcome to the server {member.mention}""")


client.run(token)
