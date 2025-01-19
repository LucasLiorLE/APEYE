import discord
from discord import app_commands
from bot_utils import handle_logs, getUUID

@app_commands.command(
    name="uuid",
    description='Gets a Minecraft UUID for a specifed user.'
)
@app_commands.describe(
    username='A Minecraft username.'
)
async def uuid(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    try:
        uuid = await getUUID(interaction, username)
        if uuid:
            await interaction.followup.send(f"The UUID for {username} is {uuid}")
    except Exception as e:
        await handle_logs(interaction, e)
