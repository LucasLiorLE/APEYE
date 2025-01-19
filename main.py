"""
Major.Release.Push

Major - Everything a major update happens; Change of code, rework of everything, etc.
Release - Every release that happens, usually involving finally having a ton of fixes/new commands
Push - Every push that happens, or commit that is big enough.
"""

"""
Made by LucasLiorLE (https://github.com/LucasLiorLE/APEYE)
    - This is just my bot I made for fun, mostly during my free time.
    - Feel free to "steal" or take portions of my code.
    - Has a lot of usefull utilities!
    - /help for more info!

Release Notes:
    - bot_utils now exists, it's my own package used to manage my own bot.
    - Prefix commands should now work.
    - Video and image related commands (check videos and images cog)
    - EXP system now has a server and client
        - exp and level commands group

This was last updated: 1/17/2025 8:19 PM
"""

import discord
from discord.ext import commands

import os, random, datetime, math, asyncio, asyncpraw

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path

from aiohttp import ClientSession
from ossapi import Ossapi

from bot_utils import (
    open_file,
    save_file,
    get_player_data,
    __version__
)

class InvalidKeyError(Exception): ...

botAdmins = [721151215010054165]
botMods = []
botTesters = []

class StatusManager:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = [
            "noob",
            "Glory to the CCP! (我们的)",
            "https://www.nohello.com/",
        ]

    async def change_status(self):
        while True:
            await self.bot.wait_until_ready()
            current_status = random.choice(self.status_messages)

            await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name=current_status))
            await asyncio.sleep(600)

intents = discord.Intents.all()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.dm_messages = True
intents.members = True

class APEYEBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('>'),
            intents=intents,
            case_insensitive=True
        )
        self.status_manager = StatusManager(self)

    async def setup_hook(self):
        try:
            print("Loading cogs...\n-----------------")
            await load_cogs()
            print("-----------------\nCogs loaded successfully.")
            
            # print("Clearing existing commands...")
            # Clear global commands
            # self.tree.clear_commands(guild=None)
            # Clear guild-specific commands
            # for guild in self.guilds:
            #     self.tree.clear_commands(guild=guild)
                
            print("Syncing commands...")
            await self.tree.sync()
            print(f"{len(self.tree.get_commands())} commands successfully synced.")
        except Exception as e:
            print(f"An error occurred during setup: {e}")
        print("Bot is ready.")

bot = APEYEBot()

secrets = Path('storage/secrets.env')
load_dotenv(dotenv_path=secrets)

client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
user_agent = os.getenv("user_agent")
cr_api = os.getenv("cr_api")
token = os.getenv("token")
osu_api = os.getenv("osu_api")
osu_secret = os.getenv("osu_secret")
hypixel_api = os.getenv("hypixel_api")

# https://sky.shiiyu.moe/api/v2/profile/ also works as a skyblock profile command.

async def test_hy_key() -> bool:
    async with ClientSession() as session:
        async with session.get(f"https://api.hypixel.net/player?key={hypixel_api}") as response:
            if response.status == 403:
                data = await response.json()
                if data.get("success") == False and data.get("cause") == "Invalid API key": 
                    return False
            elif response.status == 400: # UUID is not provided, therefore it would return 400
                return True
            else:
                print(f"Request failed with status code: {response.status}")
                return False

user_last_message_time = {}

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if isinstance(message.channel, discord.DMChannel):
        return

    server_id = str(message.guild.id)
    member_id = str(message.author.id)
    current_time = datetime.now(timezone.utc)

    server_info = open_file("info/server_info.json")
    member_data = open_file("info/member_info.json")

    afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})
    exp_data = server_info.setdefault(server_id, {}).setdefault("exp", {})

    if member_id in afk_data:
        original_name = afk_data[member_id].get("original_name")
        del afk_data[member_id]
        save_file("info/server_info.json", server_info)

        await message.add_reaction("👋")
        await message.channel.send(f"Welcome back, {message.author.mention}! You are no longer AFK.", delete_after=3)
        if original_name and message.author.display_name != original_name:
            try:
                await message.author.edit(nick=original_name)
            except discord.Forbidden:
                pass

    for user in message.mentions:
        user_id = str(user.id)
        if user_id in afk_data:
            afk_reason = afk_data[user_id].get("reason", None)
            afk_time = afk_data[user_id].get("time", datetime.now(timezone.utc).isoformat())
            embed = discord.Embed(
                title=f"{user.display_name} is AFK",
                description=afk_reason,
                timestamp=datetime.fromisoformat(afk_time),
                color=discord.Color.orange(),
            )
            await message.channel.send(embed=embed)

    if member_id not in member_data:
        member_data[member_id] = {"EXP": 0}

    if member_id not in exp_data:
        exp_data[member_id] = {"EXP": 0}

    last_message_time = user_last_message_time.get(member_id)

    if last_message_time is None or current_time - last_message_time >= timedelta(minutes=1):
        message_length = len(message.content)
        exp_gain = min(75, math.floor(message_length / 15)) + (random.randint(5, 15)) 

        member_data[member_id]["EXP"] += exp_gain

        if "exp" not in server_info:
            server_info["exp"] = {}
        if server_id not in server_info["exp"]:
            server_info["exp"][server_id] = {}
        server_info["exp"][server_id][member_id] = server_info["exp"][server_id].get(member_id, 0) + exp_gain

        save_file("info/member_info.json", member_data)
        save_file("info/server_info.json", server_info)

async def load_cogs():
    def find_cogs(directory):
        cogs = []
        ignore = ['cr.py']
        
        for item in os.listdir(directory):
            if item in ignore:
                continue
                
            path = os.path.join(directory, item)
            if os.path.isfile(path) and item.endswith('.py') and item != '__init__.py':
                module_path = path.replace(os.sep, '.')[2:-3]
                cogs.append(module_path)
            elif os.path.isdir(path):
                init_file = os.path.join(path, '__init__.py')
                if os.path.exists(init_file):
                    module_path = path.replace(os.sep, '.')[2:]
                    cogs.append(module_path)
                else:
                    cogs.extend(find_cogs(path))
        return cogs

    cog_paths = find_cogs('./cogs')
    cog_paths.sort(key=lambda x: "group" not in x)
    
    for cog_path in cog_paths:
        try:
            await bot.load_extension(cog_path)
            print(f"Loaded {cog_path}")
            # print(f"Current commands: {[cmd.name for cmd in bot.tree.get_commands()]}")
        except Exception as e:
            print(f"Failed to load {cog_path}: {e}")

async def check_apis():
    # Check Hypixel API
    if not await test_hy_key():
        raise InvalidKeyError("Invalid hypixel API key provided. Please check secrets.env, or possibly expired code?")
    print("Hypixel API key is valid.")

    # Check Clash Royale API
    if not await get_player_data(None):
        raise InvalidKeyError("Invalid Clash Royale Key passed. Please check secrets.env\n"
                              "InvalidKeyError: If your key is there, consider checking if your IP is authorized.")
    print("Clash Royale key is valid.")
    
    # Check Osu API
    try:
        osu_api = Ossapi(int(osu_api), osu_secret)
        print("Osu API key is valid.")
    except ValueError:
        raise InvalidKeyError("Invalid API keys; Are you sure you entered your osu api correctly?")

    # Check Reddit API
    try:
        reddit = asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        ) 
        print("Reddit API is valid.")
    except Exception as e:
        raise InvalidKeyError(f"An error occured when checking reddit API: {e}\n"
                              "InvalidKeyError: Are you sure you entered secrets.env correctly?")
    
    return True

async def main():
    print("Script loaded.")
    print(f"Current Version: v{__version__}")

    # if not await check_apis():
    #     raise InvalidKeyError()

    print("The bot is starting, please give it a minute.")
    try:
        await bot.start(token)
    except discord.errors.LoginFailure:
        print("Possible incorrect bot token has been passed. Please check secrets.env, otherwise restart.")
    except KeyboardInterrupt: # Not needed here
        print("Ctrl + C detected. Shutting down gracefully...")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Bot is shutting down. If an error occurs, you can ignore it.")
        await bot.close()

if __name__ == "__main__": # Not needed anymore, but still here. It was because I imported main in cogs/info.py
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
    except Exception as e:
        print(f"An unexpected error occurred during bot execution: {e}")

        print(f"An unexpected error occurred during bot execution: {e}")
