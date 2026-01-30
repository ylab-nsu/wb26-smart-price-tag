"""
Модуль для отправки данных на ESP32 устройства
"""

import requests
import json
import logging
from datetime import datetime
from typing import Dict, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ESPSender')


class ESPSender:
    """
    Класс для отправки данных на ESP32 устройства
    """
    
    def __init__(self, timeout: int = 5, retry_count: int = 2):
        """
        Инициализация отправителя
        
        Args:
            timeout: Таймаут запроса в секундах
            retry_count: Количество повторных попыток
        """
        self.timeout = timeout
        self.retry_count = retry_count
    
    def send_to_esp(self, ip_address: str, data: Dict) -> Dict:
        """
        Отправка данных на ESP32 устройство
        
        Args:
            ip_address: IP адрес ESP32
            data: Данные для отправки
            
        Returns:
            Результат отправки
        """
        logger.info(f"Отправка данных на ESP32: {ip_address}")
        
        # Формируем URL для отправки
        url = f"http://{ip_address}/api/price"
        
        # Подготавливаем данные - убираем ненужные поля
        esp_data = {
            "device_id": data.get("device_id", ""),
            "product_name": data.get("product_name", ""),
            "current_price": float(data.get("current_price", 0)),
            "weight": float(data.get("weight", 0))
        }
        
        logger.info(f"Данные для отправки: {esp_data}")
        
        for attempt in range(self.retry_count):
            try:
                logger.debug(f"Попытка {attempt + 1} отправки на {ip_address}")
                
                response = requests.post(
                    url,
                    json=esp_data,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                logger.debug(f"Статус ответа: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        logger.info(f"Успешно отправлено на {ip_address}")
                        return {
                            "success": True,
                            "message": f"Данные отправлены на ESP32 ({ip_address})",
                            "status_code": response.status_code,
                            "response_data": response_data,
                            "ip_address": ip_address,
                            "timestamp": datetime.now().isoformat()
                        }
                    except json.JSONDecodeError:
                        logger.warning(f"Некорректный JSON в ответе от {ip_address}")
                        return {
                            "success": True,
                            "message": f"Данные отправлены (некорректный JSON в ответе)",
                            "status_code": response.status_code,
                            "raw_response": response.text,
                            "ip_address": ip_address,
                            "timestamp": datetime.now().isoformat()
                        }
                else:
                    logger.warning(f"Ошибка HTTP {response.status_code} от {ip_address}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при подключении к {ip_address}")
                if attempt < self.retry_count - 1:
                    continue
                return {
                    "success": False,
                    "message": f"Таймаут при подключении к ESP32 ({ip_address})",
                    "error": "timeout",
                    "ip_address": ip_address,
                    "timestamp": datetime.now().isoformat()
                }
            
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ошибка подключения к {ip_address}: {str(e)}")
                if attempt < self.retry_count - 1:
                    continue
                return {
                    "success": False,
                    "message": f"Не удалось подключиться к ESP32 ({ip_address})",
                    "error": "connection_error",
                    "details": str(e),
                    "ip_address": ip_address,
                    "timestamp": datetime.now().isoformat()
                }
            
            except Exception as e:
                logger.error(f"Ошибка при отправке на {ip_address}: {str(e)}")
                return {
                    "success": False,
                    "message": f"Ошибка при отправке на ESP32 ({ip_address})",
                    "error": str(e),
                    "ip_address": ip_address,
                    "timestamp": datetime.now().isoformat()
                }
        
        # Если все попытки не удались
        return {
            "success": False,
            "message": f"Не удалось отправить данные на ESP32 ({ip_address})",
            "error": "all_attempts_failed",
            "ip_address": ip_address,
            "timestamp": datetime.now().isoformat()
        }
    
    def test_connection(self, ip_address: str, tag_id: str = None, 
                       endpoint: str = "/api/price") -> Dict:
        """
        Тестирование соединения с ESP32 устройством
        
        Args:
            ip_address: IP адрес ESP32
            tag_id: ID ценника (опционально)
            endpoint: API endpoint для тестирования
            
        Returns:
            Результат тестирования
        """
        logger.info(f"Тестирование соединения с ESP32: {ip_address}")
        
        url = f"http://{ip_address}{endpoint}"
        
        try:
            # Пробуем GET запрос для проверки доступности
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"ESP32 доступен: {ip_address}")
                    return {
                        "success": True,
                        "message": "ESP32 доступен",
                        "status_code": response.status_code,
                        "response_data": data,
                        "ip_address": ip_address,
                        "timestamp": datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    logger.info(f"ESP32 доступен (некорректный JSON): {ip_address}")
                    return {
                        "success": True,
                        "message": "ESP32 доступен",
                        "status_code": response.status_code,
                        "raw_response": response.text,
                        "ip_address": ip_address,
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                logger.warning(f"ESP32 вернул ошибку {response.status_code}")
                return {
                    "success": False,
                    "message": f"ESP32 вернул ошибку {response.status_code}",
                    "status_code": response.status_code,
                    "ip_address": ip_address,
                    "timestamp": datetime.now().isoformat()
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при подключении к {ip_address}")
            return {
                "success": False,
                "message": f"ESP32 не отвечает (таймаут)",
                "error": "timeout",
                "ip_address": ip_address,
                "timestamp": datetime.now().isoformat()
            }
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения к {ip_address}: {str(e)}")
            return {
                "success": False,
                "message": f"Не удалось подключиться к ESP32",
                "error": "connection_error",
                "details": str(e),
                "ip_address": ip_address,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при тестировании {ip_address}: {str(e)}")
            return {
                "success": False,
                "message": f"Ошибка при тестировании ESP32",
                "error": str(e),
                "ip_address": ip_address,
                "timestamp": datetime.now().isoformat()
            }


# Создаем глобальный экземпляр для использования во всем приложении
esp_sender = ESPSender()