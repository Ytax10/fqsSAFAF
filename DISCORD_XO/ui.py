import discord
from discord.ui import View, Button
import traceback

class GameSizeView(View):
    """Меню выбора количества игроков."""
    def __init__(self, gm, guild):
        super().__init__(timeout=60)
        self.gm = gm
        self.guild = guild

    @discord.ui.button(label="2 игрока", style=discord.ButtonStyle.primary)
    async def two_players(self, interaction: discord.Interaction, button: Button):
        await self._start_search(interaction, 2)

    @discord.ui.button(label="3 игрока", style=discord.ButtonStyle.primary)
    async def three_players(self, interaction: discord.Interaction, button: Button):
        await self._start_search(interaction, 3)

    @discord.ui.button(label="4 игрока", style=discord.ButtonStyle.primary)
    async def four_players(self, interaction: discord.Interaction, button: Button):
        await self._start_search(interaction, 4)

    async def _start_search(self, interaction, size):
        user_id = interaction.user.id
        status = await self.gm.add_to_queue(user_id, self.guild, size)
        if "начинается" in status:
            gid = self.gm.player_game[user_id]
            game = self.gm.games[gid]
            await interaction.response.edit_message(content=status, view=None)
            await self._send_dm_to_players(game)
        else:
            # Ожидание – обновляем сообщение
            await interaction.response.edit_message(content=status, view=None)

    async def _send_dm_to_players(self, game):
        guild = game.guild
        for pid in list(game.players):
            print(f"[INFO] Отправляю ЛС для {pid}")
            member = guild.get_member(pid)
            if not member:
                print(f"[ERROR] Участник {pid} не найден на сервере")
                continue
            try:
                # Кнопки только тому, чей ход
                view = GameView(game, self.gm, pid) if pid == game.turn else None
                embed = self._make_embed(game, pid)
                msg = await member.send(embed=embed, view=view)
                game.player_messages[pid] = msg.id
                print(f"[SUCCESS] Сообщение отправлено {member.name} (msg id {msg.id})")
            except discord.Forbidden:
                print(f"[BLOCKED] ЛС закрыты у {member.name}")
            except Exception:
                print(f"[EXCEPTION] Ошибка отправки ЛС для {member.name}:\n{traceback.format_exc()}")

    def _make_embed(self, game, pid):
        embed = discord.Embed(title="🧮 Тетрадь", description=game.render_board(), color=0xADD8E6)
        embed.add_field(name="Ваша фигура", value=game.piece_of[pid])
        if game.winner:
            embed.add_field(name="Победитель", value=f"<@{game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{game.turn}>")
        return embed

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
        embed = discord.Embed(
            title="Выберите количество игроков",
            description="Сколько участников будет в игре?",
            color=0xADD8E6
        )
        view = GameSizeView(self.gm, guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="❓ Правила", style=discord.ButtonStyle.secondary, row=0)
    async def rules(self, interaction: discord.Interaction, button: Button):
        text = ("**Правила**\n• Поле 16×16\n• У каждого своя фигура: 🔴🔺🟩🔹\n"
                "• Ходите по очереди, выбирая клетку кнопками\n"
                "• Можно играть вдвоём, втроём или вчетвером\n"
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
        self._add_column_buttons()

    def _add_column_buttons(self):
        self.clear_items()
        cols = [chr(ord('A')+i) for i in range(16)]
        for i, col in enumerate(cols):
            row_idx = i // 4
            btn = Button(label=col, style=discord.ButtonStyle.secondary, row=row_idx)
            btn.callback = self.col_callback(col)
            self.add_item(btn)

    def _add_row_buttons(self):
        self.clear_items()
        for r in range(1, 17):
            row_idx = (r-1)//4
            btn = Button(label=str(r), style=discord.ButtonStyle.primary, row=row_idx)
            btn.callback = self.row_callback(r)
            self.add_item(btn)

    def col_callback(self, col):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.game.turn or interaction.user.id != self.viewer_id:
                return await interaction.response.send_message("Не ваш ход", ephemeral=True)
            self.selected_col = col
            self._add_row_buttons()
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
            result, game = await self.gm.make_move(interaction.user.id, coord)
            self._add_column_buttons()
            await self._update_both_messages()
            if game and game.winner:
                self.stop()
                self.gm.end_game(self.game.id)
                await interaction.response.edit_message(content="Игра окончена!", embed=self._make_embed(), view=None)
            else:
                await interaction.response.edit_message(content=result, embed=self._make_embed(), view=self)
        return callback

    async def on_timeout(self):
        print(f"Игра #{self.game.id} прервана по таймауту.")
        self.gm.end_game(self.game.id)

    async def _update_both_messages(self):
        guild = self.game.guild
        for pid in list(self.game.players):
            msg_id = self.game.player_messages.get(pid)
            if not msg_id:
                continue
            member = guild.get_member(pid)
            if not member:
                try:
                    member = await guild.fetch_member(pid)
                except Exception:
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

    def _make_embed(self):
        embed = discord.Embed(title="🧮 Тетрадь", description=self.game.render_board(), color=0xADD8E6)
        if self.game.winner:
            embed.add_field(name="Победитель", value=f"<@{self.game.winner}>")
        else:
            embed.add_field(name="Ходит", value=f"<@{self.game.turn}>")
        return embed
