from __future__ import annotations

import math
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bd_models.models import BallInstance, Player, balls
from raritylist.config import (
    ITEMS_PER_PAGE,
    NOT_OWNED_EMOJI_NAME,
    NOT_OWNED_FALLBACK,
    OWNED_EMOJI_NAME,
    OWNED_FALLBACK,
)

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


def format_rarity(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def find_named_emoji(bot: "BallsDexBot", name: str, fallback: str) -> str:
    application_emojis = getattr(bot, "application_emojis", None)

    if application_emojis:
        if isinstance(application_emojis, dict):
            emojis = application_emojis.values()
        else:
            emojis = application_emojis

        for emoji in emojis:
            if emoji.name == name:
                return str(emoji)

    for emoji in bot.emojis:
        if emoji.name == name:
            return str(emoji)

    return fallback


class RarityPaginator(discord.ui.View):
    def __init__(
        self,
        *,
        bot: "BallsDexBot",
        author_id: int,
        cards: list,
        owned_ball_ids: set[int],
        owned_emoji: str,
        not_owned_emoji: str,
    ):
        super().__init__(timeout=180)

        self.bot = bot
        self.author_id = author_id
        self.cards = cards
        self.owned_ball_ids = owned_ball_ids
        self.owned_emoji = owned_emoji
        self.not_owned_emoji = not_owned_emoji

        self.page = 0
        self.pages = max(1, math.ceil(len(cards) / ITEMS_PER_PAGE))

        self._update_buttons()

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This rarity list belongs to someone else. "
                "Use `/rarities` to open your own.",
                ephemeral=True,
            )
            return False

        return True

    def _update_buttons(self):
        self.first.disabled = self.page <= 0
        self.back.disabled = self.page <= 0
        self.next.disabled = self.page >= self.pages - 1
        self.last.disabled = self.page >= self.pages - 1

    def make_embed(self, user: discord.abc.User) -> discord.Embed:
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE

        visible_cards = self.cards[start:end]

        lines = []

        for card in visible_cards:
            if card.pk in self.owned_ball_ids:
                status = self.owned_emoji
            else:
                status = self.not_owned_emoji

            card_emoji = self.bot.get_emoji(card.emoji_id)

            if card_emoji:
                card_emoji_text = str(card_emoji)
            else:
                card_emoji_text = "▫️"

            lines.append(
                f"{status} {card_emoji_text} **{card.country}**\n"
                f"Rarity: {format_rarity(card.rarity)}%"
            )

        if not lines:
            lines.append("No enabled cards were found.")

        embed = discord.Embed(
            title="Cards Ranked by Rarity",
            description=(
                "A list of cards sorted by rarity.\n\n"
                + "\n".join(lines)
            ),
            color=discord.Color.blurple(),
        )

        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url,
        )

        embed.set_footer(
            text=(
                f"Page {self.page + 1}/{self.pages} "
                f"({len(self.cards)} entries) • "
                f"{self.owned_emoji} owned • "
                f"{self.not_owned_emoji} not owned"
            )
        )

        return embed

    async def _refresh(
        self,
        interaction: discord.Interaction,
    ):
        self._update_buttons()

        await interaction.response.edit_message(
            embed=self.make_embed(interaction.user),
            view=self,
        )

    @discord.ui.button(
        label="≪",
        style=discord.ButtonStyle.secondary,
    )
    async def first(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = 0
        await self._refresh(interaction)

    @discord.ui.button(
        label="Back",
        style=discord.ButtonStyle.primary,
    )
    async def back(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    @discord.ui.button(
        label="Next",
        style=discord.ButtonStyle.primary,
    )
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = min(
            self.pages - 1,
            self.page + 1,
        )
        await self._refresh(interaction)

    @discord.ui.button(
        label="≫",
        style=discord.ButtonStyle.secondary,
    )
    async def last(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = self.pages - 1
        await self._refresh(interaction)

    @discord.ui.button(
        label="Quit",
        style=discord.ButtonStyle.danger,
    )
    async def quit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        self.stop()

        await interaction.response.edit_message(
            view=self,
        )


class RarityList(commands.Cog):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command(name="rarities")
    async def rarities(
        self,
        interaction: discord.Interaction["BallsDexBot"],
    ):
        """Show all cards by rarity and mark which ones you own."""

        await interaction.response.defer(thinking=True)

        player = await Player.objects.aget_or_none(
            discord_id=interaction.user.id
        )

        if player is None:
            owned_ball_ids = set()

        else:
            owned_ball_ids = {
                ball_id
                async for ball_id in (
                    BallInstance.objects
                    .filter(player=player)
                    .values_list("ball_id", flat=True)
                    .distinct()
                )
            }

        cards = sorted(
            (
                card
                for card in balls.values()
                if card.enabled
            ),
            key=lambda card: (
                card.rarity,
                card.country.casefold(),
            ),
        )

        owned_emoji = find_named_emoji(
            self.bot,
            OWNED_EMOJI_NAME,
            OWNED_FALLBACK,
        )

        not_owned_emoji = find_named_emoji(
            self.bot,
            NOT_OWNED_EMOJI_NAME,
            NOT_OWNED_FALLBACK,
        )

        view = RarityPaginator(
            bot=self.bot,
            author_id=interaction.user.id,
            cards=cards,
            owned_ball_ids=owned_ball_ids,
            owned_emoji=owned_emoji,
            not_owned_emoji=not_owned_emoji,
        )

        await interaction.followup.send(
            embed=view.make_embed(interaction.user),
            view=view,
        )