import discord
from discord import app_commands
import os
import asyncio
from database import Database
from game import GameManager
from ui import MenuView

db = Database()
game_manager = GameManager(db)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@tree.command(name="menu", description="Открыть главное меню игры")
async def menu_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🧮 Тетрадь по математике — мультиплеер",
        description="**Добро пожаловать!**\nЗдесь можно посмотреть лидеров, запустить игру или почитать правила.",
        color=0xADD8E6
    )
    embed.set_image(url="https://i.imgur.com/MPk8qLm.png")  # заглушка тетрадного листа
    view = MenuView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    await db.connect()
    await tree.sync()
    print(f"Бот {bot.user} готов!")

@bot.event
async def on_close():
    await db.close()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Токен не найден")
    bot.run(token)