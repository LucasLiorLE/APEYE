from discord.ext import commands
from discord import app_commands
from .commands import uuid, avatar

class MinecraftCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="minecraft", description="Minecraft related commands")

class MinecraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        minecraft_group = MinecraftCommandsGroup()
        
        minecraft_group.add_command(uuid)
        minecraft_group.add_command(avatar)
        
        self.bot.tree.add_command(minecraft_group)

async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))