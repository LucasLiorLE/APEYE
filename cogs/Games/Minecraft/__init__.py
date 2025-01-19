
from .minecraft import MinecraftCog

async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))