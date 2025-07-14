import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# List of Discord channel IDs to send messages to
CHANNEL_IDS = [1393739742234939422, 1394125194569973911]  # Add more channel IDs as needed
COLLECTION_ADDRESS = 'koru'

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for commands
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clean(ctx):
    """Delete all messages in the current channel."""
    await ctx.send("Cleaning up messages...", delete_after=2)
    def not_pinned(msg):
        return not msg.pinned
    deleted = await ctx.channel.purge(limit=None, check=not_pinned)
    await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

last_listing_ids = set()
last_buy_ids = set()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    track_nft_events.start()

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
        activities_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/activities?offset=0&limit=40"
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
                        tx_id = item.get('txId')
                        if tx_id and tx_id not in last_buy_ids:
                            new_buys.append(item)
                # Send new listings (oldest first) as embeds with fallbacks
                for item in new_listings:
                    mint = item.get('tokenMint', 'Unknown')
                    price = item.get('price', 'N/A')
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
                        # Try to extract #number from mint if possible
                        name = f"NFT {mint[:6]}..."
                    # Build embed
                    embed = discord.Embed(
                        title=f"{name}",
                        description=f"**Price:** {price} SOL",
                        color=0x2ecc71
                    )
                    if image:
                        embed.set_image(url=image)
                    embed.add_field(name="Magic Eden", value=f"[View on Magic Eden](https://magiceden.io/item-details/{mint})", inline=False)
                    # If discord.py 2.x+, add a button (try/except for compatibility)
                    components = None
                    try:
                        from discord.ui import Button, View
                        class MEView(View):
                            def __init__(self):
                                super().__init__()
                                self.add_item(Button(label="View on Magic Eden", url=f"https://magiceden.io/item-details/{mint}"))
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
                    mint = item.get('mint', '')
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
                    embed = discord.Embed(
                        title=f"{name}",
                        description=f"**Sold for:** {price} SOL\n**Buyer:** {buyer}",
                        color=0xe67e22
                    )
                    if image:
                        embed.set_image(url=image)
                    embed.add_field(name="Magic Eden", value=f"[View on Magic Eden](https://magiceden.io/item-details/{mint})", inline=False)
                    components = None
                    try:
                        from discord.ui import Button, View
                        class MEView(View):
                            def __init__(self):
                                super().__init__()
                                self.add_item(Button(label="View on Magic Eden", url=f"https://magiceden.io/item-details/{mint}"))
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
                    last_buy_ids.add(item.get('txId'))
                if not new_buys:
                    print("[LOG] No new buys found.")
            else:
                print(f"[ERROR] Failed to fetch activities: {resp.status}")

@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am your NFT tracker bot.')

if __name__ == '__main__':
    bot.run(TOKEN)
