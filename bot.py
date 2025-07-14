import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = 1393739742234939422  # Replace with your Discord channel ID
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
    channel = bot.get_channel(CHANNEL_ID)
    print(f"[LOG] Checking events for collection {COLLECTION_ADDRESS} in channel {CHANNEL_ID}")
    if channel is None:
        print(f"[ERROR] Channel with ID {CHANNEL_ID} not found.")
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
                # Send new listings (oldest first)
                for item in new_listings:
                    mint = item.get('tokenMint', 'Unknown')
                    price = item.get('price', 'N/A')
                    msg = f"New Listing: {mint} for {price} SOL\nLink: https://magiceden.io/item-details/{mint}"
                    await channel.send(msg)
                    print(f"[SENT] Listing: {mint} for {price} SOL")
                    last_listing_ids.add(mint)
                if not new_listings:
                    print("[LOG] No new listings found.")
                # Send new buys (oldest first)
                for item in new_buys:
                    price = item.get('price', 'N/A')
                    buyer = item.get('buyer', 'Unknown')
                    mint = item.get('mint', '')
                    msg = f"New Buy: {price} SOL by {buyer}\nLink: https://magiceden.io/item-details/{mint}"
                    await channel.send(msg)
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
