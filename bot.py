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
server_configs = {
    "welcome_channel": None,
    "autorole_id": None,
    "ticket_category_id": None,
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
                if c.name in ["ban", "unban", "kick", "mute", "unmute", "clear", "setup_logs", "giveaway", 
                              "autoconfiglog", "modlog", "messagelog", "voicelog", "rolelog", "raidlog", "ticketlog", 
                              "welcome", "autorole", "niveauconfig", "ticketconfig", "say", "annonce"]:
                    mod_cmds.append(f"`?{c.name}`")
                elif c.name in ["8ball", "dice", "coinflip", "joke", "avatar", "hug", "slap", "rate"]:
                    fun_cmds.append(f"`?{c.name}`")
                else:
                    general_cmds.append(f"`?{c.name}`")

        embed.add_field(name="🎮 Commandes Membres & Niveaux", value=" ".join(general_cmds + fun_cmds), inline=False)
        
        if is_mod:
            embed.add_field(name="🛡️ Commandes de Modération & Configuration", value=" ".join(mod_cmds), inline=False)
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
# ÉVÉNEMENTS & LOGS FONCTIONNELS
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # XP Messages (Gain ralenti : 5 à 10 XP, palier à 300)
    user_id = message.author.id
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1, "vocal_xp": 0}

    user_xp[user_id]["xp"] += random.randint(5, 10)
    current_xp = user_xp[user_id]["xp"]
    current_level = user_xp[user_id]["level"]
    next_level_xp = current_level * 300

    if current_xp >= next_level_xp:
        user_xp[user_id]["level"] += 1
        await message.channel.send(f"🎉 Bravo {message.author.mention}, tu passes au **niveau {user_xp[user_id]['level']}** ! 🚀")

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
# COMMANDE LEVEL / RANK (CORRIGÉE SANS ERREUR PILLOW)
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

@bot.command(name="niveauconfig", help="Configuration du système de niveaux.")
@commands.has_permissions(administrator=True)
async def niveauconfig(ctx):
    await ctx.send("✅ Système de niveaux actif.")

# ===========================================================
# SYSTÈME DE TICKETS AVEC ARCHIVAGE TRANSCRIPT (.TXT)
# ===========================================================
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.secondary, emoji="📩", custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        category_id = server_configs.get("ticket_category_id")
        category = guild.get_channel(category_id) if category_id else None

        ticket_channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
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
        await ticket_channel.send(f"Bienvenue {interaction.user.mention} !\nExpliquez votre problème, un membre du staff vous répondra.", view=close_view)

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

@bot.command(name="ticketconfig", help="Crée le panneau de création de tickets avec bouton.")
@commands.has_permissions(administrator=True)
async def ticketconfig(ctx):
    embed = discord.Embed(
        title="New Panel (1)",
        description="To create a ticket use the Create ticket button",
        color=discord.Color.from_rgb(46, 204, 113)
    )
    embed.set_footer(text="Ticketing system • Sécurisé")
    
    view = TicketView()
    await ctx.send(embed=embed, view=view)

# ===========================================================
# CONFIGURATION LOGS
# ===========================================================
@bot.command(name="autoconfiglog", help="Crée automatiquement tous les salons de logs.")
@commands.has_permissions(administrator=True)
async def autoconfiglog(ctx):
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
    }

    category = await guild.create_category("📜 • Logs", overwrites=overwrites)
    server_configs["ticket_category_id"] = category.id
    
    c1 = await guild.create_text_channel("🛡️・logs-modération", category=category, overwrites=overwrites)
    c2 = await guild.create_text_channel("📜・logs-messages", category=category, overwrites=overwrites)
    c3 = await guild.create_text_channel("🔊・logs-vocaux", category=category, overwrites=overwrites)
    c4 = await guild.create_text_channel("👑・logs-rôles", category=category, overwrites=overwrites)
    c5 = await guild.create_text_channel("🚨・logs-anti-raid", category=category, overwrites=overwrites)
    c6 = await guild.create_text_channel("🎫・logs-tickets", category=category, overwrites=overwrites)

    server_configs["logs"] = {"mod": c1.id, "message": c2.id, "voice": c3.id, "role": c4.id, "raid": c5.id, "ticket": c6.id}
    await ctx.send("✅ Salons de logs et catégorie de tickets créés avec succès !")

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
# COMMANDE GIVEAWAY DYNAMIQUE (COMPTE À REBOURS LIVE)
# ===========================================================
@bot.command(name="giveaway", help="Lance un giveaway dynamique. Utilisation : ?giveaway <durée en secondes> <lot>")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, duration: int, *, prize: str):
    await ctx.message.delete()
    
    end_time = datetime.now() + timedelta(seconds=duration)
    end_str = end_time.strftime("%A à %H:%M")

    embed = discord.Embed(
        title=f"🎉 {prize}",
        description="Réagis avec 🎉 pour participer !",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    
    box_content = f"```\n┌─────────────────────────────┐\n│        INFORMATIONS         │\n├─────────────────────────────┤\n│  Gagnant(s)  : 1            │\n│  Participants: 0            │\n└─────────────────────────────┘\n```"
    embed.add_field(name="", value=box_content, inline=False)
    embed.set_footer(text=f"Organisé par : @{ctx.author.name} • Fin : {end_str}")

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
        countdown_text = f"Fin dans : {mins}min {secs}s ({end_str})" if remaining > 0 else "Terminé !"

        try:
            fetched_msg = await ctx.channel.fetch_message(msg.id)
            participants_count = 0
            for reaction in fetched_msg.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            participants_count += 1

            updated_box = f"```\n┌─────────────────────────────┐\n│        INFORMATIONS         │\n├─────────────────────────────┤\n│  Gagnant(s)  : 1            │\n│  Participants: {participants_count:<12} │\n└─────────────────────────────┘\n```"
            
            embed.clear_fields()
            embed.add_field(name="", value=updated_box, inline=False)
            embed.set_footer(text=f"Organisé par : @{ctx.author.name} • Fin : {countdown_text}")
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
        winner = random.choice(participants)
        await ctx.send(f"🎊 Félicitations {winner.mention} ! Tu remportes **{prize}** !")
    else:
        await ctx.send(f"❌ Personne n'a participé au giveaway pour **{prize}**.")

# ===========================================================
# MODÉRATION & UTILS (Mis à jour : Embed + MP)
# ===========================================================
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    embed = discord.Embed(title="🔨 Sanction : Bannissement", description=f"Vous avez été banni de **{ctx.guild.name}**.\n**Raison :** {reason}", color=discord.Color.red())
    try:
        await member.send(embed=embed)
    except:
        pass
    await member.ban(reason=reason)
    
    public_embed = discord.Embed(title="🔨 Utilisateur banni", description=f"**{member}** a été banni.\n**Raison :** {reason}", color=discord.Color.red())
    await ctx.send(embed=public_embed)

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_input: str):
    banned = [e async for e in ctx.guild.bans()]
    for entry in banned:
        if str(entry.user.id) == user_input or str(entry.user) == user_input:
            await ctx.guild.unban(entry.user)
            return await ctx.send(f"🔓 {entry.user} débanni.")
    await ctx.send("❌ Utilisateur introuvable.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    embed = discord.Embed(title="👢 Sanction : Expulsion", description=f"Vous avez été expulsé de **{ctx.guild.name}**.\n**Raison :** {reason}", color=discord.Color.orange())
    try:
        await member.send(embed=embed)
    except:
        pass
    await member.kick(reason=reason)
    
    public_embed = discord.Embed(title="👢 Utilisateur expulsé", description=f"**{member}** a été expulsé.\n**Raison :** {reason}", color=discord.Color.orange())
    await ctx.send(embed=public_embed)

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason: str = "Aucune raison"):
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    
    embed = discord.Embed(title="🔇 Sanction : Mute (Timeout)", description=f"Vous avez été réduit au silence sur **{ctx.guild.name}** pour **{minutes} minute(s)**.\n**Raison :** {reason}", color=discord.Color.yellow())
    try:
        await member.send(embed=embed)
    except:
        pass
        
    public_embed = discord.Embed(title="🔇 Utilisateur mute", description=f"**{member}** a été mute pour {minutes} min.\n**Raison :** {reason}", color=discord.Color.yellow())
    await ctx.send(embed=public_embed)

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    
    embed = discord.Embed(title="✅ Fin de sanction", description=f"Vous avez été unmute sur **{ctx.guild.name}**.", color=discord.Color.green())
    try:
        await member.send(embed=embed)
    except:
        pass
        
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

@bot.command(name="joke")
async def joke(ctx):
    await ctx.send(f"😂 Pourquoi les plongeurs plongent en arrière ? ...")

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
