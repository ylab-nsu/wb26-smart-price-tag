from pico_display import EPD_2in13_B_V4_Landscape
from lora_e32 import LoRaE32, Configuration, BROADCAST_ADDRESS
from machine import UART
import utime
import ujson

from lora_e32_constants import FixedTransmission
from lora_e32_operation_constant import ResponseStatusCode

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

def read_products_from_file(filename="product_list.txt"):
    """Читает все продукты из txt файла"""
    products = []
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        # Пробуем распарсить как JSON
                        product = ujson.loads(line)
                        if 'name' in product and 'weight' in product and 'price' in product:
                            products.append(product)
                    except:
                        # Если не JSON, пробуем старый формат "name,weight,price"
                        if ',' in line:
                            parts = line.split(',')
                            if len(parts) == 3:
                                products.append({
                                    'name': parts[0].strip(),
                                    'weight': parts[1].strip(),
                                    'price': parts[2].strip()
                                })
    except:
        pass  # Файла нет или он пуст
    return products

def save_products_to_file(products, filename="product_list.txt"):
    try:
        with open(filename, "w") as f:
            for product in products:
                # Сохраняем как JSON строку для простоты парсинга
                f.write(ujson.dumps(product) + "\n")
        return True
    except Exception as e:
        print(f"Error saving to file: {e}")
        return False

def update_or_add_product(products, new_product):
    """Обновляет существующий продукт или добавляет новый"""
    for i, product in enumerate(products):
        if product['name'] == new_product['name']:
            # Обновляем существующий
            products[i] = new_product
            return products, "updated"
    
    # Добавляем новый
    products.append(new_product)
    return products, "added"

def show_last_product(epd, products):
    """Показывает последний продукт на дисплее"""
    if products:
        last_product = products[-1]
        draw_price_tag_with_data(epd, 
                               last_product['name'], 
                               last_product['weight'], 
                               last_product['price'])
        return True
    else:
        draw_waiting_message(epd)
        return False

def extract_message_from_raw(raw_data):
    """Извлекает сообщение из сырых данных LoRa"""
    if isinstance(raw_data, bytes):
        if len(raw_data) >= 3 and raw_data[0:2] == b'\xff\xff':
            # Пропускаем префикс бродкаста (3 байта)
            message_bytes = raw_data[3:]
            try:
                return message_bytes.decode('utf-8')
            except:
                return str(message_bytes)
        else:
            try:
                return raw_data.decode('utf-8')
            except:
                return str(raw_data)
    return raw_data

def view_products():
    products = read_products_from_file()
    if products:
        print(f"\nTotal products: {len(products)}")
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['name']}: {product['weight']}kg, {product['price']}rub/kg")
    else:
        print("No products in file")

def main():
    # Инициализация LoRa
    uart2 = UART(2)
    lora = LoRaE32('433T20D', uart2, aux_pin=5, m0_pin=25, m1_pin=26)
    code = lora.begin()
    print(f"LoRa init: {ResponseStatusCode.get_description(code)}")

    # Настройка LoRa на прием всех сообщений
    config = Configuration('433T20D')
    config.ADDL = BROADCAST_ADDRESS
    config.ADDH = BROADCAST_ADDRESS
    config.OPTION.fixedTransmission = FixedTransmission.FIXED_TRANSMISSION
    code, _ = lora.set_configuration(config)
    print(f"LoRa config: {ResponseStatusCode.get_description(code)}")

    # Инициализация дисплея
    epd = init_display()
    
    # Чтение существующих продуктов
    products = read_products_from_file()
    print(f"Loaded {len(products)} products from file")
    
    # Показываем последний продукт или ожидание
    show_last_product(epd, products)
    
    print("Waiting for LoRa messages...")
    
    while True:
        # Используем прямое чтение из UART (как раньше)
        if lora.uart.any() > 0:
            raw_data = lora.uart.read()
            if raw_data:
                # Извлекаем сообщение
                message = extract_message_from_raw(raw_data)
                print(f"Received raw: {raw_data}")
                print(f"Extracted message: {message}")
                
                try:
                    # Пробуем распарсить как JSON
                    product_data = ujson.loads(message)
                    print(f"Parsed as JSON: {product_data}")
                except:
                    # Если не JSON, пробуем старый формат
                    print("Not JSON, trying old format...")
                    product_data = None
                    if ',' in message:
                        parts = message.split(',')
                        if len(parts) == 3:
                            product_data = {
                                'name': parts[0].strip(),
                                'weight': parts[1].strip(),
                                'price': parts[2].strip()
                            }
                
                if product_data and 'name' in product_data and 'weight' in product_data and 'price' in product_data:
                    print(f"Valid product data: {product_data}")
                    
                    products, action = update_or_add_product(products, product_data)
                    print(f"Product {action}: {product_data['name']}")
                    
                    if save_products_to_file(products):
                        print(f"Saved {len(products)} products to file")
                    
                    show_last_product(epd, products)
                else:
                    print("Invalid message format or missing fields")
        
        # Небольшая задержка
        utime.sleep_ms(100)

if __name__ == "__main__":
    main()