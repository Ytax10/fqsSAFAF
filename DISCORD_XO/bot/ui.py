import discord
from discord.ui import View, Button

class MenuView(View):
    def __init__(self, game_manager=None):
        super().__init__(timeout=None)
        self.gm = game_manager

    @discord.ui.button(label="🏆 Таблица лидеров", style=discord.ButtonStyle.primary, row=0)
    async def leaderboard_button(self, interaction: discord.Interaction, button: Button):
        from main import db
        top = await db.get_top(10)
        desc = ""
        for idx, (uid, wins, rating) in enumerate(top, start=1):
            user = interaction.client.get_user(uid) or await interaction.client.fetch_user(uid)
            name = user.name if user else f"ID {uid}"
            desc += f"`{idx}.` **{name}** — {wins} побед\n"
        embed = discord.Embed(title="🏆 Лидеры", description=desc or "Пусто", color=0xFFD700)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎮 Играть", style=discord.ButtonStyle.success, row=0)
    async def play_button(self, interaction: discord.Interaction, button: Button):
        # Создаём приглашение в Activity
        app_id = os.getenv("DISCORD_APP_ID")
        if not app_id:
            await interaction.response.send_message("❌ Не задан APP_ID", ephemeral=True)
            return
        # Discord Activity invite ссылка
        invite_url = f"https://discord.com/activities/{app_id}?channel={interaction.channel_id}"
        embed = discord.Embed(
            title="🎮 Игра «Тетрадь»",
            description="Нажмите кнопку ниже, чтобы запустить игру в голосовом канале!",
            color=0xADD8E6
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Запустить игру", url=invite_url))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="❓ Правила", style=discord.ButtonStyle.secondary, row=0)
    async def rules_button(self, interaction: discord.Interaction, button: Button):
        rules = (
            "**Правила игры «Тетрадь»**\n"
            "• Поле 8×8, ваша фигура – случайная из 🔴🔺🟩🔹.\n"
            "• Ходите по очереди, нажимая на клетку.\n"
            "• Победит тот, кто первым заполнит всю строку, столбец или диагональ своей фигурой.\n"
            "• Игра запускается в голосовом канале."
        )
        await interaction.response.send_message(embed=discord.Embed(title="📖 Правила", description=rules, color=0xADD8E6), ephemeral=True)