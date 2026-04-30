import discord
from discord.ui import View, Select, Button
import traceback

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
        guild = interaction.guild
        status = await self.gm.add_to_queue(interaction.user.id, guild)
        if "начинается" in status:
            await interaction.response.send_message(status)
            gid = self.gm.player_game[interaction.user.id]
            game = self.gm.games[gid]
            await self._send_dm_to_players(game)
        else:
            await interaction.response.send_message(status, ephemeral=True)

    async def _send_dm_to_players(self, game):
        guild = game.guild
        for pid in list(game.players):
            print(f"[INFO] Отправляю ЛС для {pid}")
            member = guild.get_member(pid) or await self._fetch_member(guild, pid)
            if not member:
                print(f"[ERROR] Участник {pid} не найден")
                continue
            try:
                view = GameView(game, self.gm, pid) if pid == game.turn else None
                embed = self._make_embed(game, pid)
                msg = await member.send(embed=embed, view=view)
                game.player_messages[pid] = msg.id
                print(f"[SUCCESS] Сообщение отправлено {member.name} (msg id {msg.id})")
            except discord.Forbidden:
                print(f"[BLOCKED] ЛС закрыты у {member.name}")
            except Exception:
                print(f"[EXCEPTION] Ошибка отправки ЛС для {member.name}:\n{traceback.format_exc()}")

    async def _fetch_member(self, guild, pid):
        member = guild.get_member(pid)
        if member is None:
            try:
                member = await guild.fetch_member(pid)
            except Exception:
                pass
        return member

    def _make_embed(self, game, pid):
        embed = discord.Embed(title="🧮 Тетрадь (16×16)", description=game.render_board(), color=0xADD8E6)
        embed.add_field(name="Ваша фигура", value=game.piece_of[pid])
        if game.winner:
            embed.add_field(name="Победитель", value=f"<@{game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{game.turn}>")
        return embed

    @discord.ui.button(label="❓ Правила", style=discord.ButtonStyle.secondary, row=0)
    async def rules(self, interaction: discord.Interaction, button: Button):
        text = ("**Правила**\n• Поле 16×16\n• У каждого своя фигура: 🔴🔺🟩🔹\n"
                "• Ходите по очереди, выбирая клетку в выпадающих меню\n"
                "• Победит тот, кто первым заполнит строку, столбец или диагональ")
        embed = discord.Embed(title="📖 Правила", description=text, color=0xADD8E6)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GameView(View):
    def __init__(self, game, gm, viewer_id):
        super().__init__(timeout=600)
        self.game = game
        self.gm = gm
        self.viewer_id = viewer_id
        self.selected_col = None
        self.selected_row = None

        # Выпадающий список для столбца
        col_select = Select(
            placeholder="Выберите столбец (A–P)",
            options=[discord.SelectOption(label=col, value=col) for col in COLS[:16]],
            row=0
        )
        col_select.callback = self.col_select_callback
        self.add_item(col_select)

        # Выпадающий список для строки
        row_select = Select(
            placeholder="Выберите строку (1–16)",
            options=[discord.SelectOption(label=str(r), value=str(r)) for r in range(1, 17)],
            row=1
        )
        row_select.callback = self.row_select_callback
        self.add_item(row_select)

    async def col_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
            return await interaction.response.send_message("Не ваш ход", ephemeral=True)
        self.selected_col = interaction.data["values"][0]
        await interaction.response.defer()
        # Если строка уже выбрана, совершаем ход
        if self.selected_row is not None:
            await self._try_move(interaction)
        else:
            # Просто обновим сообщение с подсказкой
            embed = self._make_embed()
            embed.set_footer(text=f"Выбран столбец {self.selected_col}. Выберите строку.")
            await interaction.edit_original_response(embed=embed, view=self)

    async def row_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
            return await interaction.response.send_message("Не ваш ход", ephemeral=True)
        self.selected_row = int(interaction.data["values"][0])
        await interaction.response.defer()
        if self.selected_col is not None:
            await self._try_move(interaction)
        else:
            embed = self._make_embed()
            embed.set_footer(text=f"Выбрана строка {self.selected_row}. Выберите столбец.")
            await interaction.edit_original_response(embed=embed, view=self)

    async def _try_move(self, interaction: discord.Interaction):
        coord = f"{self.selected_col}{self.selected_row}"
        # Сбрасываем выбранные значения для следующего хода
        self.selected_col = None
        self.selected_row = None
        result, game = await self.gm.make_move(interaction.user.id, coord)
        # Обновляем оба сообщения
        await self._update_both_messages()
        if game and game.winner:
            self.gm.end_game(self.game.id)
            await interaction.edit_original_response(content="Игра окончена!", embed=self._make_embed(), view=None)
            self.stop()
        else:
            await interaction.edit_original_response(content=result, embed=self._make_embed(), view=self)

    async def on_timeout(self):
        print(f"Игра #{self.game.id} прервана по таймауту.")
        self.gm.end_game(self.game.id)

    async def _update_both_messages(self):
        guild = self.game.guild
        for pid in self.game.players:
            msg_id = self.game.player_messages.get(pid)
            if not msg_id:
                continue
            member = guild.get_member(pid)
            if not member:
                member = await self._fetch_member(guild, pid)
            if not member:
                continue
            try:
                msg = await member.fetch_message(msg_id)
                embed = self._make_embed()
                if self.game.winner:
                    await msg.edit(embed=embed, view=None)
                else:
                    if pid == self.game.turn:
                        new_view = GameView(self.game, self.gm, pid)
                        await msg.edit(embed=embed, view=new_view)
                    else:
                        await msg.edit(embed=embed, view=None)
            except Exception:
                print(f"Ошибка обновления сообщения для {pid}:\n{traceback.format_exc()}")

    async def _fetch_member(self, guild, pid):
        member = guild.get_member(pid)
        if member is None:
            try:
                member = await guild.fetch_member(pid)
            except Exception:
                pass
        return member

    def _make_embed(self):
        embed = discord.Embed(title="🧮 Тетрадь (16×16)", description=self.game.render_board(), color=0xADD8E6)
        if self.game.winner:
            embed.add_field(name="Победитель", value=f"<@{self.game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{self.game.turn}>")
        return embed
