import discord
from discord import app_commands
from bot_utils import get_clan_data, handle_logs

@app_commands.command(
    name="clan", 
    description="Get data about a Clash Royale clan."
)
@app_commands.describe(
    clantag="The clan's tag (the one with the #)."
)
async def clan(interaction: discord.Interaction, clantag: str):
    await interaction.response.defer()
    try:
        if not clantag.startswith("#"):
            clantag = "#" + clantag.strip()

        clan_data = await get_clan_data(clantag.replace("#", "%23"))

        if clan_data:
            embed = discord.Embed(title=f"Clan Data for {clan_data['name']}", color=discord.Color.blue())

            embed.add_field(name="<:Clan:1300957220422549514> Name", value=f"{clan_data['name']} ({clan_data['tag']})")
            embed.add_field(name="<:Trophy:1299093384882950245> Clan Score", value=clan_data['clanScore'])
            embed.add_field(name="<:ClanTrophies:1300956037272309850> Clan Trophies", value=clan_data['clanWarTrophies'])
            embed.add_field(name="<:Trophy:1299093384882950245> Required Trophies", value=clan_data['requiredTrophies'])
            embed.add_field(name="<:Cards:1300955092534558850> Weekly Donations", value=clan_data['donationsPerWeek'])
            embed.add_field(name="<:Members:1300956053588152373> Members", value=clan_data['members'])
            embed.add_field(name="<:Clan:1300957220422549514> Description", value=clan_data['description'])
            embed.set_footer(text=f"The clan is currently {clan_data['type']} | Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"Clan data not found for tag: {clantag}")
    except Exception as e:
        await handle_logs(interaction, e)