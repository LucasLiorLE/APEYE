import re
import discord
from discord import app_commands, ButtonStyle
from discord.ui import View, Button
from bot_utils import open_file, get_player_data, handle_logs

class ProfileView(View):
    def __init__(self, player_data, current_page="main"):
        super().__init__(timeout=None)
        self.player_data = player_data
        self.current_page = current_page
        self.main_button = Button(label="Main", style=ButtonStyle.secondary)
        self.main_button.callback = self.show_main_page
        self.add_item(self.main_button)
        self.deck_button = Button(label="Current Deck", style=ButtonStyle.secondary)
        self.deck_button.callback = self.show_deck_page
        self.add_item(self.deck_button)
        self.path_button = Button(label="Path of Legends", style=ButtonStyle.secondary)
        self.path_button.callback = self.show_path_page
        self.add_item(self.path_button)
        self.update_buttons()
        self.emoji_data = self.load_emoji_data()

    def load_emoji_data(self):
        return open_file("storage/emoji_data.json")

    def update_buttons(self):
        self.main_button.disabled = self.current_page == "main"
        self.deck_button.disabled = self.current_page == "deck"
        self.path_button.disabled = self.current_page == "path"

    async def show_main_page(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons()

        embed = self.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_deck_page(self, interaction: discord.Interaction):
        self.current_page = "deck"
        self.update_buttons()

        embed = self.create_deck_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_path_page(self, interaction: discord.Interaction):
        self.current_page = "path"
        self.update_buttons()

        embed = self.create_path_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_main_embed(self):
        name = self.player_data.get("name", "Unknown")
        user_id = self.player_data.get("tag", "Unknown")

        wins = self.player_data.get("wins", 0)
        losses = self.player_data.get("losses", 0)

        trophies = self.player_data.get("trophies", "Unknown")
        max_trophies = self.player_data.get("bestTrophies", "Unknown")
        arena = self.player_data.get("arena", {}).get("name", "Unknown")

        legacy_trophies = self.player_data.get("legacyTrophyRoadHighScore", "Unknown")
        
        goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("trophies", "Unknown")
        max_goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("bestTrophies", "Unknown")
        goblin_arena = self.player_data.get("progress", {}).get("goblin-road", {}).get("arena", {}).get("name", "Unknown")

        clan_name = self.player_data.get("clan", {}).get("name", "No Clan")
        clan_tag = self.player_data.get("clan", {}).get("tag", "N/A")
        clan_role = self.player_data.get("role", "Unknown")

        embed = discord.Embed(title=f"{name}'s Clash Royale Profile", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{name} ({user_id})", inline=False)
        embed.add_field(name="Wins/Losses", value=f"{wins}/{losses} ({(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0:.2f}%)", inline=False)
        embed.add_field(name="<:Trophy:1299093384882950245> Trophy Road", value=f"{trophies}/{max_trophies} ({arena})", inline=False)
        if legacy_trophies is not None and (legacy_trophies > 0 if isinstance(legacy_trophies, (int, float)) else False):
            embed.add_field(name="<:Trophy:1299093384882950245> Legacy Trophies", value=legacy_trophies, inline=False)
        if int(max_goblin_trophies) > 0:
            embed.add_field(name="<:Goblin_Trophy:1299093585274343508> Goblin Queen's Journey", value=f"{goblin_trophies}/{max_goblin_trophies} ({goblin_arena})", inline=False)
        embed.add_field(name="Clan", value=f"{clan_name} ({clan_role}) ({clan_tag})", inline=False)
        return embed

    def create_path_embed(self):
        current_path_of_legends = self.player_data.get("currentPathOfLegendSeasonResult", {})
        best_path_of_legends = self.player_data.get("bestPathOfLegendSeasonResult", {})
        last_path_of_legends = self.player_data.get("lastPathOfLegendSeasonResult", {})

        cPOL_league = current_path_of_legends.get("leagueNumber", "Unknown")
        bPOL_league = best_path_of_legends.get("leagueNumber", "Unknown")
        lPOL_league = last_path_of_legends.get("leagueNumber", "Unknown")

        cPOL_rank = current_path_of_legends.get("rank", "Unknown")
        bPOL_rank = best_path_of_legends.get("rank", "Unknown")
        lPOL_rank = last_path_of_legends.get("rank", "Unknown")

        embed = discord.Embed(title="Path of Legends", color=discord.Color.purple())

        embed.add_field(
            name="Current Path of Legends",
            value=f"League: {self.get_league_emoji(cPOL_league)} | Rank: {cPOL_rank}",
            inline=False
        )
        embed.add_field(
            name="Best Path of Legends",
            value=f"League: {self.get_league_emoji(bPOL_league)} | Rank: {bPOL_rank}",
            inline=False
        )
        embed.add_field(
            name="Last Path of Legends",
            value=f"League: {self.get_league_emoji(lPOL_league)} | Rank: {lPOL_rank}",
            inline=False
        )

        return embed

    def create_deck_embed(self):
        embed = discord.Embed(title="Deck Information", color=discord.Color.green())

        current_deck = self.player_data.get("currentDeck", [])
        card_ids = []  

        for index, card in enumerate(current_deck):
                name = card.get("name", "Unknown")
                level = card.get("level", "Unknown")
                star_level = card.get("starLevel", "0")
                emoji = self.get_card_emoji(name)

                card_id = card.get("id")
                if card_id:
                        card_ids.append(str(card_id))

                field_value = f"{emoji} | Level: {level} | Star Level: {star_level}"
                embed.add_field(name=f"Card {index + 1}: {name}", value=field_value, inline=False)

        embed.description=f"[Click here to copy the deck](https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={'%3B'.join(card_ids)}&l=Royals)"

        return embed
    
    def get_league_emoji(self, rank):
        league_names = {
            1: "Challenger 1",
            2: "Challenger 2",
            3: "Challenger 3",
            4: "Master 1",
            5: "Master 2",
            6: "Master 3",
            7: "Champion",
            8: "Grand Champion",
            9: "Royal Champion",
            10: "Ultimate Champion"
        }

        if rank in league_names:
            emoji_id = self.emoji_data.get(f"cr{league_names[rank].replace(' ', '')}")
            if emoji_id:
                return f"<:cr{league_names[rank].replace(' ', '')}:{emoji_id}> {league_names[rank]}"
        
        return "❓ Unknown League"
    
    def get_card_emoji(self, card_name):
        formatted_name = ''.join(re.findall(r'[A-Za-z]', card_name))
        emoji_id = self.emoji_data.get(formatted_name)
        if emoji_id:
            return f"<:{formatted_name}:{emoji_id}>"
        return "❓" 


@app_commands.command(
    name="profile", 
    description="Get Clash Royale player profile data."
)
@app_commands.describe(
    tag="The user's tag (The one with the #).", 
    user="The user ID of the member."
)
async def profile(interaction: discord.Interaction, tag: str = None, user: discord.User = None):
    await interaction.response.defer()
    try:
        member_info = open_file("info/member_info.json")

        if tag is None:
            user_id = str(user.id) or str(interaction.user.id)
            cr_id = member_info.get(user_id, {}).get("cr_id")

            if cr_id:
                tag = cr_id
            else:
                await interaction.followup.send("No linked Clash Royale account found.")
                return
        else:
            if not tag.startswith("#"):
                tag = "#" + tag.strip()

        player_data = await get_player_data(tag.replace("#", "%23"))

        if player_data:
            view = ProfileView(player_data)
            embed = view.create_main_embed()
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"Player data not found for tag: {tag}")
    except Exception as e:
        await handle_logs(interaction, e)