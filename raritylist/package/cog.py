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
    percentage = value * 100
    return f"{percentage:.6f}".rstrip("0").rstrip(".")


def find_named_emoji(
    bot: "BallsDexBot",
    name: str,
    fallback: str,
) -> str:
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


def get_card_emoji(
    bot: "BallsDexBot",
    emoji_id: int,
) -> str:
    emoji = bot.get_emoji(emoji_id)

    if emoji is not None:
        return str(emoji)

    return f"<:card:{emoji_id}>"


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
        rarity_filter: str,
    ):
        super().__init__(timeout=180)

        self.bot = bot
        self.author_id = author_id
        self.cards = cards
        self.owned_ball_ids = owned_ball_ids
        self.owned_emoji = owned_emoji
        self.not_owned_emoji = not_owned_emoji
        self.rarity_filter = rarity_filter

        self.page = 0
        self.pages = max(
            1,
            math.ceil(len(cards) / ITEMS_PER_PAGE),
        )

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

    def _update_buttons(self) -> None:
        self.first.disabled = self.page <= 0
        self.back.disabled = self.page <= 0
        self.next.disabled = self.page >= self.pages - 1
        self.last.disabled = self.page >= self.pages - 1

    def make_embed(
        self,
        user: discord.abc.User,
    ) -> discord.Embed:
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        visible_cards = self.cards[start:end]

        lines: list[str] = []

        for card in visible_cards:
            if card.pk in self.owned_ball_ids:
                status = self.owned_emoji
            else:
                status = self.not_owned_emoji

            card_emoji = get_card_emoji(
                self.bot,
                card.emoji_id,
            )

            lines.append(
                f"{card_emoji} **{card.country}** {status}\n"
                f"Rarity: {format_rarity(card.rarity)}%"
            )

        if not lines:
            if self.rarity_filter == "owned":
                lines.append("You do not own any enabled cards.")
            elif self.rarity_filter == "not_owned":
                lines.append("You own every enabled card.")
            else:
                lines.append("No enabled cards were found.")

        if self.rarity_filter == "owned":
            filter_text = "Owned"
        elif self.rarity_filter == "not_owned":
            filter_text = "Not Owned"
        else:
            filter_text = "All"

        embed = discord.Embed(
            title="Cards Ranked by Rarity",
            description=(
                f"Showing: **{filter_text}**\n\n"
                + "\n".join(lines)
            ),
            color=discord.Color.blurple(),
        )

        embed.set_footer(
            text=(
                f"Page {self.page + 1}/{self.pages} "
                f"({len(self.cards)} entries)"
            )
        )

        return embed

    async def _refresh(
        self,
        interaction: discord.Interaction,
    ) -> None:
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
        self.page = max(
            0,
            self.page - 1,
        )
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
    def __init__(
        self,
        bot: "BallsDexBot",
    ):
        self.bot = bot

@app_commands.command(
    name="rarities",
    description="Show cards ranked by rarity.",
)
@app_commands.describe(
    owned="Filter cards by whether you own them.",
)
async def rarities(
    self,
    interaction: discord.Interaction["BallsDexBot"],
    owned: bool | None = None,
):
    await interaction.response.defer(
        thinking=True,
    )

    player = await Player.objects.aget_or_none(
        discord_id=interaction.user.id,
    )

    if player is None:
        owned_ball_ids: set[int] = set()
    else:
        owned_ball_ids = {
            ball_id
            async for ball_id in (
                BallInstance.objects
                .filter(player=player)
                .values_list(
                    "ball_id",
                    flat=True,
                )
                .distinct()
            )
        }

    cards = [
        card
        for card in balls.values()
        if card.enabled
    ]

    # owned: True = only owned cards
    if owned is True:
        cards = [
            card
            for card in cards
            if card.pk in owned_ball_ids
        ]

    # owned: False = only cards not owned
    elif owned is False:
        cards = [
            card
            for card in cards
            if card.pk not in owned_ball_ids
        ]

    # owned not selected = show everything

    cards = sorted(
        cards,
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