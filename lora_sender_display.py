# main.py - ESP32 Price Tag Web Server with LoRa
import network
import time
import socket
import json
import machine
import ujson
from collections import OrderedDict

# import for lora connection
from lora_e32 import LoRaE32, Configuration
from machine import UART
import utime
import ujson

from lora_e32_constants import FixedTransmission
from lora_e32_operation_constant import ResponseStatusCode

# параметры WIFI  
WIFI_SSID = "Xiaomi 14T"
WIFI_PASSWORD = "AsdAf112017"

# идентификатор шлюза
DEVICE_ID = "TAG-101"

# LORA CONFIG
LORA_CHANNEL = 23
LORA_SENDER_ADDRESS = 0x02

# PRODUCT DATA
price_data = {
    "device_id": DEVICE_ID,
    "product_name": "Shluz", 
    "current_price": 0.0,  
    "weight": 0.5,        
    "battery": 85,       
    "signal": 92,
    "is_active": True,
    "last_update": None
}


def init_lora():
    """
    Initialize LoRa module
    """
    try:
        print("[LORA] Initializing...")
        # Инициализация LoRa модуля
        uart2 = UART(2)
        lora = LoRaE32('433T20D', uart2, aux_pin=5, m0_pin=25, m1_pin=26)
        code = lora.begin()
        print(f"Initialization: {ResponseStatusCode.get_description(code)}")
        
        print(f"[LORA] Begin status: {code}")
        
        # Конфигурация
        configuration_to_set = Configuration('433T20D')
        configuration_to_set.ADDL = 0x02
        configuration_to_set.OPTION.fixedTransmission = FixedTransmission.TRANSPARENT_TRANSMISSION
        code, confSetted = lora.set_configuration(configuration_to_set)
        print(f"Set configuration: {ResponseStatusCode.get_description(code)}")

        if code == ResponseStatusCode.SUCCESS:
            print("[LORA] LoRa module initialized successfully")
            return lora
        else:
            print("[LORA] LoRa initialization failed")
            return None
            
    except Exception as e:
        print(f"[LORA] Error: {e}")
        return None


def send_lora_message(lora_module, message_data):
    """
    Send data via LoRa - ОБНОВЛЕНО для нового формата данных
    """
    if lora_module is None:
        print("[LORA] Module not ready")
        return False
    
    try:
        product_data = OrderedDict([
            ('name', str(message_data.get("product_name", "Product"))[:20]),
            ('weight', str(message_data.get("weight", 0))),
            ('price', str(message_data.get("current_price", 0)))
        ])

       
        print(f"[LORA] Подготовлены данные: {product_data}")

        print("Sending messages...")
        
        # Преобразуем словарь в строку JSON
        product_str = ujson.dumps(product_data)
        print(f"[LORA] Отправляем по LoRa: {product_str}")
        print(f"[LORA] Размер сообщения: {len(product_str)} байт")
    
        # Отправка сообщения
        code = lora_module.send_broadcast_message(23, product_str)
        print(f"[LORA] Статус отправки: {ResponseStatusCode.get_description(code)}")
        print(f"[LORA] Send code: {code}")
        
        if code == ResponseStatusCode.SUCCESS:
            print("[LORA] Success")
            return True
        else:
            print(f"[LORA] Failed: {ResponseStatusCode.get_description(code)}")
            return False
    
        utime.sleep(2)

        print("All messages sent!")
            
    except Exception as e:
        print(f"[LORA] Error: {e}")
        return False



def connect_wifi():
    print("\n[WIFI] Connecting to:", WIFI_SSID)
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print("Connecting", end="")
        
        for i in range(20):
            if wlan.isconnected():
                break
            print(".", end="")
            time.sleep(0.5)
    
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print("\n[WIFI] Connected!")
        print("[WIFI] IP:", ip)
        print("[WIFI] Device:", DEVICE_ID)
        return wlan, ip
    else:
        print("\n[WIFI] Failed")
        return None, None


def update_price_data(new_data):
    update_count = 0
    
    print(f"[DATA] New data received: {new_data}")
    
    for key, value in new_data.items():
        if key == "product_name" and key in price_data:
            old_value = price_data[key]
            price_data[key] = str(value)
            update_count += 1
            print(f"[DATA] {key}: {old_value} -> {price_data[key]}")
            
        elif key == "current_price" and key in price_data:
            try:
                old_value = price_data[key]
                price_data[key] = float(value)
                update_count += 1
                print(f"[DATA] {key}: {old_value} -> {price_data[key]}")
            except:
                print(f"[DATA] Bad format for {key}: {value}")
                
        elif key == "weight" and key in price_data:
            try:
                old_value = price_data[key]
                price_data[key] = float(value)
                update_count += 1
                print(f"[DATA] {key}: {old_value} -> {price_data[key]}")
            except:
                print(f"[DATA] Bad format for {key}: {value}")
                
        elif key == "battery" and key in price_data:
            try:
                old_value = price_data[key]
                price_data[key] = int(value)
                update_count += 1
                print(f"[DATA] {key}: {old_value} -> {price_data[key]}")
            except:
                print(f"[DATA] Bad format for {key}: {value}")
                
        elif key == "device_id":
            pass
                
        else:
            pass
    
    if update_count > 0:
        price_data["last_update"] = time.time()
        print(f"[DATA] Updated {update_count} fields")
        return True
    else:
        print("[DATA] No fields updated")
        return False


def parse_http_request(request):
    """Parse HTTP request"""
    try:
        request_str = request.decode("utf-8", errors='ignore')
    except:
        try:
            request_str = request.decode("latin-1")
        except:
            request_str = str(request)
    
    lines = request_str.split("\r\n")
    
    if not lines:
        return None, None, None, None
    
    request_line = lines[0].split()
    if len(request_line) < 2:
        return None, None, None, None
    
    method = request_line[0]
    path = request_line[1]
    
    headers = {}
    for i in range(1, len(lines)):
        if not lines[i]:
            break
        if ": " in lines[i]:
            key, value = lines[i].split(": ", 1)
            headers[key.lower()] = value
    
    body = None
    if "\r\n\r\n" in request_str:
        body_str = request_str.split("\r\n\r\n", 1)[1]
        if body_str.strip():
            body = body_str
    
    return method, path, headers, body


def send_http_response(client, status_code, content_type, content):
    response = f"HTTP/1.1 {status_code}\r\n"
    response += "Content-Type: " + content_type + "\r\n"
    response += "Content-Length: " + str(len(content)) + "\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    response += content
    
    try:
        client.send(response.encode("utf-8"))
    except Exception as e:
        print(f"[HTTP] Send error: {e}")


def handle_request(client, request, lora_module):
    try:
        method, path, headers, body = parse_http_request(request)
        
        if not method or not path:
            send_http_response(client, "400 Bad Request", "text/plain", "Bad request")
            return
        
        print(f"\n[HTTP] {method} {path}")
        if body:
            print(f"[HTTP] Body length: {len(body)} bytes")
        
        if path == "/":
            html = f"""<html>
<head><title>ESP32 Price Tag - {DEVICE_ID}</title></head>
<body>
<h1>ESP32 Price Tag</h1>
<p><strong>Device ID:</strong> {price_data['device_id']}</p>
<p><strong>Product:</strong> {price_data['product_name']}</p>
<p><strong>Price:</strong> {price_data['current_price']} RUB</p>
<p><strong>Weight:</strong> {price_data['weight']} kg</p>
<p><strong>Battery:</strong> {price_data['battery']}%</p>
<p><strong>Status:</strong> {'Active' if price_data['is_active'] else 'Inactive'}</p>
<p><strong>LoRa:</strong> {'Ready' if lora_module else 'Off'}</p>
<hr>
<h3>API:</h3>
<ul>
<li><a href="/api/status">/api/status</a> - Status</li>
<li><a href="/api/price">/api/price</a> - Price (GET/POST/PUT)</li>
</ul>
<p><strong>Last update:</strong> {time.ctime(price_data['last_update']) if price_data['last_update'] else 'Never'}</p>
</body></html>"""
            
            send_http_response(client, "200 OK", "text/html", html)
            return
        
        # API: Status
        elif path == "/api/status":
            wlan = network.WLAN(network.STA_IF)
            status = {
                "device_id": DEVICE_ID,
                "status": "online",
                "wifi_connected": wlan.isconnected(),
                "ip_address": wlan.ifconfig()[0] if wlan.isconnected() else None,
                "lora_ready": lora_module is not None,
                "lora_channel": LORA_CHANNEL if lora_module else None,
                "timestamp": time.time(),
                "data": price_data
            }
            
            response_json = json.dumps(status)
            send_http_response(client, "200 OK", "application/json", response_json)
            return
        
        # API: Price info
        elif path == "/api/price":
            if method == "GET":
                response_json = json.dumps(price_data)
                send_http_response(client, "200 OK", "application/json", response_json)
                return
            
            elif method in ["POST", "PUT"]:
                if not body:
                    send_http_response(client, "400 Bad Request", "application/json", 
                                      json.dumps({"error": "No data provided"}))
                    return
                
                try:
                    # Парсим JSON
                    data = json.loads(body)
                    print(f"[HTTP] Received data: {list(data.keys())}")
                    
                    # Обновляем данные
                    is_updated = update_price_data(data)
                    
                    # Пробуем отправить по LoRa
                    lora_sent = False
                    if is_updated and lora_module:
                        print("[LORA] Trying to forward updated data...")
                        lora_sent = send_lora_message(lora_module, data)
                    
                    # Формируем ответ
                    response_data = {
                        "success": True,
                        "device_id": DEVICE_ID,
                        "message": "Data updated and forwarded via LoRa" if lora_sent else "Data updated",
                        "updated": is_updated,
                        "lora_forwarded": lora_sent,
                        "received_data": data,
                        "current_data": price_data,
                        "battery": price_data["battery"],
                        "timestamp": time.time()
                    }
                    
                    response_json = json.dumps(response_data)
                    send_http_response(client, "200 OK", "application/json", response_json)
                    return
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON: {str(e)}"
                    print(f"[HTTP] JSON error: {error_msg}")
                    send_http_response(client, "400 Bad Request", "application/json",
                                      json.dumps({"error": error_msg}))
                    return
                except Exception as e:
                    error_msg = f"Server error: {str(e)}"
                    print(f"[HTTP] Error: {error_msg}")
                    send_http_response(client, "500 Internal Server Error", "application/json",
                                      json.dumps({"error": error_msg}))
                    return
        
        else:
            send_http_response(client, "404 Not Found", "text/plain", "Not found")
            
    except Exception as e:
        print(f"[HTTP] Handler error: {e}")
        send_http_response(client, "500 Internal Server Error", "text/plain", "Server error")

def start_web_server(ip, lora_module, port=80):
    """Start web server"""
    print(f"[SERVER] Starting on {ip}:{port}")
    
    addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(addr)
    server.listen(5)
    
    print("[SERVER] Ready")
    print(f"[SERVER] API: http://{ip}/api/price")
    print(f"[SERVER] LoRa: {'ON' if lora_module else 'OFF'}")
    
    while True:
        try:
            client, addr = server.accept()
            print(f"\n[SERVER] Connection from: {addr[0]}")
            
            client.settimeout(10.0) 
            
            try:
                # Читаем запрос
                request = b""
                while True:
                    try:
                        chunk = client.recv(1024)
                        if not chunk:
                            break
                        request += chunk
                        
                        if b"\r\n\r\n" in request:
                            try:
                                request_str = request.decode("utf-8")
                                headers_part = request_str.split("\r\n\r\n")[0]
                                content_length = 0
                                
                                for line in headers_part.split("\r\n"):
                                    if line.lower().startswith("content-length:"):
                                        content_length = int(line.split(":", 1)[1].strip())
                                        break
                                
                                if content_length > 0:
                                    body_received = len(request) - len(headers_part) - 4
                                    while body_received < content_length:
                                        chunk = client.recv(1024)
                                        if not chunk:
                                            break
                                        request += chunk
                                        body_received += len(chunk)
                            
                            except:
                                pass
                            break
                            
                    except socket.timeout:
                        break
                    except Exception as e:
                        print(f"[SERVER] Read error: {e}")
                        break
                
                if request:
                    handle_request(client, request, lora_module)
                
            except Exception as e:
                print(f"[SERVER] Client error: {e}")
            finally:
                try:
                    client.close()
                except:
                    pass
            
        except KeyboardInterrupt:
            print("\n[SERVER] Stopped by user")
            break
        except Exception as e:
            print(f"[SERVER] Error: {e}")
            try:
                client.close()
            except:
                pass



def main():
    print("\n" + "="*50)
    print("ESP32 Price Tag with LoRa")
    print("Device ID:", DEVICE_ID)
    print("="*50)
    
    # Инициализация LoRa
    lora_module = init_lora()
    
    # Подключаемся к WiFi
    wlan, ip = connect_wifi()
    if not ip:
        print("[MAIN] WiFi connection failed, trying once more...")
        time.sleep(2)
        wlan, ip = connect_wifi()
        if not ip:
            print("[MAIN] Rebooting...")
            time.sleep(3)
            machine.reset()
    
    # Запускаем сервер
    try:
        start_web_server(ip, lora_module)
    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user")
    except Exception as e:
        print(f"[MAIN] Crashed: {e}")
        print("[MAIN] Rebooting...")
        time.sleep(5)
        machine.reset()


if __name__ == "__main__":
    main()