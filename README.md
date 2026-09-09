# BallsDex Rarity List Package

Adds a `/rarities` command to BallsDex.

The command:

- shows all enabled cards
- sorts them by rarity
- shows the card emoji
- shows `:owned:` if the user owns the card
- shows `:notowned:` if the user does not own the card
- includes pagination buttons

## Required emojis

Create custom Discord emojis named:

- `owned`
- `notowned`

If those emojis cannot be found, the package falls back to 🟢 and 🔴.

## BallsDex configuration

Add this to `config/extra.toml`:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/Lordkyllian0/Rarity-list-package.git@main"
path = "raritylist"
enabled = true