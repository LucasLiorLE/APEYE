from .cr import ClashRoyaleCog

async def setup(bot):
    await bot.add_cog(ClashRoyaleCog(bot))