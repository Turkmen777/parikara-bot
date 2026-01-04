import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8123803682:AAENNoQJnT63ErS5w0JdPg8r4q-sxx28rBs")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1003663534213"))
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "8444800411").split(',')))

MIN_AMOUNT = int(os.getenv("MIN_AMOUNT", "50"))
