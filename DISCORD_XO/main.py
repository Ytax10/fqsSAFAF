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
    # Сразу откладываем ответ, чтобы избежать таймаута
    await interaction.response.defer(ephemeral=False)
    try:
        embed = discord.Embed(
            title="🧮 Тетрадь по математике",
            description="**Выберите действие:**",
            color=0xADD8E6
        )
        view = MenuView(gm)
        # Используем edit_original_response вместо send_message, так как мы уже defer()
        await interaction.edit_original_response(embed=embed, view=view)
    except Exception as e:
        print(f"Ошибка в /menu: {traceback.format_exc()}")
        try:
            await interaction.edit_original_response(content="Произошла внутренняя ошибка. Попробуйте позже.")
        except:
            pass

@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов!")
    try:
        await db.connect()
        print("База данных подключена.")
    except Exception as e:
        print(f"Ошибка подключения БД: {traceback.format_exc()}")
    try:
        synced = await tree.sync()
        print(f"Синхронизировано {len(synced)} команд(ы): {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {traceback.format_exc()}")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Ошибка в событии {event}: {traceback.format_exc()}")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Токен не найден")
    bot.run(token)
