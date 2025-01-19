from discord.ext import commands
from discord import app_commands
from .commands import clan, connect, profile

class ClashRoyaleCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="cr", description="Clash Royale related commands.")

class ClashRoyaleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        clashroyale_group = ClashRoyaleCommandsGroup()

        clashroyale_group.add_command(clan)
        clashroyale_group.add_command(connect)
        clashroyale_group.add_command(profile)

        self.bot.tree.add_command(clashroyale_group)

async def setup(bot):
    await bot.add_cog(ClashRoyaleCog(bot))