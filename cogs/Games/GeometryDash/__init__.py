from .gd import GeometryDashCog

async def setup(bot):
    await bot.add_cog(GeometryDashCog(bot))