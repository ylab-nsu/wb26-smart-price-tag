"""
Конфигурация для подключения к ESP32 устройствам
"""

# Настройки WiFi сети
WIFI_CONFIG = {
    'ssid': 'WIFI_name',      # имя WiFi сети
    'password': 'WIFI_password', # Пароль WiFi
    'timeout': 10              # Таймаут подключения (сек)
}

# Базовые настройки ESP32 устройств
ESP_CONFIG = {
    'base_port': 80,
    'timeout': 5,
    'retry_count': 3,
    'update_endpoint': '/api/price',      # Эндпоинт для обновления цены (PUT)
    'status_endpoint': '/api/status',     # Эндпоинт для получения статуса (GET)
    'config_endpoint': '/api/config',     # Эндпоинт для конфигурации (GET)
}

# Список ESP32 устройств
# Формат: 'tag_id': {'ip': '192.168.1.xxx', 'name': 'Описание'}
ESP_DEVICES = {
    'TAG-101': {'ip': '10.133.210.157', 'name': 'Shluz', 'type': 'eink'},
}

# Логирование
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = 'esp_connection.log'