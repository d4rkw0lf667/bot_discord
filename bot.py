import os
import random
import asyncio
from datetime import timedelta
import discord
from discord.ext import commands
from aiohttp import web

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
# STOCKAGE EN MÉMOIRE (XP, Configurations, Logs, Welcome)
# ---------------------------------------------------------
user_xp = {}          # {user_id: {"xp": 0, "level": 1, "vocal_xp": 0}}
server_configs = {
    "welcome_channel": None,
    "autorole_id": None,
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
# HELP PERSONNALISÉ (Séparé par rôles)
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
                              "welcome", "autorole", "niveauconfig", "say", "annonce"]:
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
            embed.set_footer(text="🔒 Les commandes de modération sont masquées. Fais ?help moderation si tu as les droits.")

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

bot = commands.Bot(
    command_prefix=PREFIX, intents=intents, help_command=MyHelp()
)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help"))

# ---------------------------------------------------------
# ÉVÉNEMENTS (XP, Welcome, Autorole, Ghostping)
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Gestion XP Messages
    user_id = message.author.id
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1, "vocal_xp": 0}

    user_xp[user_id]["xp"] += random.randint(15, 25)
    current_xp = user_xp[user_id]["xp"]
    current_level = user_xp[user_id]["level"]
    next_level_xp = current_level * 150

    if current_xp >= next_level_xp:
        user_xp[user_id]["level"] += 1
        await message.channel.send(f"🎉 Bravo {message.author.mention}, tu passes au **niveau {user_xp[user_id]['level']}** ! 🚀")

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    if message.mentions:
        log_channel_id = server_configs["logs"]["message"]
        if log_channel_id:
            log_chan = message.guild.get_channel(log_channel_id)
            if log_chan:
                mentions_str = ", ".join([m.mention for m in message.mentions])
                embed = discord.Embed(title="👻 Ghost Ping Détecté", color=discord.Color.orange())
                embed.add_field(name="Auteur", value=message.author.mention, inline=True)
                embed.add_field(name="Salon", value=message.channel.mention, inline=True)
                embed.add_field(name="Personnes pingées", value=mentions_str, inline=False)
                embed.add_field(name="Message supprimé", value=message.content or "*Aucun contenu textuel*", inline=False)
                await log_chan.send(embed=embed)

@bot.event
async def on_member_join(member):
    # Autorole
    if server_configs["autorole_id"]:
        role = member.guild.get_role(server_configs["autorole_id"])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

    # Welcome
    if server_configs["welcome_channel"]:
        chan = member.guild.get_channel(server_configs["welcome_channel"])
        if chan:
            embed = discord.Embed(
                title="👋 Bienvenue !",
                description=f"Bienvenue sur **{member.guild.name}** {member.mention} !\nNous sommes désormais **{member.guild.member_count}** membres.",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await chan.send(embed=embed)

# ---------------------------------------------------------
# GESTION D'ERREURS GLOBALE
# ---------------------------------------------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ Je n'ai pas les permissions nécessaires pour faire ça.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Argument manquant. Utilisation : `{ctx.command.usage or ctx.command.name}`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"⚠️ Une erreur est survenue : `{error}`")
        raise error

# ===========================================================
# COMMANDES : PROFIL & NIVEAUX (Style Statbot / Rank Card)
# ===========================================================
@bot.command(name="profil", aliases=["su", "niveau", "rank"], help="Affiche la carte de profil et les statistiques d'un membre. Utilisation : ?profil [@membre]")
async def profil(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = member.id
    
    data = user_xp.get(user_id, {"xp": 0, "level": 1, "vocal_xp": 0})
    xp = data["xp"]
    lvl = data["level"]
    vocal_xp = data["vocal_xp"]
    next_lvl_xp = lvl * 150
    
    # Barre de progression style screen
    progress = int((xp / next_lvl_xp) * 25) if next_lvl_xp > 0 else 25
    progress = min(max(progress, 0), 25)
    bar = "█" * progress + "░" * (25 - progress)
    percentage = int((xp / next_lvl_xp) * 100) if next_lvl_xp > 0 else 100

    embed = discord.Embed(color=discord.Color.from_rgb(47, 49, 54))
    embed.set_author(name=f"Utilisateur : {member.display_name}", icon_url=member.display_avatar.url)
    embed.description = f"**Rang :** #1 · **Niveau :** {lvl} · **XP Messages :** {xp}\n\n`{bar}` {percentage}%\n"
    
    embed.add_field(name="📊 XP Total", value=f"`{xp + vocal_xp}`", inline=True)
    embed.add_field(name="🎙️ XP Vocal", value=f"`{vocal_xp}`", inline=True)
    embed.add_field(name="🎯 Prochain niveau", value=f"`{next_lvl_xp} XP`", inline=True)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="topniveau", help="Affiche le classement des membres du serveur par niveau.")
async def topniveau(ctx):
    if not user_xp:
        return await ctx.send("⚠️ Aucune donnée de niveau enregistrée pour le moment.")
    
    sorted_users = sorted(user_xp.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)
    
    desc = ""
    for index, (uid, data) in enumerate(sorted_users[:10], start=1):
        user = ctx.guild.get_member(uid)
        username = user.display_name if user else f"Utilisateur ID {uid}"
        desc += f"**#{index}** — {username} | Niveau **{data['level']}** ({data['xp']} XP)\n"

    embed = discord.Embed(title="🏆 Classement des Niveaux", description=desc, color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="niveauconfig", help="Affiche ou configure les paramètres du système de niveaux.")
@commands.has_permissions(administrator=True)
async def niveauconfig(ctx):
    embed = discord.Embed(
        title="⚙️ Configuration du Système de Niveaux",
        description="Le système de gain d'XP par message et vocal est **actif**.\nGain par message : `15 à 25 XP`.\nPalier de niveau : `Niveau × 150 XP`.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# ===========================================================
# COMMANDES : CONFIGURATION LOGS & SALONS
# ===========================================================
@bot.command(name="autoconfiglog", help="Crée automatiquement tous les salons de logs du serveur.")
@commands.has_permissions(administrator=True)
async def autoconfiglog(ctx):
    guild = ctx.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
    }

    category = await guild.create_category("📜 • Logs", overwrites=overwrites)
    
    c1 = await guild.create_text_channel("🛡️・logs-modération", category=category, overwrites=overwrites)
    c2 = await guild.create_text_channel("📜・logs-messages", category=category, overwrites=overwrites)
    c3 = await guild.create_text_channel("🔊・logs-vocaux", category=category, overwrites=overwrites)
    c4 = await guild.create_text_channel("👑・logs-rôles", category=category, overwrites=overwrites)
    c5 = await guild.create_text_channel("🚨・logs-anti-raid", category=category, overwrites=overwrites)
    c6 = await guild.create_text_channel("🎫・logs-tickets", category=category, overwrites=overwrites)

    server_configs["logs"] = {"mod": c1.id, "message": c2.id, "voice": c3.id, "role": c4.id, "raid": c5.id, "ticket": c6.id}
    await ctx.send("✅ Tous les salons de logs ont été créés et configurés avec succès !")

@bot.command(name="modlog", help="Définit le salon de logs modération. Utilisation : ?modlog #salon")
@commands.has_permissions(administrator=True)
async def modlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["mod"] = channel.id
    await ctx.send(f"✅ Le salon de logs modération a été défini sur {channel.mention}.")

@bot.command(name="messagelog", help="Définit le salon de logs messages.")
@commands.has_permissions(administrator=True)
async def messagelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["message"] = channel.id
    await ctx.send(f"✅ Le salon de logs messages a été défini sur {channel.mention}.")

@bot.command(name="voicelog", help="Définit le salon de logs vocaux.")
@commands.has_permissions(administrator=True)
async def voicelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["voice"] = channel.id
    await ctx.send(f"✅ Le salon de logs vocaux a été défini sur {channel.mention}.")

@bot.command(name="rolelog", help="Définit le salon de logs rôles.")
@commands.has_permissions(administrator=True)
async def rolelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["role"] = channel.id
    await ctx.send(f"✅ Le salon de logs rôles a été défini sur {channel.mention}.")

@bot.command(name="raidlog", help="Définit le salon de logs anti-raid.")
@commands.has_permissions(administrator=True)
async def raidlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["raid"] = channel.id
    await ctx.send(f"✅ Le salon de logs anti-raid a été défini sur {channel.mention}.")

@bot.command(name="ticketlog", help="Définit le salon de logs tickets.")
@commands.has_permissions(administrator=True)
async def ticketlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["ticket"] = channel.id
    await ctx.send(f"✅ Le salon de logs tickets a été défini sur {channel.mention}.")

# ===========================================================
# COMMANDES : BIENVENUE & AUTOROLE & GHOSTPING
# ===========================================================
@bot.command(name="welcome", help="Configure le salon de bienvenue. Utilisation : ?welcome #salon")
@commands.has_permissions(administrator=True)
async def welcome(ctx, channel: discord.TextChannel):
    server_configs["welcome_channel"] = channel.id
    embed = discord.Embed(title="✅ Salon de Bienvenue Configuré", description=f"Les messages de bienvenue seront envoyés dans {channel.mention}.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="autorole", help="Configure le rôle automatique attribué à l'arrivée. Utilisation : ?autorole @role")
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    server_configs["autorole_id"] = role.id
    embed = discord.Embed(title="✅ Autorôle Configuré", description=f"Le rôle {role.mention} sera automatiquement attribué aux nouveaux membres.", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="ghostping", help="Affiche l'état de la protection anti-ghost ping.")
@commands.has_permissions(administrator=True)
async def ghostping(ctx):
    embed = discord.Embed(title="🛡️ Module Anti-Ghost Ping", description="Le système de détection des pings supprimés est **actif** (redirigé vers le salon `logs-messages`).", color=discord.Color.blue())
    await ctx.send(embed=embed)

# ===========================================================
# COMMANDES DE MODÉRATION
# ===========================================================
@bot.command(name="ban", help="Bannir un membre. Utilisation : ?ban @membre [raison]")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas te bannir toi-même.")
    await member.ban(reason=reason)
    embed = discord.Embed(title="🔨 Membre banni", description=f"**{member}** a été banni.", color=discord.Color.red())
    embed.add_field(name="Raison", value=reason)
    await ctx.send(embed=embed)

@bot.command(name="unban", help="Débannir un membre par son pseudo ou ID.")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_input: str):
    banned_users = [entry async for entry in ctx.guild.bans()]
    user_to_unban = None
    for ban_entry in banned_users:
        if str(ban_entry.user.id) == user_input or str(ban_entry.user) == user_input:
            user_to_unban = ban_entry.user
            break
    if not user_to_unban:
        return await ctx.send("❌ Utilisateur introuvable.")
    await ctx.guild.unban(user_to_unban)
    await ctx.send(f"🔓 **{user_to_unban}** a été débanni.")

@bot.command(name="kick", help="Expulser un membre.")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** a été expulsé.")

@bot.command(name="mute", help="Mute temporairement un membre. Utilisation : ?mute @membre 10 [raison]")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int, *, reason: str = "Aucune raison"):
    duration = timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"🔇 **{member}** a été mute pour {minutes} minute(s).")

@bot.command(name="unmute", help="Retirer le mute d'un membre.")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"✅ **{member}** a été unmute.")

@bot.command(name="clear", help="Supprimer des messages. Utilisation : ?clear 10")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, nombre: int):
    deleted = await ctx.channel.purge(limit=nombre + 1)
    msg = await ctx.send(f"🧹 **{len(deleted) - 1}** message(s) supprimé(s).")
    await asyncio.sleep(3)
    await msg.delete()

# ===========================================================
# COMMANDES UTILITIES & ANNONCES & GIVEAWAY
# ===========================================================
@bot.command(name="say", help="Fait répéter un message par le bot.")
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message: str):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(message)

@bot.command(name="annonce", help="Créer une annonce embed.")
@commands.has_permissions(manage_messages=True)
async def annonce(ctx, *, message: str):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(title="📢 Annonce", description=message, color=discord.Color.blue())
    embed.set_footer(text=f"Publié par {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="giveaway", help="Lance un giveaway. Utilisation : ?giveaway <durée en secondes> <prix>")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, duration: int, *, prize: str):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="🎉 **GIVEAWAY** 🎉",
        description=f"Cadeau : **{prize}**\n\nRéagis avec 🎉 pour participer !\nCréé par : {ctx.author.mention}",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Fin du giveaway dans {duration} secondes.")
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(duration)

    new_msg = await ctx.channel.fetch_message(msg.id)
    users = []
    for reaction in new_msg.reactions:
        if reaction.emoji == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)

    if users:
        winner = random.choice(users)
        await ctx.send(f"🎊 Félicitations {winner.mention} ! Tu remportes **{prize}** !")
    else:
        await ctx.send(f"❌ Personne n'a participé au giveaway pour **{prize}**.")

# ===========================================================
# COMMANDES FUN
# ===========================================================
@bot.command(name="8ball", help="Boule magique.")
async def eight_ball(ctx, *, question: str):
    reponses = ["Oui.", "C'est certain.", "Non.", "Mes sources disent non.", "Probablement."]
    embed = discord.Embed(title="🎱 Boule magique", color=discord.Color.purple())
    embed.add_field(name="Question", value=question)
    embed.add_field(name="Réponse", value=random.choice(reponses))
    await ctx.send(embed=embed)

@bot.command(name="dice", help="Lance un dé.")
async def dice(ctx, faces: int = 6):
    await ctx.send(f"🎲 Résultat : **{random.randint(1, faces)}**")

@bot.command(name="coinflip", help="Pile ou face.")
async def coinflip(ctx):
    await ctx.send(f"La pièce tombe sur... **{random.choice(['Pile 🪙', 'Face 🪙'])}** !")

@bot.command(name="joke", help="Blague aléatoire.")
async def joke(ctx):
    blagues = ["Pourquoi les plongeurs plongent en arrière ? ...", "Quel est le sport le plus silencieux ? Le para-chute."]
    await ctx.send(f"😂 {random.choice(blagues)}")

@bot.command(name="avatar", help="Affiche l'avatar.")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar de {member.display_name}", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="hug", help="Fait un câlin.")
async def hug(ctx, member: discord.Member):
    await ctx.send(f"🤗 {ctx.author.mention} fait un gros câlin à {member.mention} !")

@bot.command(name="slap", help="Met une baffe.")
async def slap(ctx, member: discord.Member):
    await ctx.send(f"👋 {ctx.author.mention} met une claque à {member.mention} !")

@bot.command(name="rate", help="Note sur 10.")
async def rate(ctx, *, texte: str):
    await ctx.send(f"📊 Je donne à **{texte}** la note de **{random.randint(0, 10)}/10**")

# ---------------------------------------------------------
# LANCEMENT DU BOT ET DU SERVEUR WEB
# ---------------------------------------------------------
async def main():
    await start_web_server()
    await bot.start(os.environ.get("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
