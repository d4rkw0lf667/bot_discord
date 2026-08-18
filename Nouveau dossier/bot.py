import os
import random
import asyncio
from datetime import timedelta
import discord
from discord.ext import commands

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
PREFIX = "?"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand()
)


@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help"))


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
        await ctx.send(
            f"⚠️ Argument manquant. Utilisation : `{ctx.command.usage or ctx.command.name}`"
        )
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.")
    elif isinstance(error, commands.UserNotFound):
        await ctx.send("❌ Utilisateur introuvable.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ Argument invalide.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignorer les commandes inconnues
    else:
        await ctx.send(f"⚠️ Une erreur est survenue : `{error}`")
        raise error


# ===========================================================
# COMMANDES DE MODÉRATION
# ===========================================================


@bot.command(name="ban", help="Bannir un membre. Utilisation : ?ban @membre [raison]")
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas te bannir toi-même.")
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send(
            "❌ Tu ne peux pas bannir ce membre (rôle égal ou supérieur au tien)."
        )

    # Envoi du message privé avant le ban
    try:
        embed_mp = discord.Embed(
            title=f"🔨 Banni de {ctx.guild.name}", color=discord.Color.red()
        )
        embed_mp.add_field(name="Raison", value=reason, inline=False)
        embed_mp.add_field(name="Modérateur", value=ctx.author.mention, inline=False)
        await member.send(embed=embed_mp)
    except discord.Forbidden:
        pass

    await member.ban(reason=reason)

    embed = discord.Embed(
        title="🔨 Membre banni",
        description=f"**{member}** a été banni par {ctx.author.mention}",
        color=discord.Color.red(),
    )
    embed.add_field(name="Raison", value=reason)
    await ctx.send(embed=embed)


@bot.command(
    name="unban", help="Débannir un membre. Utilisation : ?unban Pseudo#0000 ou ID"
)
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
async def unban(ctx, *, user_input: str):
    banned_users = [entry async for entry in ctx.guild.bans()]
    user_to_unban = None

    # Recherche par ID ou par nom/tag
    for ban_entry in banned_users:
        user = ban_entry.user
        if (
            str(user.id) == user_input
            or str(user) == user_input
            or user.name == user_input
        ):
            user_to_unban = user
            break

    if user_to_unban is None:
        return await ctx.send("❌ Utilisateur introuvable dans la liste des bannis.")

    await ctx.guild.unban(user_to_unban)

    embed = discord.Embed(
        title="🔓 Membre débanni",
        description=f"**{user_to_unban}** a été débanni par {ctx.author.mention}",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)


@bot.command(
    name="kick", help="Expulser un membre. Utilisation : ?kick @membre [raison]"
)
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas t'expulser toi-même.")
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send(
            "❌ Tu ne peux pas expulser ce membre (rôle égal ou supérieur au tien)."
        )

    # Envoi du message privé
    try:
        embed_mp = discord.Embed(
            title=f"👢 Expulsé de {ctx.guild.name}", color=discord.Color.orange()
        )
        embed_mp.add_field(name="Raison", value=reason, inline=False)
        embed_mp.add_field(name="Modérateur", value=ctx.author.mention, inline=False)
        await member.send(embed=embed_mp)
    except discord.Forbidden:
        pass

    await member.kick(reason=reason)

    embed = discord.Embed(
        title="👢 Membre expulsé",
        description=f"**{member}** a été expulsé par {ctx.author.mention}",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Raison", value=reason)
    await ctx.send(embed=embed)


@bot.command(
    name="mute",
    help="Mute un membre (timeout, en minutes). Utilisation : ?mute @membre 10 [raison]",
)
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
async def mute(
    ctx, member: discord.Member, minutes: int, *, reason: str = "Aucune raison fournie"
):
    if member == ctx.author:
        return await ctx.send("❌ Tu ne peux pas te mute toi-même.")
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send(
            "❌ Tu ne peux pas mute ce membre (rôle égal ou supérieur au tien)."
        )
    if minutes <= 0 or minutes > 40320:
        return await ctx.send(
            "⚠️ La durée doit être comprise entre 1 minute et 28 jours (40320 minutes)."
        )

    duration = timedelta(minutes=minutes)

    # Envoi du message privé
    try:
        embed_mp = discord.Embed(
            title=f"🔇 Mute dans {ctx.guild.name}", color=discord.Color.gold()
        )
        embed_mp.add_field(name="Durée", value=f"{minutes} minute(s)", inline=False)
        embed_mp.add_field(name="Raison", value=reason, inline=False)
        embed_mp.add_field(name="Modérateur", value=ctx.author.mention, inline=False)
        await member.send(embed=embed_mp)
    except discord.Forbidden:
        pass

    await member.timeout(duration, reason=reason)

    embed = discord.Embed(
        title="🔇 Membre mute",
        description=f"**{member}** a été mute par {ctx.author.mention} pour **{minutes} minute(s)**",
        color=discord.Color.gold(),
    )
    embed.add_field(name="Raison", value=reason)
    await ctx.send(embed=embed)


@bot.command(
    name="unmute", help="Retirer le mute d'un membre. Utilisation : ?unmute @membre"
)
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"✅ **{member}** a été unmute.")


@bot.command(
    name="clear", help="Supprimer un nombre de messages. Utilisation : ?clear 10"
)
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True)
async def clear(ctx, nombre: int):
    if nombre <= 0:
        return await ctx.send("⚠️ Le nombre doit être supérieur à 0.")
    if nombre > 100:
        return await ctx.send(
            "⚠️ Tu ne peux pas supprimer plus de 100 messages à la fois."
        )

    deleted = await ctx.channel.purge(limit=nombre + 1)
    msg = await ctx.send(f"🧹 **{len(deleted) - 1}** message(s) supprimé(s).")
    await asyncio.sleep(3)
    await msg.delete()


# ===========================================================
# COMMANDES UTILITIES & ANNONCES
# ===========================================================


@bot.command(
    name="say",
    help="Fait répéter un message par le bot (Administrateurs uniquement). Utilisation : ?say <message>",
)
@commands.has_permissions(administrator=True)
async def say(ctx, *, message: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    await ctx.send(message)


@bot.command(
    name="annonce",
    help="Créer une annonce sous forme d'embed. Utilisation : ?annonce <texte>",
)
@commands.has_permissions(administrator=True)
async def annonce(ctx, *, message: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    embed = discord.Embed(
        title="📢 Annonce", description=message, color=discord.Color.blue()
    )
    embed.set_footer(
        text=f"Publié par {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url,
    )
    await ctx.send(embed=embed)


# ===========================================================
# COMMANDES FUN
# ===========================================================


@bot.command(
    name="8ball",
    help="Pose une question à la boule magique. Utilisation : ?8ball <question>",
)
async def eight_ball(ctx, *, question: str):
    reponses = [
        "Oui, sans aucun doute.",
        "C'est certain.",
        "Probablement.",
        "Demande à nouveau plus tard.",
        "Je ne peux pas le dire pour l'instant.",
        "Non, ne compte pas dessus.",
        "Mes sources disent non.",
        "C'est très douteux.",
        "Concentre-toi et redemande.",
    ]
    embed = discord.Embed(title="🎱 Boule magique", color=discord.Color.purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Réponse", value=random.choice(reponses), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="dice", help="Lance un dé. Utilisation : ?dice [faces=6]")
async def dice(ctx, faces: int = 6):
    if faces < 2:
        return await ctx.send("⚠️ Le dé doit avoir au moins 2 faces.")
    resultat = random.randint(1, faces)
    await ctx.send(f"🎲 Tu as obtenu : **{resultat}** (dé à {faces} faces)")


@bot.command(name="coinflip", help="Pile ou face. Utilisation : ?coinflip")
async def coinflip(ctx):
    resultat = random.choice(["Pile 🪙", "Face 🪙"])
    await ctx.send(f"La pièce tombe sur... **{resultat}** !")


@bot.command(name="joke", help="Raconte une blague. Utilisation : ?joke")
async def joke(ctx):
    blagues = [
        "Pourquoi les plongeurs plongent-ils toujours en arrière et jamais en avant ? Parce que sinon ils tombent dans le bateau.",
        "Quel est le sport le plus silencieux ? Le para-chute.",
        "Que dit un escargot quand il croise une limace ? 'Regarde, un nudiste !'",
        "Pourquoi les poissons détestent-ils jouer au tennis ? Parce qu'ils ont peur du filet.",
        "C'est l'histoire d'un mec... elle est belge.",
    ]
    await ctx.send(f"😂 {random.choice(blagues)}")


@bot.command(
    name="avatar", help="Affiche l'avatar d'un membre. Utilisation : ?avatar [@membre]"
)
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(
        title=f"Avatar de {member.display_name}", color=discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="hug", help="Fais un câlin à quelqu'un. Utilisation : ?hug @membre")
async def hug(ctx, member: discord.Member):
    await ctx.send(f"🤗 {ctx.author.mention} fait un gros câlin à {member.mention} !")


@bot.command(
    name="slap",
    help="Mets une baffe à quelqu'un (pour rire). Utilisation : ?slap @membre",
)
async def slap(ctx, member: discord.Member):
    await ctx.send(
        f"👋 {ctx.author.mention} met une énorme claque à {member.mention} !"
    )


@bot.command(name="rate", help="Note quelque chose sur 10. Utilisation : ?rate <texte>")
async def rate(ctx, *, texte: str):
    note = random.randint(0, 10)
    await ctx.send(f"📊 Je donne à **{texte}** une note de **{note}/10**")


# ===========================================================
# LANCEMENT DU BOT
# ===========================================================
if __name__ == "__main__":
    TOKEN = "VOTRE_TOKEN_DISCORD_ICI"  # <-- Mettez votre vrai Token Discord ici
    bot.run(
        "p3eLBRKuMub1GAhKYOzsueyh9r+LlVo+mkaK9SowEUCS4KOjii/DzXPC3AiaecNFc/pP4Sw7TTk0/Sw2vrNTkw=="
    )
