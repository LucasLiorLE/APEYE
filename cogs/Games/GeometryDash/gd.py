from discord.ext import commands
from discord import app_commands
from .commands import profile

class GeometryDashGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="gd", description="Geometry dash related commands.")
  
class GeometryDashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        geometrydash_group = GeometryDashGroup()
        geometrydash_group.add_command(profile)
        self.bot.tree.add_command(geometrydash_group)

async def setup(bot):
    await bot.add_cog(GeometryDashCog(bot))
