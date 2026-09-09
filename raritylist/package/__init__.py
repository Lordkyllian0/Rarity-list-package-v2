import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.raritylist")


async def setup(bot: "BallsDexBot"):
    from .cog import RarityList

    await bot.add_cog(RarityList(bot))
    log.info("Rarity list package loaded successfully.")