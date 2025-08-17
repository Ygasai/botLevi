import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, time
import time as time_module
from nextcord.ext import commands, tasks
import nextcord
from database import get_collection
import json

# Словарь для сопоставления английских названий ролей с русскими
role_translation = {
    "chief_curator": "куратор проекта",
    "curator": "куратор",
    "chief_admin": "главный администратор",
    "senior_admin": "старший администратор",
    "admin": "администратор",
    "junior_admin": "младший администратор",
    "senior_moderator": "старший модератор",
    "moderator": "модератор",
    "junior_moderator": "младший модератор",
    "senior_helper": "старший хелпер",
    "helper": "хелпер"
}

# Локальный словарь с зарплатными ставками в монетах
local_salary_rates = {
    "старший хелпер": 70,
    "младший модератор": 90,
    "модератор": 115,
    "старший модератор": 130,
    "младший админ": 140,
    "админ": 180,
    "старший админ": 215,
    "главный администратор": 275
}

# Определяем списки на уровне модуля
team_4 = [
    "buterbrodius", "Ygasai", "Siukumi", "Namero", "CheloBechek", "EspadaWQ", "Globall", "Chipsi", 
    "Kotik_Krutoy", "MNks", "MuvikS", "ZERATUL02", "nubekarbuzek", "gafer", "SiO2"
]

team_10 = [
    "FomkaJulik", "-_mandarin_-", "Kinigan", "Nigma21", "ayomurdy", "dikiwark", "Mr_kompaver", 
    "MyHuC", "Sins_jok", "haruta", "Tomoe_Tamagiri", "vitaliygora976"
]

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_online_times = {}
        self.last_update_times = {}
        self.message_ids = {}  # Словарь для хранения ID сообщений для каждой команды
        self.channel_id = None
        self.reset_daily_status.start()
        self.summarize_weekly_status.start()
        self.update_online_status.start()  # Запуск задачи обновления статуса
        self.collection = get_collection('online_status')  # Имя коллекции
        self.database_cog = None  # Инициализируем как None

    @commands.Cog.listener()
    async def on_ready(self):
        # Получаем экземпляр DatabaseCog после того, как бот полностью инициализирован
        self.database_cog = self.bot.get_cog('DatabaseCog')
        if not self.database_cog:
            print("DatabaseCog не найден. Убедитесь, что он добавлен в бота.")

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

    async def update_status_for_team(self, team, team_name):
        report = f"**{team_name}:**\n"
        report += "```"
        report += f"{'Статус':<3} {'Никнейм':<15} {'Роль':<20} {'Время':<10} {'Зарплата':<10}\n"
        report += "-" * 60 + "\n"
        
        for nickname in team:
            # Получаем текущее время онлайна с сайта
            current_online_time = await self.parse_online_time(nickname)
            
            # Извлекаем должность из базы данных
            data = self.collection.find_one({"nickname": nickname})
            current_role = data.get("role", "Неизвестная должность") if data else "Неизвестная должность"
            
            if current_online_time is None:
                report += f"🔴 {nickname:<15} {'Нет данных':<20} {'-':<10} {'-':<10}\n"
                continue
            
            now = datetime.now()
            last_update_time = self.last_update_times.get(nickname)
            if last_update_time is None or (now - last_update_time).total_seconds() > 120:
                status = "🔴"
            else:
                status = "🟢"
            
            if self.last_online_times.get(nickname) != current_online_time:
                self.last_online_times[nickname] = current_online_time
                self.last_update_times[nickname] = now
                # Сохранение в базу данных
                self.collection.update_one(
                    {"nickname": nickname},
                    {"$set": {"online_time": current_online_time, "last_updated": now}},
                    upsert=True
                )
            
            # Рассчитываем зарплату на основе текущего времени онлайна
            salary = self.calculate_local_salary(current_online_time, current_role)
            report += f"{status:<3} {nickname:<15} {current_role:<20} {current_online_time:<10} {salary:<10}\n"
        
        report += "```\n"

        if self.channel_id:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    if team_name not in self.message_ids:
                        message = await channel.send(report)
                        self.message_ids[team_name] = message.id
                    else:
                        message = await channel.fetch_message(self.message_ids[team_name])
                        await message.edit(content=report)
                    print(f"Сообщение для {team_name} обновлено")  # Логирование для отладки
                except Exception as e:
                    print(f"Ошибка при обновлении сообщения для {team_name}: {e}")

    @tasks.loop(time=time(23, 59))
    async def reset_daily_status(self):
        if self.channel_id:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                try:
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    for team in [team_4, team_10]:
                        for nickname in team:
                            online_time = self.last_online_times.get(nickname, "0 ч 0 мин")
                            self.collection.update_one(
                                {"nickname": nickname},
                                {"$push": {"daily_records": {"date": current_date, "online_time": online_time}}},
                                upsert=True
                            )
                    self.last_online_times.clear()
                    self.last_update_times.clear()
                except Exception as e:
                    print(f"Ошибка при сбросе статуса: {e}")

    @tasks.loop(time=time(23, 59), count=7)
    async def summarize_weekly_status(self):
        if datetime.now().weekday() == 6:  # Воскресенье
            for team in [team_4, team_10]:
                for nickname in team:
                    records = self.collection.find_one({"nickname": nickname}).get("daily_records", [])
                    total_time = sum(self.parse_time(record["online_time"]) for record in records)
                    self.collection.update_one(
                        {"nickname": nickname},
                        {"$set": {"weekly_total": total_time}, "$unset": {"daily_records": ""}}
                    )

    def parse_time(self, time_str):
        # Пример функции для преобразования времени в минуты
        match = re.match(r'(\d+)\s*ч\s*(\d+)\s*мин', time_str)
        if match:
            hours, minutes = map(int, match.groups())
            return hours * 60 + minutes
        return 0

    def calculate_local_salary(self, online_time: str, role: str) -> int:
        """Рассчитывает зарплату в монетах на основе отыгранного времени и роли за полный час"""
        match = re.match(r'(\d+)\s*ч\s*(\d+)\s*мин', online_time)
        if match:
            hours, minutes = map(int, match.groups())
            total_hours = hours  # Округляем вниз до ближайшего целого часа
            rate = local_salary_rates.get(role.lower(), 0)
            return total_hours * rate
        return 0

    @nextcord.slash_command(name='setstatuschannel')
    async def set_status_channel(self, interaction: nextcord.Interaction, channel: nextcord.TextChannel):
        """Устанавливает канал для обновления статуса"""
        await interaction.response.defer(ephemeral=True)

        self.channel_id = channel.id
        message_4 = await channel.send("Инициализация статуса для Команды #4...")
        message_10 = await channel.send("Инициализация статуса для Команды #10...")
        self.message_ids["Команда #4"] = message_4.id
        self.message_ids["Команда #10"] = message_10.id

        # Запускаем обновление статуса сразу после установки канала
        await self.update_online_status()

    @tasks.loop(seconds=5)  # Пример: обновление статуса каждые 10 минут
    async def update_online_status(self):
        for team, team_name in [(team_4, "Команда #4"), (team_10, "Команда #10")]:
            await self.update_status_for_team(team, team_name)