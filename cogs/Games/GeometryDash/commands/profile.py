import discord
from discord import app_commands
from aiohttp import ClientSession
from bot_utils import handle_logs

@app_commands.command(
        name="profile", 
        description="Fetch a Geometry Dash player's profile data.",
    )
@app_commands.describe(
    username="The Geometry Dash username to fetch."
)
async def profile(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    try:
        async with ClientSession() as session:
            async with session.get(f"https://gdbrowser.com/api/profile/{username}") as response:
                if response.status == 200:
                    data = await response.json()

                    if "username" not in data:
                        await interaction.followup.send(f"User {username} not found.", ephemeral=True)
                        return
                    
                    embed = discord.Embed(title="Geometry Dash Profile",description=f"Profile information for **{data['username']}**",color=discord.Color.blue())
                    
                    embed.add_field(name="Username",value=f"{data['username']} (Account ID: {data['accountID']})",inline=False)
                    
                    embed.add_field(
                        name="Stats",
                        value=(
                            f"<:Stars:1299321915411791922> **Stars**: {data['stars']}\n"
                            f"<:Moons:1299321898169274378> **Moons**: {data['moons']}\n"
                            f"<:Coins:1299321945954713670> **Coins**: {data['coins']}\n"
                            f"<:UserCoins:1299321964867092510> **User Coins**: {data['userCoins']}"
                        ),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Demons",
                        value=(
                            f"**Total Beaten**: {data['demons']}\n"
                            f"**Classic Demons**:\n"
                            f"<:EasyDemon:1299319586197471253> Easy: {data['classicDemonsCompleted']['easy']}\n"
                            f"<:MediumDemon:1299319602936942635> Medium: {data['classicDemonsCompleted']['medium']}\n"
                            f"<:HardDemon:1299319619571552318> Hard: {data['classicDemonsCompleted']['hard']}\n"
                            f"<:InsaneDemon:1299319639959928872> Insane: {data['classicDemonsCompleted']['insane']}\n"
                            f"<:ExtremeDemon:1299319662995046420> Extreme: {data['classicDemonsCompleted']['extreme']}\n"
                            f"<:WeeklyDemon:1299320499146330152> Weekly: {data['classicDemonsCompleted']['weekly']}\n"
                            f"<:Gauntlet:1299320799458627626> Gauntlet: {data['classicDemonsCompleted']['gauntlet']}\n\n"
                            f"**Platformer Demons**:\n"
                            f"<:EasyDemon:1299319586197471253> Easy: {data['platformerDemonsCompleted']['easy']}\n"
                            f"<:MediumDemon:1299319602936942635> Medium: {data['platformerDemonsCompleted']['medium']}\n"
                            f"<:HardDemon:1299319619571552318> Hard: {data['platformerDemonsCompleted']['hard']}\n"
                            f"<:ExtremeDemon:1299319662995046420> Insane: {data['platformerDemonsCompleted']['insane']}\n"
                            f"<:ExtremeDemon:1299319662995046420> Extreme: {data['platformerDemonsCompleted']['extreme']}"
                        ),
                        inline=False
                    )

                    social_links = ""
                    if data.get("youtube"):
                        social_links += f"[YouTube](https://www.youtube.com/channel/{data['youtube']})\n"
                    if data.get("twitter"):
                        social_links += f"[Twitter](https://twitter.com/{data['twitter']})\n"
                    if data.get("twitch"):
                        social_links += f"[Twitch](https://www.twitch.tv/{data['twitch']})\n"

                    if social_links:
                        embed.add_field(name="Social", value=social_links, inline=False)

                    embed.set_footer(text=f"Rank: {"Leaderboard banned" if data["rank"] == 0 else f"Rank: {data['rank']}"} | Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

                    await interaction.followup.send(embed=embed)
                else: 
                    await interaction.followup.send(f"Failed to retrieve profile for {username}.", ephemeral=True)
    except Exception as e:
        await handle_logs(interaction, e)