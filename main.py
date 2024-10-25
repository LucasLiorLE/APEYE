import json
import os
import random
import time
import math
import io
import ssl
import aiohttp
import requests
import asyncio
import asyncpraw
import re
import humanize
import datetime
import traceback

from io import BytesIO
from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageSequence
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord import Role, app_commands
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput

logs = {}
log_id_counter = 1  

def storage_log(type, error):
    global log_id_counter  

    type = type.lower()

    if type not in logs:
        logs[type] = []

    log_entry = {
        "Error": error,
        "ID": log_id_counter,
        "time": int(time.time())
    }

    logs[type].append(log_entry)
    print(error)

    log_id_counter += 1

class StatusManager:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = [
            "https://discord.gg/rbRwnD5DSd",
            "Glory to the CCP! (我们的)",
            "https://www.nohello.com/",
        ]

    async def change_status(self):
        while True:
            await self.bot.wait_until_ready()
            current_status = random.choice(self.status_messages)

            await self.bot.change_presence(
                status=discord.Status.dnd, activity=discord.Game(name=current_status)
            )
            await asyncio.sleep(600)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.dm_messages = True
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)

def parse_duration(duration_str):
    duration_regex = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = duration_regex.match(duration_str)

    if not match:
        return None

    days, hours, minutes, seconds = match.groups()

    total_duration = timedelta()

    if days:
        total_duration += timedelta(days=int(days))
    if hours:
        total_duration += timedelta(hours=int(hours))
    if minutes:
        total_duration += timedelta(minutes=int(minutes))
    if seconds:
        total_duration += timedelta(seconds=int(seconds))

    return total_duration

def check_user(interaction: discord.Interaction, original_user: discord.User) -> bool:
    return interaction.user.id == original_user.id

def open_file(filename):
    with open(filename, "r") as f:
        file_data = json.load(f)
    return file_data

def save_file(filename, data):
    with open(filename, "w") as f:
        json.dump(
            data,
            f,
            indent=4,
            default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o,
        )

secrets = open_file("storage/secrets.json")

client_id = secrets.get("client_id")
client_secret = secrets.get("client_secret")
user_agent = secrets.get("user_agent")
cr_API = secrets.get("cr_API")
token = secrets.get("token")

reddit = asyncpraw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
) 


async def handle_error(interaction: discord.Interaction, error, log_error_id):
    embed = discord.Embed(title="An error occurred", color=discord.Color.red())
    embed.add_field(name="Error", value=str(error), inline=False)
    embed.add_field(name="ID", value=log_error_id, inline=False)
    
    storage_log("error", str(error))
    
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_application_command_error(interaction: discord.Interaction, error):
    handle_error(interaction, error, log_error_id=log_id_counter)

@bot.event
async def on_command_error(interaction: discord.Interaction, error):
    handle_error(interaction, error, log_error_id=log_id_counter)

class ReplyModal(discord.ui.Modal):
    def __init__(self, user, message_id, reply_author):
        super().__init__(title="Reply to User")
        self.user = user
        self.message_id = message_id
        self.reply_author = reply_author
        self.add_item(
            TextInput(
                label="Your reply",
                placeholder="Type your reply here...",
                style=discord.TextStyle.long,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        reply_content = self.children[0].value
        try:
            await self.user.send(
                f"**Reply from {self.reply_author.display_name}:**\n{reply_content}"
            )
            await interaction.response.send_message(
                f"Replied to {self.user.mention}: {reply_content}", ephemeral=True
            )
            reply_log_channel = bot.get_channel(1291626347713790033)
            if reply_log_channel:
                embed = discord.Embed(
                    title="Reply Sent",
                    description=f"**Replied to:** {self.user.mention}\n"
                    f"**Replied by:** {self.reply_author.mention}\n"
                    f"**Original Message ID:** {self.message_id}\n"
                    f"**Reply Content:** {reply_content}",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                )
                await reply_log_channel.send(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed to send the reply. The user may have DMs disabled.",
                ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Failed to send the DM or log the reply.", ephemeral=True
            )

class ReplyButton(Button):
    def __init__(self, user, message_id):
        super().__init__(label="Reply", style=discord.ButtonStyle.primary)
        self.user = user
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        modal = ReplyModal(self.user, self.message_id, interaction.user)
        await interaction.response.send_modal(modal)

user_last_message_time = {}
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        for guild in bot.guilds:
            member = guild.get_member(message.author.id)
            if member:
                preferences = open_file("info/preferences.json")
                guild_id = str(guild.id)

                if guild_id in preferences and "dmLogs" in preferences[guild_id]:
                    dm_log_channel = bot.get_channel(preferences[guild_id]["dmLogs"])
                    if dm_log_channel:
                        embed = discord.Embed(
                            title="Direct Message Received",
                            description=f"**User:** {message.author.mention}\n"
                                        f"**Message:** {message.content or '[No text content]'}\n"
                                        f"**Message ID:** {message.id}",
                            color=discord.Color.blue(),
                            timestamp=message.created_at,
                        )

                        if message.attachments:
                            for attachment in message.attachments:
                                embed.add_field(
                                    name="Attachment",
                                    value=attachment.url,
                                    inline=False,
                                )

                        reply_button = ReplyButton(user=message.author, message_id=message.id)
                        view = discord.ui.View()
                        view.add_item(reply_button)

                        await dm_log_channel.send(embed=embed, view=view)

    if not isinstance(message.channel, discord.DMChannel):
        member_id = str(message.author.id)
        current_time = datetime.now()

        member_data = open_file("info/member_info.json")

        if member_id not in member_data:
            member_data[member_id] = {"EXP": 0}

        last_message_time = user_last_message_time.get(member_id)

        if last_message_time is None or current_time - last_message_time >= timedelta(minutes=1):
            message_length = len(message.content)
            exp_gain = math.floor(message_length / 15)

            member_data[member_id]["EXP"] += exp_gain
            user_last_message_time[member_id] = current_time

            save_file("info/member_info.json", member_data)

        await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.tree.sync()
    status_manager = StatusManager(bot)
    bot.loop.create_task(status_manager.change_status())

@bot.tree.command(name="error", description="Allows you to view a certain error.")
async def view_error(interaction: discord.Interaction, error_id: int):
    await interaction.response.defer()
    for log_type, log_entries in logs.items():
        for entry in log_entries:
            if entry["ID"] == error_id:
                timestamp = entry["time"]
                error_message = entry["Error"]
                embed = discord.Embed(
                    title=f"Error ID: {error_id}",
                    color=discord.Color.red()
                )
                embed.add_field(name="Type", value=log_type.capitalize(), inline=False)
                embed.add_field(name="Error", value=error_message, inline=False)
                embed.add_field(name="Timestamp", value=timestamp, inline=False)
                await interaction.followup.send(embed=embed)
                return

    await interaction.followup.send(f"No error found with ID {error_id}")

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="ccp", description="Ping a user and send a message.")
@app_commands.describe(
    choice="Select whether to increase or decrease the Social Credit Score",
    user_id="The ID of the user to mention",
)
@app_commands.choices(
    choice=[
        app_commands.Choice(name="Increase", value="increase"),
        app_commands.Choice(name="Decrease", value="decrease"),
    ]
)
async def ccp(interaction: discord.Interaction, choice: str, user_id: str):
    await interaction.response.defer()

    if choice == "increase":
        message = f"<@{user_id}> (我们的) Good work citizen, and glory to the CCP! Remember to redeem your food units after 12:00 P.M."
    elif choice == "decrease":
        message = (
            f"<@{user_id}> (我们的) :arrow_double_down: Your Social Credit Score has decreased "
            ":arrow_double_down:. Please refrain from making more of these comments or we will have "
            "to send a Reeducation Squad to your location. Thank you! Glory to the CCP! :flag_cn: (我们的)"
        )

    await interaction.followup.send(message)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="ping", description="Shows your latency and the bot's latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()
    start_time = time.time()

    time.sleep(0.17)
    metadata_args_parsing_time = (time.time() - start_time) * 1000

    processing_start_time = time.time()
    await asyncio.sleep(0.1)
    processing_time = (time.time() - processing_start_time) * 1000
    end_time = time.time()
    round_trip_latency = round((end_time - start_time) * 1000)
    bot_latency = round(bot.latency * 1000)
    color = (0x00FF00 if bot_latency < 81 else 0xFFFF00 if bot_latency < 201 else 0xFF0000)
    embed = discord.Embed(
        title="Pong! 🏓",
        description=(
            f"Your approximate latency: {round_trip_latency}ms\n"
            f"Bot's latency: {bot_latency}ms\n"
            f"Metadata and Args Parsing: {metadata_args_parsing_time:.2f}ms\n"
            f"Processing Time: {processing_time:.2f}ms\n"
            f"Response Time: {round_trip_latency + processing_time:.2f}ms"
        ),
        color=color,
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="info", description="Displays information about the bot.")
async def info(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = discord.Embed(
        title="Bot Info",
        description="This bot is developed by LucasLiorLE.",
        color=0x808080,
    )
    embed.add_field(name="Version", value="v1.0.8a")
    embed.add_field(name="Server Count", value=len(bot.guilds), inline=True)
    embed.add_field(name="Library", value="Discord.py", inline=True)
    embed.add_field(name="Other", value="Ok")
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

    button = discord.ui.Button(label="Visit Website", url="https://lucasliorle.github.io")
    view = discord.ui.View()
    view.add_item(button)

    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="serverinfo", description="Shows information about the server.")
async def serverinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild

    roles = [role.name for role in guild.roles]
    categories = len(guild.categories)
    text_channels = len([channel for channel in guild.text_channels])
    voice_channels = len([channel for channel in guild.voice_channels])
    created_at = guild.created_at.strftime("%m/%d/%Y %I:%M %p")

    embed = discord.Embed(title="Server Info", color=0x808080)
    embed.add_field(name="Test", value="test", inline=False)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Roles", value=len(roles), inline=True)
    embed.add_field(name="Category Channels", value=categories, inline=True)
    embed.add_field(name="Text Channels", value=text_channels, inline=True)
    embed.add_field(name="Voice Channels", value=voice_channels, inline=True)
    embed.add_field(name="Role List", value=", ".join(roles), inline=False)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Server Created", value=f"{created_at}", inline=True)
    embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.avatar.url,
    )

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="roleinfo", description="Provides information for a role.")
@app_commands.describe(role="The role to get the info for")
async def roleinfo(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()

    permissions = role.permissions
    permissions_list = [perm for perm, value in permissions if value]

    role_created_at = role.created_at
    role_created_date = role_created_at.strftime("%m/%d/%Y %H:%M")
    days_ago = (datetime.now(timezone.utc) - role_created_at).days

    embed = discord.Embed(title=f"Role info for {role.name}", color=role.color)
    embed.add_field(name="Role ID", value=role.id, inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
    embed.add_field(name="Hoist", value=str(role.hoist), inline=True)
    embed.add_field(
        name="Position",
        value=f"{role.position}/{len(interaction.guild.roles)}",
        inline=True,
    )
    embed.add_field(
        name="Permissions",
        value=", ".join(permissions_list) if permissions_list else "No permissions",
        inline=False,
    )
    embed.add_field(name="Member Count", value=len(role.members), inline=True)
    embed.add_field(
        name="Role Created On",
        value=f"{role_created_date} ({days_ago} days ago)",
        inline=True,
    )

    if role.icon:
        embed.set_thumbnail(url=role.icon.url)

    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="userinfo", description="Provides information about a user.")
@app_commands.describe(member="The member to get the info for",)
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    member = member or interaction.user
    roles = [role.name for role in member.roles]
    embed = discord.Embed(title="User Info", color=0x808080)
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="Username", value=member.display_name)
    embed.add_field(name="User ID", value=member.id)
    embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"))
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"))
    embed.add_field(name="Roles", value=", ".join(roles))
    embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
    await interaction.followup.send(embed=embed)

class AvatarGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="avatar", description="Avatar-related commands")

    @app_commands.command(name="get", description="Displays a user's global avatar.")
    @app_commands.describe(member="The member to get the avatar for")
    async def get(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x808080)
            embed.set_image(url=member.avatar.url)
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=interaction.user.avatar.url,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_error(interaction, e, log_error_id=log_id_counter)


    @app_commands.command(
        name="server",
        description="Displays a user's server-specific avatar if available.",
    )
    @app_commands.describe(member="The member to get the server-specific avatar for")
    async def server(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Server Avatar", color=0x808080)
            embed.set_image(url=member.display_avatar.url)  
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=interaction.user.avatar.url,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_error(interaction, e, log_error_id=log_id_counter)

bot.tree.add_command(AvatarGroup())

@bot.tree.command(name="mlevel", description="Calculate mee6 levels and how long it will take you to achieve them.")
@app_commands.describe( 
    current_level="Your current level",
    current_exp="Your current EXP in that level",
    target_level="The level you want to achieve",
    hours_per_day="Hours you will chat everyday"
)
async def mlevel(interaction: discord.Interaction, current_level: int, current_exp: int, target_level: int, hours_per_day: int):
    await interaction.response.defer()

    def exp_required(level):
        total_exp = 0
        for l in range(1, level + 1):
            total_exp += 5 * (l ** 2) + 50 * l + 100
        return total_exp

    target_exp = exp_required(target_level)
    current_level_exp = exp_required(current_level)
    required_exp = target_exp - (current_level_exp + current_exp)
    estimated_messages = required_exp / 20
    estimated_days = math.ceil(required_exp / (hours_per_day * 1200))

    embed = discord.Embed(
        title="Mee6 Level Calculator",
        description=f"Estimated based off you chat {hours_per_day} hours per day and gain {hours_per_day * 1200} EXP.\n**Other Info**\nCurrent Level: {current_level}\nCurrent EXP: {current_exp}\nTarget Level: {target_level}\nTotal EXP: {current_level_exp}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Required EXP", value=f"{required_exp:,}", inline=True)
    embed.add_field(name="Estimated Messages", value=f"{math.ceil(estimated_messages * 1.5):,}", inline=True)
    embed.add_field(name="Estimated Days", value=f"{estimated_days:,}", inline=True)
    embed.set_footer(
        text=f"Requested by {interaction.user}",
        icon_url=interaction.user.avatar.url,
    )

    await interaction.followup.send(embed=embed)

"""
GEOMETRY DASH COMMANDS
"""
class GeometryDashCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="gd", description="Geometry Dash related commands")

    @app_commands.command(name="gdprofile", description="Fetch a Geometry Dash profile.")
    @app_commands.describe(username="The Geometry Dash username to fetch.")
    async def gdprofile(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://gdbrowser.com/api/profile/{username}") as response:
                if response.status == 200:
                    data = await response.json()

                    if "username" not in data:
                        await interaction.followup.send(f"User {username} not found.", ephemeral=True)
                        return
                    
                    embed = discord.Embed(
                        title="Geometry Dash Profile",
                        description=f"Profile information for **{data['username']}**",
                        color=discord.Color.blue()
                    )
                    
                    embed.add_field(
                        name="Username",
                        value=f"{data['username']} (Account ID: {data['accountID']})",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Stats",
                        value=(
                            f"<:Stars:1299321915411791922> **Stars**: {data['stars']}\n"
                            f"<:Moons:1299321898169274378> **Moons**: {data['moons']}\n"
                            f"<:Coins:1299321945954713670> **Coins**: {data['coins']}\n"
                            f"<:UserCoins:1299321964867092510> **User Coins**: {data['userCoins']}"
                        ),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Demons",
                        value=(
                            f"**Total Beaten**: {data['demons']}\n"
                            f"**Classic Demons**:\n"
                            f" - <:EasyDemon:1299319586197471253> Easy: {data['classicDemonsCompleted']['easy']}\n"
                            f" - <:MediumDemon:1299319602936942635> Medium: {data['classicDemonsCompleted']['medium']}\n"
                            f" - <:HardDemon:1299319619571552318> Hard: {data['classicDemonsCompleted']['hard']}\n"
                            f" - <:InsaneDemon:1299319639959928872> Insane: {data['classicDemonsCompleted']['insane']}\n"
                            f" - <:ExtremeDemon:1299319662995046420> Extreme: {data['classicDemonsCompleted']['extreme']}\n"
                            f" - <:WeeklyDemon:1299320499146330152> Weekly: {data['classicDemonsCompleted']['weekly']}\n"
                            f" - <:Gauntlet:1299320799458627626> Gauntlet: {data['classicDemonsCompleted']['gauntlet']}\n\n"
                            f"**Platformer Demons**:\n"
                            f" - <:EasyDemon:1299319586197471253> Easy: {data['platformerDemonsCompleted']['easy']}\n"
                            f" - <:MediumDemon:1299319602936942635> Medium: {data['platformerDemonsCompleted']['medium']}\n"
                            f" - <:HardDemon:1299319619571552318> Hard: {data['platformerDemonsCompleted']['hard']}\n"
                            f" - <:ExtremeDemon:1299319662995046420> Insane: {data['platformerDemonsCompleted']['insane']}\n"
                            f" - <:ExtremeDemon:1299319662995046420> Extreme: {data['platformerDemonsCompleted']['extreme']}"
                        ),
                        inline=False
                    )

                    social_links = ""
                    if data.get("youtube"):
                        social_links += f"[YouTube](https://www.youtube.com/channel/{data['youtube']})\n"
                    if data.get("twitter"):
                        social_links += f"[Twitter](https://twitter.com/{data['twitter']})\n"
                    if data.get("twitch"):
                        social_links += f"[Twitch](https://www.twitch.tv/{data['twitch']})\n"

                    if social_links:
                        embed.add_field(name="Social", value=social_links, inline=False)

                    embed.set_footer(
                        text=f"Rank: {data["rank"]} | Requested by {interaction.user}",
                        icon_url=interaction.user.avatar.url
                    )

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"Failed to retrieve profile for {username}.", ephemeral=True)

bot.tree.add_command(GeometryDashCommandGroup())

"""
CLASH ROYALE COMMANDS
"""

async def get_player_data(tag: str):
    api_url = f"https://api.clashroyale.com/v1/players/{tag}"  
    headers = {
        "Authorization": f"Bearer {cr_API}"  
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:

            try:
                response_json = await response.json()

                if response.status == 200:
                    return response_json
            except Exception as e:
                error_message = await response.text()  
                try:
                    error_info = await response.json()
                    message = error_info.get("message", "No message provided")
                    error_type = error_info.get("type", "No type provided")
                except Exception:
                    message = "Failed to retrieve message"
                    error_type = "Unknown error type"

                return None

async def get_clan_data(clan_tag: str):
    api_url = f"https://api.clashroyale.com/v1/clans/{clan_tag}"

    headers = {
        "Authorization": f"Bearer {cr_API}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status == 200:
                clan_data = await response.json()
                return {
                    "name": clan_data.get("name", "N/A"),
                    "tag": clan_data.get("tag", "N/A"),
                    "clanScore": clan_data.get("clanScore", 0),
                    "clanWarTrophies": clan_data.get("clanWarTrophies", 0),
                    "requiredTrophies": clan_data.get("requiredTrophies", 0),
                    "donationsPerWeek": clan_data.get("donationsPerWeek", 0),
                    "members": clan_data.get("members", 0),
                    "description": clan_data.get("description", "No description available."),
                    "type": clan_data.get("type", "N/A"),
                }
            else:
                return None

class ProfileView(View):
    def __init__(self, player_data, current_page="main"):
        super().__init__(timeout=None)
        self.player_data = player_data
        self.current_page = current_page
        self.main_button = Button(label="Main", style=discord.ButtonStyle.primary)
        self.main_button.callback = self.show_main_page
        self.add_item(self.main_button)
        self.deck_button = Button(label="Deck", style=discord.ButtonStyle.secondary)
        self.deck_button.callback = self.show_deck_page
        self.add_item(self.deck_button)
        self.update_buttons()
        self.emoji_data = self.load_emoji_data()

    def load_emoji_data(self):
        with open("storage/emoji_data.json", "r") as f:
            return json.load(f)

    def update_buttons(self):
        self.main_button.disabled = self.current_page == "main"
        self.deck_button.disabled = self.current_page == "deck"

    async def show_main_page(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons()

        embed = self.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_deck_page(self, interaction: discord.Interaction):
        self.current_page = "deck"
        self.update_buttons()

        embed = self.create_deck_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_main_embed(self):
        name = self.player_data.get("name", "Unknown")
        user_id = self.player_data.get("tag", "Unknown")
        wins = self.player_data.get("wins", 0)
        losses = self.player_data.get("losses", 0)
        trophies = self.player_data.get("trophies", "Unknown")
        max_trophies = self.player_data.get("bestTrophies", "Unknown")
        arena = self.player_data.get("arena", {}).get("name", "Unknown")
        goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("trophies", "Unknown")
        max_goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("bestTrophies", "Unknown")
        goblin_arena = self.player_data.get("progress", {}).get("goblin-road", {}).get("arena", {}).get("name", "Unknown")
        clan_name = self.player_data.get("clan", {}).get("name", "No Clan")
        clan_tag = self.player_data.get("clan", {}).get("tag", "N/A")
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        embed = discord.Embed(title=f"{name}'s Clash Royale Profile", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{name} ({user_id})", inline=False)
        embed.add_field(name="Wins/Losses", value=f"{wins}/{losses} ({winrate:.2f}%)", inline=False)
        embed.add_field(name="<:Trophy:1299093384882950245> Trophy Road", value=f"{trophies}/{max_trophies} ({arena})", inline=False)
        embed.add_field(name="<:GoblinTrophy:1299093585274343508> Goblin Queen's Journey", value=f"{goblin_trophies}/{max_goblin_trophies} ({goblin_arena})", inline=False)
        embed.add_field(name="Clan", value=f"{clan_name} ({clan_tag})", inline=False)
        return embed

    def create_deck_embed(self):
        embed = discord.Embed(title="Deck Information", color=discord.Color.green())

        current_deck = self.player_data.get("currentDeck", [])
        card_ids = []  

        for index, card in enumerate(current_deck):
                name = card.get("name", "Unknown")
                level = card.get("level", "Unknown")
                star_level = card.get("starLevel", "0")
                emoji = self.get_card_emoji(name)

                card_id = card.get("id")
                if card_id:
                        card_ids.append(str(card_id))

                field_value = f"{emoji} | Level: {level} | Star Level: {star_level}"
                embed.add_field(name=f"Card {index + 1}: {name}", value=field_value, inline=False)

        embed.description=f"[Click here to copy the deck](https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={'%3B'.join(card_ids)}&l=Royals)"

        return embed

    def get_card_emoji(self, card_name):
        formatted_name = ''.join(re.findall(r'[A-Za-z]', card_name))
        emoji_id = self.emoji_data.get(formatted_name)
        if emoji_id:
            return f"<:{formatted_name}:{emoji_id}>"
        return "❓" 

class ClashRoyaleCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="cr", description="Clash Royale related commands")

    @app_commands.command(name="connect", description="Connect your Clash Royale profile.")
    @app_commands.describe(
        tag="Your player tag",
    )   
    async def crconnect(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer()

        if not tag.startswith("#"):
            tag = f"#{tag}"

        player_data = await get_player_data(tag.replace("#", "%23"))

        if not player_data:
            await interaction.response.send_message("Failed to retrieve data for the provided player tag.", ephemeral=True)
            return

        random_deck = random.sample(
            ["Giant", "Mini P.E.K.K.A", "Fireball", "Archers", "Minions", "Knight", "Musketeer", "Arrows"], k=8
        )
        random_deck_str = " ".join(f"`{card}`" for card in random_deck)
        await interaction.followup.send(f"Please use the following deck: {random_deck_str}\nYou have 5 minutes to make it.")

        await asyncio.sleep(300)

        current_deck = player_data.get("currentDeck", [])
        player_deck_names = [card.get("name", "Unknown") for card in current_deck]

        if sorted(player_deck_names) == sorted(random_deck):
            member_info = open_file("info/member_info.json")
            discord_user_id = str(interaction.user.id)

            if discord_user_id not in member_info:
                member_info[discord_user_id] = {}

            member_info[discord_user_id]["cr_id"] = tag
            save_file("info/member_info.json", member_info)

            await interaction.followup.send("Deck matched! Your Clash Royale ID has been successfully linked.")
        else:
            await interaction.followup.send("Deck did not match. Please try again.")

    @app_commands.command(name="profile", description="Get Clash Royale player profile data")
    @app_commands.describe(
        tag="The user's tag (The one with the #, optional)",
        user="The user ID of the member (optional)"
    )
    async def clash_royale_profile(self, interaction: discord.Interaction, tag: str = None, user: str = None):
        await interaction.response.defer()

        member_info = open_file("info/member_info.json")

        if tag is None:
            user_id = str(interaction.user.id)
            cr_id = member_info.get(user_id, {}).get("cr_id")

            if cr_id:
                tag = cr_id
            else:
                await interaction.followup.send("No linked Clash Royale account found.")
                return
        else:
            if not tag.startswith("#"):
                tag = "#" + tag.strip()


        player_data = await get_player_data(tag.replace("#", "%23"))

        if player_data:
            view = ProfileView(player_data)
            embed = view.create_main_embed()
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"Player data not found for tag: {tag}")

    @app_commands.command(name="clan", description="Get data about a Clash Royale clan")
    @app_commands.describe(clantag="The clan's tag (the one with the #)")
    async def clan(self, interaction: discord.Interaction, clantag: str):
        await interaction.response.defer()

        if not clantag.startswith("#"):
            clantag = "#" + clantag.strip()

        clan_data = await get_clan_data(clantag.replace("#", "%23"))

        if clan_data:
            embed = discord.Embed(title=f"Clan Data for {clan_data['name']}", color=discord.Color.blue())

            embed.add_field(name="Name", value=f"{clan_data['name']} ({clan_data['tag']})", inline=True)
            embed.add_field(name="Clan Score", value=clan_data['clanScore'], inline=True)
            embed.add_field(name="Clan Trophies", value=clan_data['clanWarTrophies'], inline=True)
            embed.add_field(name="Required Trophies", value=clan_data['requiredTrophies'], inline=True)
            embed.add_field(name="Weekly Donations", value=clan_data['donationsPerWeek'], inline=True)
            embed.add_field(name="Members", value=clan_data['members'], inline=True)
            embed.add_field(name="Description", value=clan_data['description'], inline=True)

            embed.set_footer(text=f"The clan is currently **{clan_data['type']}**")

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"Clan data not found for tag: {clantag}")

bot.tree.add_command(ClashRoyaleCommandGroup())

"""
ROBLOX COMMANDS
"""

async def fetch_roblox_bio(roblox_user_id):
    async with aiohttp.ClientSession() as session:
        url = f"https://users.roblox.com/v1/users/{roblox_user_id}"
        async with session.get(url) as response:
            data = await response.json()
            return data.get("description", "")

async def GetRobloxID(roblox_username):
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [roblox_username], "excludeBannedUsers": True},
        )
        if response.status != 200:
            return None
        data = await response.json()
        if not data["data"]:
            return None
        return data["data"][0]["id"]

class RobloxGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="roblox", description="Roblox account-related commands")

    @app_commands.command(name="connect", description="Connect with your Roblox account")
    @app_commands.describe(username="The username to connect to")
    @app_commands.checks.cooldown(1, 60)
    async def rbxconnect(self, interaction: discord.Interaction, username: str):
        color_sequence = " ".join(
            random.choices(
                ["orange", "strawberry", "pear", "apple", "banana", "watermelon"], k=10
            )
        )
        await interaction.response.send_message(
            f"Please update your Roblox bio with this sequence:\n**{color_sequence}**\nYou have 1 minute to complete it."
        )

        await asyncio.sleep(60)

        roblox_user_id = await GetRobloxID(username)
        if roblox_user_id is None:
            await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
            return

        bio = await fetch_roblox_bio(roblox_user_id)

        if color_sequence in bio:
            member_info = open_file("info/member_info.json")
            discord_user_id = str(interaction.user.id)

            if discord_user_id not in member_info:
                member_info[discord_user_id] = {}

            member_info[discord_user_id]["roblox_username"] = username
            member_info[discord_user_id]["roblox_id"] = roblox_user_id
            save_file("info/member_info.json", member_info)

            await interaction.followup.send(f"Success! Your Roblox account is now linked.")

        else:
            await interaction.followup.send("Failed! Your Roblox bio did not match the given sequence.")

    @app_commands.command(name="description", description="Provides the description of a Roblox account.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).")
    async def rbxdescription(self, interaction: discord.Interaction, username: str = None):
        await interaction.response.defer()
        discord_user_id = str(interaction.user.id)
        member_info = open_file("info/member_info.json")

        if (
            discord_user_id not in member_info
            or "roblox_id" not in member_info[discord_user_id]
        ):
            await interaction.response.send_message("You don't have a linked Roblox account.")
            return

        if username:
            roblox_user_id = await GetRobloxID(username)
            if roblox_user_id is None:
                await interaction.response.send_message(f"Failed to retrieve Roblox ID for {username}.")
                return
        else:
            roblox_user_id = member_info[discord_user_id]["roblox_id"]

        bio = await fetch_roblox_bio(roblox_user_id)
        embed = discord.Embed(title=f"User Description for {roblox_user_id}", description=bio, color=0x808080)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="info", description="Provides info about your linked Roblox account.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).")
    async def rbxinfo(self, interaction: discord.Interaction, username: str = None):
        await interaction.response.defer()
        discord_user_id = str(interaction.user.id)
        member_info = open_file("info/member_info.json")

        if (
            discord_user_id not in member_info
            or "roblox_id" not in member_info[discord_user_id]
        ):
            await interaction.followup.send("You don't have a linked Roblox account.")
            return

        if username:
            roblox_user_id = await GetRobloxID(username)
            if roblox_user_id is None:
                await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                return
        else:
            roblox_user_id = member_info[discord_user_id]["roblox_id"]

        async with aiohttp.ClientSession() as session:
            async def fetch_friends_count(roblox_user_id: int):
                try:
                    async with session.get(f"https://friends.roblox.com/v1/users/{roblox_user_id}/friends/count") as response:
                        data = await response.json()
                        return data.get("count", 0)
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return 0

            async def fetch_followers_count(roblox_user_id: int):
                try:
                    async with session.get(f"https://friends.roblox.com/v1/users/{roblox_user_id}/followers/count") as response:
                        data = await response.json()
                        return data.get("count", 0)
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return 0

            async def fetch_following_count(roblox_user_id: int):
                try:
                    async with session.get(f"https://friends.roblox.com/v1/users/{roblox_user_id}/followings/count") as response:
                        data = await response.json()
                        return data.get("count", 0)
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return 0

            async def fetch_user_presence(roblox_user_id: int):
                try:
                    async with session.post(
                        "https://presence.roblox.com/v1/presence/users",
                        json={"userIds": [roblox_user_id]}
                    ) as response:
                        data = await response.json()
                        return data["userPresences"][0]
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return None

            async def fetch_user_info(roblox_user_id: int):
                try:
                    async with session.get(f"https://users.roblox.com/v1/users/{roblox_user_id}") as response:
                        return await response.json()
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return None

            async def check_premium(roblox_user_id: int):
                try:
                    headers = {
                        'accept': 'application/json'
                    }
                    url = f"https://premiumfeatures.roblox.com/v1/users/{roblox_user_id}/validate-membership"

                    async with session.get(url, headers=headers) as response:

                        if response.status == 200:
                            return await response.json()
                        else:
                            storage_log("error", f"{await response.text()}")                    
                            return None
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return None

            is_premium = await check_premium(roblox_user_id)
            friends_count = await fetch_friends_count(roblox_user_id)
            followers_count = await fetch_followers_count(roblox_user_id)
            following_count = await fetch_following_count(roblox_user_id)
            presence_data = await fetch_user_presence(roblox_user_id)
            if presence_data is None:
                await interaction.followup.send_message("Failed to fetch user presence. Please try again later.")
                return

            user_info = await fetch_user_info(roblox_user_id)
            if user_info is None:
                await interaction.followup.send_message("Failed to fetch user information. Please try again later.")
                return

        embed = discord.Embed(title=f"{'<:Premium:1298832636805910589>' if is_premium else ''}Roblox Account Info", color=0x808080)
        display_name = user_info.get("displayName", "N/A")
        username = user_info.get("name", "N/A")
        embed.add_field(
            name="Username",
            value=f"{display_name} (@{username})",
            inline=False,
        )
        embed.add_field(
            name="Friends/Followers/Following",
            value=f"Friends: {friends_count}\nFollowers: {followers_count}\nFollowing: {following_count}",
            inline=False,
        )

        status = "Offline" if presence_data["userPresenceType"] == 0 else "Online"
        last_online = datetime.strptime(presence_data["lastOnline"][:-1], "%Y-%m-%dT%H:%M:%S.%f")
        last_online_str = last_online.strftime("%m-%d-%Y")  
        embed.add_field(
            name="Status",
            value=f"{status} | Last online: {last_online_str}",
            inline=False,
        )
        creation_date = datetime.strptime(user_info["created"][:-1], "%Y-%m-%dT%H:%M:%S.%f")
        creation_date_str = creation_date.strftime("%m-%d-%Y")  
        embed.set_footer(
            text=f"Account created: {creation_date_str} | Requested by {interaction.user}",
            icon_url=interaction.user.avatar.url
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="avatar", description="Provides a Roblox account's avatar.")
    @app_commands.describe(
        username="The username of the Roblox account (leave blank to use linked account).",
        items="Whether or not to display the list of currently worn items (default: False)."
    )
    async def rbxavatar(self, interaction: discord.Interaction, username: str = None, items: bool = False):
        await interaction.response.defer()
        discord_user_id = str(interaction.user.id)
        member_info = open_file("info/member_info.json")

        if (
            discord_user_id not in member_info
            or "roblox_id" not in member_info[discord_user_id]
        ):
            await interaction.followup.send("You don't have a linked Roblox account.")
            return

        if username:
            roblox_user_id = await GetRobloxID(username)
            if roblox_user_id is None:
                await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                return
        else:
            roblox_user_id = member_info[discord_user_id]["roblox_id"]

        async with aiohttp.ClientSession() as session:
            async def get_avatar_items(session, roblox_user_id: int):
                url = f"https://avatar.roblox.com/v1/users/{roblox_user_id}/currently-wearing"
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if not data['assetIds']:  
                                return None  
                            return data['assetIds']
                        else:
                            return None
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return None

            async def get_avatar_thumbnail(session, roblox_user_id: int):
                url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={roblox_user_id}&size=720x720&format=Png&isCircular=false"
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and data['data'][0]['state'] == 'Completed':
                                return data['data'][0]['imageUrl']
                            else:
                                return None
                        else:
                            return None
                except Exception as e:
                    await handle_error(interaction, e, log_error_id=log_id_counter)
                    return None

            avatar_thumbnail_url = await get_avatar_thumbnail(session, roblox_user_id)

            if items:
                asset_ids = await get_avatar_items(session, roblox_user_id)
            else:
                asset_ids = None

            embed = discord.Embed(
                title="Roblox Avatar View",
                color=discord.Color.blue()
            )
            embed.set_image(url=avatar_thumbnail_url)  
            embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

            if items:
                if asset_ids:
                    urls = [f"https://www.roblox.com/catalog/{asset_id}" for asset_id in asset_ids]
                    url_list = '\n'.join(urls)
                    embed.description = url_list  
                else:
                    embed.description = "This user has no currently worn items."  
            else:
                embed.description = "Currently worn items are not displayed."

            await interaction.followup.send(embed=embed)

bot.tree.add_command(RobloxGroup())

class GloveView(discord.ui.View):
    def __init__(
        self,
        badge_embed,
        glove_embed,
        full_glove_data,
        obtained_gloves,
        roblox_id,
        owned_gamepasses,
        not_owned_gamepasses,
    ):
        super().__init__(timeout=None)
        self.badge_embed = badge_embed
        self.glove_embed = glove_embed
        self.full_glove_data = full_glove_data
        self.obtained_gloves = obtained_gloves
        self.roblox_id = roblox_id
        self.owned_gamepasses = owned_gamepasses
        self.not_owned_gamepasses = not_owned_gamepasses
        self.current_page = "glove_data"
        self.update_buttons()

    def update_buttons(self):
        self.glove_data_button.disabled = self.current_page == "glove_data"
        self.full_glove_data_button.disabled = self.current_page == "full_glove_data"
        self.additional_badges_button.disabled = (self.current_page == "additional_badges")
        self.gamepass_data_button.disabled = self.current_page == "gamepass_data"

    @discord.ui.button(label="Glove Data", style=discord.ButtonStyle.secondary)
    async def glove_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "glove_data"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.glove_embed], view=self)

    @discord.ui.button(label="Full Glove Data", style=discord.ButtonStyle.secondary)
    async def full_glove_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "full_glove_data"
        self.update_buttons()

        full_glove_description = "\n".join(
            [
                f"{glove} - <t:{int(datetime.strptime(obtain_date[:19], '%Y-%m-%dT%H:%M:%S').timestamp())}:F>"
                for glove, obtain_date in self.obtained_gloves.items()
            ]
        )

        full_glove_embed = discord.Embed(
            title=f"Full Glove Data for {interaction.user.name}",
            description=full_glove_description
            if full_glove_description
            else "No gloves obtained.",
            color=0xFF0000,
        )

        await interaction.response.edit_message(embeds=[full_glove_embed], view=self)

    @discord.ui.button(label="Additional Badges", style=discord.ButtonStyle.secondary)
    async def additional_badges_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "additional_badges"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.badge_embed], view=self)

    @discord.ui.button(label="Gamepass Data", style=discord.ButtonStyle.secondary)
    async def gamepass_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "gamepass_data"
        self.update_buttons()

        gamepass_embed = discord.Embed(
            title=f"Gamepass Data for {interaction.user.name}", color=0xFF0000
        )
        gamepass_embed.add_field(
            name="Owned",
            value=", ".join(self.owned_gamepasses) if self.owned_gamepasses else "None",
            inline=False,
        )
        gamepass_embed.add_field(
            name="Not Owned",
            value=", ".join(self.not_owned_gamepasses)
            if self.not_owned_gamepasses
            else "None",
            inline=False,
        )

        await interaction.response.edit_message(embed=gamepass_embed, view=self)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="cgloves", description="Check all the user's gloves in slap battles.")
@app_commands.describe(username="The user to check gloves for (leave empty to check your own)",)
async def cgloves(interaction: discord.Interaction, username: str = None):
    await interaction.response.defer()

    discord_user_id = str(interaction.user.id)

    if username is None:
        member_info = open_file("info/member_info.json")
        if (
            discord_user_id not in member_info
            or "roblox_id" not in member_info[discord_user_id]
        ):
            await interaction.followup.send("You need to provide a Roblox username or </roblox connect:1293791462260998156> your account first.")
            return
        roblox_id = member_info[discord_user_id]["roblox_id"]
    else:
        roblox_id = await GetRobloxID(username)
        if roblox_id is None:
            await interaction.followup.send(f"No data found for the username: {username}")
            return

    gloves = open_file("storage/gloves.json")
    all_badge_ids = [badge_id for badge_ids in gloves.values() for badge_id in badge_ids]
    url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, all_badge_ids))}"

    async with aiohttp.ClientSession() as session:
        response = await session.get(url)

        if response.status == 200:
            data = await response.json()
            if not data["data"]:
                await interaction.followup.send(f"No badges found for the user: {username if username else interaction.user.name}")
                return

            owned = [
                glove
                for glove, badge_ids in gloves.items()
                if all(
                    any(badge.get("badgeId") == badge_id for badge in data["data"])
                    for badge_id in badge_ids
                )
            ]
            not_owned = [glove for glove in gloves.keys() if glove not in owned]

            total_gloves = len(gloves)
            owned_gloves = len(owned)
            glove_percentage = (owned_gloves / total_gloves) * 100
            glove_percentage_str = f"{glove_percentage:.1f}"

            glove_embed = discord.Embed(
                title=f"SB Gloves Data for {username if username else interaction.user.name} ({roblox_id}):",
                description=f"Badge gloves:\n{owned_gloves}/{total_gloves} badge gloves owned ({glove_percentage_str}%)",
                color=0xFF0000,
            )
            glove_embed.add_field(
                name="OWNED", 
                value=", ".join(owned) if owned else "None", inline=False
            )
            glove_embed.add_field(
                name="NOT OWNED",
                value=", ".join(not_owned) if not_owned else "None",
                inline=False,
            )

            obtained_gloves = {
                glove: badge["awardedDate"]
                for glove, badge_ids in gloves.items()
                for badge_id in badge_ids
                for badge in data["data"]
                if badge.get("badgeId") == badge_id
            }

            additional_badges = {
                "Welcome": 2124743766,
                "You met the owner": 2124760252,
                "you met snow": 2124760875,
                "[REDACTED]": 2124760911,
                "Divine Punishment": 2124760917,
                "really?": 2124760923,
                "barzil": 2124775097,
                "The one": 2124807750,
                "Ascend": 2124807752,
                "1 0 0": 2124836270,
                'The "Reverse" Incident': 2124912059,
                "Clipped Wings": 2147535393,
                "Apostle of Judgement": 4414399146292319,
                "court evidence": 2124760907,
                "duck": 2124760916,
                "The Lone Orange": 2128220957,
                "The Hunt Event": 1195935784919838,
                "The Backrooms": 2124929812,
                "pog": 2124760877,
            }

            badge_ids = ",".join(map(str, additional_badges.values()))
            url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={badge_ids}"

            async with aiohttp.ClientSession() as session:
                response = await session.get(url)
                if response.status == 200:
                    data = await response.json()

                    badge_embed = discord.Embed(
                        title=f"Additional Badges for {username if username else interaction.user.name} ({roblox_id}):",
                        color=0xFF0000,
                    )

                    obtained_badges = {badge["badgeId"]: badge["awardedDate"] for badge in data["data"]}

                    for badge_name, badge_id in additional_badges.items():
                        if badge_id in obtained_badges:
                            awarded_date = obtained_badges[badge_id]
                            date, time, fraction = awarded_date.replace("Z", "+0000").partition(".")
                            fraction = fraction[: fraction.index("+")][:6] + "+0000"
                            awarded_date = f"{date}.{fraction}"
                            awarded_date = datetime.strptime(awarded_date, "%Y-%m-%dT%H:%M:%S.%f%z")
                            epoch_time = int(awarded_date.timestamp())
                            badge_embed.add_field(
                                name=f"<:check:1292269189536682004> | {badge_name}",
                                value=f"Obtained on <t:{epoch_time}:F>",
                                inline=False,
                            )
                        else:
                            badge_embed.add_field(
                                name=f"❌ | {badge_name}",
                                value="Not obtained",
                                inline=False,
                            )

                    gamepass_items = {
                        "2x Slaps": 15037108,
                        "5x Slaps": 15037147,
                        "Radio": 16067226,
                        "nothing": 16127797,
                        "OVERKILL": 16361133,
                        "Spectator": 19150776,
                        "Custom death audio": 21651535,
                        "CUSTOM GLOVE": 33742082,
                        "Animation Pack": 37665008,
                        "Vampire": 45176930,
                        "Ultra Instinct": 85895851,
                        "Cannoneer": 174818129,
                    }

                    owned_gamepasses = []
                    not_owned_gamepasses = []

                    async with aiohttp.ClientSession() as session:
                        for item_name, item_id in gamepass_items.items():
                            url = f"https://inventory.roblox.com/v1/users/{roblox_id}/items/1/{item_id}/is-owned"
                            async with session.get(url) as item_response:
                                if item_response.status == 200:
                                    item_data = await item_response.json()
                                    if item_data:
                                        owned_gamepasses.append(item_name)
                                    else:
                                        not_owned_gamepasses.append(item_name)

                    view = GloveView(
                        badge_embed,
                        glove_embed,
                        full_glove_data=obtained_gloves,
                        obtained_gloves=obtained_gloves,
                        roblox_id=roblox_id,
                        owned_gamepasses=owned_gamepasses,
                        not_owned_gamepasses=not_owned_gamepasses,
                    )

                    await interaction.followup.send(embeds=[glove_embed], view=view)

                else:
                    await interaction.followup.send("An error occurred while fetching the user's badges.")
        else:
            await interaction.followup.send("An error occurred while fetching the user's gloves.")

"""
FUN COMMANDS
"""

@bot.tree.command(name="say", description="Say a message in a channel")
@app_commands.describe(
    channel="The user to talk in",
    message="The message to send",
    attachment="An optional attachment to include",
    message_id="An optional message to reply to",
)
@commands.has_permissions(manage_messages=True)
async def say(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str = None,
    attachment: discord.Attachment = None,
    message_id: str = None,
):
    await interaction.response.defer()
    try:
        reference_message = None

        if message_id:
            try:
                reference_message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                await interaction.followup.send(f"Message with ID {message_id} not found in {channel.mention}.")
                return
            except discord.HTTPException as e:
                await interaction.followup.send(f"An error occurred while fetching the message: {e}")
                return

        if attachment:
            await channel.send(
                content=message,
                file=await attachment.to_file(),
                reference=reference_message,
            )
        else:
            await channel.send(content=message, reference=reference_message)

        await interaction.followup.send(f"Sent '{message}' to {channel.mention}")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)


@bot.tree.command(name="dm", description="Directly message a person.")
@app_commands.describe(
    user="The user to DM",
    message="The message to send to them",
    attachment="An optional attachment to include",
)
async def dm(
    interaction: discord.Interaction,
    user: discord.Member,
    message: str = None,
    attachment: discord.Attachment = None,
):
    await interaction.response.defer()
    try:
        if attachment:
            await user.send(content=message, file=await attachment.to_file())
        else:
            await user.send(content=message)
        await interaction.followup.send(f"Sent '{message}' to {user}")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)                  

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="fact", description="Fetches a random fact.")
async def fact(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        url = "https://uselessfacts.jsph.pl/random.json?language=en"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            embed = discord.Embed(title="Random Fact 🤓", description=data["text"], color=0x9370DB)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the fact.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="joke", description="Fetches a random joke.")
async def joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        url = "https://official-joke-api.appspot.com/jokes/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            if "setup" in data and "punchline" in data:
                joke_setup = data["setup"]
                joke_punchline = data["punchline"]
                await interaction.followup.send(content=f"**{joke_setup}**\n\n*||{joke_punchline}||*")
            else:
                await interaction.followup.send(content="Sorry, I couldn't fetch a joke right now. Try again later!")
        else:
            await interaction.followup.send(content="An error occurred while fetching the joke.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)
 

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="cat", description="Fetches a cute cat picture.")
async def cat(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        url = "https://api.thecatapi.com/v1/images/search"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            cat_image_url = data[0]["url"]

            embed = discord.Embed(title="Here's a cute cat for you!", color=0xFFA07A)
            embed.set_image(url=cat_image_url)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the cat picture.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter) 

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="dog", description="Fetches an adorable dog picture.")
async def dog(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        url = "https://dog.ceo/api/breeds/image/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            dog_image_url = data["message"]

            embed = discord.Embed(title="Here's a cute dog for you!", color=0xADD8E6)
            embed.set_image(url=dog_image_url)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the dog picture.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter) 

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="quote", description="Fetches an inspirational quote.")
async def quote(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        url = "https://zenquotes.io/api/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()[0]

            embed = discord.Embed(title=data["q"], description=f"-{data['a']}", color=0x66CDAA)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.follow.send(content="An error occurred while fetching the quote.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)   

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(
    name="meme",
    description="Fetches a funny meme!"
)
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://meme-api.com/gimme") as response:
                if response.status == 200:  
                    data = await response.json()
                    meme_data = data[0]

                    embed = discord.Embed(
                        title=f"({meme_data['title']})[{meme_data['postLink']}]",
                        color=0x66CDAA
                    )
                    embed.set_image(url=meme_data["url"])
                    embed.set_footer(text=f"{meme_data['ups']} Upvotes | By: {meme_data['author']}")
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("An error occurred when trying to fetch the meme")
        except Exception as e:
            await handle_error(interaction, e, log_error_id=log_id_counter)


"""
MODERATION COMMANDS
"""

async def store_modlog(modlog, user, moderator, reason):
    preferences = open_file("info/preferences.json")
    modlogs = open_file("info/modlogs.json")
    modstats = open_file("info/modstats.json")
    server_id = modlog["serverID"]

    if server_id not in modlogs:
        modlogs[server_id] = {}

    channel_id = preferences.get(server_id, {}).get("modLogs")
    channel = None

    if channel_id:
        channel = bot.get_channel(channel_id)

    embed = discord.Embed(title="Moderation Log", color=discord.Color.blue())
    embed.add_field(name="Type", value=modlog["type"], inline=False)
    embed.add_field(name="Moderator", value=str(moderator), inline=False)
    embed.add_field(name="Reason/Arguments", value=f"{reason}", inline=False)
    embed.add_field(name="Time", value=f"<t:{int(time.time())}:F>")

    if user is not None:
        user_id = str(user.id)
        embed.add_field(name="User", value=str(user), inline=False)

        if user_id not in modlogs[server_id]:
            modlogs[server_id][user_id] = {}

        last_case_number = max(map(int, modlogs[server_id][user_id].keys()), default=0)
        new_case_number = last_case_number + 1

        modlogs[server_id][user_id][new_case_number] = {
            "Type": modlog["type"],
            "User": str(user),
            "Moderator": str(moderator),
            "Reason": reason,
            "Time": int(time.time()),
        }

        moderator_id = str(moderator.id)

        if moderator_id not in modstats.get(server_id, {}):
            modstats[server_id][moderator_id] = {}

        if modlog["type"] in ["Kick", "Mute", "Ban"]:
            if moderator_id not in modstats[server_id]:
                modstats[server_id][moderator_id] = {}

            modstats[server_id][moderator_id][new_case_number] = {
                "type": modlog["type"],
                "timestamp": int(time.time()),
            }

    if channel is not None:
        await channel.send(embed=embed)

    save_file("modlogs.json", modlogs)
    save_file("modstats.json", modstats)

@bot.tree.command(name="setlogs", description="Changes the log channels of your server")
@app_commands.describe(
    option="Choose the type of log (Message Logs, DM Logs, Mod Logs)",
    channel="The channel to send logs to",
)
@app_commands.choices(
    option=[
        app_commands.Choice(name="Message Logs", value="messageLogs"),
        app_commands.Choice(name="DM Logs", value="dmLogs"),
        app_commands.Choice(name="Mod Logs", value="modLogs"),
    ]
)
async def setlogs(interaction: discord.Interaction, option: str, channel: discord.TextChannel):
    await interaction.response.defer()
    preferences = open_file("info/preferences.json")
    guild_id = str(interaction.guild_id)
    if guild_id not in preferences:
        preferences[guild_id] = {}

    preferences[guild_id][option] = channel.id
    save_file("preferences.json", preferences)
    response_map = {
        "messageLogs": f"Message Logs will be sent to: {channel.mention}",
        "dmLogs": f"DM Logs will be sent to: {channel.mention}",
        "modLogs": f"Mod Logs will be sent to: {channel.mention}",
    }

    await interaction.followup.send(response_map.get(option, "Invalid option selected."))

@bot.tree.command(name="setroles", description="Allows you to set the server roles")
@app_commands.describe(option="Choose the role to set", role="The role to set for members")
@app_commands.choices(option=[app_commands.Choice(name="Member", value="member")])
async def setroles(interaction: discord.Interaction, option: str, role: discord.Role):
    await interaction.response.defer()
    try:
        preferences = open_file("info/preferences.json")
        guild_id = str(interaction.guild_id)

        if guild_id not in preferences:
            preferences[guild_id] = {}

        preferences[guild_id][option] = role.id
        save_file("preferences.json", preferences)

        await interaction.followup.send(f"The role '{role.name}' has been set for members.")
    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)

@bot.tree.command(name="purge", description="Deletes a set amount of messages from a specified user.")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(
    user="The user whose messages you want to delete (optional)",
    amount="The number of messages to delete",
)
async def purge(interaction: discord.Interaction, amount: int, user: discord.User = None):
    await interaction.response.defer()
    if amount <= 0:
        await interaction.response.send_message("The amount must be greater than zero.", ephemeral=True)
        return

    messages_to_delete = []

    if user is None:
        deleted_messages = await interaction.channel.purge(limit=amount)
        messages_to_delete = deleted_messages
    else:
        async for message in interaction.channel.history(limit=None):
            if len(messages_to_delete) >= amount:
                break
            if message.author.id == user.id:
                messages_to_delete.append(message)

        for message in messages_to_delete:
            await message.delete()

    modlog = {
        "serverID": str(interaction.guild_id),
        "type": "Purge",
        "channel": interaction.channel.id,
    }
    reason = f"Deleted {len(messages_to_delete)} messages"

    await store_modlog(modlog, None, interaction.user.name, reason)
    embed = discord.Embed(title="Messages deleted", description=reason)
    await interaction.followup.send(embed=embed, delete_after=5)

@bot.tree.command(name="clean", description="Clears up to 10 bot messages, or a specified amount.")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(amount="The number of bot messages to delete (optional, default is 10)")
async def clean(interaction: discord.Interaction, amount: int = 10):
    await interaction.response.defer()
    if amount <= 0:
        await interaction.followup.send("The amount must be greater than zero.", ephemeral=True)
        return

    deleted_count = 0

    async for message in interaction.channel.history(limit=None):
        if deleted_count >= amount:
            break
        if message.author.bot:
            await message.delete()
            deleted_count += 1

    modlog = {
        "serverID": str(interaction.guild_id),
        "type": "Clean",
        "channel": interaction.channel.id,
    }
    reason = f"Deleted {len(amount)} bot messages"

    await store_modlog(modlog, None, interaction.user.name, reason)
    embed = discord.Embed(title="Messages deleted", description=reason)
    await interaction.followup.send(embed=embed, delete_after=5)

@bot.tree.command(name="lock", description="Lock a channel.")
@app_commands.describe(
    channel="The channel to lock (default is the current channel)",
    role="The role to lock the channel for (default is 'Member')",
    reason="The reason for locking the channel (default is 'No reason provided')",
)
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(
    interaction: discord.Interaction,
    channel: discord.TextChannel = None,
    role: discord.Role = None,
    reason: str = "No reason provided",
):

    channel = channel or interaction.channel

    await interaction.response.defer()

    preferences = open_file("info/preferences.json")
    guild_id = str(interaction.guild_id)

    if role is None:
        role_id = preferences.get(guild_id, {}).get("member")
        role = interaction.guild.get_role(role_id) if role_id else None

    if role is None:
        await interaction.followup.send("No role found to lock the channel for.", ephemeral=True)
        return

    if role not in channel.overwrites:
        overwrites = {role: discord.PermissionOverwrite(send_messages=False)}
        await channel.edit(overwrites=overwrites)
    else:
        await channel.set_permissions(role, send_messages=False)

    modlog = {
        "serverID": str(interaction.guild_id),
        "type": "Lock",
        "channel": channel.id,
    }
    reason_with_role = f"{reason}. Role: {role.name}"
    await store_modlog(modlog, None, interaction.user.name, reason_with_role)

    await interaction.followup.send(
        f"{channel.mention} has been locked for {role.name}.\nReason: {reason}",
        ephemeral=True,
    )

@bot.tree.command(name="unlock", description="Unlock a channel.")
@app_commands.describe(
    channel="The channel to unlock (default is the current channel)",
    role="The role to unlock the channel for (default is 'Member')",
    reason="The reason for unlocking the channel (default is 'No reason provided')",
)
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(
    interaction: discord.Interaction,
    channel: discord.TextChannel = None,
    role: discord.Role = None,
    reason: str = "No reason provided",
):
    await interaction.response.defer()
    channel = channel or interaction.channel
    preferences = open_file("info/preferences.json")
    guild_id = str(interaction.guild_id)

    if role is None:
        role_id = preferences.get(guild_id, {}).get("member")
        role = interaction.guild.get_role(role_id) if role_id else None

    if role is None:
        await interaction.followup.send("No role found to unlock the channel for.", ephemeral=True)
        return

    if role in channel.overwrites:
        await channel.set_permissions(role, send_messages=True)

    modlog = {
        "serverID": str(interaction.guild_id),
        "type": "Unlock",
        "channel": channel.id,
    }
    reason_with_role = f"{reason}. Role: {role.name}"
    await store_modlog(modlog, None, interaction.user.name, reason_with_role)

    await interaction.followup.send(
        f"{channel.mention} has been unlocked for {role.name}.\nReason: {reason}",
        ephemeral=True,
    )

@bot.tree.command(name="slowmode", description="Sets or removes the slowmode delay for the channel.")
@app_commands.describe(delay="Slowmode in seconds (max of 21600, omit for no slowmode)")
@app_commands.checks.has_permissions(manage_messages=True)
async def slowmode(interaction: discord.Interaction, delay: int = None):
    await interaction.response.defer()
    try:
        channel_name = interaction.channel.name

        if delay is None:
            await interaction.channel.edit(slowmode_delay=0)
            reason = f"Slowmode removed in #{channel_name}."
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Slowmode",
                    description="Slowmode has been removed.",
                    color=0x00FF00,
                ),
                ephemeral=True,
            )
        elif 0 <= delay <= 21600:
            await interaction.channel.edit(slowmode_delay=delay)
            reason = f"Slowmode set to {delay} seconds in #{channel_name}."
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Slowmode",
                    description=f"Slowmode set to {delay} seconds.",
                    color=0x00FF00,
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Slowmode Error",
                    description="Please provide a delay between 0 and 21600 seconds.",
                    color=0xFF0000,
                ),
                ephemeral=True,
            )
            return

        modlog = {
            "serverID": str(interaction.guild_id),
            "type": "Slowmode",
            "channel": interaction.channel.id,
        }
        await store_modlog(modlog, None, interaction.user.name, reason)

    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)
  

@bot.tree.command(name="nick", description="Changes a member's nickname.")
@app_commands.describe(
    member="The member to manage nicknames for",
    new_nick="The new nickname of the member",
)
@app_commands.checks.has_permissions(manage_nicknames=True)
async def nick(interaction: discord.Interaction, member: discord.Member, new_nick: str):

    await interaction.response.defer()
    try:
        old_nick = member.display_name
        await member.edit(nick=new_nick)

        reason = f"Changed {member.name}'s nickname from {old_nick} to {new_nick} for {member.display_name}"
        await interaction.followup.send(
            embed=discord.Embed(
                title="Nickname Changed",
                description=f"Changed {old_nick}'s nickname to {new_nick}.",
                color=0x32A852,
            ),
            ephemeral=True,
        )

        modlog = {
            "serverID": str(interaction.guild_id),
            "type": "Nickname Change",
            "channel": interaction.channel.id,
        }
        await store_modlog(modlog, None, interaction.user.name, reason)

    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)    

@bot.tree.command(name="mute", description="Mutes a member for a specified duration")
async def mute(
    interaction: discord.Interaction,
    member: discord.Member,
    time: str,
    reason: str = "No reason provided",
):
    await interaction.response.defer()

    try:
        duration = parse_duration(time)

        if not duration:
            await interaction.followup.send(
                "Invalid time format. Please use formats like `1h10m15s` or `15s1h10m`."
            )
            return

        try:
            embed = discord.Embed(
                title=f"You have been muted in {interaction.guild.name}.",
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Moderator", value=interaction.user.mention, inline=False
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Duration", value=duration, inline=False)
            embed.set_footer(
                text=f"If you think this is a mistake, please contact a staff member. ID: {str(member.id)}"
            )
            await member.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("I couldn't send a DM to the member.")

        until = discord.utils.utcnow() + duration
        await member.timeout(until, reason=reason)
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        human_readable_time = (f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)")
        modlog = {"serverID": str(interaction.guild.id), "type": "Mute"}
        modlog_reason = f"{reason}\nMuted for {human_readable_time}"
        await store_modlog(modlog, member, interaction.user.name, modlog_reason)
        embed = discord.Embed(title=f"{member.display_name} has been muted.", color=discord.Color.orange())
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Duration", value=f"{human_readable_time}")
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)

@bot.tree.command(name="unmute", description="Unmutes a member.")
@commands.has_permissions(kick_members=True)
async def unmute(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):

    await interaction.response.defer()
    try:
        await member.timeout(None, reason=reason)
        try:
            await member.send(f"You have been unmuted in {interaction.guild.name}.")
        except discord.Forbidden:
            await interaction.followup.send("I couldn't send a DM to the member.")

        modlog = {"serverID": str(interaction.guild.id), "type": "Unmute"}

        await store_modlog(modlog, None, interaction.user.name, reason)

        embed = discord.Embed(
            title=f"{member.display_name} has been unmuted.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_error(interaction, e, log_error_id=log_id_counter)    

@bot.tree.command(name="kick", description="Kick a member out of the guild.")
@commands.has_permissions(kick_members=True)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No Reason Provided.",
):

    await interaction.response.defer()

    await member.kick(reason=reason)
    await interaction.followup.send(f"{member} has been kicked. Reason: {reason}")
    modlog = {"serverID": str(interaction.guild.id), "type": "Kick"}

    await store_modlog(modlog, None, interaction.user.name, reason)
    embed = discord.Embed(
        title=f"You have been kicked in {interaction.guild.name}.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text="If you think this is a mistake, please contact an staff member")
    await member.send(embed=embed)

class DelLog(discord.ui.Select):
    def __init__(
        self,
        log_type,
        member: discord.Member,
        embed: discord.Embed,
        interaction: discord.Interaction,
        *args,
        **kwargs,
    ):
        placeholder = f"Delete a {log_type.rstrip('s')}"
        super().__init__(placeholder=placeholder, *args, **kwargs)

        self.log_type = log_type
        self.member = member
        self.embed = embed
        self.interaction = interaction
        self.logs = open_file(f"{log_type}.json")

        self.options = [
            discord.SelectOption(
                label=f"{log_type.capitalize()} {index + 1}",
                description=log["reason"],
                value=str(index),
            )
            for index, log in enumerate(self.logs.get(str(member.id), []))
        ]

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        logs_for_member = self.logs.get(str(self.member.id), [])

        if selected_index < len(logs_for_member):
            del logs_for_member[selected_index]
            if logs_for_member:
                self.logs[str(self.member.id)] = logs_for_member
            else:
                del self.logs[str(self.member.id)]
            save_file(f"{self.log_type}.json", self.logs)

            self.embed.clear_fields()
            updated_logs = self.logs.get(str(self.member.id), [])

            if updated_logs:
                for index, log in enumerate(updated_logs):
                    time_str = f"<t:{log['time']}:R>"
                    moderator = self.interaction.guild.get_member(log["moderator"])
                    moderator_name = moderator.display_name if moderator else "Unknown"
                    self.embed.add_field(
                        name=f"Warned by {moderator_name}",
                        value=f"Reason: {log['reason']}\nTime: {time_str}",
                        inline=False,
                    )

                self.options = [
                    discord.SelectOption(
                        label=f"{self.log_type.capitalize()} {index + 1}",
                        description=log["reason"],
                        value=str(index),
                    )
                    for index, log in enumerate(updated_logs)
                ]
            else:
                self.embed.description = (
                    f"No {self.log_type} left for {self.member.display_name}."
                )

            await interaction.response.edit_message(embed=self.embed, view=self.view)
            await interaction.followup.send(
                f"Deleted {self.log_type.capitalize()} {selected_index + 1} for {self.member.display_name}.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
@bot.tree.command(name="warn", description="Warns a member.")
@app_commands.describe(member="The member to warn.", reason="Reason for the warn.")
@app_commands.choices(
    reason=[
        app_commands.Choice(name="Spamming", value="spamming"),
        app_commands.Choice(name="Flood", value="flood"),
        app_commands.Choice(name="Bot Commands", value="bot commands"),
        app_commands.Choice(name="Soft NSFW", value="soft nsfw"),
        app_commands.Choice(name="Hard NSFW", value="hard nsfw"),
        app_commands.Choice(name="Advertising", value="advertising"),
        app_commands.Choice(name="Tragic Event Joke", value="tragic event joke"),
        app_commands.Choice(name="Fatherless Joke", value="fatherless joke"),
        app_commands.Choice(name="KYS Joke", value="kys joke"),
    ]
)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    filename = "warns.json"
    warnings = open_file(filename)

    if str(member.id) in warnings:
        last_warning_time = warnings[str(member.id)][-1]["time"]
        if int(time.time()) - int(last_warning_time) < 60:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Warning Error",
                    description=f"{member.mention} has been warned recently and cannot be warned again yet.",
                    color=0xFF0000,
                )
            )
            return

    member_warnings = warnings.get(str(member.id), [])
    member_warnings.append(
        {
            "reason": reason,
            "moderator": interaction.user.id,
            "time": int(time.time()),
        }
    )

    warnings[str(member.id)] = member_warnings
    save_file(filename, warnings)

    await interaction.response.send_message(
        embed=discord.Embed(
            title="Warning Issued",
            description=f"{member.mention} has been warned for: {reason}",
            color=0xFFA500,
        )
    )

    embed = discord.Embed(
        title=f"You were warned in {interaction.guild.name}.",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(
        text=f"If you think this is a mistake, please contact a staff member. ID: {str(member.id)}"
    )

    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send("Could not send a DM to the user.", ephemeral=True)

    modlog = {
        "serverID": str(interaction.guild_id),
        "type": "Warn",
        "channel": interaction.channel.id,
    }

    await store_modlog(modlog, None, interaction.user.name, reason)

    punishment_durations = {
        "spamming": 1 * 60 * 60,
        "flood": 1 * 60 * 60,
        "bot commands": 0.5 * 60 * 60,
        "soft nsfw": 2 * 60 * 60,
        "hard nsfw": 24 * 60 * 60,
        "advertising": 6 * 60 * 60,
        "tragic event joke": 12 * 60 * 60,
        "fatherless joke": 3 * 60 * 60,
        "kys joke": 6 * 60 * 60,
    }

    mute_duration = punishment_durations.get(reason.lower(), 0)
    if len(member_warnings) > 2:
        mute_duration += (len(member_warnings) - 2) * 60 * 60

    if mute_duration > 0:
        try:
            await member.timeout(timedelta(seconds=mute_duration))
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Member Muted",
                    description=f"{member.mention} has been automatically muted for {mute_duration // 60} minutes due to {len(member_warnings)} warnings.",
                    color=0xFF0000,
                )
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Mute Failed",
                    description=f"Failed to mute {member.mention} due to insufficient permissions.",
                    color=0xFF0000,
                )
            )

@bot.tree.command(name="warns", description="Displays the warnings for a member.")
@app_commands.describe(member="The member whose warnings you want to view.")
async def warns(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    member = member or interaction.user
    filename = "warns.json"
    warnings = open_file(filename)

    member_warnings = warnings.get(str(member.id), [])
    embed = discord.Embed(title=f"Warnings for {member.display_name}", color=0xFFA500)

    if member_warnings:
        for warning in member_warnings:
            time_str = f"<t:{warning['time']}:R>"
            moderator = interaction.guild.get_member(warning["moderator"])
            moderator_name = moderator.display_name if moderator else "Unknown"
            embed.add_field(
                name=f"Warned by {moderator_name}",
                value=f"Reason: {warning['reason']}\nTime: {time_str}",
                inline=False,
            )

        view = discord.ui.View()
        del_log_dropdown = DelLog("warns", member, embed, interaction)
        view.add_item(del_log_dropdown)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(f"No warnings found for {member.display_name}.", ephemeral=True)

@bot.tree.command(name="note", description="Gives a note to a member.")
@app_commands.describe(
    member="The member to add a note to", note="Whatever you want to say"
)
async def note(interaction: discord.Interaction, member: discord.Member, note: str):
    await interaction.response.defer()

    filename = "notes.json"
    warnings = open_file(filename)
    member_warnings = warnings.get(str(member.id), [])
    member_warnings.append({"reason": note, "moderator": interaction.user.id, "time": int(time.time())})
    warnings[str(member.id)] = member_warnings
    save_file(filename, warnings)
    await interaction.followup.send(
        embed=discord.Embed(
            title="Note Added",
            description=f"Added note to: {member.mention}; {note}",
            color=0xFFA500,
        )
    )

@bot.tree.command(name="notes", description="Displays the notes for a member")
@app_commands.describe(member="The member whose notes you want to view.")
async def notes(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    member = member or interaction.user
    filename = "notes.json"
    notes = open_file(filename)
    member_notes = notes.get(str(member.id), [])
    embed = discord.Embed(title=f"Notes for {member.display_name}", color=0xFFA500)

    if member_notes:
        for note in member_notes:
            time_str = f"<t:{note['time']}:R>"
            moderator = interaction.guild.get_member(note["moderator"])
            moderator_name = moderator.display_name if moderator else "Unknown"
            embed.add_field(
                name=f"Note by {moderator_name}",
                value=f"Note: {note['reason']}\nTime: {time_str}",
                inline=False,
            )

        view = discord.ui.View()
        del_log_dropdown = DelLog("notes", member, embed, interaction)
        view.add_item(del_log_dropdown)

        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send(
            f"No notes found for {member.display_name}.", ephemeral=True
        )

async def send_modlog_embed(interaction: discord.Interaction, user: discord.User, page: int):
    modlogs = open_file("info/modlogs.json")
    server_id = str(interaction.guild.id)
    user_id = str(user.id)

    user_logs = modlogs.get(server_id, {}).get(user_id, {})
    total_logs = len(user_logs)

    if total_logs == 0:
        await interaction.response.send_message(f"No logs found for {user}.", ephemeral=True)
        return None, total_logs, 0

    logs_per_page = 10
    total_pages = (total_logs // logs_per_page) + (
        1 if total_logs % logs_per_page > 0 else 0
    )

    if page < 1 or page > total_pages:
        await interaction.response.send_message(
            f"Invalid page number. Please provide a page between 1 and {total_pages}.",
            ephemeral=True,
        )
        return None, total_logs, total_pages

    embed = discord.Embed(title=f"Modlogs for {user}", color=discord.Color.blue())

    start_index = (page - 1) * logs_per_page
    end_index = start_index + logs_per_page
    logs_to_display = list(user_logs.items())[start_index:end_index]

    for case_number, log in logs_to_display:
        embed.add_field(
            name=f"Case #{case_number}",
            value=(
                f"Type: {log['Type']}\n"
                f"User: {log['User']}\n"
                f"Moderator: {log['Moderator']}\n"
                f"Reason: {log['Reason']}\n"
                f"Time: <t:{log['Time']}:F>"
            ),
            inline=False,
        )

    embed.set_footer(text=f"{total_logs} total logs | Page {page} of {total_pages}")

    return embed, total_logs, total_pages

class LogSelect(discord.ui.Select):
    def __init__(self, options, interaction, user, current_page):
        super().__init__(
            placeholder=f"Current page: {current_page}",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.interaction = interaction
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return

        await interaction.response.defer()
        selected_page = int(self.values[0])
        embed, total_logs, total_pages = await send_modlog_embed(self.interaction, self.user, selected_page)
        await interaction.message.edit(embed=embed)
        self.placeholder = f"Current page: {selected_page}"
        await interaction.message.edit(view=self.view)

@bot.tree.command(name="modlogs", description="View moderation logs for a user.")
async def modlogs(interaction: discord.Interaction, user: discord.User, page: int = 1):
    embed, total_logs, total_pages = await send_modlog_embed(interaction, user, page)

    if embed is None:
        return

    options = [
        discord.SelectOption(label=f"Page {i + 1}", value=str(i + 1))
        for i in range(total_pages)
    ]

    select_menu = LogSelect(options, interaction, user, page)
    view = discord.ui.View()
    view.add_item(select_menu)

    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(
    name="modstats", description="Check the moderation statistics of a moderator"
)
@commands.has_permissions(kick_members=True)
async def modstats(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user

    await interaction.response.defer()

    modstats = open_file("modstats.json")
    stats = {
        "kick": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
        "mute": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
        "ban": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
    }

    totals = {"last 7 days": 0, "last 30 days": 0, "all time": 0}
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    for server_id, moderators in modstats.items():
        user_stats = moderators.get(str(member.id), {})

        for case_number, action in user_stats.items():
            action_type = action["type"].lower()
            action_time = datetime.fromtimestamp(action["timestamp"], timezone.utc)

            if action_type in stats:
                if action_time > seven_days_ago:
                    stats[action_type]["last 7 days"] += 1
                    totals["last 7 days"] += 1
                if action_time > thirty_days_ago:
                    stats[action_type]["last 30 days"] += 1
                    totals["last 30 days"] += 1
                stats[action_type]["all time"] += 1
                totals["all time"] += 1

    embed = discord.Embed(title=f"Moderation Statistics for {member.display_name}", color=0xFFA500)
    embed.add_field(name="\u200b", value="**Last 7 days**", inline=True)
    embed.add_field(name="\u200b", value="**Last 30 days**", inline=True)
    embed.add_field(name="\u200b", value="**All Time**", inline=True)

    for action_type in stats.keys():
        embed.add_field(
            name=f"**{action_type.capitalize()}**",
            value=str(stats[action_type]["last 7 days"]),
            inline=True,
        )
        embed.add_field(name="\u200b", value=str(stats[action_type]["last 30 days"]), inline=True)
        embed.add_field(name="\u200b", value=str(stats[action_type]["all time"]), inline=True)

    embed.add_field(name="**Total**", value=str(totals["last 7 days"]), inline=True)
    embed.add_field(name="\u200b", value=str(totals["last 30 days"]), inline=True)
    embed.add_field(name="\u200b", value=str(totals["all time"]), inline=True)

    await interaction.followup.send(embed=embed)

"""
OTHER COMMANDS
"""

def get_next_report_id(reports_data):
    if reports_data:
        return max(map(int, reports_data.keys())) + 1
    return 1

def blacklist_user(user_id):
    member_info = open_file("info/member_info.json")
    if str(user_id) not in member_info:
        member_info[str(user_id)] = {"TicketBlacklist": True}
    else:
        member_info[str(user_id)]["TicketBlacklist"] = True
    save_file("info/member_info.json", member_info)

def is_user_blacklisted(user_id):
    member_info = open_file("info/member_info.json")
    return member_info.get(str(user_id), {}).get("TicketBlacklist", False)

class ReportButtons(discord.ui.View):
    def __init__(self, report_id, reports_data, message):
        super().__init__(timeout=None)
        self.report_id = str(report_id)
        self.reports_data = reports_data
        self.message = message

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.",ephemeral=True,)
            return

        report["Status"] = "Accepted"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been accepted!")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Accepted\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter']}")

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been accepted.", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defe
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.", ephemeral=True)
            return

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter']}")

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been declined.", ephemeral=True)

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary)
    async def blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        blacklist_user(interaction.user.id)

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)
        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.\nYou are now ticket blacklisted.")

        await interaction.followup.send(f"The report has been declined and the reported is now blacklisted.", ephemeral=True)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} has been declined and you have been blacklisted.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined (Blacklisted)\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.greyple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter']}")

        await self.message.edit(embed=embed, view=None)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="report", description="Report an in game rule breaker")
@app_commands.choices(
    type=[
        app_commands.Choice(name="Auto Win", value="Auto Win"),
        app_commands.Choice(name="Ability Spam", value="Ability Spam"),
        app_commands.Choice(name="Alchemist Auto Brew", value="Alchemist Auto Brew"),
        app_commands.Choice(name="Bob Auto Farm", value="Bob Auto Farm"),
        app_commands.Choice(name="Bypassing", value="Bypassing"),
        app_commands.Choice(name="False Votekick", value="False Votekick"),
        app_commands.Choice(name="Flight", value="Flight"),
        app_commands.Choice(name="Framing Exploit", value="Framing Exploit"),
        app_commands.Choice(name="Item Vacuum", value="Item Vacuum"),
        app_commands.Choice(name="Kick Exploit", value="Kick Exploit"),
        app_commands.Choice(name="Godmode", value="Godmode"),
        app_commands.Choice(name="NSFW", value="NSFW"),
        app_commands.Choice(name="Reach", value="Reach"),
        app_commands.Choice(name="Rhythm Ability Spam", value="Rhythm Ability Spam"),
        app_commands.Choice(name="Slap Aura", value="Slap Aura"),
        app_commands.Choice(name="Slap Auto Farm", value="Slap Auto Farm"),
        app_commands.Choice(name="Slapple Farm", value="Slapple Farm"),
        app_commands.Choice(name="Teleport", value="Teleport"),
        app_commands.Choice(name="Toxicity", value="Toxicity"),
        app_commands.Choice(name="Trap Auto Farm", value="Trap Auto Farm"),
        app_commands.Choice(name="Anti Acid/Lava", value="Anti Acid/Lava"),
        app_commands.Choice(name="Anti Ragdoll", value="Anti Ragdoll"),
        app_commands.Choice(name="Anti Void", value="Anti Void"),
        app_commands.Choice(name="Other", value="Other"),
    ]
)
@app_commands.describe(
    type="The type of exploit they used",
    proof="Use medal or youtube and post the link",
    user="The user to report",
    other="Any other information needed)",
)
async def report(interaction: discord.Interaction, type: str, proof: str, user: str, other: str):
    await interaction.response.defer()

    member_info = open_file("info/member_info.json")
    reporter_id = str(interaction.user.id)

    if member_info.get(reporter_id, {}).get("TicketBlacklist"):
        await interaction.followup.send("You are blacklisted from submitting reports.", ephemeral=True)
        return

    reports_data = open_file("info/reports.json")
    report_id = get_next_report_id(reports_data)

    timestamp = datetime.now().isoformat()
    new_report = {
        "Status": "Open",
        "Reporter": reporter_id,
        "User": user,
        "Proof": proof,
        "Type": type,
        "Other": other,
        "Timestamp": timestamp,
    }

    reports_data[str(report_id)] = new_report
    save_file("reports.json", reports_data)

    report_embed = discord.Embed(
        title=f"Report ID: {report_id}",
        description=f"**Type:** {type}\n**Proof:** {proof}\n**Reported User:** {user}\n**Other:** {other}",
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    report_embed.set_footer(text=f"Reported by {interaction.user.display_name}")

    guild = interaction.client.get_guild(1279160584662679673)
    report_channel = guild.get_channel(1292649491203096646)
    if report_channel:
        message = await report_channel.send(embed=report_embed, view=None)
        await message.edit(view=ReportButtons(report_id, reports_data, message))
        await interaction.followup.send(f"Your report has been submitted for {user}.")
    else:
        await interaction.followup.send("Report channel not found.", ephemeral=True)

bot.run(token)
