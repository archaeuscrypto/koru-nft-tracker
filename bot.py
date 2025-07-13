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
        # Track new listings
        listings_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/listings?offset=0&limit=10"
        print(f"[LOG] Fetching listings from: {listings_url}")
        async with session.get(listings_url) as resp:
            print(f"[LOG] Listings response status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"[LOG] Listings data received: {data}")
                global last_listing_ids
                new_listings = []
                for item in data:
                    # Use 'pdaAddress' as the unique ID for listings
                    listing_id = item.get('pdaAddress')
                    if listing_id and listing_id not in last_listing_ids:
                        print(f"[NEW LISTING] {item}")
                        new_listings.append(item)
                        last_listing_ids.add(listing_id)
                if new_listings:
                    for item in new_listings:
                        name = item.get('token', {}).get('name', 'Unknown')
                        price = item.get('price', 'N/A')
                        mint = item.get('tokenMint') or item.get('token', {}).get('mintAddress', '')
                        msg = f"New Listing: {name} for {price} SOL\nLink: https://magiceden.io/item-details/{mint}"
                        await channel.send(msg)
                        print(f"[SENT] {msg}")
                else:
                    print("[LOG] No new listings found.")
                # Keep only the latest 50 IDs
                if len(last_listing_ids) > 50:
                    last_listing_ids = set(list(last_listing_ids)[-50:])
            else:
                print(f"[ERROR] Failed to fetch listings: {resp.status}")

        # Track new buys (sales)
        sales_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/activities?offset=0&limit=20&type=buyNow"
        print(f"[LOG] Fetching buys from: {sales_url}")
        async with session.get(sales_url) as resp:
            print(f"[LOG] Buys response status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"[LOG] Buys data received: {data}")
                global last_buy_ids
                new_buys = []
                for item in data:
                    if item['txId'] not in last_buy_ids:
                        print(f"[NEW BUY] {item}")
                        new_buys.append(item)
                        last_buy_ids.add(item['txId'])
                if new_buys:
                    for item in new_buys:
                        price = item.get('price', 'N/A')
                        buyer = item.get('buyer', 'Unknown')
                        mint = item.get('mint', '')
                        msg = f"New Buy: {price} SOL by {buyer}\nLink: https://magiceden.io/item-details/{mint}"
                        await channel.send(msg)
                        print(f"[SENT] {msg}")
                else:
                    print("[LOG] No new buys found.")
                # Keep only the latest 50 IDs
                if len(last_buy_ids) > 50:
                    last_buy_ids = set(list(last_buy_ids)[-50:])
            else:
                print(f"[ERROR] Failed to fetch buys: {resp.status}")

@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am your NFT tracker bot.')

if __name__ == '__main__':
    bot.run(TOKEN)
