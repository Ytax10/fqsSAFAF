import discord
from discord.ui import View, Button
import traceback

class MenuView(View):
    def __init__(self, gm):
        super().__init__(timeout=None)
        self.gm = gm

    @discord.ui.button(label="🏆 Лидеры", style=discord.ButtonStyle.primary, row=0)
    async def leaders(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)  # чтобы избежать таймаута
        from main import db
        top = await db.get_top(10)
        desc = "\n".join(f"`{i}.` <@{uid}> — {w} побед" for i, (uid, w, _) in enumerate(top, 1))
        embed = discord.Embed(title="🏆 Таблица лидеров", description=desc or "Пока пусто", color=0xFFD700)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="🎮 Играть", style=discord.ButtonStyle.success, row=0)
    async def play(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=False)  # сразу откладываем ответ
        status = await self.gm.add_to_queue(interaction.user.id)
        if "начинается" in status:
            await interaction.edit_original_response(content=status)
            gid = self.gm.player_game[interaction.user.id]
            game = self.gm.games[gid]
            # Отправляем игру в ЛС обоим игрокам (может занять время)
            await self._send_dm_to_players(game)
        else:
            await interaction.edit_original_response(content=status)

    async def _send_dm_to_players(self, game):
        from main import bot
        for pid in list(game.players):
            user = bot.get_user(pid) or await bot.fetch_user(pid)
            if not user:
                print(f"❌ Не удалось найти пользователя {pid}")
                continue
            try:
                if user.dm_channel is None:
                    await user.create_dm()
                dm_channel = user.dm_channel
                view = GameView(game, self.gm, pid)
                embed = self._make_embed(game, pid)
                msg = await dm_channel.send(embed=embed, view=view)
                game.player_messages[pid] = msg.id
                print(f"✅ Игровое сообщение отправлено {user.name} (ID {pid})")
            except discord.Forbidden:
                print(f"🚫 Нет доступа к ЛС пользователя {pid}")
            except Exception as e:
                print(f"⚠️ Ошибка отправки ЛС для {pid}: {e}")

    def _make_embed(self, game, pid):
        embed = discord.Embed(title="🧮 Тетрадь", description=game.render_board(), color=0xADD8E6)
        embed.add_field(name="Ваша фигура", value=game.piece_of[pid])
        if game.winner:
            embed.add_field(name="Победитель", value=f"<@{game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{game.turn}>")
        return embed

    @discord.ui.button(label="❓ Правила", style=discord.ButtonStyle.secondary, row=0)
    async def rules(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        text = ("**Правила**\n• Поле 8×8\n• У каждого своя фигура: 🔴🔺🟩🔹\n"
                "• Ходите по очереди, выбирая клетку кнопками\n"
                "• Победит тот, кто первым заполнит строку, столбец или диагональ")
        embed = discord.Embed(title="📖 Правила", description=text, color=0xADD8E6)
        await interaction.edit_original_response(embed=embed)


class GameView(View):
    def __init__(self, game, gm, viewer_id):
        super().__init__(timeout=600)
        self.game = game
        self.gm = gm
        self.viewer_id = viewer_id
        self.selected_col = None

        # Столбцы A-D
        for col in ["A", "B", "C", "D"]:
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self.col_callback(col)
            self.add_item(btn)
        # Столбцы E-H
        for col in ["E", "F", "G", "H"]:
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=1)
            btn.callback = self.col_callback(col)
            self.add_item(btn)
        # Строки 1-4
        for r in range(1, 5):
            btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=2)
            btn.callback = self.row_callback(r)
            self.add_item(btn)
        # Строки 5-8
        for r in range(5, 9):
            btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=3)
            btn.callback = self.row_callback(r)
            self.add_item(btn)

    def col_callback(self, col):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            self.selected_col = col
            embed = self._make_embed()
            embed.set_footer(text=f"Выбран столбец {col}. Выберите строку.")
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def row_callback(self, row):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            if self.selected_col is None:
                return await interaction.response.send_message("Сначала выберите столбец", ephemeral=True)
            coord = f"{self.selected_col}{row}"
            self.selected_col = None
            # Делаем ход
            result, game = await self.gm.make_move(interaction.user.id, coord)
            # Обновляем сообщения у обоих игроков
            await self._update_both_messages()
            if game and game.winner:
                self.stop()
                await interaction.response.edit_message(content="Игра окончена!", embed=self._make_embed(), view=None)
            else:
                await interaction.response.edit_message(content=result, embed=self._make_embed(), view=self)
        return callback

    async def _update_both_messages(self):
        from main import bot
        for pid in self.game.players:
            msg_id = self.game.player_messages.get(pid)
            if not msg_id:
                continue
            user = bot.get_user(pid) or await bot.fetch_user(pid)
            if not user:
                continue
            try:
                if user.dm_channel is None:
                    await user.create_dm()
                msg = await user.dm_channel.fetch_message(msg_id)
                embed = self._make_embed()
                if self.game.winner:
                    await msg.edit(embed=embed, view=None)
                else:
                    if pid == self.game.turn:
                        await msg.edit(embed=embed, view=self)
                    else:
                        await msg.edit(embed=embed, view=None)
            except Exception as e:
                print(f"Ошибка обновления сообщения для {pid}: {e}")

    def _make_embed(self):
        embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
        if self.game.winner:
            embed.add_field(name="Победитель", value=f"<@{self.game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{self.game.turn}>")
        return embed
