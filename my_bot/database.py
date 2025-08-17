from pymongo import MongoClient

# Подключение к MongoDB
client = MongoClient("mongodb://ygasai1:5UVoUUjnyxsyHObC@ac-9we0vdt-shard-00-00.s6xopix.mongodb.net:27017,ac-9we0vdt-shard-00-01.s6xopix.mongodb.net:27017,ac-9we0vdt-shard-00-02.s6xopix.mongodb.net:27017/?ssl=true&replicaSet=atlas-p2lygj-shard-0&authSource=admin&retryWrites=true&w=majority&appName=Cluster0")
db = client['online']  # Замените 'local' на имя вашей базы данных

# Пример функции для получения коллекции
def get_collection(online):
    return db[online]