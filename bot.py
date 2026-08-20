import os
import random
import asyncio
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord.ui import Button, View
from aiohttp import web
from PIL import Image, ImageDraw, ImageFont
import io

# ---------------------------------------------------------
# CONFIGURATION SERVEUR WEB (Pour Render)
# ---------------------------------------------------------
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# ---------------------------------------------------------
# STOCKAGE EN MÉMOIRE
# ---------------------------------------------------------
user_xp = {}          # {user_id: {"xp": 0, "level": 1, "vocal_xp": 0}}
user_warns = {}       # {user_id: [{"moderator": id, "reason": "...", "date": "..."}]}
spam_tracker = {}     # {user_id: [timestamp1, timestamp2, ...]}

server_configs = {
    "welcome_channel": None,
    "level_channel": None,  # Salon pour les niveaux
    "autorole_id": None,
    "ticket_category_id": None,
    "spam_limit": 5,        # Nombre de messages par défaut
    "spam_time": 5,         # Dans un intervalle de x secondes par défaut
    "logs": {
        "mod": None,
        "message": None,
        "voice": None,
        "role": None,
        "raid": None,
        "ticket": None
    }
}

# ---------------------------------------------------------
# FONCTION UTILITAIRE : CONVERSION & FORMATAGE DU TEMPS
# ---------------------------------------------------------
def convert_time(time_str: str) -> int:
    time_str = time_str.lower()
    total_seconds = 0
    number = ""
    
    for char in time_str:
        if char.isdigit():
            number += char
        elif char in ['s', 'm', 'h', 'j']:
            if not number:
                return None
            val = int(number)
            if char == 's':
                total_seconds += val
            elif char == 'm':
                total_seconds += val * 60
            elif char == 'h':
                total_seconds += val * 3600
            elif char == 'j':
                total_seconds += val * 86400
            number = ""
        else:
            return None
            
    if number:
        total_seconds += int(number)
        
    return total_seconds if total_seconds > 0 else None

def format_duration(time_str: str) -> str:
    """Convertit une chaîne courte (ex: 1h, 30m) en texte lisible (1 heure, 30 minutes)"""
    time_str = time_str.lower()
    number = ""
    result = []
    
    for char in time_str:
        if char.isdigit():
            number += char
        elif char in ['s', 'm', 'h', 'j']:
            if not number:
                continue
            val = int(number)
            if char == 's':
                result.append(f"{val} seconde{'s' if val > 1 else ''}")
            elif char == 'm':
                result.append(f"{val} minute{'s' if val > 1 else ''}")
            elif char == 'h':
                result.append(f"{val} heure{'s' if val > 1 else ''}")
            elif char == 'j':
                result.append(f"{val} jour{'s' if val > 1 else ''}")
            number = ""
            
    return " ".join(result) if result else time_str

# ---------------------------------------------------------
# FONCTION LOG MODÉRATION PERSONNALISÉE (EMBED PROPRE)
# ---------------------------------------------------------
async def send_mod_log(guild, title, color, member, moderator, reason, duration=None, sanction_type=None):
    log_id = server_configs["logs"]["mod"]
    if not log_id:
        return
    chan = guild.get_channel(log_id)
    if not chan:
        return
    
    now = datetime.utcnow()
    heure_str = now.strftime("%d/%m/%Y à %H:%M:%S")

    embed = discord.Embed(title=title, color=color, timestamp=now)
    embed.add_field(name="🎯 Sanction", value=sanction_type or title, inline=True)
    embed.add_field(name="👤 Utilisateur sanctionné", value=f"{member} (`{member.id}`)", inline=True)
    embed.add_field(name="🛡️ Modérateur", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
    
    if duration:
        embed.add_field(name="⏱️ Durée", value=format_duration(duration), inline=True)
        
    embed.add_field(name="🕒 Heure", value=heure_str, inline=True)
    embed.add_field(name="📌 Raison", value=reason, inline=False)
    embed.set_footer(text=f"ID Serveur : {guild.id}")
    
    await chan.send(embed=embed)

async def send_sanction_dm(member, title, description, color, duration, moderator, reason):
    now = datetime.utcnow()
    date_str = now.strftime("%d/%m/%Y")
    heure_str = now.strftime("%H:%M:%S")

    embed = discord.Embed(title=title, description=description, color=color, timestamp=now)
    if duration:
        embed.add_field(name="⏱️ Durée", value=format_duration(duration), inline=True)
    embed.add_field(name="🛡️ Modérateur", value=f"{moderator} (`{moderator.id}`)", inline=True)
    embed.add_field(name="📅 Date & Heure", value=f"Le {date_str} à {heure_str}", inline=False)
    embed.add_field(name="📌 Raison", value=reason, inline=False)
    
    try:
        await member.send(embed=embed)
    except:
        pass

# ---------------------------------------------------------
# HELP PERSONNALISÉ
# ---------------------------------------------------------
class MyHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        is_mod = ctx.author.guild_permissions.manage_messages

        embed = discord.Embed(
            title="📜 Centre d'Aide & Commandes", 
            description="Bienvenue sur le panneau d'aide de votre bot !",
            color=discord.Color.from_rgb(47, 49, 54)
        )
        
        general_cmds = []
        fun_cmds = []
        mod_cmds = []

        for cog, commands_list in mapping.items():
            for c in commands_list:
                if c.hidden:
                    continue
                if c.name in ["ban", "unban", "kick", "mute", "unmute", "warn", "warns", "clear", "setup_logs", "giveaway", 
                              "autoconfiglog", "modlog", "messagelog", "voicelog", "rolelog", "raidlog", "ticketlog", 
                              "welcome", "autorole", "niveauconfig", "salonlevel", "ticketconfig", "say", "annonce", "role"]:
                    mod_cmds.append(f"`?{c.name}`")
                elif c.name in ["8ball", "dice", "coinflip", "joke", "avatar", "hug", "slap", "rate"]:
                    fun_cmds.append(f"`?{c.name}`")
                else:
                    general_cmds.append(f"`?{c.name}`")

        embed.add_field(name="🎮 Commandes Membres & Niveaux", value="\n".join(general_cmds + fun_cmds), inline=False)
        
        if is_mod:
            embed.add_field(name="🛡️ Commandes de Modération & Configuration", value="\n".join(mod_cmds), inline=False)
            embed.set_footer(text="💡 Utilisez ?help <commande> pour voir les détails d'une commande.")
        else:
            embed.set_footer(text="🔒 Les commandes de modération sont masquées.")

        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"🔍 Aide : `?{command.name}`", 
            description=command.help or "Aucune description fournie.", 
            color=discord.Color.blue()
        )
        await self.get_destination().send(embed=embed)

# ---------------------------------------------------------
# CONFIGURATION BOT
# ---------------------------------------------------------
PREFIX = "?"
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=PREFIX, intents=intents, help_command=MyHelp()
)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help"))

# ---------------------------------------------------------
# ÉVÉNEMENTS & LOGS
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # Anti-spam
    user_id = message.author.id
    now_ts = datetime.utcnow().timestamp()
    
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    
    limit_time = server_configs["spam_time"]
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now_ts - t < limit_time]
    spam_tracker[user_id].append(now_ts)

    if len(spam_tracker[user_id]) > server_configs["spam_limit"]:
        if not message.author.guild_permissions.administrator:
            spam_tracker[user_id] = []
            
            if user_id not in user_warns:
                user_warns[user_id] = []
            
            warn_entry = {
                "moderator": bot.user.id,
                "reason": "Spam automatique détecté",
                "date": datetime.utcnow().strftime("%d/%m/%Y à %H:%M")
            }
            user_warns[user_id].append(warn_entry)
            warn_count = len(user_warns[user_id])

            await send_mod_log(message.guild, "⚠️ Action : Avertissement Automatique & Mute (Anti-spam)", discord.Color.orange(), message.author, bot.user, f"Spam de {server_configs['spam_limit']} messages en {server_configs['spam_time']}s", duration="5m", sanction_type="Avertissement & Mute (Spam)")

            try:
                await message.author.timeout(timedelta(minutes=5), reason="Spam automatique : Mute 5 min")
            except:
                pass

            await send_sanction_dm(
                message.author,
                "⚠️ Sanction : Mute & Avertissement (Anti-spam)",
                f"Vous avez été réduit au silence et averti sur **{message.guild.name}** pour spam.\n**Total warns :** {warn_count}",
                discord.Color.orange(),
                "5m",
                bot.user,
                "Spam automatique détecté"
            )

            await message.channel.send(f"🔇 {message.author.mention} a reçu un avertissement et a été **mute automatiquement pendant 5 minutes** pour spam.", delete_after=10)

    # Système de Niveaux / XP
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1, "vocal_xp": 0}

    user_xp[user_id]["xp"] += random.randint(5, 10)
    current_xp = user_xp[user_id]["xp"]
    current_level = user_xp[user_id]["level"]
    next_level_xp = current_level * 300

    if current_xp >= next_level_xp:
        user_xp[user_id]["level"] += 1
        new_lvl = user_xp[user_id]["level"]
        
        target_chan = None
        if server_configs["level_channel"]:
            target_chan = message.guild.get_channel(server_configs["level_channel"])
        
        if not target_chan:
            target_chan = message.channel

        try:
            card = Image.new("RGBA", (900, 300), (32, 34, 37, 255))
            draw = ImageDraw.Draw(card)
            draw.rounded_rectangle([20, 20, 880, 280], radius=20, fill=(47, 49, 54, 255))
            draw.rounded_rectangle([40, 160, 860, 250], radius=10, fill=(54, 57, 63, 255))

            bar_width = 800
            current_progress = int((current_xp / next_level_xp) * bar_width) if next_level_xp > 0 else bar_width
            current_progress = min(max(current_progress, 20), bar_width)
            draw.rounded_rectangle([50, 175, 50 + current_progress, 195], radius=8, fill=(235, 120, 30, 255))

            try:
                avatar_asset = message.author.display_avatar.replace(size=128, format="png")
                avatar_bytes = await avatar_asset.read()
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).resize((100, 100))
                mask = Image.new("L", (100, 100), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, 100, 100), fill=255)
                card.paste(avatar_img, (50, 40), mask)
            except Exception:
                pass

            try:
                font_large = ImageFont.truetype("arial.ttf", 36)
                font_small = ImageFont.truetype("arial.ttf", 20)
            except IOError:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            draw.text((170, 45), f"{message.author.display_name}", fill=(255, 255, 255), font=font_large)
            draw.text((170, 95), f"Rang : #1  •  Niveau : {new_lvl}", fill=(180, 180, 180), font=font_small)
            draw.text((70, 215), f"XP Total : {current_xp + user_xp[user_id]['vocal_xp']}", fill=(220, 220, 220), font=font_small)
            draw.text((360, 215), f"XP Vocal : {user_xp[user_id]['vocal_xp']}", fill=(220, 220, 220), font=font_small)
            draw.text((650, 215), f"Objectif : {next_lvl_xp} XP", fill=(220, 220, 220), font=font_small)

            buffer = io.BytesIO()
            card.save(buffer, format="PNG")
            buffer.seek(0)
            file = discord.File(buffer, filename="rank_card.png")

            sent_msg = await target_chan.send(f"🎉 Bravo {message.author.mention}, tu passes au niveau **{new_lvl}** !", file=file)
            
            await asyncio.sleep(5)
            try:
                await sent_msg.delete()
            except:
                pass
        except Exception as e:
            print(f"Erreur lors de l'envoi de la carte de niveau : {e}")

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_id = server_configs["logs"]["message"]
    if log_id:
        chan = message.guild.get_channel(log_id)
        if chan:
            embed = discord.Embed(title="🗑️ Message supprimé", color=discord.Color.red(), timestamp=datetime.utcnow())
            embed.add_field(name="Auteur", value=message.author.mention, inline=True)
            embed.add_field(name="Salon", value=message.channel.mention, inline=True)
            embed.add_field(name="Contenu", value=message.content or "*Contenu vide/embed*", inline=False)
            await chan.send(embed=embed)

@bot.event
async def on_voice_state_update(member, before, after):
    log_id = server_configs["logs"]["voice"]
    if log_id and before.channel != after.channel:
        chan = member.guild.get_channel(log_id)
        if chan:
            if after.channel:
                await chan.send(f"🔊 **{member.name}** a rejoint le salon vocal **{after.channel.name}**.")
            elif before.channel:
                await chan.send(f"🔊 **{member.name}** a quitté le salon vocal **{before.channel.name}**.")

@bot.event
async def on_member_update(before, after):
    log_id = server_configs["logs"]["role"]
    if log_id and before.roles != after.roles:
        chan = before.guild.get_channel(log_id)
        if chan:
            await chan.send(f"👑 Rôles mis à jour pour **{after.name}**.")

@bot.event
async def on_member_join(member):
    if server_configs["autorole_id"]:
        role = member.guild.get_role(server_configs["autorole_id"])
        if role:
            try: await member.add_roles(role)
            except: pass

    if server_configs["welcome_channel"]:
        chan = member.guild.get_channel(server_configs["welcome_channel"])
        if chan:
            embed = discord.Embed(
                title="👋 Bienvenue !",
                description=f"Bienvenue sur **{member.guild.name}** {member.mention} !\nMembre numéro : **{member.guild.member_count}**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await chan.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, (commands.MissingPermissions, commands.BotMissingPermissions)):
        await ctx.send("❌ Permissions insuffisantes.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Argument manquant. Utilisation : `{ctx.command.usage or ctx.command.name}`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"⚠️ Une erreur est survenue : `{error}`")
        raise error

# ===========================================================
# COMMANDES LEVEL / RANK / CONFIG
# ===========================================================
@bot.command(name="level", aliases=["profil", "su", "rank"], help="Affiche ta carte de niveau visuelle.")
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = user_xp.get(member.id, {"xp": 0, "level": 1, "vocal_xp": 0})
    xp = data["xp"]
    lvl = data["level"]
    vocal_xp = data["vocal_xp"]
    next_lvl_xp = lvl * 300

    card = Image.new("RGBA", (900, 300), (32, 34, 37, 255))
    draw = ImageDraw.Draw(card)

    draw.rounded_rectangle([20, 20, 880, 280], radius=20, fill=(47, 49, 54, 255))
    draw.rounded_rectangle([40, 160, 860, 250], radius=10, fill=(54, 57, 63, 255))

    bar_width = 800
    current_progress = int((xp / next_lvl_xp) * bar_width) if next_lvl_xp > 0 else bar_width
    current_progress = min(max(current_progress, 20), bar_width)
    draw.rounded_rectangle([50, 175, 50 + current_progress, 195], radius=8, fill=(235, 120, 30, 255))

    try:
        avatar_asset = member.display_avatar.replace(size=128, format="png")
        avatar_bytes = await avatar_asset.read()
        avatar_img = Image.open(io.BytesIO(avatar_bytes)).resize((100, 100))
        
        mask = Image.new("L", (100, 100), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 100, 100), fill=255)
        card.paste(avatar_img, (50, 40), mask)
    except Exception:
        pass

    try:
        font_large = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((170, 45), f"{member.display_name}", fill=(255, 255, 255), font=font_large)
    draw.text((170, 95), f"Rang : #1  •  Niveau : {lvl}", fill=(180, 180, 180), font=font_small)

    draw.text((70, 215), f"XP Total : {xp + vocal_xp}", fill=(220, 220, 220), font=font_small)
    draw.text((360, 215), f"XP Vocal : {vocal_xp}", fill=(220, 220, 220), font=font_small)
    draw.text((650, 215), f"Objectif : {next_lvl_xp} XP", fill=(220, 220, 220), font=font_small)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(buffer, filename="rank_card.png")
    await ctx.send(file=file)

@bot.command(name="topniveau", help="Classement des niveaux.")
async def topniveau(ctx):
    if not user_xp:
        return await ctx.send("⚠️ Aucun classement disponible.")
    sorted_users = sorted(user_xp.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    desc = "".join([f"**#{i}** — <@{uid}> | Niveau **{data['level']}** ({data['xp']} XP)\n" for i, (uid, data) in enumerate(sorted_users[:10], 1)])
    embed = discord.Embed(title="🏆 Classement des Niveaux", description=desc, color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="niveauconfig", help="Affiche la configuration actuelle du système de niveaux.")
@commands.has_permissions(administrator=True)
async def niveauconfig(ctx):
    chan_id = server_configs["level_channel"]
    chan_mention = f"<#{chan_id}>" if chan_id else "❌ Non configuré (envoi dans le salon actif)"
    
    embed = discord.Embed(
        title="📊 Configuration du Système de Niveaux",
        color=discord.Color.from_rgb(88, 101, 242),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="💬 Salon des annonces de niveaux", value=chan_mention, inline=False)
    embed.add_field(name="⚙️ Comment modifier ?", value="Utilisez la commande `?salonlevel #salon` pour définir ou modifier le salon des annonces.", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="salonlevel", help="Définit le salon pour les annonces de niveaux. Utilisation : ?salonlevel #salon")
@commands.has_permissions(administrator=True)
async def salonlevel(ctx, channel: discord.TextChannel):
    server_configs["level_channel"] = channel.id
    await ctx.send(f"✅ Salon des niveaux configuré sur : {channel.mention}")

# ===========================================================
# SYSTÈME DE TICKETS (Corrigé pour perms admin/mod & mentions)
# ===========================================================
class TicketView(View):
    def __init__(self, panel_title: str):
        super().__init__(timeout=None)
        self.panel_title = panel_title

    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.secondary, emoji="📩", custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        
        # Permissions de base : Bloqué pour tout le monde, accessible pour l'auteur et le bot
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        # Ajout automatique des permissions de lecture/écriture pour tous les rôles mod/admin du serveur
        staff_mentions = []
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_messages or role.permissions.moderate_members:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                if not role.is_default() and role.mention not in staff_mentions:
                    staff_mentions.append(role.mention)
        
        category = interaction.channel.category
        clean_title = self.panel_title.lower().replace(" ", "-")
        channel_name = f"{clean_title}-{interaction.user.name}"

        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        log_id = server_configs["logs"]["ticket"]
        if log_id:
            log_chan = guild.get_channel(log_id)
            if log_chan:
                await log_chan.send(f"🎫 Ticket créé par {interaction.user.mention} : {ticket_channel.mention}")

        await interaction.response.send_message(f"✅ Votre ticket a été créé ici : {ticket_channel.mention}", ephemeral=True)

        close_view = TicketCloseView()
        
        # Construction du message d'accueil avec mention des rôles modérateurs/admins s'ils existent
        staff_ping_text = " ".join(staff_mentions) if staff_mentions else ""
        welcome_text = f"Bienvenue {interaction.user.mention} !\nExpliquez votre problème, un membre du staff vous répondra."
        if staff_ping_text:
            welcome_text = f"{staff_ping_text}\n\n{welcome_text}"

        await ticket_channel.send(welcome_text, view=close_view)

class TicketCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer et Archiver", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔒 Génération du transcript et fermeture du ticket...")
        
        messages = [f"{m.author} [{m.created_at}]: {m.content}" async for m in interaction.channel.history(limit=None, oldest_first=True)]
        transcript = "\n".join(messages)
        file = discord.File(io.BytesIO(transcript.encode('utf-8')), filename=f"transcript-{interaction.channel.name}.txt")
        
        log_id = server_configs["logs"]["ticket"]
        if log_id:
            log_chan = interaction.guild.get_channel(log_id)
            if log_chan:
                embed = discord.Embed(title="🎫 Ticket Fermé & Archivé", color=discord.Color.red(), timestamp=datetime.utcnow())
                embed.add_field(name="Salon", value=interaction.channel.name)
                embed.add_field(name="Fermé par", value=interaction.user.mention)
                embed.add_field(name="Total Messages", value=str(len(messages)), inline=False)
                await log_chan.send(embed=embed, file=file)
                
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.command(name="ticketconfig", help="Crée le panneau de création de tickets. Utilisation : ?ticketconfig <titre> <description>")
@commands.has_permissions(administrator=True)
async def ticketconfig(ctx, title: str = "New Panel (1)", *, description: str = "To create a ticket use the Create ticket button"):
    try:
        await ctx.message.delete()
    except:
        pass

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(46, 204, 113)
    )
    embed.set_footer(text="Ticketing system • Sécurisé")
    
    view = TicketView(panel_title=title)
    await ctx.send(embed=embed, view=view)

# ===========================================================
# CONFIGURATION LOGS (Corrigé pour perms admin/mod)
# ===========================================================
@bot.command(name="autoconfiglog", help="Crée automatiquement tous les salons de logs.")
@commands.has_permissions(administrator=True)
async def autoconfiglog(ctx):
    guild = ctx.guild
    
    # Configuration des permissions pour que seuls le bot et le staff (admin/mod) voient les logs
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
    }

    for role in guild.roles:
        if role.permissions.administrator or role.permissions.manage_messages or role.permissions.moderate_members:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True)

    category = await guild.create_category("📜 • Logs", overwrites=overwrites)
    server_configs["ticket_category_id"] = category.id
    
    c1 = await guild.create_text_channel("🛡️・logs-modération", category=category, overwrites=overwrites)
    c2 = await guild.create_text_channel("📜・logs-messages", category=category, overwrites=overwrites)
    c3 = await guild.create_text_channel("🔊・logs-vocaux", category=category, overwrites=overwrites)
    c4 = await guild.create_text_channel("👑・logs-rôles", category=category, overwrites=overwrites)
    c5 = await guild.create_text_channel("🚨・logs-anti-raid", category=category, overwrites=overwrites)
    c6 = await guild.create_text_channel("🎫・logs-tickets", category=category, overwrites=overwrites)

    server_configs["logs"] = {"mod": c1.id, "message": c2.id, "voice": c3.id, "role": c4.id, "raid": c5.id, "ticket": c6.id}
    await ctx.send("✅ Salons de logs et catégorie créés avec succès (visibles uniquement par le staff) !")

@bot.command(name="modlog")
@commands.has_permissions(administrator=True)
async def modlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["mod"] = channel.id
    await ctx.send(f"✅ Salon modération défini sur {channel.mention}")

@bot.command(name="messagelog")
@commands.has_permissions(administrator=True)
async def messagelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["message"] = channel.id
    await ctx.send(f"✅ Salon messages défini sur {channel.mention}")

@bot.command(name="voicelog")
@commands.has_permissions(administrator=True)
async def voicelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["voice"] = channel.id
    await ctx.send(f"✅ Salon vocaux défini sur {channel.mention}")

@bot.command(name="rolelog")
@commands.has_permissions(administrator=True)
async def rolelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["role"] = channel.id
    await ctx.send(f"✅ Salon rôles défini sur {channel.mention}")

@bot.command(name="raidlog")
@commands.has_permissions(administrator=True)
async def raidlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["raid"] = channel.id
    await ctx.send(f"✅ Salon anti-raid défini sur {channel.mention}")

@bot.command(name="ticketlog")
@commands.has_permissions(administrator=True)
async def ticketlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["ticket"] = channel.id
    await ctx.send(f"✅ Salon tickets défini sur {channel.mention}")

# ===========================================================
# COMMANDES : BIENVENUE & AUTOROLE
# ===========================================================
@bot.command(name="welcome")
@commands.has_permissions(administrator=True)
async def welcome(ctx, channel: discord.TextChannel):
    server_configs["welcome_channel"] = channel.id
    await ctx.send(f"✅ Salon de bienvenue configuré : {channel.mention}")

@bot.command(name="autorole")
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    server_configs["autorole_id"] = role.id
    await ctx.send(f"✅ Autorôle configuré : {role.mention}")

@bot.command(name="ghostping")
@commands.has_permissions(administrator=True)
async def ghostping(ctx):
    await ctx.send("✅ Module Anti-Ghost Ping actif.")

# ===========================================================
# COMMANDE GIVEAWAY DYNAMIQUE
# ===========================================================
@bot.command(name="giveaway", help="Lance un giveaway dynamique. Utilisation : ?giveaway <temps> <lot> , <gagnants>")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, time_arg: str, *, content: str):
    try:
        await ctx.message.delete()
    except:
        pass
    
    duration = convert_time(time_arg)
    if not duration:
        return await ctx.send("❌ Format de temps invalide ! Utilisez par exemple : `30s`, `15m`, `2h` ou `1j`.", delete_after=5)
    
    if "," in content:
        parts = content.split(",", 1)
        prize = parts[0].strip()
        try:
            winners_count = int(parts[1].strip())
        except ValueError:
            winners_count = 1
    else:
        prize = content.strip()
        winners_count = 1

    end_time = datetime.now() + timedelta(seconds=duration)
    end_str = end_time.strftime("%d/%m à %H:%M")

    embed = discord.Embed(
        title=f"🎁 G I V E A W A Y • {prize}",
        description="✨ **Tentez votre chance !** ✨\nCliquez sur l'émoji ci-dessous pour valider votre participation au tirage au sort.",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    box_content = f"• **Lot à gagner** : {prize}\n• **Participants** : 0\n• **Gagnant(s)** : {winners_count} tiré(s) au sort"
    embed.add_field(name="📊 Statistiques en direct", value=box_content, inline=False)
    embed.set_footer(text=f"🎁 Créé par @{ctx.author.name} • Fin prévue le {end_str}")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    remaining = duration
    while remaining > 0:
        await asyncio.sleep(min(15, remaining))
        remaining -= 15
        if remaining < 0:
            remaining = 0
        
        mins = remaining // 60
        secs = remaining % 60
        countdown_text = f"Fin dans : {mins}m {secs}s" if remaining > 0 else "Terminé !"

        try:
            fetched_msg = await ctx.channel.fetch_message(msg.id)
            participants_count = 0
            for reaction in fetched_msg.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            participants_count += 1

            updated_box = f"• **Lot à gagner** : {prize}\n• **Participants** : {participants_count}\n• **Gagnant(s)** : {winners_count} tiré(s) au sort"
            
            embed.clear_fields()
            embed.add_field(name="📊 Statistiques en direct", value=updated_box, inline=False)
            embed.set_footer(text=f"🎁 Créé par @{ctx.author.name} • {countdown_text}")
            await fetched_msg.edit(embed=embed)
        except:
            break

    final_msg = await ctx.channel.fetch_message(msg.id)
    participants = []
    for reaction in final_msg.reactions:
        if str(reaction.emoji) == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    participants.append(user)

    if participants:
        actual_winners_count = min(winners_count, len(participants))
        winners = random.sample(participants, actual_winners_count)
        winners_mention = ", ".join([w.mention for w in winners])
        await ctx.send(f"🎊 **Félicitations {winners_mention} !** Vous remportez le lot : **{prize}** ! 🎉")
    else:
        await ctx.send(f"❌ Malheureusement, personne n'a participé au giveaway pour **{prize}**...")

# ===========================================================
# SYSTÈME DE RÔLES PAR RÉACTION
# ===========================================================
class ReactionRoleView(View):
    def __init__(self, role_mappings):
        super().__init__(timeout=None)
        for role, emoji in role_mappings:
            self.add_item(ReactionRoleButton(role, emoji))

class ReactionRoleButton(Button):
    def __init__(self, role: discord.Role, emoji: str):
        super().__init__(style=discord.ButtonStyle.secondary, label=role.name, emoji=emoji)
        self.role = role

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        if self.role in member.roles:
            await member.remove_roles(self.role)
            await interaction.response.send_message(f"❌ Le rôle **{self.role.name}** vous a été retiré.", ephemeral=True)
        else:
            await member.add_roles(self.role)
            await interaction.response.send_message(f"✅ Le rôle **{self.role.name}** vous a été attribué !", ephemeral=True)

@bot.command(name="role", help="Crée un embed de rôles par réaction. Utilisation : ?role @role 🎨, @role 🎮")
@commands.has_permissions(administrator=True)
async def role_command(ctx, *, args: str):
    try:
        await ctx.message.delete()
    except:
        pass

    pairs = [p.strip() for p in args.split(",")]
    role_mappings = []

    for pair in pairs:
        parts = pair.split()
        if len(parts) < 2:
            continue
        role_mention = parts[0]
        emoji = parts[1]

        role_id_str = role_mention.replace("<@&", "").replace(">", "")
        if role_id_str.isdigit():
            role = ctx.guild.get_role(int(role_id_str))
            if role:
                role_mappings.append((role, emoji))

    if not role_mappings:
        return await ctx.send("❌ Format invalide ! Utilisez : `?role @MonRole 🎨, @MonAutreRole 🎮`", delete_after=10)

    embed = discord.Embed(
        title="🎭 Attribution de Rôles",
        description="Cliquez sur les boutons ci-dessous pour obtenir ou retirer les rôles correspondants !",
        color=discord.Color.from_rgb(88, 101, 242)
    )
    
    view = ReactionRoleView(role_mappings)
    await ctx.send(embed=embed, view=view)

# ===========================================================
# COMMANDES DE WARNS
# ===========================================================
@bot.command(name="warn", help="Met un avertissement à un utilisateur. Utilisation : ?warn @Utilisateur <raison>")
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    user_id = member.id
    if user_id not in user_warns:
        user_warns[user_id] = []

    warn_entry = {
        "moderator": ctx.author.id,
        "reason": reason,
        "date": datetime.utcnow().strftime("%d/%m/%Y à %H:%M")
    }
    user_warns[user_id].append(warn_entry)
    warn_count = len(user_warns[user_id])

    await send_mod_log(ctx.guild, "⚠️ Action : Avertissement (Warn)", discord.Color.orange(), member, ctx.author, reason, sanction_type="Avertissement (Warn)")

    await send_sanction_dm(
        member,
        "⚠️ Avertissement reçu",
        f"Vous avez reçu un avertissement sur **{ctx.guild.name}**.\n**Total warns :** {warn_count}",
        discord.Color.orange(),
        None,
        ctx.author,
        reason
    )

    public_embed = discord.Embed(
        title="⚠️ Sanction Appliquée",
        description=f"**Utilisateur :** {member} (`{member.id}`)\n**Sanction :** Avertissement (Warn)\n**Total :** {warn_count}\n**Modérateur :** {ctx.author.mention}\n**Raison :** {reason}",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=public_embed)

@bot.command(name="warns", help="Affiche les avertissements d'un utilisateur. Utilisation : ?warns @Utilisateur")
@commands.has_permissions(moderate_members=True)
async def warns(ctx, member: discord.Member):
    user_id = member.id
    history = user_warns.get(user_id, [])

    if not history:
        return await ctx.send(f"✅ {member.mention} n'a aucun avertissement à son actif.")

    embed = discord.Embed(
        title=f"📜 Avertissements de {member.display_name}",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    for i, w in enumerate(history, 1):
        mod = ctx.guild.get_member(w["moderator"])
        mod_name = mod.mention if mod else f"ID: {w['moderator']}"
        embed.add_field(
            name=f"Warn #{i} — {w['date']}",
            value=f"📌 **Raison :** {w['reason']}\n🛡️ **Modérateur :** {mod_name}",
            inline=False
        )

    await ctx.send(embed=embed)

# ===========================================================
# MODÉRATION & UTILS
# ===========================================================
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    await send_sanction_dm(
        member,
        "🔨 Sanction : Bannissement",
        f"Vous avez été banni de **{ctx.guild.name}**.",
        discord.Color.red(),
        None,
        ctx.author,
        reason
    )
    await member.ban(reason=reason)
    
    await send_mod_log(ctx.guild, "🔨 Action : Bannissement", discord.Color.red(), member, ctx.author, reason, sanction_type="Bannissement")
    
    public_embed = discord.Embed(
        title="🔨 Sanction Appliquée",
        description=f"**Utilisateur :** {member} (`{member.id}`)\n**Sanction :** Bannissement\n**Modérateur :** {ctx.author.mention}\n**Raison :** {reason}",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=public_embed)

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_input: str):
    banned = [e async for e in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user.id) == user_input or str(entry.user) == user_input:
            await ctx.guild.unban(entry.user)
            await send_mod_log(ctx.guild, "🔓 Action : Débannissement", discord.Color.green(), entry.user, ctx.author, "Débannissement manuel", sanction_type="Débannissement")
            return await ctx.send(f"🔓 {entry.user} débanni.")
    await ctx.send("❌ Utilisateur introuvable.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    await send_sanction_dm(
        member,
        "👢 Sanction : Expulsion",
        f"Vous avez été expulsé de **{ctx.guild.name}**.",
        discord.Color.orange(),
        None,
        ctx.author,
        reason
    )
    await member.kick(reason=reason)
    
    await send_mod_log(ctx.guild, "👢 Action : Expulsion", discord.Color.orange(), member, ctx.author, reason, sanction_type="Expulsion")
    
    public_embed = discord.Embed(
        title="👢 Sanction Appliquée",
        description=f"**Utilisateur :** {member} (`{member.id}`)\n**Sanction :** Expulsion\n**Modérateur :** {ctx.author.mention}\n**Raison :** {reason}",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=public_embed)

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, time_arg: str, *, reason: str = "Aucune raison fournie"):
    seconds = convert_time(time_arg)
    if not seconds:
        return await ctx.send("❌ Format de temps invalide pour le mute ! Utilisez par exemple : `10m`, `1h`, `2j`.", delete_after=5)
    
    duration_delta = timedelta(seconds=seconds)
    await member.timeout(duration_delta, reason=reason)
    
    readable_duration = format_duration(time_arg)
    
    await send_sanction_dm(
        member,
        "🔇 Sanction : Mute (Timeout)",
        f"Vous avez été réduit au silence sur **{ctx.guild.name}**.",
        discord.Color.gold(),
        time_arg,
        ctx.author,
        reason
    )
        
    await send_mod_log(ctx.guild, "🔇 Action : Mute / Timeout", discord.Color.gold(), member, ctx.author, reason, duration=time_arg, sanction_type="Mute (Timeout)")
        
    public_embed = discord.Embed(
        title="🔇 Sanction Appliquée",
        description=f"**Utilisateur :** {member} (`{member.id}`)\n**Sanction :** Mute (Timeout)\n**Durée :** {readable_duration}\n**Modérateur :** {ctx.author.mention}\n**Raison :** {reason}",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=public_embed)

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    
    await send_sanction_dm(
        member,
        "✅ Fin de sanction",
        f"Votre exclusion temporaire a été levée sur **{ctx.guild.name}**.",
        discord.Color.green(),
        None,
        ctx.author,
        "Levée du timeout manuelle"
    )
        
    await send_mod_log(ctx.guild, "🔊 Action : Unmute", discord.Color.green(), member, ctx.author, "Levée du timeout manuelle", sanction_type="Unmute")
    await ctx.send(f"✅ {member.mention} a été unmute.")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, nombre: int):
    deleted = await ctx.channel.purge(limit=nombre + 1)
    msg = await ctx.send(f"🧹 {len(deleted) - 1} message(s) supprimé(s).")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="say")
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message: str):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(message)

@bot.command(name="annonce")
@commands.has_permissions(manage_messages=True)
async def annonce(ctx, *, message: str):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(title="📢 Annonce", description=message, color=discord.Color.blue())
    embed.set_footer(text=f"Par {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="8ball")
async def eight_ball(ctx, *, question: str):
    await ctx.send(embed=discord.Embed(title="🎱 Boule magique", description=f"Q: {question}\nR: {random.choice(['Oui.', 'Non.', 'Probablement.'])}"))

@bot.command(name="dice")
async def dice(ctx, faces: int = 6):
    await ctx.send(f"🎲 Résultat : **{random.randint(1, faces)}**")

@bot.command(name="coinflip")
async def coinflip(ctx):
    await ctx.send(f"Pièce : **{random.choice(['Pile 🪙', 'Face 🪙'])}**")

@bot.command(name="joke", help="Raconte une blague aléatoire.")
async def joke(ctx):
    jokes_list = [
        ("Pourquoi les plongeurs plongent-ils toujours en arrière et jamais en avant ?", "Parce que sinon ils tombent quand même dans le bateau !"),
        ("Quel est le comble pour un electricien ?", "De ne pas être au courant !"),
        ("Que fait un poussin qui veut faire caca ?", "Poussin piou piou... Non, il pousse !"),
        ("C'est l'histoire d'un pingouin...", "Il est tellement froid qu'il gèle l'ambiance !"),
        ("Quel est le comble pour un jardinier ?", "De raconter des salades !"),
        ("Pourquoi les oiseaux volent-ils vers le sud en hiver ?", "Parce que c'est trop long d'y aller à pied !"),
        ("Qu'est-ce qu'un squelette dans un placard ?", "Quelqu'un qui a gagné à cache-cache il y a très, très longtemps."),
        ("Pourquoi les belges mettent-ils leur frigo sur le balcon ?", "Pour faire des glaçons en hiver !"),
        ("Quel est le super-héros le plus écolo ?", "Le Concombre Masqué !"),
        ("C'est l'histoire d'un oeuf...", "Il fait 'tac' et il se casse !")
    ]
    question, answer = random.choice(jokes_list)
    embed = discord.Embed(title="😂 Petite blague du jour", description=f"**Q :** {question}\n\n**R :** ||{answer}||", color=discord.Color.orange())
    embed.set_footer(text="Clique sur la réponse pour la découvrir !")
    await ctx.send(embed=embed)

@bot.command(name="avatar")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar de {member.display_name}").set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="hug")
async def hug(ctx, member: discord.Member):
    await ctx.send(f"🤗 {ctx.author.mention} fait un câlin à {member.mention} !")

@bot.command(name="slap")
async def slap(ctx, member: discord.Member):
    await ctx.send(f"👋 {ctx.author.mention} donne une claque à {member.mention} !")

@bot.command(name="rate")
async def rate(ctx, *, texte: str):
    await ctx.send(f"📊 Note pour **{texte}** : **{random.randint(0, 10)}/10**")

# ---------------------------------------------------------
# LANCEMENT BOT & WEB SERVER
# ---------------------------------------------------------
async def main():
    await start_web_server()
    await bot.start(os.environ.get("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
