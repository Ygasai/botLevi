import nextcord
from nextcord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(name='тест')
    async def тест(self, interaction: nextcord.Interaction):
        """Проверка работоспособности бота"""
        await interaction.response.send_message(f'{interaction.user.mention} WORK')

    @nextcord.slash_command(name='sendmessage')
    async def send_message(self, interaction: nextcord.Interaction, message: str):
        """Отправляет указанное сообщение в канал"""
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(message)
        await interaction.followup.send("Сообщение отправлено.", ephemeral=True)

    @nextcord.slash_command(name='helper')
    async def helper(self, interaction: nextcord.Interaction, member: nextcord.Member, new_nickname: str):
        """Выдает роль 'Хелпер' и изменяет никнейм пользователя"""
        if "Админ" not in [role.name for role in interaction.user.roles]:
            await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
            return
        role = nextcord.utils.get(interaction.guild.roles, name="Хелпер")
        if role is None:
            await interaction.response.send_message("Роль 'Хелпер' не найдена.", ephemeral=True)
            return
        try:
            await member.add_roles(role)
            await member.edit(nick=new_nickname)
            await interaction.response.send_message(f"Роль 'Хелпер' выдана и никнейм изменен на {new_nickname}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)

    @nextcord.slash_command(name='lvlup')
    async def lvlup(self, interaction: nextcord.Interaction, member1: nextcord.Member, member2: nextcord.Member = None, member3: nextcord.Member = None):
        """Повышает должность пользователей"""
        if "Админ" not in [role.name for role in interaction.user.roles]:
            await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
            return
        role_hierarchy = {
            "Хелпер": "Модератор",
            "Модератор": "Админ"
        }
        members = [member1, member2, member3]
        await interaction.response.defer(ephemeral=True)
        for member in filter(None, members):
            current_roles = [role.name for role in member.roles]
            for current_role, next_role in role_hierarchy.items():
                if current_role in current_roles:
                    current_role_obj = nextcord.utils.get(interaction.guild.roles, name=current_role)
                    next_role_obj = nextcord.utils.get(interaction.guild.roles, name=next_role)
                    if current_role_obj and next_role_obj:
                        try:
                            await member.remove_roles(current_role_obj)
                            await member.add_roles(next_role_obj)
                            await interaction.followup.send(f"{member.mention} повышен с {current_role} до {next_role}.", ephemeral=True)
                        except Exception as e:
                            await interaction.followup.send(f"Ошибка при повышении {member.mention}: {str(e)}", ephemeral=True)
                    break
            else:
                await interaction.followup.send(f"{member.mention} не имеет роли для повышения.", ephemeral=True)