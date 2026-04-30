import discord
from discord.ui import View, Button

class MenuView(View):
    def __init__(self, gm):
        super().__init__(timeout=None)
        self.gm = gm

    @discord.ui.button(label="🏆 Лидеры", style=discord.ButtonStyle.primary, row=0)
    async def leaders(self, interaction: discord.Interaction, button: Button):
        from main import db
        top = await db.get_top(10)
        desc = "\n".join(f"`{i}.` <@{uid}> — {w} побед" for i, (uid, w, _) in enumerate(top, 1))
        embed = discord.Embed(title="🏆 Таблица лидеров", description=desc or "Пока пусто", color=0xFFD700)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎮 Играть", style=discord.ButtonStyle.success, row=0)
    async def play(self, interaction: discord.Interaction, button: Button):
        status = await self.gm.add_to_queue(interaction.user.id)
        if "начинается" in status:
            await interaction.response.send_message(status)
            gid = self.gm.player_game[interaction.user.id]
            game = self.gm.games[gid]
            # Отправляем личные сообщения обоим игрокам
            await self._send_dm_to_players(game)
        else:
            await interaction.response.send_message(status, ephemeral=True)

    async def _send_dm_to_players(self, game):
        """Отправляет доску и кнопки в ЛС каждому игроку"""
        for pid in game.players:
            user = await self._fetch_user(pid)
            if user is None:
                # Если не можем найти пользователя, пропускаем (можно уведомить в канал)
                continue
            try:
                view = GameView(game, self.gm, pid)
                embed = self._make_embed(game, pid)
                msg = await user.send(embed=embed, view=view)
                # Сохраняем id сообщения, чтобы обновлять позже
                game.player_messages[pid] = msg.id
            except discord.Forbidden:
                # ЛС закрыты, сообщаем в канал (но канал не сохраняем, можно передать как аргумент)
                # Вместо сложностей пока просто пропускаем, игру можно будет продолжить через другого игрока
                pass

    async def _fetch_user(self, uid):
        from main import bot
        user = bot.get_user(uid)
        if user is None:
            try:
                user = await bot.fetch_user(uid)
            except:
                pass
        return user

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
        text = ("**Правила**\n• Поле 8×8\n• У каждого своя фигура: 🔴🔺🟩🔹\n"
                "• Ходите по очереди, выбирая клетку кнопками\n"
                "• Победит тот, кто первым заполнит строку, столбец или диагональ")
        embed = discord.Embed(title="📖 Правила", description=text, color=0xADD8E6)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GameView(View):
    """View для конкретного игрока, но при ходе обновляет сообщения обоих"""
    def __init__(self, game, gm, viewer_id):
        super().__init__(timeout=600)  # 10 минут на игру
        self.game = game
        self.gm = gm
        self.viewer_id = viewer_id   # тот, кто видит эту кнопку
        self.selected_col = None

        # Столбцы A-D (ряд 0)
        for col in ["A", "B", "C", "D"]:
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self.col_callback(col)
            self.add_item(btn)
        # Столбцы E-H (ряд 1)
        for col in ["E", "F", "G", "H"]:
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=1)
            btn.callback = self.col_callback(col)
            self.add_item(btn)
        # Строки 1-4 (ряд 2)
        for r in range(1, 5):
            btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=2)
            btn.callback = self.row_callback(r)
            self.add_item(btn)
        # Строки 5-8 (ряд 3)
        for r in range(5, 9):
            btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=3)
            btn.callback = self.row_callback(r)
            self.add_item(btn)

    def col_callback(self, col):
        async def callback(interaction: discord.Interaction):
            # Проверяем, что нажал тот, кто должен ходить, и что это его View
            if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            self.selected_col = col
            embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
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
            # Обновляем сообщения обоих игроков
            await self._update_both_messages()
            # Если игра окончена, удаляем кнопки
            if game and game.winner:
                # Останавливаем все View (убираем кнопки)
                self.stop()
                for pid in game.players:
                    if pid != interaction.user.id:
                        # Остановим View у соперника, если он ещё активен
                        # Но проще просто отправить финальное сообщение без view
                        pass
                # Обновим оба сообщения без view
                await self._update_both_messages(final=True)
            else:
                # Просто подтверждаем ход
                await interaction.response.edit_message(content=result, embed=self._make_embed(), view=self)
        return callback

    async def _update_both_messages(self, final=False):
        """Обновляет сообщения в ЛС у обоих игроков актуальным состоянием"""
        from main import bot
        for pid in self.game.players:
            msg_id = self.game.player_messages.get(pid)
            if not msg_id:
                continue
            user = await self._fetch_user(pid)
            if not user:
                continue
            try:
                channel = user.dm_channel
                if not channel:
                    channel = await user.create_dm()
                msg = await channel.fetch_message(msg_id)
                embed = self._make_embed()
                if final:
                    await msg.edit(embed=embed, view=None)
                else:
                    # View передаём только тому, чей сейчас ход? Нет, кнопки должны быть видны тому, чей ход, а у другого убираем.
                    # Упростим: обновим View только тому, чей сейчас ход, а другому отправим без View.
                    if pid == self.game.turn:
                        await msg.edit(embed=embed, view=self)
                    else:
                        await msg.edit(embed=embed, view=None)
            except:
                pass

    def _make_embed(self):
        embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
        if self.game.winner:
            embed.add_field(name="Победитель", value=f"<@{self.game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{self.game.turn}>")
        return embed

    async def _fetch_user(self, uid):
        from main import bot
        user = bot.get_user(uid)
        if not user:
            try:
                user = await bot.fetch_user(uid)
            except:
                pass
        return user