import os
import random
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View
from PIL import Image, ImageDraw, ImageFont
import io

# --- CONFIG ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="?", intents=intents)

# --- BDD MÉMOIRE (Remplace par une vraie BDD plus tard) ---
user_xp = {}
server_configs = {
    "logs": {"mod": None, "voice": None, "role": None, "ticket": None}
}

# --- LOGIQUE NIVEAU & XP ---
@bot.event
async def on_message(message):
    if message.author.bot: return
    uid = message.author.id
    if uid not in user_xp: user_xp[uid] = {"xp": 0, "level": 1}
    
    # XP ralenti : gain 5-10 par message, palier 300 par niveau
    user_xp[uid]["xp"] += random.randint(5, 10)
    if user_xp[uid]["xp"] >= (user_xp[uid]["level"] * 300):
        user_xp[uid]["level"] += 1
        await message.channel.send(f"🎉 GG {message.author.mention}, tu passes niveau {user_xp[uid]['level']} !")
    await bot.process_commands(message)

# --- COMMANDE LEVEL (Image) ---
@bot.command(name="level")
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    data = user_xp.get(member.id, {"xp": 0, "level": 1})
    
    # Correction : pas de paramètre 'format' ici
    card = Image.new("RGBA", (900, 300), (32, 34, 37, 255))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([20, 20, 880, 280], radius=20, fill=(47, 49, 54, 255))
    draw.rounded_rectangle([40, 160, 860, 250], radius=10, fill=(54, 57, 63, 255))
    
    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    await ctx.send(file=discord.File(buffer, "rank.png"))

# --- LOGS VOCAL & RÔLE ---
@bot.event
async def on_voice_state_update(member, before, after):
    log_id = server_configs["logs"]["voice"]
    if log_id and before.channel != after.channel:
        chan = member.guild.get_channel(log_id)
        if chan:
            action = f"quitté {before.channel.name}" if not after.channel else f"rejoint {after.channel.name}"
            await chan.send(f"🔊 {member.name} a {action}.")

@bot.event
async def on_member_update(before, after):
    log_id = server_configs["logs"]["role"]
    if log_id and before.roles != after.roles:
        chan = before.guild.get_channel(log_id)
        if chan:
            await chan.send(f"👑 Rôles modifiés pour {after.name}.")

# --- LOGS TICKETS AVEC TRANSCRIPT ---
class TicketCloseView(View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel
    
    @discord.ui.button(label="Fermer et Archiver", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: Button):
        messages = [f"{m.author}: {m.content}" async for m in self.channel.history(limit=None, oldest_first=True)]
        transcript = "\n".join(messages)
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{self.channel.name}.txt")
        
        log_id = server_configs["logs"]["ticket"]
        if log_id:
            log_chan = interaction.guild.get_channel(log_id)
            if log_chan:
                embed = discord.Embed(title="Ticket Fermé", color=discord.Color.red())
                embed.add_field(name="Salon", value=self.channel.name)
                embed.add_field(name="Messages", value=str(len(messages)))
                await log_chan.send(embed=embed, file=file)
        await self.channel.delete()

# --- CONFIG COMMANDS ---
@bot.command()
@commands.has_permissions(administrator=True)
async def voicelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["voice"] = channel.id
    await ctx.send(f"✅ Logs vocaux : {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def rolelog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["role"] = channel.id
    await ctx.send(f"✅ Logs rôles : {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketlog(ctx, channel: discord.TextChannel):
    server_configs["logs"]["ticket"] = channel.id
    await ctx.send(f"✅ Logs tickets : {channel.mention}")

# (Ajoute tes autres commandes de config de la même façon)

bot.run(os.environ.get("DISCORD_TOKEN"))
