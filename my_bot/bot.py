import json
import nextcord
from nextcord.ext import commands
from cogs.status import Status
from cogs.admin import Admin

# Загрузка конфига
with open('config.json', 'r') as file:
    config = json.load(file)

# Настройка намерений
intents = nextcord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

# Загрузка когов
bot.add_cog(Status(bot))
bot.add_cog(Admin(bot))

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')

bot.run(config['token'])