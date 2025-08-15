import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, time
from nextcord.ext import commands, tasks
import nextcord

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_online_times = {}
        self.last_update_times = {}
        self.message_id = None
        self.channel_id = None
        self.nicknames = [
            "buterbrodius", "Ygasai", "Siukumi", "Namero", "CheloBechek", "EspadaWQ", "Globall", "Chipsi", "Kotik_Krutoy", "MNks", "MuvikS", "ZERATUL02", "nubekarbuzek", "gafer", "SiO2",
        ]
        self.update_online_status.start()
        self.reset_daily_status.start()

    async def parse_online_time(self, nickname):
        url = "https://loliland.ru/ru/team"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    text = await response.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    nickname_divs = soup.find_all('div', class_='player__nickname')
                    for div in nickname_divs:
                        current_nick = div.get_text(strip=True)
                        if nickname.lower() == current_nick.lower():
                            player_card = div.find_parent('div', class_='player-card')
                            if not player_card:
                                continue
                            time_blocks = player_card.find_all('p', class_='pc-data-text_main-text')
                            if time_blocks:
                                return time_blocks[0].get_text(strip=True)
                            time_blocks = player_card.find_all(string=re.compile(r'\d+\s*[чмин]+'))
                            if time_blocks:
                                return time_blocks[0].strip()
            return None
        except Exception as e:
            print(f"Ошибка при парсинге: {e}")
            return None

    @tasks.loop(seconds=10)
    async def update_online_status(self):
        status_messages = []
        for nickname in self.nicknames:
            current_online_time = await self.parse_online_time(nickname)
            if current_online_time is None:
                continue
            now = datetime.now()
            if self.last_online_times.get(nickname) != current_online_time:
                self.last_online_times[nickname] = current_online_time
                self.last_update_times[nickname] = now
            if self.last_update_times.get(nickname) and (now - self.last_update_times[nickname]) > timedelta(minutes=2):
                status_messages.append(f"🔴 {nickname} - сегодня отыграл {self.last_online_times[nickname]}")
            else:
                status_messages.append(f"🟢 {nickname} - сегодня отыграл {self.last_online_times[nickname]}")
        if self.message_id and self.channel_id:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(self.message_id)
                    await message.edit(content="\n".join(status_messages))
                except Exception as e:
                    print(f"Ошибка при обновлении сообщения: {e}")

    @tasks.loop(time=time(23, 59))  # Укажите время в формате (час, минута)
    async def reset_daily_status(self):
        if self.channel_id:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    status_messages_with_date = [f"{msg} (Дата: {current_date})" for msg in self.last_online_times.values()]
                    new_message = await channel.send("\n".join(status_messages_with_date))
                    self.message_id = new_message.id
                except Exception as e:
                    print(f"Ошибка при создании нового сообщения: {e}")
        self.last_online_times.clear()
        self.last_update_times.clear()

    @nextcord.slash_command(name='setstatuschannel')
    async def set_status_channel(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel):
        """Устанавливает канал для обновления статуса"""
        self.channel_id = channel.id
        message = await channel.send("Инициализация статуса...")
        self.message_id = message.id
        await interaction.followup.send(f"Канал для статуса установлен: {channel.mention}", ephemeral=True)