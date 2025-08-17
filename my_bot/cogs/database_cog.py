import nextcord
from nextcord.ext import commands, tasks
from database import get_collection
from datetime import datetime, timedelta, time
import time as time_module
import re
from .status import Status, team_4, team_10  # Импортируем списки команд

# Словарь с зарплатными ставками в монетах
salary_rates = {
    "старший хелпер": 70,
    "младший модератор": 90,
    "модератор": 115,
    "старший модератор": 130,
    "младший админ": 140,
    "админ": 180,
    "старший админ": 215,
    "главный админ": 275
}

class DatabaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collection = get_collection('online_status')
        self.team_4 = team_4
        self.team_10 = team_10
        self.moderators = self.team_4 + self.team_10
        self.last_online_times = {nickname: "0 ч 0 мин" for nickname in self.moderators}
        self.status_cog = Status(bot)  # Создаем экземпляр класса Status
        self.update_online_data.start()
        self.save_daily_data.start()
        self.generate_daily_report.start()
        self.night_report.start()

    def calculate_salary(self, online_time: str, role: str) -> int:
        """Рассчитывает зарплату в монетах на основе отыгранного времени и роли за полный час"""
        match = re.match(r'(\d+)\s*ч\s*(\d+)\s*мин', online_time)
        if match:
            hours, minutes = map(int, match.groups())
            total_hours = hours  # Округляем вниз до ближайшего целого часа
            rate = salary_rates.get(role.lower(), 0)
            return total_hours * rate
        return 0

    @tasks.loop(seconds=30)
    async def update_online_data(self):
        current_date = datetime.now().strftime("%Y-%m-%d")
        for nickname in self.moderators:
            current_online_time = await self.status_cog.parse_online_time(nickname)

            if current_online_time and self.last_online_times[nickname] != current_online_time:
                self.last_online_times[nickname] = current_online_time
                data = self.collection.find_one({"nickname": nickname})
                role = data.get("role", "Неизвестная должность") if data else "Неизвестная должность"
                salary = self.calculate_salary(current_online_time, role)

                self.collection.update_one(
                    {"nickname": nickname},
                    {"$set": {"current_online_time": current_online_time, "current_salary": salary}}
                )
                # Обновляем daily_records за текущий день
                self.collection.update_one(
                    {"nickname": nickname, "daily_records.date": current_date},
                    {"$set": {"daily_records.$.online_time": current_online_time, "daily_records.$.salary": salary}},
                    upsert=True
                )

    @tasks.loop(seconds=60)
    async def save_daily_data(self):
        """Сохраняет данные онлайна в конце дня и подготавливает новый день"""
        now = datetime.now()
        if now.hour == 23 and now.minute == 59:
        current_date = datetime.now().strftime("%Y-%m-%d")
        for nickname, online_time in self.last_online_times.items():
            # Сохраняем данные за текущий день
            self.collection.update_one(
                {"nickname": nickname},
                {"$push": {"daily_records": {"date": current_date, "online_time": online_time}}},
                upsert=True
            )
        # Сброс данных для нового дня
        self.last_online_times = {nickname: "0 ч 0 мин" for nickname in self.moderators}

    @tasks.loop(seconds=60)
    async def night_report(self):
        """Отправляет вечерний отчёт в 23:59"""
        now = datetime.now()
        if now.hour == 23 and now.minute == 59:
            current_date = datetime.now().strftime("%Y-%m-%d")
            report = f"Отчет по онлайну и зарплате за {current_date}:\n\n"

            for team_name, team in [("Команда 4", self.team_4), ("Команда 10", self.team_10)]:
                report += f"{team_name}:\n"
                for nickname in team:
                    data = self.collection.find_one({"nickname": nickname})
                    if data:
                        online_time = data.get("current_online_time", "Нет данных")
                        salary = data.get("current_salary", 0)
                        report += f"{nickname}: {online_time}, Зарплата: {salary} монет\n"
                    else:
                        report += f"{nickname}: Нет данных\n"
                report += "\n"

            channel_id = 1405298249761296494  # Замените на фактический ID канала
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(report)

    def generate_report(self, report_type: str) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
        report = f"Отчет по онлайну за {current_date}:\n"
        moderators = self.team_4 if report_type == "4" else self.team_10 if report_type == "10" else []
        for nickname in moderators:
            data = self.collection.find_one({"nickname": nickname})
            if data and "daily_records" in data:
                if report_type == "10":
                    # Логика для отчета по команде 10
                    online_time = next((record["online_time"] for record in data["daily_records"] if record["date"] == current_date), "0 ч 0 мин")
                elif report_type == "4":
                    # Логика для отчета по команде 4
                    online_time = data.get("current_online_time", "0 ч 0 мин")
                else:
                    online_time = "Неизвестный тип отчета"
                report += f"{nickname}: {online_time}\n"
            else:
                report += f"{nickname}: Нет данных\n"
        return report

    @nextcord.slash_command(name='saveonlinedata')
    async def save_online_data(self, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)

        current_date = datetime.now().strftime("%Y-%m-%d")
        for nickname in self.moderators:
            current_online_time = await self.status_cog.parse_online_time(nickname)
            if current_online_time:
                self.last_online_times[nickname] = current_online_time
                # Попытка обновить существующую запись
                result = self.collection.update_one(
                    {"nickname": nickname, "daily_records.date": current_date},
                    {"$set": {"daily_records.$.online_time": current_online_time}}
                )
                # Если запись не обновлена, добавляем новую
                if result.matched_count == 0:
                    self.collection.update_one(
                        {"nickname": nickname},
                        {"$push": {"daily_records": {"date": current_date, "online_time": current_online_time}}},
                        upsert=True
                    )
        await interaction.followup.send("Данные онлайна сохранены за сегодняшний день.", ephemeral=True)

    @nextcord.slash_command(name='cleardata')
    async def clear_data(self, interaction: nextcord.Interaction):
        """Очищает данные в базе данных и записывает актуальную информацию из парсинга"""
        await interaction.response.defer(ephemeral=True)

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.collection.delete_many({})  # Очищаем все данные в коллекции

        for nickname in self.moderators:
            current_online_time = await self.status_cog.parse_online_time(nickname)
            if current_online_time:
                self.collection.insert_one({
                    "nickname": nickname,
                    "daily_records": [{"date": current_date, "online_time": current_online_time}]
                })
        await interaction.followup.send("Данные очищены и обновлены с актуальной информацией.", ephemeral=True)

    @nextcord.slash_command(name='showdata')
    async def show_data(self, interaction: nextcord.Interaction, user: nextcord.User):
        nickname = user.display_name
        data = self.collection.find_one({"nickname": nickname})
        if not data or "daily_records" not in data:
            await interaction.response.send_message("Нет данных для этого пользователя.", ephemeral=True)
            return

        records = data["daily_records"]
        message = f"Данные онлайна для {nickname}:\n"
        for record in records:
            message += f"Дата: {record['date']}, Время онлайн: {record['online_time']}\n"

        await interaction.response.send_message(message, ephemeral=True)

    @nextcord.slash_command(name='addonlinedata')
    async def add_online_data(self, interaction: nextcord.Interaction, user: nextcord.User, hours: int, minutes: int, date: str):
        """Изменяет данные онлайна за указанную дату"""
        nickname = user.display_name
        try:
            # Проверяем и форматируем дату
            current_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message("Неверный формат даты. Используйте YYYY-MM-DD.", ephemeral=True)
            return

        online_time = f"{hours} ч {minutes} мин"
        
        # Попытка обновить существующую запись
        result = self.collection.update_one(
            {"nickname": nickname, "daily_records.date": current_date},
            {"$set": {"daily_records.$.online_time": online_time}}
        )
        
        # Если запись не обновлена, добавляем новую
        if result.matched_count == 0:
            self.collection.update_one(
                {"nickname": nickname},
                {"$push": {"daily_records": {"date": current_date, "online_time": online_time}}},
                upsert=True
            )
        
        await interaction.response.send_message(f"Данные онлайна для {nickname} обновлены: {online_time} на {current_date}.", ephemeral=True)

    @nextcord.slash_command(name='totalonline')
    async def total_online(self, interaction: nextcord.Interaction, user: nextcord.User, days: int = 7):
        """Подсчитывает общий онлайн за последние дни"""
        nickname = user.display_name
        data = self.collection.find_one({"nickname": nickname})
        if not data or "daily_records" not in data:
            await interaction.response.send_message("Нет данных для этого пользователя.", ephemeral=True)
            return

        total_minutes = 0
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Суммируем время из daily_records
        for record in data["daily_records"]:
            record_date = datetime.strptime(record["date"], "%Y-%m-%d")
            if record_date >= cutoff_date:
                time_str = record["online_time"]
                match = re.match(r'(\d+)\s*ч\s*(\d+)\s*мин', time_str)
                if match:
                    hours, minutes = map(int, match.groups())
                    total_minutes += hours * 60 + minutes

        # Добавляем текущее время онлайн, если оно существует
        if "current_online_time" in data:
            current_time_str = data["current_online_time"]
            match = re.match(r'(\d+)\s*ч\s*(\d+)\s*мин', current_time_str)
            if match:
                hours, minutes = map(int, match.groups())
                total_minutes += hours * 60 + minutes

        total_hours = total_minutes // 60
        total_minutes %= 60
        await interaction.response.send_message(f"Общий онлайн для {nickname} за последние {days} дней: {total_hours} ч {total_minutes} мин.", ephemeral=True)

    @nextcord.slash_command(name='dailyreport')
    async def daily_report(self, interaction: nextcord.Interaction, team: str):
        """Формирует и отправляет отчет по онлайну за текущий день для указанной команды"""
        if team == "4":
            selected_team = team_4
        elif team == "10":
            selected_team = team_10
        else:
            await interaction.response.send_message("Неверный выбор команды. Используйте '4' или '10'.", ephemeral=True)
            return

        report = self.generate_report_for_team(selected_team)
        await interaction.response.send_message(report, ephemeral=True)

    def generate_report_for_team(self, team) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
        report = f"Отчет по онлайну за {current_date}:\n"
        for nickname in team:
            data = self.collection.find_one({"nickname": nickname})
            if data:
                online_time = data.get("current_online_time", "Нет данных")
                if online_time == "Нет данных" and "daily_records" in data:
                    record = next((record for record in data["daily_records"] if record["date"] == current_date), None)
                    if record:
                        online_time = record["online_time"]
                report += f"{nickname}: {online_time}\n"
            else:
                report += f"{nickname}: Нет данных\n"
        return report

def setup(bot):
    bot.add_cog(DatabaseCog(bot))