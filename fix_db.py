import sqlite3
import json

# Подключаемся к базе данных
db_path = "data/ncdc.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Очищаем глобальный конфиг
cursor.execute("DELETE FROM global_config")

# 2. Создаем правильный конфиг как Python-словарь (никаких проблем с кавычками!)
global_settings = {
    "static.auto_provision.server.url": "https://ncdc-dev.bsmuk.ru/provision/",
    "static.auto_provision.power_on": 1,
    "static.auto_provision.repeat.minutes": 1,
    "static.network.ip_address_mode": 0,  # 0 = IPv4 (НЕ 1!)
    "static.network.ipv6_enable": 0,
    "local_time.time_zone": "+10",
    "local_time.dhcp_time": 1,
    "ldap.enable": 0,
    "features.action_uri_limit_ip": "10.30.30.30"
}

# 3. Вставляем как JSON-строку
cursor.execute(
    "INSERT INTO global_config (settings) VALUES (?)",
    (json.dumps(global_settings),)
)

# 4. Исправляем режим 802.1x для T46U (0 = EAP-TLS)
cursor.execute(
    "UPDATE phone_models SET ieee802_1x_mode = 0 WHERE name = 'T46U'"
)

# Сохраняем изменения
conn.commit()

# 5. Проверяем результат
print("=== Глобальный конфиг ===")
cursor.execute("SELECT settings FROM global_config")
row = cursor.fetchone()
if row:
    settings = json.loads(row[0])
    print(f"ip_address_mode: {settings.get('static.network.ip_address_mode')}")
    print(f"ipv6_enable: {settings.get('static.network.ipv6_enable')}")
    print(f"autop url: {settings.get('static.auto_provision.server.url')}")

print("\n=== Модель T46U ===")
cursor.execute("SELECT name, ieee802_1x_mode FROM phone_models WHERE name = 'T46U'")
row = cursor.fetchone()
if row:
    print(f"Модель: {row[0]}, 802.1x mode: {row[1]} (0=EAP-TLS, 2=EAP-MD5)")

conn.close()
print("\n✅ База данных успешно обновлена!")