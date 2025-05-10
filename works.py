import discord
from discord.ext import commands
from discord.commands import option
import asyncio
import json
import os
import re
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.guild_messages = True
intents.reactions = True
intents.typing = False

bot = commands.Bot(command_prefix="w!", intents=intents)

NEKOTINA_BOT_ID = 429457053791158281
KEYWORDS_PATTERN = r"(\+|\racha|monedas|esfuerzo|experiencia|:xp:|:coins:|completado|:moneybag:)"

server_data = defaultdict(lambda: {
    'allowed_roles': set(),
    'logs_channel': None,
    'work_logs_channel': None,
    'works': {},
})

# ----------- GUARDAR / CARGAR -----------

def save_data():
    with open('data.json', 'w') as f:
        json.dump(server_data, f, indent=4, default=list)

def load_data():
    global server_data
    if os.path.exists('data.json'):
        with open('data.json', 'r') as f:
            raw = json.load(f)
            for guild_id, data in raw.items():
                server_data[int(guild_id)] = {
                    'allowed_roles': set(data.get('allowed_roles', [])),
                    'logs_channel': data.get('logs_channel'),
                    'work_logs_channel': data.get('work_logs_channel'),
                    'works': data.get('works', {}),
                }

load_data()

# ----------- LOG GENERAL -----------

async def log_general(guild_id, content, channel=None):
    logs_id = server_data[guild_id].get('logs_channel')
    if logs_id:
        log_channel = bot.get_channel(logs_id)
        if log_channel:
            embed = discord.Embed(description=content, color=discord.Color.blue())
            if channel:
                embed.set_footer(text=f"Canal: {channel.name}")
            await log_channel.send(embed=embed)

# ----------- EVENTOS -----------

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión.')

@bot.event
async def on_message(message):
    if message.author.bot and message.author.id != NEKOTINA_BOT_ID:
        return

    await bot.process_commands(message)

    if message.content.startswith(bot.command_prefix):
        guild_id = message.guild.id
        await log_general(guild_id, f"{message.author.mention} usó el comando `{message.content}`.", message.channel)

    guild_id = message.guild.id

    # Cuando NEKOTINA responde en cualquier canal
    if message.author.id == NEKOTINA_BOT_ID:
        channel_id = message.channel.id
        channel_data = server_data[guild_id]['channels'].get(channel_id)
        if not channel_data:
            return

        if channel_data['active_work']:
            elapsed = asyncio.get_event_loop().time() - channel_data['active_work']
            if elapsed <= 60:
                content_lower = message.content.lower()

                if not content_lower and message.embeds:
                    embed = message.embeds[0]
                    parts = [
                        embed.title or "",
                        embed.description or "",
                    ]
                    if not content_lower and message.embeds:
                        embed = message.embeds[0]
                        parts = [
                            embed.title or "",
                            embed.description or "",
                        ]
                        for field in embed.fields:
                            parts.append(field.name or "")
                            parts.append(field.value or "")
                        content_lower = " ".join(parts).lower()

                if re.search(KEYWORDS_PATTERN, content_lower):
                    owner_id = channel_data.get('owner_id')
                    if not owner_id:
                        return

                    owner = message.guild.get_member(owner_id)
                    if not owner:
                        return

                    channel_data['points'] += 1
                    channel_data['active_work'] = None

                    # ---------- ACTUALIZAR EL RANKING GLOBAL ----------
                    user_id = str(owner.id)
                    if 'works' not in server_data[guild_id]:
                        server_data[guild_id]['works'] = {}

                    if user_id not in server_data[guild_id]['works']:
                        server_data[guild_id]['works'][user_id] = {
                            'count': 0,
                            'last_channel': message.channel.id
                        }

                    server_data[guild_id]['works'][user_id]['count'] += 1
                    server_data[guild_id]['works'][user_id]['last_channel'] = message.channel.id
                    save_data()

                    embed = discord.Embed(
                        title="¡Tarea registrada!",
                        description=f"{owner.mention} ganó 1 punto.\nTotal: {channel_data['points']}",
                        color=discord.Color.orange()
                    )
                    await message.channel.send(embed=embed, delete_after=5)

                    work_logs_id = server_data[guild_id]['work_logs_channel']
                    if work_logs_id:
                        work_channel = bot.get_channel(work_logs_id)
                        if work_channel:
                            await work_channel.send(embed=embed)

    # Cuando el usuario escribe comandos como ".work"
    if message.content.lower() in ['.w', '.work', 'neko work', 'nekowork', '!work', '!w']:
        channel_id = message.channel.id
        if guild_id not in server_data:
            server_data[guild_id] = {'channels': {}, 'work_logs_channel': None}
        if 'channels' not in server_data[guild_id]:
            server_data[guild_id]['channels'] = {}

        if channel_id not in server_data[guild_id]['channels']:
            server_data[guild_id]['channels'][channel_id] = {
                'points': 0,
                'owner_id': None,
                'active_work': None
            }

        server_data[guild_id]['channels'][channel_id]['owner_id'] = message.author.id
        server_data[guild_id]['channels'][channel_id]['active_work'] = asyncio.get_event_loop().time()
        save_data()



# ----------- COMANDOS -----------

@bot.command()
@commands.has_permissions(administrator=True)
async def resetworks(ctx):
    server_data[ctx.guild.id]['works'] = {}
    save_data()
    await ctx.send("Todos los works han sido reseteados.")
    await log_general(ctx.guild.id, f"{ctx.author.mention} reseteó los works.", ctx.channel)

@bot.command()
@commands.has_permissions(administrator=True)
async def logs(ctx):
    server_data[ctx.guild.id]['logs_channel'] = ctx.channel.id
    save_data()
    await ctx.send("Este canal ha sido establecido como canal de logs generales.")

@bot.command()
@commands.has_permissions(administrator=True)
async def logsworks(ctx):
    server_data[ctx.guild.id]['work_logs_channel'] = ctx.channel.id
    save_data()
    await ctx.send("Este canal ha sido establecido como canal de logs de works.")

@bot.command()
@commands.has_permissions(administrator=True)
async def addwork(ctx, member: discord.Member, amount: int = 1):
    guild_id = ctx.guild.id
    user_id = str(member.id)
    works = server_data[guild_id].setdefault('works', {})
    user_data = works.setdefault(user_id, {'count': 0, 'last_channel': ctx.channel.id})
    user_data['count'] += amount
    user_data['last_channel'] = ctx.channel.id
    save_data()
    await ctx.send(f"✅ Se han agregado {amount} work(s) a {member.mention}. Total: {user_data['count']}")

@bot.command()
@commands.has_permissions(administrator=True)
async def delwork(ctx, member: discord.Member, amount: int = 1):
    guild_id = ctx.guild.id
    user_id = str(member.id)
    works = server_data[guild_id].setdefault('works', {})
    user_data = works.setdefault(user_id, {'count': 0, 'last_channel': ctx.channel.id})
    user_data['count'] = max(0, user_data['count'] - amount)
    user_data['last_channel'] = ctx.channel.id
    save_data()
    await ctx.send(f"❌ Se han quitado {amount} work(s) a {member.mention}. Total: {user_data['count']}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setroles(ctx, *roles: discord.Role):
    if not roles:
        await ctx.send("Debes mencionar al menos un rol.")
        return
    server_data[ctx.guild.id]['allowed_roles'] = set(role.id for role in roles)
    save_data()
    await ctx.send("Roles permitidos actualizados.")

# ----------- COMANDOS SLASH -----------

@bot.slash_command(name="resetworks", description="Resetea todos los works del servidor.")
@commands.has_permissions(administrator=True)
async def resetworks_slash(ctx: discord.ApplicationContext):
    server_data[ctx.guild.id]['works'] = {}
    save_data()
    await ctx.respond("Todos los works han sido reseteados.")
    await log_general(ctx.guild.id, f"{ctx.author.mention} reseteó los works.", ctx.channel)

@bot.slash_command(name="logs", description="Establece este canal como canal de logs generales.")
@commands.has_permissions(administrator=True)
async def logs_slash(ctx: discord.ApplicationContext):
    server_data[ctx.guild.id]['logs_channel'] = ctx.channel.id
    save_data()
    await ctx.respond("Este canal ha sido establecido como canal de logs generales.")

@bot.slash_command(name="logsworks", description="Establece este canal como canal de logs de works.")
@commands.has_permissions(administrator=True)
async def logsworks_slash(ctx: discord.ApplicationContext):
    server_data[ctx.guild.id]['work_logs_channel'] = ctx.channel.id
    save_data()
    await ctx.respond("Este canal ha sido establecido como canal de logs de works.")

@bot.slash_command(name="addwork", description="Agrega works manualmente a un usuario.")
@option("usuario", discord.Member)
@option("cantidad", int, default=1)
@commands.has_permissions(administrator=True)
async def addwork_slash(ctx: discord.ApplicationContext, usuario: discord.Member, cantidad: int):
    guild_id = ctx.guild.id
    user_id = str(usuario.id)
    works = server_data[guild_id].setdefault('works', {})
    user_data = works.setdefault(user_id, {'count': 0, 'last_channel': ctx.channel.id})
    user_data['count'] += cantidad
    user_data['last_channel'] = ctx.channel.id
    save_data()
    await ctx.respond(f"✅ Se han agregado {cantidad} work(s) a {usuario.mention}. Total: {user_data['count']}")

@bot.slash_command(name="delwork", description="Quita works manualmente a un usuario.")
@option("usuario", discord.Member)
@option("cantidad", int, default=1)
@commands.has_permissions(administrator=True)
async def delwork_slash(ctx: discord.ApplicationContext, usuario: discord.Member, cantidad: int):
    guild_id = ctx.guild.id
    user_id = str(usuario.id)
    works = server_data[guild_id].setdefault('works', {})
    user_data = works.setdefault(user_id, {'count': 0, 'last_channel': ctx.channel.id})
    user_data['count'] = max(0, user_data['count'] - cantidad)
    user_data['last_channel'] = ctx.channel.id
    save_data()
    await ctx.respond(f"❌ Se han quitado {cantidad} work(s) a {usuario.mention}. Total: {user_data['count']}")

@bot.slash_command(name="setroles", description="Define los roles que pueden usar los comandos del bot.")
@commands.has_permissions(administrator=True)
async def set_roles(ctx: discord.ApplicationContext, role: discord.Role):
    guild_id = ctx.guild.id
    roles = server_data[guild_id].setdefault('allowed_roles', set())
    roles.add(role.id)
    server_data[guild_id]['allowed_roles'] = roles
    save_data()
    await ctx.respond(f"✅ Rol permitido actualizado: {role.mention}")

# ---------------- BOTONES ----------------

class RankingView(discord.ui.View):
    def __init__(self, ctx, embeds):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.embeds = embeds
        self.index = 0

    async def update(self, interaction):
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label='⏮️', style=discord.ButtonStyle.gray)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("No puedes usar estos botones.", ephemeral=True)
        self.index = (self.index - 1) % len(self.embeds)
        await self.update(interaction)

    @discord.ui.button(label='⏭️', style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("No puedes usar estos botones.", ephemeral=True)
        self.index = (self.index + 1) % len(self.embeds)
        await self.update(interaction)

# ---------------- FUNCIÓN DE VALIDACIÓN ----------------/

def tiene_permiso(ctx):
    if ctx.author.guild_permissions.administrator:
        return True
    roles_permitidos = server_data[ctx.guild.id]['allowed_roles']
    return any(role.id in roles_permitidos for role in ctx.author.roles)

# ---------------- COMANDO RANKING ----------------

@bot.command()
async def ranking(ctx):
    if not tiene_permiso(ctx):
        return await ctx.send("❌ No tienes permiso para usar este comando.")

    guild_id = ctx.guild.id
    work_data = server_data[guild_id].get('works', {})

    if not work_data:
        return await ctx.send("No hay registros de works todavía.")

    sorted_data = sorted(work_data.items(), key=lambda x: x[1].get('count', 0), reverse=True)

    embeds = []
    per_page = 5
    for i in range(0, len(sorted_data), per_page):
        embed = discord.Embed(
            title="🏆 Ranking de Works",
            description=f"Página {len(embeds) + 1}/{(len(sorted_data) + per_page - 1) // per_page}",
            color=discord.Color.green()
        )
        for idx, (user_id, data) in enumerate(sorted_data[i:i + per_page], start=1):
            user = ctx.guild.get_member(int(user_id))
            canal = ctx.guild.get_channel(data['last_channel']) if data.get('last_channel') else None
            nombre = user.display_name if user else f"`Usuario desconocido` ({user_id})"
            canal_texto = f" en {canal.mention}" if canal else ""
            embed.add_field(
                name=f"{idx + i}. {nombre}",
                value=f"Works: {data['count']}{canal_texto}",
                inline=False
            )
        embeds.append(embed)

    view = RankingView(ctx, embeds)
    await ctx.send(embed=embeds[0], view=view)


# ---------------- SLASH COMMAND ----------------

@bot.slash_command(name="ranking", description="Muestra el ranking de works con botones.")
async def slash_ranking(ctx):
    if not ctx.author.guild_permissions.administrator:
        roles_permitidos = server_data[ctx.guild.id]['allowed_roles']
        if not any(role.id in roles_permitidos for role in ctx.author.roles):
            return await ctx.respond("❌ No tienes permiso para usar este comando.", ephemeral=True)

    guild_id = ctx.guild.id
    work_data = server_data[guild_id].get('works', {})

    if not work_data:
        return await ctx.respond("No hay registros de works todavía.")

    sorted_data = sorted(work_data.items(), key=lambda x: x[1].get('count', 0), reverse=True)

    embeds = []
    per_page = 5
    for i in range(0, len(sorted_data), per_page):
        embed = discord.Embed(
            title="🏆 Ranking de Works",
            description=f"Página {len(embeds) + 1}/{(len(sorted_data) + per_page - 1) // per_page}",
            color=discord.Color.green()
        )
        for idx, (user_id, data) in enumerate(sorted_data[i:i + per_page], start=1):
            user = ctx.guild.get_member(int(user_id))
            canal = ctx.guild.get_channel(data['last_channel']) if data.get('last_channel') else None
            nombre = user.display_name if user else f"`Usuario desconocido` ({user_id})"
            canal_texto = f" en {canal.mention}" if canal else ""
            embed.add_field(
                name=f"{idx + i}. {nombre}",
                value=f"Works: {data['count']}{canal_texto}",
                inline=False
            )
        embeds.append(embed)

    view = RankingView(ctx, embeds)
    await ctx.respond(embed=embeds[0], view=view)



if __name__ == "__main__":
    bot.run(TOKEN)
