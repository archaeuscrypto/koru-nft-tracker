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
        # Fetch all activities and filter by type in code
        activities_url = f"https://api-mainnet.magiceden.dev/v2/collections/{COLLECTION_ADDRESS}/activities?offset=0&limit=40"
        print(f"[LOG] Fetching activities from Magic Eden API.")
        async with session.get(activities_url) as resp:
            print(f"[LOG] Activities response status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                global last_listing_ids, last_buy_ids
                new_listings = []
                new_buys = []
                for item in data:
                    activity_type = item.get('type')
                    # Debug: print type and key IDs for each activity
                    debug_id = item.get('pdaAddress') or item.get('txId') or item.get('mint') or item.get('tokenMint')
                    print(f"[DEBUG] Activity type: {activity_type}, ID: {debug_id}")
                    # Listings
                    if activity_type == 'list':
                        listing_id = item.get('pdaAddress')
                        if listing_id and listing_id not in last_listing_ids:
                            print(f"[NEW LISTING] {listing_id}")
                            new_listings.append(item)
                            last_listing_ids.add(listing_id)
                    # Buys
                    elif activity_type == 'buyNow':
                        tx_id = item.get('txId')
                        if tx_id and tx_id not in last_buy_ids:
                            print(f"[NEW BUY] {tx_id}")
                            new_buys.append(item)
                            last_buy_ids.add(tx_id)
                # Send new listings
                if new_listings:
                    for item in new_listings:
                        name = item.get('token', {}).get('name', 'Unknown')
                        price = item.get('price', 'N/A')
                        mint = item.get('tokenMint') or item.get('token', {}).get('mintAddress', '')
                        msg = f"New Listing: {name} for {price} SOL\nLink: https://magiceden.io/item-details/{mint}"
                        await channel.send(msg)
                        print(f"[SENT] Listing: {name} for {price} SOL")
                else:
                    print("[LOG] No new listings found.")
                # Send new buys
                if new_buys:
                    for item in new_buys:
                        price = item.get('price', 'N/A')
                        buyer = item.get('buyer', 'Unknown')
                        mint = item.get('mint', '')
                        msg = f"New Buy: {price} SOL by {buyer}\nLink: https://magiceden.io/item-details/{mint}"
                        await channel.send(msg)
                        print(f"[SENT] Buy: {price} SOL by {buyer}")
                else:
                    print("[LOG] No new buys found.")
                # Keep only the latest 50 IDs
                if len(last_listing_ids) > 50:
                    last_listing_ids = set(list(last_listing_ids)[-50:])
                if len(last_buy_ids) > 50:
                    last_buy_ids = set(list(last_buy_ids)[-50:])
            else:
                print(f"[ERROR] Failed to fetch activities: {resp.status}")

@bot.command()
async def hello(ctx):
    await ctx.send('Hello! I am your NFT tracker bot.')

if __name__ == '__main__':
    bot.run(TOKEN)
