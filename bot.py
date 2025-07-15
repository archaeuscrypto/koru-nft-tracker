
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

import aiohttp
import asyncio
import json
from typing import Literal

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# List of Discord channel IDs to send messages to
CHANNEL_IDS = [1393739742234939422, 1394185183959191572]  # Add more channel IDs as needed
COLLECTION_ADDRESS = 'koru'

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for commands
bot = commands.Bot(command_prefix='!', intents=intents)

ALLOWED_USER_IDS = {908499792043335680}  # Replace with actual allowed user IDs (as integers)

RARITY_ROLE_IDS = {
    "mythic": 1394729409243643995,
    "legendary": 1394729689909559417,
    "epic": 1394729993615183972,
    "rare": 1394730089480196158
}

TIER_ROLES = {
    "mythic": "Mythic Hunter",
    "legendary": "Legendary Seeker",
    "epic": "Epic Tracker",
    "rare": "Rare Chaser"
}

@bot.event
async def on_message(message):
    # Allow messages from the bot itself and allowed users
    if message.author == bot.user or message.author.id in ALLOWED_USER_IDS:
        await bot.process_commands(message)
        return
    # Delete all other user messages in the channel
    try:
        await message.delete()
    except Exception as e:
        print(f"[ERROR] Could not delete message from {message.author}: {e}")

# Sync tree for slash commands
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    # Set bot status and activity
    activity = discord.Activity(type=discord.ActivityType.watching, name="for wild Koru")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    try:
        synced = await bot.tree.sync()
        print(f"[LOG] Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"[ERROR] Syncing slash commands: {e}")
    track_nft_events.start()


@bot.command()
@commands.has_permissions(manage_messages=True)
async def clean(ctx):
    """Delete all messages in the current channel."""
    await ctx.send("Cleaning up messages...", delete_after=2)
    def not_pinned(msg):
        return not msg.pinned
    deleted = await ctx.channel.purge(limit=None, check=not_pinned)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

@bot.tree.command(name="sub", description="Subscribe to rarity alerts")
@app_commands.describe(tier="Choose a rarity tier to subscribe to")
async def sub(interaction: discord.Interaction, tier: Literal["mythic", "legendary", "epic", "rare"]):
    guild = interaction.guild
    role_name = TIER_ROLES[tier]
    role = discord.utils.get(guild.roles, name=role_name)

    if role is None:
        await interaction.response.send_message(
            f"❌ Role **{role_name}** not found. Ask an admin to create it.",
            ephemeral=True
        )
        return

    try:
        await interaction.user.add_roles(role)
        await interaction.response.send_message(
            f"✅ Subscribed to **{tier.title()}** alerts! ({role.mention})",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"Error assigning role: {e}", ephemeral=True)


@bot.tree.command(name="unsub", description="Unsubscribe from rarity alerts")
@app_commands.describe(tier="Choose a rarity tier to unsubscribe from")
async def unsub(interaction: discord.Interaction, tier: Literal["mythic", "legendary", "epic", "rare"]):
    guild = interaction.guild
    role_name = TIER_ROLES[tier]
    role = discord.utils.get(guild.roles, name=role_name)

    if role is None:
        await interaction.response.send_message(
            f"❌ Role **{role_name}** not found. Nothing to remove.",
            ephemeral=True
        )
        return

    try:
        await interaction.user.remove_roles(role)
        await interaction.response.send_message(
            f"✅ Unsubscribed from **{tier.title()}** alerts.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"Error removing role: {e}", ephemeral=True)


# Load rarity data once at startup
RARITY_DATA = None
RARITY_PATH = os.path.join(os.path.dirname(__file__), 'rarity-ranking.json')
try:
    with open(RARITY_PATH, 'r', encoding='utf-8') as f:
        RARITY_DATA = json.load(f)
except Exception as e:
    print(f"[ERROR] Could not load rarity-ranking.json: {e}")


# Tier emojis for rarity
tier_emojis = {
    "Mythic": "🟣",
    "Legendary": "🟡",
    "Epic": "🟢",
    "Rare": "🔵",
    "Common": "⚪"
}

# Rarity color hex codes for embeds
rarity_colors = {
    "Mythic": "#a98dd6",     # 🟣
    "Legendary": "#FFD700",  # 🟡
    "Epic": "#77b058",       # 🟢
    "Rare": "#55abed",       # 🔵
    "Common": "#FFFFFF"      # ⚪
}

def get_rarity_color(rarity):
    return int(rarity_colors.get(rarity, "#2ecc71").lstrip('#'), 16)

last_listing_ids = set()
last_buy_ids = set()


@bot.tree.command(name="topholders", description="Show the top Koru NFT holders.")
async def toppholders(interaction: discord.Interaction):
    """Fetch and display the top Koru NFT holders in an embed."""
    await interaction.response.defer(thinking=True)
    url = "https://api-mainnet.magiceden.dev/v2/collections/koru/holder_stats"
    headers = {"accept": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"Failed to fetch holder stats: {resp.status}")
                    return
                data = await resp.json()
        holders = data.get('topHolders', [])
        if not holders:
            await interaction.followup.send("No holder data found.")
            return
        top = holders[:25]
        embed = discord.Embed(
            title="Top Koru NFT Holders",
            description="Here are the top 25 holders by number of NFTs held.",
            color=0x3498db
        )
        for idx, holder in enumerate(top, 1):
            addr = holder.get('owner', 'Unknown')
            count = holder.get('tokens', 0)
            solscan = f'https://solscan.io/account/{addr}'
            # Prefer sol domain if available
            sol_domain = None
            owner_display = holder.get('ownerDisplay', {})
            if isinstance(owner_display, dict):
                sol_domain = owner_display.get('sol')
            display_name = sol_domain if sol_domain else f"{addr[:4]}...{addr[-4:]}"
            embed.add_field(
                name=f"#{idx}: {display_name}",
                value=f"NFTs: **{count}** | [Solscan]({solscan})",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error fetching top holders: {e}")

@tasks.loop(seconds=60)
async def track_nft_events():
    await bot.wait_until_ready()
    channels = [bot.get_channel(cid) for cid in CHANNEL_IDS]
    print(f"[LOG] Checking events for collection {COLLECTION_ADDRESS} in channels {CHANNEL_IDS}")
    if not any(channels):
        print(f"[ERROR] None of the channels in {CHANNEL_IDS} were found.")
        return
    async with aiohttp.ClientSession() as session:
        # Fetch all activities and filter by type in code
        activities_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/activities?limit=10"
        print(f"[LOG] Fetching activities from Magic Eden API.")
        async with session.get(activities_url) as resp:
            print(f"[LOG] Activities response status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                # Only send new listings and buys (not previously sent), in chronological order
                global last_listing_ids, last_buy_ids
                new_listings = []
                new_buys = []
                # Collect new listings (oldest first)
                for item in reversed(data):
                    if item.get('type') == 'list':
                        listing_id = item.get('tokenMint')
                        if listing_id and listing_id not in last_listing_ids:
                            new_listings.append(item)
                # Collect new buys (oldest first)
                for item in reversed(data):
                    if item.get('type') == 'buyNow':
                        mint = item.get('tokenMint')
                        if mint and mint not in last_buy_ids:
                            new_buys.append(item)
                # Send new listings (oldest first) as embeds with fallbacks
                for item in new_listings:
                    mint = item.get('tokenMint', 'Unknown')
                    price = item.get('price', 'N/A')
                    lister = item.get('seller', 'Unknown')
                    lister_link = f'https://solscan.io/account/{lister}' if lister != 'Unknown' else None
                    # Try to get name and image from activity
                    name = item.get('name')
                    image = item.get('image')
                    # Fallback: fetch metadata if missing
                    if not name or not image:
                        try:
                            async with aiohttp.ClientSession() as meta_session:
                                meta_url = f"https://api-mainnet.magiceden.dev/v2/tokens/{mint}"
                                async with meta_session.get(meta_url) as meta_resp:
                                    if meta_resp.status == 200:
                                        meta = await meta_resp.json()
                                        if not name:
                                            name = meta.get('name', mint)
                                        if not image:
                                            image = meta.get('image')
                        except Exception as e:
                            print(f"[ERROR] Metadata fetch failed for {mint}: {e}")
                    if not name:
                        name = f"NFT {mint[:6]}..."

                    # Extract NFT number from name (e.g., "Koru #1234")
                    nft_number = None
                    if name:
                        import re
                        match = re.search(r'#(\d+)', name)
                        if match:
                            nft_number = match.group(1)
                    # Lookup rarity info
                    rarity_str = ''
                    embed_color = 0x2ecc71  # default green
                    if nft_number and RARITY_DATA and nft_number in RARITY_DATA:
                        rarity = RARITY_DATA[nft_number]
                        tier = rarity.get('tier', 'Unknown')
                        emoji = tier_emojis.get(tier, '')
                        rarity_str = f"**Rarity:** {emoji} {tier} | **Rank:** {rarity.get('rank', 'N/A')}"
                        embed_color = get_rarity_color(tier)
                    elif nft_number:
                        rarity_str = "**Rarity:** Unknown | **Rank:** N/A"

                    # Fetch floor price
                    floor_price = None
                    try:
                        stats_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/stats"
                        async with session.get(stats_url) as stats_resp:
                            if stats_resp.status == 200:
                                stats_data = await stats_resp.json()
                                floor_price = stats_data.get('floorPrice')
                    except Exception as e:
                        print(f"[ERROR] Could not fetch floor price: {e}")
                    floor_sol = None
                    if floor_price:
                        try:
                            floor_sol = float(floor_price) / 1_000_000_000
                        except Exception:
                            floor_sol = None

                    # Build embed
                    lister_display = f"[Seller]({lister_link})" if lister_link else '`Unknown`'
                    desc = f"**Price:** {price} SOL"
                    if rarity_str:
                        desc += f"\n{rarity_str}"
                    # Add rarity role ping if valid tier and role ID
                    if 'tier' in locals():
                        role_id = RARITY_ROLE_IDS.get(tier.lower())
                        if role_id:
                            desc += f"\n\n<@&{role_id}>"
                        else:
                            desc += f"\n\n{lister_display}"
                    else:
                        desc += f"\n\n{lister_display}"

                    embed = discord.Embed(
                        title=f"🔥 New Listing: {name}",
                        description=desc,
                        color=embed_color
                    )
                    if image:
                        embed.set_image(url=image)

                    components = None
                    try:
                        from discord.ui import Button, View
                        class MEView(View):
                            def __init__(self):
                                super().__init__()
                                self.add_item(Button(label="Magic Eden", url=f"https://magiceden.io/item-details/{mint}"))
                                if floor_sol is not None:
                                    self.add_item(Button(label=f"Floor: {floor_sol:.3f} SOL", disabled=True))
                                else:
                                    self.add_item(Button(label="Floor: N/A", disabled=True))
                        components = MEView()
                    except Exception:
                        pass
                    for channel in channels:
                        if channel:
                            if components:
                                await channel.send(embed=embed, view=components)
                            else:
                                await channel.send(embed=embed)
                    print(f"[SENT] Listing: {name} for {price} SOL")
                    last_listing_ids.add(mint)
                if not new_listings:
                    print("[LOG] No new listings found.")
                # Send new buys (oldest first) as embeds with fallbacks
                for item in new_buys:
                    price = item.get('price', 'N/A')
                    buyer = item.get('buyer', 'Unknown')
                    buyer_link = f'https://solscan.io/account/{buyer}' if buyer != 'Unknown' else None
                    # Use tokenMint for consistency, fallback to mint
                    mint = item.get('tokenMint') or item.get('mint', '')
                    # Try to get name and image from activity
                    name = item.get('name')
                    image = item.get('image')
                    # Fallback: fetch metadata if missing
                    if mint and (not name or not image):
                        try:
                            async with aiohttp.ClientSession() as meta_session:
                                meta_url = f"https://api-mainnet.magiceden.dev/v2/tokens/{mint}"
                                async with meta_session.get(meta_url) as meta_resp:
                                    if meta_resp.status == 200:
                                        meta = await meta_resp.json()
                                        if not name:
                                            name = meta.get('name', mint)
                                        if not image:
                                            image = meta.get('image')
                        except Exception as e:
                            print(f"[ERROR] Metadata fetch failed for {mint}: {e}")
                    if not name:
                        name = f"NFT {mint[:6]}..."

                    # Extract NFT number from name (e.g., "Koru #1234")
                    nft_number = None
                    if name:
                        import re
                        match = re.search(r'#(\d+)', name)
                        if match:
                            nft_number = match.group(1)
                    # Lookup rarity info
                    rarity_str = ''
                    embed_color = 0xe67e22  # default orange
                    if nft_number and RARITY_DATA and nft_number in RARITY_DATA:
                        rarity = RARITY_DATA[nft_number]
                        tier = rarity.get('tier', 'Unknown')
                        emoji = tier_emojis.get(tier, '')
                        rarity_str = f"**Rarity:** {emoji} {tier} | **Rank:** {rarity.get('rank', 'N/A')}"
                        embed_color = get_rarity_color(tier)
                    elif nft_number:
                        rarity_str = "**Rarity:** Unknown | **Rank:** N/A"

                    # Fetch floor price for buy messages
                    floor_price = None
                    try:
                        stats_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/stats"
                        async with session.get(stats_url) as stats_resp:
                            if stats_resp.status == 200:
                                stats_data = await stats_resp.json()
                                floor_price = stats_data.get('floorPrice')
                    except Exception as e:
                        print(f"[ERROR] Could not fetch floor price: {e}")
                    floor_sol = None
                    if floor_price:
                        try:
                            floor_sol = float(floor_price) / 1_000_000_000
                        except Exception:
                            floor_sol = None

                    buyer_display = f"[Buyer]({buyer_link})" if buyer_link else '`Unknown`'
                    seller = item.get('seller', 'Unknown')
                    seller_link = f'https://solscan.io/account/{seller}' if seller != 'Unknown' else None
                    seller_display = f"[Seller]({seller_link})" if seller_link else '`Unknown`'
                    desc = f"**Sold for:** {price} SOL"
                    if rarity_str:
                        desc += f"\n{rarity_str}"
                    desc += f"\n\n{seller_display} 🤝 {buyer_display}"
                    embed = discord.Embed(
                        title=f"🎉 New Buy: {name}",
                        description=desc,
                        color=embed_color
                    )
                    if image:
                        embed.set_image(url=image)
                    components = None
                    try:
                        from discord.ui import Button, View
                        class MEView(View):
                            def __init__(self):
                                super().__init__()
                                self.add_item(Button(label="Magic Eden", url=f"https://magiceden.io/item-details/{mint}"))
                                if floor_sol is not None:
                                    self.add_item(Button(label=f"Floor: {floor_sol:.3f} SOL", disabled=True))
                                else:
                                    self.add_item(Button(label="Floor: N/A", disabled=True))
                        components = MEView()
                    except Exception:
                        pass
                    for channel in channels:
                        if channel:
                            if components:
                                await channel.send(embed=embed, view=components)
                            else:
                                await channel.send(embed=embed)
                    print(f"[SENT] Buy: {price} SOL by {buyer}")
                    last_buy_ids.add(mint)
                if not new_buys:
                    print("[LOG] No new buys found.")
            else:
                print(f"[ERROR] Failed to fetch activities: {resp.status}")

@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am your NFT tracker bot.')

if __name__ == '__main__':
    bot.run(TOKEN)