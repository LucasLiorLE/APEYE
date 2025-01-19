import discord
from discord import app_commands
from bot_utils import handle_logs, getUUID

@app_commands.command(
    name="avatar",
    description='Gets a Minecraft avatar for a specifed user.'
)
@app_commands.describe(
    username='A Minecraft username.'
)
async def avatar(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    try:
        uuid = await getUUID(interaction, username)
        if uuid:
            image_url = f"https://api.mineatar.io/body/full/{uuid}"

            embed = discord.Embed(title=f"{username}'s Avatar", color=discord.Color.blue())
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("UUID not found for the provided username.")
    except Exception as e:
        await handle_logs(interaction, e)
