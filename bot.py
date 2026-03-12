import discord
import requests
import json
import os
import asyncio
import sys
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import time
from urllib.parse import urlencode
bot_state = {
    "status": "starting",
    "guilds": [],
    "ready": False,
    "latency": 0,
}


print("🚀 STARTING BOT...")

# Load config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    BOT_TOKEN = config['token']
    CLIENT_ID = config['id']
    CLIENT_SECRET = config['secret']
    MAIN_SERVER = 1461680385560940566  # Your main server ID
    DJOIN_CHANNEL = 1477969479186251901  # Channel where !djoin can be used
    
    # Role-based member pulling limits
    ROLE_LIMITS = {
        '1477969370792722464': 3,      # Members: 3
        '1477970111959928984': 5,      # Bronze: 5
        '1477969366560669778': 7,      # Gold: 7
        '1477969365382205504': 25,     # Premium: 25
        '1477969364669173792': 40,     # Diamond: 40
        '1477969363930976296': 80      # Emerald: 80
    }
    
    print(f"✅ Config loaded")
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🆔 Client ID: {CLIENT_ID}")
    print(f"🔒 Secret: {CLIENT_SECRET[:8]}...")
    print(f"🏠 Main Server: {MAIN_SERVER}")
    
except Exception as e:
    print(f"❌ Config error: {e}")
    exit(1)

# Create bot
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix=['!', '?'], intents=intents)
bot.remove_command("help")

# Store server join times
server_join_times = {}

def update_bot_state():
    """Update shared bot state for admin panel - writes to file for redirect_app.py"""
    bot_state['ready'] = True
    bot_state['latency'] = bot.latency
    bot_state['guilds'] = [
        {
            'name': g.name,
            'id': g.id,
            'members': g.member_count,
            'is_main': g.id == MAIN_SERVER
        } for g in bot.guilds
    ]
    try:
        with open('bot_status.json', 'w') as f:
            json.dump(bot_state, f)
    except Exception as e:
        print(f"❌ Error writing bot_status.json: {e}")

@bot.event
async def on_ready():
    print(f'🎯 Bot is ready: {bot.user}')
    print(f'📋 Loaded commands: {[command.name for command in bot.commands]}')
    
    update_bot_state()
    
    # Initialize server join times
    for guild in bot.guilds:
        if guild.id != MAIN_SERVER:
            server_join_times[guild.id] = datetime.now()
            print(f"📝 Tracking server: {guild.name} ({guild.id})")
    
    # Start the cleanup task
    check_server_ages.start()
    admin_panel_tasks.start()

@tasks.loop(seconds=5)
async def admin_panel_tasks():
    """Process admin panel requests and keep bot_state in sync"""
    update_bot_state()
    
    # Read commands from admin panel (via bot_commands.json)
    if os.path.exists('bot_commands.json'):
        try:
            with open('bot_commands.json', 'r') as f:
                cmd = json.load(f)
            os.remove('bot_commands.json')
            
            action = cmd.get('action')
            if action == 'set_status':
                activity_type = cmd.get('type', 'online')
                activity_text = cmd.get('text', '')
                if activity_type == 'online':
                    await bot.change_presence(status=discord.Status.online, activity=None)
                elif activity_type == 'playing':
                    await bot.change_presence(activity=discord.Game(name=activity_text))
                elif activity_type == 'listening':
                    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=activity_text))
                elif activity_type == 'watching':
                    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=activity_text))
                elif activity_type == 'streaming':
                    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.streaming, name=activity_text, url="https://twitch.tv/dummy"))
                print(f"✅ Admin panel: Status → {activity_type} {activity_text}")
            elif action == 'restart':
                print("🔄 Admin panel: Restart requested")
                await bot.close()
        except Exception as e:
            print(f"❌ Admin panel command error: {e}")

@tasks.loop(hours=24)  # Run once per day
async def check_server_ages():
    """Check servers and leave if they're older than 14 days (except main server)"""
    print("🔍 Checking server ages...")
    
    for guild in bot.guilds:
        if guild.id == MAIN_SERVER:
            continue  # Never leave main server
        
        guild_id = guild.id
        guild_name = guild.name
        guild_age = None
        
        # Calculate age
        if guild_id in server_join_times:
            join_time = server_join_times[guild_id]
            guild_age = datetime.now() - join_time
        else:
            # If we don't have a join time, assume we joined now
            server_join_times[guild_id] = datetime.now()
            guild_age = timedelta(0)
        
        if guild_age >= timedelta(days=14):
            try:
                print(f"🚪 Leaving server {guild_name} ({guild_id}) - Age: {guild_age.days} days")
                await guild.leave()
                
                # Send notification to main server
                main_guild = bot.get_guild(MAIN_SERVER)
                if main_guild:
                    # Find first text channel bot can send to
                    for channel in main_guild.text_channels:
                        if channel.permissions_for(main_guild.me).send_messages:
                            embed = discord.Embed(
                                title="🚪 Bot Left Server",
                                description=f"**Server:** {guild_name}\n**ID:** {guild_id}\n**Reason:** Server age ({guild_age.days} days) exceeded 14 days",
                                color=0xED4245,
                                timestamp=datetime.now()
                            )
                            await channel.send(embed=embed)
                            break
                
                # Remove from tracking
                if guild_id in server_join_times:
                    del server_join_times[guild_id]
                    
            except Exception as e:
                print(f"❌ Error leaving server {guild_name}: {e}")
        else:
            print(f"✅ Server {guild_name} is {guild_age.days} days old - OK")

@bot.event
async def on_guild_join(guild):
    """Track when bot joins a new server"""
    if guild.id != MAIN_SERVER:
        server_join_times[guild.id] = datetime.now()
        print(f"📝 Bot joined new server: {guild.name} ({guild.id})")
        
        # Send notification to main server
        main_guild = bot.get_guild(MAIN_SERVER)
        if main_guild:
            for channel in main_guild.text_channels:
                if channel.permissions_for(main_guild.me).send_messages:
                    embed = discord.Embed(
                        title="🏠 Bot Joined Server",
                        description=f"**Server:** {guild.name}\n**ID:** {guild.id}\n**Members:** {guild.member_count}\n**Will leave after:** 14 days",
                        color=0x57F287,
                        timestamp=datetime.now()
                    )
                    await channel.send(embed=embed)
                    break

@bot.event
async def on_guild_remove(guild):
    """Remove server from tracking when bot leaves"""
    if guild.id in server_join_times:
        del server_join_times[guild.id]
        print(f"🗑️ Removed tracking for server: {guild.name} ({guild.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command not found. Use `!help` to see available commands.")
    else:
        print(f"❌ Command error: {error}")

def refresh_access_token(refresh_token):
    """Refresh an expired access token"""
    try:
        data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        response = requests.post('https://discord.com/api/v10/oauth2/token', data=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return None

def get_valid_token(user_id, access_token, refresh_token):
    """Get a valid access token, refreshing if needed"""
    # First test if current token works
    headers = {'Authorization': f'Bearer {access_token}'}
    test_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
    
    if test_response.status_code == 200:
        return access_token  # Token is still valid
    
    # Token is invalid, try to refresh
    print(f"🔄 Token expired for user {user_id}, refreshing...")
    new_tokens = refresh_access_token(refresh_token)
    
    if new_tokens:
        # Update the token in auths.txt
        update_token_in_file(user_id, new_tokens['access_token'], new_tokens['refresh_token'])
        return new_tokens['access_token']
    else:
        print(f"❌ Failed to refresh token for user {user_id}")
        return None

def update_token_in_file(user_id, new_access_token, new_refresh_token):
    """Update tokens in auths.txt file"""
    try:
        if not os.path.exists('auths.txt'):
            return False
        
        with open('auths.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split(',')
            if len(parts) >= 3 and parts[0] == user_id:
                # Update this user's tokens
                new_line = f"{user_id},{new_access_token},{new_refresh_token}\n"
                new_lines.append(new_line)
                updated = True
                print(f"✅ Updated tokens for user {user_id}")
            else:
                new_lines.append(line + '\n')
        
        if updated:
            with open('auths.txt', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        
        return False
    except Exception as e:
        print(f"❌ Error updating tokens in file: {e}")
        return False

@bot.command(name='get_token')
async def get_auth_token(ctx):
    """Get authentication link"""
    try:
        # Use the correct authorization URL with guilds.join scope
        oauth_url = "https://discord.com/oauth2/authorize?client_id=1470029553887088781&response_type=code&redirect_uri=https%3A%2F%2Fparrotgames.free.nf%2Fdiscord-redirect.html&scope=guilds.join"
        
        embed = discord.Embed(
            title="🔐 Authentication Required",
            description="**Click the link below to get your authentication code:**",
            color=0x5865F2
        )
        embed.add_field(
            name="🚨 IMPORTANT",
            value="**Codes expire in 10 minutes!** Complete authentication quickly.",
            inline=False
        )
        embed.add_field(
            name="🔗 Auth Link", 
            value=f"[**👉 CLICK HERE TO AUTHENTICATE 👈**]({oauth_url})",
            inline=False
        )
        embed.add_field(
            name="📝 Steps:",
            value="1. Click the link above\n2. Authorize the application\n3. **IMMEDIATELY** copy the code\n4. Use `!auth YOUR_CODE_HERE`",
            inline=False
        )
        
        await ctx.send(embed=embed)
        print(f"✅ Sent auth link to {ctx.author.name}")
        
    except Exception as e:
        await ctx.send(f"❌ Error generating auth link: {str(e)}")
        print(f"❌ Error in get_token: {e}")

@bot.command(name='auth')
async def authenticate_user(ctx, authorization_code: str):
    """Authenticate user with code - exchange for real Discord tokens"""
    authorization_code = authorization_code.strip()
    current_user_id = str(ctx.author.id)
    
    # Only accept codes that are exactly 30 characters long
    if len(authorization_code) != 30:
        return await ctx.send("❌ Code must be exactly 30 characters long.")
    
    # Exchange code for real Discord access token
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'redirect_uri': 'https://parrotgames.free.nf/discord-redirect.html'
    }
    
    try:
        print(f"🔄 Exchanging code {authorization_code} for tokens...")
        response = requests.post('https://discord.com/api/v10/oauth2/token', data=token_data)
        
        if response.status_code != 200:
            error_info = response.json() if response.content else {}
            error_msg = error_info.get('error_description', error_info.get('error', 'Unknown error'))
            print(f"❌ Token exchange failed: {error_msg}")
            return await ctx.send(f"❌ Invalid code or expired. Error: {error_msg}")
        
        # Extract real tokens from Discord
        token_info = response.json()
        access_token = token_info.get('access_token')
        refresh_token = token_info.get('refresh_token', '')
        
        if not access_token:
            return await ctx.send("❌ Failed to get access token from Discord.")
        
        print(f"✅ Got real access token: {access_token[:30]}...")
        
        # Save real tokens to file
        username = ctx.author.name
        auth_entry = f"{current_user_id},{access_token},{refresh_token}\n"
        
        existing_entries = []
        if os.path.exists('auths.txt'):
            with open('auths.txt', 'r', encoding='utf-8') as f:
                existing_entries = f.readlines()
        
        # Remove any existing entry for this user
        cleaned_entries = [line for line in existing_entries if line.strip() and not line.startswith(current_user_id)]
        cleaned_entries.append(auth_entry)
        
        # Write real tokens to file
        with open('auths.txt', 'w', encoding='utf-8') as f:
            f.writelines(cleaned_entries)
        
        return await ctx.send(f"✅ **{username}** authenticated successfully! Real token stored. Ready for `!djoin`")
        
    except Exception as e:
        print(f"❌ Auth exception: {str(e)}")
        return await ctx.send(f"❌ Authentication error: {str(e)}")
        
@bot.command(name='djoin')
async def join_server(ctx, target_server_id: str):
    """Add authenticated users to a server based on role limits"""
    try:
        # FIRST CHECK: CHANNEL RESTRICTION - MUST BE IN CORRECT CHANNEL
        if ctx.channel.id != DJOIN_CHANNEL:
            await ctx.send(f"❌ Can only use in <#{DJOIN_CHANNEL}>")
            return
        
        # SECOND CHECK: ROLE VERIFICATION
        user_roles = [role.id for role in ctx.author.roles]
        member_limit = max([ROLE_LIMITS.get(str(rid), 0) for rid in user_roles] or [0])
        
        if member_limit == 0:
            await ctx.send("❌ You lack the required role to use this command.")
            return
        
        # THIRD CHECK: BOT IN SERVER
        guild = discord.utils.get(bot.guilds, id=int(target_server_id))
        if not guild:
            invite = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot"
            await ctx.send(f"❌ Bot not in server. [Add bot]({invite})")
            return
        
        # FOURTH CHECK: AUTH FILE EXISTS
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No authenticated users.")
            return
        
        # READ USERS AND LIMIT BY ROLE
        users = [line.strip().split(',') for line in open('auths.txt').readlines() if line.strip()]
        users = [{'user_id': u[0], 'token': u[1]} for u in users if len(u) >= 2][:member_limit]
        
        if not users:
            await ctx.send("❌ No users to add.")
            return
        
        # PROCEED WITH JOINING
        msg = await ctx.send(f"🚀 Adding **{len(users)}** users to **{guild.name}**...")
        
        success, failed = 0, 0
        for user in users:
            try:
                url = f"https://discord.com/api/v10/guilds/{target_server_id}/members/{user['user_id']}"
                headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
                resp = requests.put(url, json={"access_token": user['token']}, headers=headers)
                print(f"📤 User {user['user_id']}: Status {resp.status_code} - {resp.text}")
                if resp.status_code in (201, 204):
                    success += 1
                    print(f"✅ Added user {user['user_id']}")
                else:
                    failed += 1
                    print(f"❌ Failed user {user['user_id']}: {resp.json().get('message', 'Unknown error')}")
                await asyncio.sleep(0.5)
            except Exception as e:
                failed += 1
                print(f"❌ Exception for user {user['user_id']}: {str(e)}")
        
        await msg.edit(content=f"✅ **Complete!** Added: {success} | Failed: {failed}")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='check_tokens')
async def check_token_validity(ctx):
    """Check which tokens are still valid"""
    try:
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No users are authenticated yet.")
            return
        
        users = []
        valid_count = 0
        expired_count = 0
        
        with open('auths.txt', 'r') as auth_file:
            for line in auth_file:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 3:
                    user_id = parts[0]
                    access_token = parts[1]
                    
                    # Test token validity
                    headers = {'Authorization': f'Bearer {access_token}'}
                    test_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
                    
                    if test_response.status_code == 200:
                        status = "✅ VALID"
                        valid_count += 1
                    else:
                        status = "❌ EXPIRED"
                        expired_count += 1
                    
                    users.append(f"{status} <@{user_id}>")
        
        embed = discord.Embed(
            title="🔍 TOKEN VALIDITY CHECK",
            description=f"**Valid:** {valid_count} | **Expired:** {expired_count}",
            color=0x5865F2
        )
        
        if users:
            users_text = "\n".join(users[:15])
            if len(users) > 15:
                users_text += f"\n... and {len(users) - 15} more"
            embed.add_field(name="Token Status", value=users_text, inline=False)
        
        embed.add_field(
            name="💡 Tip", 
            value="Expired tokens will be automatically refreshed when using `!djoin`", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error checking tokens: {str(error)}")

@bot.command(name='list_users')
async def list_authenticated_users(ctx):
    """List all authenticated users"""
    try:
        if not os.path.exists('auths.txt'):
            await ctx.send("❌ No users are authenticated yet.")
            return
        
        users = []
        with open('auths.txt', 'r') as auth_file:
            for line_num, line in enumerate(auth_file, 1):
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 2:
                    user_id = parts[0]
                    token_preview = parts[1][:10] + "..." if len(parts[1]) > 10 else parts[1]
                    users.append(f"`{line_num}.` <@{user_id}> - `{token_preview}`")
                elif len(parts) == 1 and parts[0]:
                    users.append(f"`{line_num}.` <@{parts[0]}> - `(no token)`")
        
        if not users:
            await ctx.send("❌ No authenticated users found.")
            return
        
        embed = discord.Embed(
            title="📋 AUTHENTICATED USERS",
            description=f"**Total: {len(users)} users**",
            color=0x5865F2
        )
        
        # Split users into chunks to avoid field length limits
        users_text = "\n".join(users[:20])  # Show first 20 users
        if len(users) > 20:
            users_text += f"\n\n... and {len(users) - 20} more users"
        
        embed.add_field(name="Users", value=users_text, inline=False)
        embed.add_field(
            name="Usage", 
            value=f"Use `!djoin SERVER_ID` to add all {len(users)} users to a server", 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing users: {str(error)}")

@bot.command(name='invite')
async def generate_invite(ctx):
    """Generate bot invite link for any server"""
    invite_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"
    
    embed = discord.Embed(
        title="🤖 BOT INVITE LINK",
        description="**Use this link to add the bot to any server:**",
        color=0x5865F2
    )
    embed.add_field(
        name="🔗 Invite Link", 
        value=f"[**👉 CLICK HERE TO INVITE BOT 👈**]({invite_url})",
        inline=False
    )
    embed.add_field(
        name="⚠️ Note",
        value="Bot will automatically leave servers after 14 days (except main server)",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='servers')
async def list_servers(ctx):
    """List all servers the bot is in"""
    try:
        if not bot.guilds:
            await ctx.send("❌ Bot is not in any servers.")
            return
        
        server_list = []
        current_time = datetime.now()
        
        for guild in bot.guilds:
            age_days = "Permanent" if guild.id == MAIN_SERVER else "Unknown"
            
            if guild.id in server_join_times:
                join_time = server_join_times[guild.id]
                age = current_time - join_time
                age_days = f"{age.days} days"
            
            server_list.append(f"`{guild.id}` - **{guild.name}** (Members: {guild.member_count}) - Age: {age_days}")
        
        embed = discord.Embed(
            title="🏠 BOT SERVERS",
            description=f"**Total: {len(bot.guilds)} servers**\n⭐ = Main Server (Never leaves)",
            color=0x5865F2
        )
        
        servers_text = "\n".join(server_list[:15])
        if len(server_list) > 15:
            servers_text += f"\n... and {len(server_list) - 15} more servers"
        
        embed.add_field(name="Servers", value=servers_text, inline=False)
        embed.add_field(
            name="ℹ️ Info", 
            value="• Bot leaves servers after 14 days\n• Main server (ID: {}) is permanent\n• Use `!djoin SERVER_ID` to add users".format(MAIN_SERVER), 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as error:
        await ctx.send(f"❌ Error listing servers: {str(error)}")

@bot.command(name='server_age')
async def check_server_age(ctx, server_id: str = None):
    """Check how long the bot has been in a server"""
    try:
        if server_id:
            guild = bot.get_guild(int(server_id))
            if not guild:
                await ctx.send(f"❌ Bot is not in server with ID: {server_id}")
                return
        else:
            guild = ctx.guild
            if not guild:
                await ctx.send("❌ This command must be used in a server")
                return
        
        if guild.id == MAIN_SERVER:
            embed = discord.Embed(
                title="⭐ MAIN SERVER",
                description=f"**{guild.name}**\nID: `{guild.id}`",
                color=0xF1C40F
            )
            embed.add_field(name="Status", value="✅ **Permanent - Never leaves**", inline=False)
            embed.add_field(name="Members", value=guild.member_count, inline=True)
            embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
            await ctx.send(embed=embed)
            return
        
        if guild.id in server_join_times:
            join_time = server_join_times[guild.id]
            current_time = datetime.now()
            age = current_time - join_time
            days_left = max(0, 14 - age.days)
            
            embed = discord.Embed(
                title="📅 SERVER AGE",
                description=f"**{guild.name}**\nID: `{guild.id}`",
                color=0x3498DB,
                timestamp=join_time
            )
            embed.add_field(name="Joined On", value=f"<t:{int(join_time.timestamp())}:F>", inline=False)
            embed.add_field(name="Current Age", value=f"{age.days} days, {age.seconds // 3600} hours", inline=True)
            embed.add_field(name="Days Until Leave", value=f"{days_left} days", inline=True)
            embed.add_field(name="Will Leave On", value=f"<t:{int((join_time + timedelta(days=14)).timestamp())}:F>", inline=False)
            embed.add_field(name="Members", value=guild.member_count, inline=True)
            embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
            
            await ctx.send(embed=embed)
        else:
            # If we don't have tracking data, add it now
            server_join_times[guild.id] = datetime.now()
            await ctx.send(f"✅ Started tracking server **{guild.name}**. Will leave after 14 days.")
            
    except Exception as error:
        await ctx.send(f"❌ Error checking server age: {str(error)}")

@bot.command(name='setstatus')
async def set_bot_status(ctx, status_type: str = None, *, activity_text: str = None):
    """Change bot status - Usage: !setstatus <online|playing|listening|watching|streaming> [text]"""
    try:
        if not status_type:
            return await ctx.send("❌ Usage: `!setstatus <type> [text]`\n\n**Availability:**\n`!setstatus online`\n\n**Activity:**\n`!setstatus playing Member Backup`\n`!setstatus listening to commands`\n`!setstatus watching servers`\n`!setstatus streaming Member Backup`")
        
        status_type = status_type.lower().strip()
        activity_text = activity_text.strip() if activity_text else None
        
        # Online status
        if status_type == 'online':
            await bot.change_presence(status=discord.Status.online, activity=None)
            await ctx.send(f"✅ Bot is **Online**")
            print(f"✅ Status: Online")
        
        # Activity types (playing, listening, watching, streaming)
        elif status_type == 'playing':
            if not activity_text:
                return await ctx.send("❌ Usage: `!setstatus playing <text>`")
            activity = discord.Game(name=activity_text)
            await bot.change_presence(activity=activity)
            await ctx.send(f"✅ **Playing** `{activity_text}`")
            print(f"✅ Now playing: {activity_text}")
        elif status_type == 'listening':
            if not activity_text:
                return await ctx.send("❌ Usage: `!setstatus listening <text>`")
            activity = discord.Activity(type=discord.ActivityType.listening, name=activity_text)
            await bot.change_presence(activity=activity)
            await ctx.send(f"✅ **Listening** to `{activity_text}`")
            print(f"✅ Listening to: {activity_text}")
        elif status_type == 'watching':
            if not activity_text:
                return await ctx.send("❌ Usage: `!setstatus watching <text>`")
            activity = discord.Activity(type=discord.ActivityType.watching, name=activity_text)
            await bot.change_presence(activity=activity)
            await ctx.send(f"✅ **Watching** `{activity_text}`")
            print(f"✅ Watching: {activity_text}")
        elif status_type == 'streaming':
            if not activity_text:
                return await ctx.send("❌ Usage: `!setstatus streaming <text>`")
            activity = discord.Activity(type=discord.ActivityType.streaming, name=activity_text, url="https://twitch.tv/dummy")
            await bot.change_presence(activity=activity)
            await ctx.send(f"✅ **Streaming** `{activity_text}`")
            print(f"✅ Streaming: {activity_text}")
        else:
            return await ctx.send(f"❌ Unknown type `{status_type}`!\n\nUse: online, playing, listening, watching, or streaming")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")
        print(f"❌ Status error: {e}")

@bot.command(name='restart')
async def restart_bot(ctx):
    """Restart the bot"""
    await ctx.send("🔄 Restarting bot...")
    print("🔄 Bot restart initiated by user")
    await bot.close()

@bot.command(name='help')
async def show_help(ctx):
    """Show all available commands"""
    embed = discord.Embed(
        title="🤖 BOT COMMANDS - COMPLETE LIST",
        color=0x5865F2
    )
    
    embed.add_field(
        name="🔐 AUTHENTICATION", 
        value="`!get_token` - Get authentication link\n`!auth CODE` - Authenticate with code\n`!check_tokens` - Check token validity", 
        inline=False
    )
    
    embed.add_field(
        name="🚀 MASS JOINING", 
        value="`!djoin SERVER_ID` - Add ALL users to server\n`!servers` - List bot servers\n`!server_age [SERVER_ID]` - Check server age", 
        inline=False
    )
    
    embed.add_field(
        name="👥 USER MANAGEMENT", 
        value="`!list_users` - List authenticated users", 
        inline=False
    )
    
    embed.add_field(
        name="🔧 UTILITY", 
        value="`!setstatus online` - Set bot online\n`!setstatus <playing|listening|watching|streaming> <text>` - Set bot activity\n`!invite` - Get bot invite link\n`!restart` - Restart bot\n`!help` - Show this help", 
        inline=False
    )
    
    embed.add_field(
        name="⚠️ IMPORTANT NOTES",
        value="• Bot leaves servers after 14 days automatically\n• Main server (ID: {}) is permanent".format(MAIN_SERVER),
        inline=False
    )
    
    await ctx.send(embed=embed)

# START BOT - auto-restart
if __name__ == "__main__":
    print("🎯 STARTING COMPLETE DISCORD BOT...")
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
    print("🔄 Bot stopped. Restarting in 3 seconds...")
    time.sleep(3)
    print("♻️ Restarting process...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
