from unittest.mock import MagicMock
from my_bot.cogs.database_cog import DatabaseCog

class TestDatabaseCog:
    
    def setUp(self):
        self.bot = MagicMock()
        self.cog = DatabaseCog(self.bot)
        self.cog.collection = MagicMock()
