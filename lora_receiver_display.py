from pico_display import EPD_2in13_B_V4_Landscape
from lora_e32 import LoRaE32, Configuration, BROADCAST_ADDRESS
from machine import UART
import utime
import ujson

from lora_e32_constants import FixedTransmission
from lora_e32_operation_constant import ResponseStatusCode

class MessageBuffer:
    def __init__(self):
        # для сборки фрагм сообщ
        self.buffer = ""
        self.last_receive_time = utime.ticks_ms()
    
    def add_fragment(self, fragment):
        self.buffer += fragment
        self.last_receive_time = utime.ticks_ms()
    
    def try_extract_json(self):
        start = self.buffer.find('{')
        if start == -1:
            return None
        
        balance = 0
        end = -1
        
        for i in range(start, len(self.buffer)):
            if self.buffer[i] == '{':
                balance += 1
            elif self.buffer[i] == '}':
                balance -= 1
                if balance == 0:
                    end = i
                    break
        
        if end != -1:
            # json нашелся
            json_str = self.buffer[start:end+1]
            # убираю обработанную часть из буфера
            self.buffer = self.buffer[end+1:]
            return json_str
        
        return None
    
    def clear(self):
        self.buffer = ""
    
    def is_timed_out(self, timeout_ms=1000):
        return utime.ticks_diff(utime.ticks_ms(), self.last_receive_time) > timeout_ms

def init_display():
    epd = EPD_2in13_B_V4_Landscape()
    epd.Clear(0xff, 0xff)
    epd.imageblack.fill(0xff)
    epd.imagered.fill(0xff)
    return epd

def draw_price_tag_with_data(epd, product_name, weight, price_per_kg):
    epd.imageblack.fill(0xff)
    epd.imagered.fill(0xff)
    
    epd.imageblack.rect(5, 10, 240, 112, 0x00)
    epd.imageblack.text("Name:", 15, 15, 0x00)
    
    display_name = product_name[:20] if len(product_name) > 20 else product_name
    epd.imageblack.text(display_name, 60, 15, 0x00)
    
    epd.imageblack.hline(10, 40, 230, 0x00)
    
    epd.imageblack.text("Weight:", 15, 55, 0x00)
    weight_text = f"{weight} kg"
    epd.imageblack.text(weight_text, 75, 55, 0x00)
    
    epd.imageblack.text("Price/kg:", 15, 75, 0x00)
    price_text = f"{price_per_kg} rub"
    epd.imageblack.text(price_text, 90, 75, 0x00)
    
    epd.imageblack.text("Total:", 15, 95, 0x00)
    
    try:
        total_price = float(weight) * float(price_per_kg)
    except:
        total_price = 0
    
    total_text = f"{total_price:.2f} rub"
    epd.imageblack.rect(65, 90, 120, 20, 0x00)
    epd.imageblack.text(total_text, 70, 95, 0x00)
    
    epd.display()

def draw_waiting_message(epd):
    epd.imageblack.fill(0xff)
    epd.imagered.fill(0xff)
    epd.imageblack.rect(5, 10, 240, 112, 0x00)
    epd.imageblack.text("Waiting for", 70, 40, 0x00)
    epd.imageblack.text("messages...", 70, 60, 0x00)
    epd.display()

def parse_product_message(message):
    # 1 пробую парсить как JSON с моими 3 полями
    try:
        data = ujson.loads(message)
        if isinstance(data, dict) and 'name' in data and 'weight' in data and 'price' in data:
            return data
    except:
        pass
    
    # 2 name,weight,price
    if ',' in message and message.count(',') == 2:
        parts = message.split(',')
        if len(parts) == 3:
            return {
                'name': parts[0].strip(),
                'weight': parts[1].strip(),
                'price': parts[2].strip()
            }
    
    # 3 name=value;weight=value;price=value
    if ';' in message and '=' in message:
        result = {}
        parts = message.split(';')
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                result[key.strip()] = value.strip()
        
        if 'name' in result and 'weight' in result and 'price' in result:
            return result
    
    return None

def read_products_from_file(filename="product_list.txt"):
    products = []
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    product = parse_product_message(line)
                    if product:
                        products.append(product)
    except:
        pass                    # или нет или он пуст
    return products

def save_products_to_file(products, filename="product_list.txt"):
    try:
        with open(filename, "w") as f:
            for product in products:
                f.write(f"{product['name']},{product['weight']},{product['price']}\n")
        return True
    except Exception as e:
        print(f"Error saving to file: {e}")
        return False

def update_or_add_product(products, new_product):
    for i, product in enumerate(products):
        if product['name'] == new_product['name']:
            products[i] = new_product
            return products, "updated"
    
    products.append(new_product)
    return products, "added"

def show_last_product(epd, products):
    if products:
        last_product = products[-1]
        draw_price_tag_with_data(epd, last_product['name'], last_product['weight'], last_product['price'])
        return True
    else:
        draw_waiting_message(epd)
        return False


# первый байт - ADDH (адрес высокого уровня) отправителя, в бродкасте вижу 0xFF
# второй байт - ADDL (адрес низкого уровня) отправителя, в бродкасте вижу 0xFF
# третий байт - CHAN (канал), в моем случае 0x17 (23 в dec: 0x17 = 1 * 16 + 7 = 16 + 7 = 23)
def extract_message_from_raw(raw_data):
    if not raw_data: return ""
    
    if isinstance(raw_data, bytes):
        # минус префикс бродкаста (первые 3 байта И если они есть)
        if len(raw_data) >= 3 and raw_data[0:2] == b'\xff\xff':
            message_bytes = raw_data[3:]
        elif len(raw_data) >= 1 and raw_data[0] == 0x17:
            # первый байт 0x17
            message_bytes = raw_data[1:]
        else:
            message_bytes = raw_data
        
        try:
            return message_bytes.decode('utf-8')
        except:
            try:
                return str(message_bytes)
            except:
                return ""
    else:
        return str(raw_data)

def main():
    uart2 = UART(2)
    lora = LoRaE32('433T20D', uart2, aux_pin=5, m0_pin=25, m1_pin=26)
    code = lora.begin()
    print(f"LoRa init: {ResponseStatusCode.get_description(code)}")

    # натсроийл LoRa на прием всех сообщений как в receiving_all_string_messages_in_the_channel.py
    config = Configuration('433T20D')
    config.ADDL = BROADCAST_ADDRESS
    config.ADDH = BROADCAST_ADDRESS
    config.OPTION.fixedTransmission = FixedTransmission.FIXED_TRANSMISSION
    code, _ = lora.set_configuration(config)
    print(f"LoRa config: {ResponseStatusCode.get_description(code)}")



    epd = init_display()

    products = read_products_from_file()
    print(f"Loaded {len(products)} products from file")
    
    # последний продукт или ожидание
    show_last_product(epd, products)
    
    # буфер для сборки сообщений
    msg_buffer = MessageBuffer()
    print("Waiting for LoRa messages...")
    
    while True:
        if lora.uart.any() > 0:
            raw_data = lora.uart.read()
            if raw_data:
                message = extract_message_from_raw(raw_data)
                print(f"Received raw: {raw_data}")
                print(f"Extracted message: {message}")
                
                msg_buffer.add_fragment(message)
                
                json_str = msg_buffer.try_extract_json()
                while json_str:
                    print(f"extracted JSON from buffer: {json_str}")
                    
                    product_data = parse_product_message(json_str)
                    if product_data:
                        print(f"Parsed product: {product_data}")
                        products, action = update_or_add_product(products, product_data)
                        print(f"Product {action}: {product_data['name']}")
                        
                        # пока в products всегда 1 элемент
                        if save_products_to_file(products):
                            print(f"Saved {len(products)} products to file")
                        
                        # пока ласт продукта
                        show_last_product(epd, products)
                    else:
                        print(f"Could not parse JSON: {json_str}")
                    
                    # извлечение следующего JSONа из буфера
                    json_str = msg_buffer.try_extract_json()
        
        if msg_buffer.is_timed_out():
            if msg_buffer.buffer:
                print(f"Buffer timeout, clearing incomplete data: {msg_buffer.buffer}")
                msg_buffer.clear()
        
        utime.sleep_ms(100)

# для REPL
def view_products():
    products = read_products_from_file()
    if products:
        print(f"\nTotal products: {len(products)}")
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['name']}: {product['weight']}kg, {product['price']}rub/kg")
    else:
        print("No products in file")

def delete_product(product_name):
    products = read_products_from_file()
    new_products = [p for p in products if p['name'] != product_name]
    
    if len(new_products) < len(products):
        save_products_to_file(new_products)
        print(f"Deleted '{product_name}'")
        return True
    else:
        print(f"Product '{product_name}' not found")
        return False

def clear_all_products():
    save_products_to_file([])
    print("All products cleared")

def show_file_size():
    import os
    try:
        stat = os.stat("product_list.txt")
        print(f"File size: {stat[6]} bytes")
    except:
        print("File not found")

if __name__ == "__main__":
    main()