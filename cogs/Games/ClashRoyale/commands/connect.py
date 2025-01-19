import random, asyncio
import discord
from discord import app_commands
from datetime import datetime, timedelta
from bot_utils import get_player_data, open_file, save_file, handle_logs

@app_commands.command(
    name="connect", 
    description="Connect your Clash Royale profile."
)
@app_commands.describe(
    tag="Your in-game player tag."
)
async def connect(interaction: discord.Interaction, tag: str):
    await interaction.response.defer()
    try:
        if not tag.startswith("#"):
            tag = f"#{tag}"

        player_data = await get_player_data(tag.replace("#", "%23"))
        if not player_data:
            await interaction.followup.send("Failed to retrieve data for the provided player tag.", ephemeral=True)
            return

        random_deck = random.sample(["Giant", "Mini P.E.K.K.A", "Fireball", "Archers", "Minions", "Knight", "Musketeer", "Arrows"], k=8)
        random_deck_str = " ".join(f"`{card}`" for card in random_deck)
        await interaction.followup.send(
            f"Please use the following deck: {random_deck_str}\nYou have 15 minutes to make it, which will be checked per minute.\n"
            "Note that the Clash Royale API can be slow, so response times may vary."
        )

        end_time = datetime.now() + timedelta(minutes=15)
        while datetime.now() < end_time:
            player_data = await get_player_data(tag.replace("#", "%23"))
            current_deck = player_data.get("currentDeck", [])
            player_deck_names = [card.get("name", "Unknown") for card in current_deck]

            if sorted(player_deck_names) == sorted(random_deck):
                member_info = open_file("info/member_info.json")
                discord_user_id = str(interaction.user.id)

                if discord_user_id not in member_info:
                    member_info[discord_user_id] = {}

                member_info[discord_user_id]["cr_id"] = tag
                save_file("info/member_info.json", member_info)

                await interaction.followup.send("Deck matched! Your Clash Royale ID has been successfully linked.")
                return

            await asyncio.sleep(60)

        await interaction.followup.send("Deck did not match within 15 minutes. Please try again.")
    except Exception as e:
        await handle_logs(interaction, e)