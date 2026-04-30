import discord
from discord import app_commands
import os
import traceback
from database import Database
from game import GameManager
from ui import MenuView

db = Database()
gm = GameManager(db)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@tree.command(name="menu", description="Главное меню игры Тетрадь")
async def menu(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🧮 Тетрадь по математике",
        description="**Выберите действие:**",
        color=0xADD8E6
    )
    view = MenuView(gm)
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await db.connect()
    await tree.sync()
    print(f"Бот {bot.user} готов!")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Токен не найден")
    bot.run(token)
