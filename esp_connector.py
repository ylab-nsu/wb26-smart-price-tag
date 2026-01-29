"""
Модуль для подключения к ESP32 устройствам по WiFi
"""

import requests
import time
import logging
from typing import Dict, Optional, Any, List
import json
from datetime import datetime

from config import ESP_CONFIG, ESP_DEVICES, LOG_LEVEL, LOG_FILE

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ESPConnector')


class ESP32Connector:
    """
    Класс для управления подключением к ESP32 устройствам
    """
    
    def __init__(self):
        """
        Инициализация подключения
        """
        self.timeout = ESP_CONFIG['timeout']
        self.retry_count = ESP_CONFIG['retry_count']
        logger.info("Инициализация ESP32Connector (режим реальных запросов)")
    
    def _get_esp_url(self, tag_id: str, endpoint: str) -> Optional[str]:
        """
        Формирование URL для запроса к ESP32
        
        Args:
            tag_id: ID ценника
            endpoint: API endpoint
            
        Returns:
            URL строку или None если устройство не найдено
        """
        if tag_id not in ESP_DEVICES:
            logger.warning(f"Устройство с tag_id={tag_id} не найдено в конфигурации")
            return None
        
        esp_info = ESP_DEVICES[tag_id]
        base_port = ESP_CONFIG['base_port']
        
        return f"http://{esp_info['ip']}:{base_port}{endpoint}"
    
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None, 
                     retry_on_fail: bool = True) -> Optional[Dict]:
        """
        Выполнение HTTP запроса с повторными попытками
        
        Args:
            method: HTTP метод ('GET', 'POST', 'PUT')
            url: URL запроса
            data: Данные для отправки
            retry_on_fail: Повторять ли при ошибке
            
        Returns:
            Ответ в виде словаря или None при ошибке
        """
        for attempt in range(self.retry_count if retry_on_fail else 1):
            try:
                logger.debug(f"Попытка {attempt + 1}: {method} {url}")
                
                if method.upper() == 'GET':
                    response = requests.get(url, timeout=self.timeout)
                elif method.upper() == 'POST':
                    headers = {'Content-Type': 'application/json'}
                    response = requests.post(url, json=data, headers=headers, 
                                           timeout=self.timeout)
                elif method.upper() == 'PUT':
                    headers = {'Content-Type': 'application/json'}
                    response = requests.put(url, json=data, headers=headers, 
                                          timeout=self.timeout)
                else:
                    logger.error(f"Неизвестный HTTP метод: {method}")
                    return None
                
                # Проверка статуса ответа
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        logger.warning(f"Некорректный JSON в ответе от {url}")
                        return {"status": "success", "raw_response": response.text}
                else:
                    logger.warning(f"Ошибка HTTP {response.status_code} от {url}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при подключении к {url} (попытка {attempt + 1})")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Ошибка подключения к {url}: {e} (попытка {attempt + 1})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса к {url}: {e}")
                break
            
            # Пауза между попытками
            if attempt < (self.retry_count - 1) and retry_on_fail:
                time.sleep(1 * (attempt + 1))  # Увеличивающаяся задержка
        
        logger.error(f"Не удалось выполнить запрос к {url} после {self.retry_count} попыток")
        return None
    
    def send_price_update(self, tag_id: str, price_data: Dict) -> Dict:
        """
        Отправка обновления цены на ESP32 устройство
        """
        logger.info(f"Отправка обновления цены для {tag_id}: {price_data}")
        
        # Формируем URL
        endpoint = ESP_CONFIG['update_endpoint']
        url = self._get_esp_url(tag_id, endpoint)
        
        if not url:
            return {
                "success": False,
                "message": f"Устройство {tag_id} не найдено в конфигурации"
            }
        
        # Подготавливаем данные для ESP32
        esp_data = {
            "price": price_data.get('current_price', 0),
            "product_name": price_data.get('name', ''),
            "old_price": price_data.get('old_price', 0),
            "discount": price_data.get('discount_percent', 0),
            "unit": price_data.get('unit', 'шт.')
        }
        
        print(f"Отправка на ESP32 {tag_id}: {esp_data}")
        
        # Отправляем PUT запрос
        result = self._make_request('PUT', url, esp_data)
        
        if result:
            logger.info(f"Цена успешно отправлена на {tag_id}")
            return {
                "success": True,
                "message": f"Цена отправлена на ESP32 ({tag_id})",
                "esp_response": result,
                "esp_ip": ESP_DEVICES[tag_id]['ip'],
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"Ошибка отправки цены на {tag_id}")
            return {
                "success": False,
                "message": f"Не удалось отправить цену на ESP32 ({tag_id})",
                "esp_ip": ESP_DEVICES[tag_id]['ip'],
                "timestamp": datetime.now().isoformat()
            }
    
    def get_device_status(self, tag_id: str) -> Dict:
        """
        Получение статуса ESP32 устройства
        
        Args:
            tag_id: ID ценника
            
        Returns:
            Статус устройства
        """
        logger.debug(f"Запрос статуса устройства {tag_id}")
        
        endpoint = ESP_CONFIG['status_endpoint']
        url = self._get_esp_url(tag_id, endpoint)
        
        if not url:
            return {
                "success": False,
                "online": False,
                "message": f"Устройство {tag_id} не найдено в конфигурации"
            }
        
        # Запрашиваем статус
        result = self._make_request('GET', url, retry_on_fail=False)
        
        if result:
            logger.debug(f"Получен статус от {tag_id}: {result}")
            return {
                "success": True,
                "online": True,
                "status": result,
                "last_checked": datetime.now().isoformat()
            }
        else:
            logger.warning(f"Устройство {tag_id} недоступно")
            return {
                "success": False,
                "online": False,
                "last_checked": datetime.now().isoformat()
            }
    
    def scan_network(self, ip_range: str = "192.168.1") -> List[Dict]:
        """
        Сканирование сети для поиска ESP32 устройств
        
        Args:
            ip_range: Диапазон IP адресов для сканирования
            
        Returns:
            Список найденных устройств
        """
        logger.info(f"Сканирование сети {ip_range}.x")
        
        found_devices = []
        
        # Реальное сканирование (можно расширить)
        # Пример простого сканирования по известным IP
        for tag_id, info in ESP_DEVICES.items():
            status = self.get_device_status(tag_id)
            if status.get('online', False):
                found_devices.append({
                    "tag_id": tag_id,
                    "ip": info['ip'],
                    "name": info['name'],
                    "type": info['type'],
                    "online": True,
                    "status": status.get('status', {})
                })
                logger.info(f"Найдено устройство: {tag_id} ({info['ip']})")
            else:
                logger.debug(f"Устройство {tag_id} ({info['ip']}) не отвечает")
        
        return found_devices
    
    def send_display_command(self, tag_id: str, command: str, params: Dict = None) -> Dict:
        """
        Отправка команды для дисплея ESP32
        
        Args:
            tag_id: ID ценника
            command: Команда ('clear', 'refresh', 'test_pattern', 'set_brightness')
            params: Параметры команды
            
        Returns:
            Результат выполнения
        """
        logger.info(f"Отправка команды дисплею {tag_id}: {command}")
        
        endpoint = ESP_CONFIG['config_endpoint']
        url = self._get_esp_url(tag_id, endpoint)
        
        if not url:
            return {
                "success": False,
                "message": f"Устройство {tag_id} не найдено"
            }
        
        data = {
            "command": command,
            "params": params or {},
            "timestamp": datetime.now().isoformat()
        }
        
        result = self._make_request('POST', url, data)
        
        if result:
            return {
                "success": True,
                "message": f"Команда '{command}' отправлена на {tag_id}",
                "esp_response": result
            }
        else:
            return {
                "success": False,
                "message": f"Ошибка отправки команды на {tag_id}"
            }


# Создаем глобальный экземпляр для использования во всем приложении
esp_connector = ESP32Connector()