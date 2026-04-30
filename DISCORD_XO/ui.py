import discord
from discord.ui import View, Button

class MenuView(View):
    def __init__(self, gm):
        super().__init__(timeout=None)
        self.gm = gm

    @discord.ui.button(label="🏆 Лидеры", style=discord.ButtonStyle.primary)
    async def leaders(self, interaction: discord.Interaction, button: Button):
        from main import db
        top = await db.get_top(10)
        desc = "\n".join(f"`{i}.` <@{uid}> — {w} побед" for i, (uid, w, _) in enumerate(top, 1))
        embed = discord.Embed(title="🏆 Таблица лидеров", description=desc or "Пока пусто", color=0xFFD700)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎮 Играть", style=discord.ButtonStyle.success)
    async def play(self, interaction: discord.Interaction, button: Button):
        status = await self.gm.add_to_queue(interaction.user.id)
        if "начинается" in status:
            # игра стартовала – отправляем в канал поле с кнопками
            await interaction.response.send_message(status)
            gid = self.gm.player_game[interaction.user.id]
            game = self.gm.games[gid]
            view = GameView(game, self.gm)
            embed = discord.Embed(title="🧮 Тетрадь", description=game.render_board(), color=0xADD8E6)
            embed.add_field(name="Ходит", value=f"<@{game.turn}>")
            await interaction.channel.send(embed=embed, view=view)
        else:
            await interaction.response.send_message(status, ephemeral=True)

    @discord.ui.button(label="❓ Правила", style=discord.ButtonStyle.secondary)
    async def rules(self, interaction: discord.Interaction, button: Button):
        text = ("**Правила**\n• Поле 8×8\n• У каждого своя фигура: 🔴🔺🟩🔹\n"
                "• Ходите по очереди, выбирая клетку кнопками\n"
                "• Победит тот, кто первым заполнит строку, столбец или диагональ")
        embed = discord.Embed(title="📖 Правила", description=text, color=0xADD8E6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GameView(View):
    def __init__(self, game, gm):
        super().__init__(timeout=300)
        self.game = game
        self.gm = gm
        self.selected_col = None
        # кнопки столбцов A-H
        for col in ["A","B","C","D","E","F","G","H"]:
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self.col_callback(col)
            self.add_item(btn)

    def col_callback(self, col):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.turn:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            self.selected_col = col
            # добавляем кнопки строк, если ещё не добавлены
            if len(self.children) < 16:
                for r in range(1,9):
                    btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=1)
                    btn.callback = self.row_callback(r)
                    self.add_item(btn)
            embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
            embed.set_footer(text=f"Выбран столбец {col}. Выберите строку.")
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def row_callback(self, row):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.turn:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            if self.selected_col is None:
                return await interaction.response.send_message("Сначала выберите столбец", ephemeral=True)
            coord = f"{self.selected_col}{row}"
            self.selected_col = None
            result, game = await self.gm.make_move(interaction.user.id, coord)
            if game and game.winner:
                embed = discord.Embed(title="Игра окончена!", description=game.render_board(), color=0xFFD700)
                embed.add_field(name="Победитель", value=f"<@{game.winner}>")
                await interaction.response.edit_message(embed=embed, view=None)
                self.stop()
            else:
                embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
                embed.add_field(name="Ходит", value=f"<@{self.game.turn}>")
                await interaction.response.edit_message(content=result, embed=embed, view=self)
        return callback