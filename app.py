from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
from datetime import datetime
import json
from esp_sender import esp_sender
from esp_connector import esp_connector
from config import ESP_DEVICES

app = Flask(__name__)
app.secret_key = 'dev-secret-key-123'

# Заранее заданные данные ценников (только необходимые поля)
PRICE_TAGS = [
    {
        "id": 11,
        "name": "Shluz",
        "current_price": 0,
        "weight": 0.5,  # Вес в кг
        "battery_level": 85,
        "last_seen": datetime.now().isoformat(),
        "esp_ip": "10.133.210.157"  # РЕАЛЬНЫЙ IP ESP32
    }
]

# Пользователи (только admin)
USERS = {
    "admin": {"password": "admin123", "role": "admin"}
}

# Текущая сессия (простая имитация)
current_user = None
user_role = None

# Функция для сортировки данных
def sort_tags(tags, sort_by='name', sort_order='asc'):
    """Сортировка списка ценников"""
    reverse = (sort_order == 'desc')
    
    if sort_by == 'name':
        return sorted(tags, key=lambda x: x['name'].lower(), reverse=reverse)
    elif sort_by == 'current_price':
        return sorted(tags, key=lambda x: x['current_price'], reverse=reverse)
    elif sort_by == 'weight':
        return sorted(tags, key=lambda x: x['weight'], reverse=reverse)
    elif sort_by == 'battery_level':
        return sorted(tags, key=lambda x: x['battery_level'], reverse=reverse)
    elif sort_by == 'last_seen':
        return sorted(tags, key=lambda x: x['last_seen'], reverse=reverse)
    else:
        return tags

# Главная страница
@app.route('/')
def index():
    """Главная страница"""
    if not current_user:
        return redirect('/login')
    
    # Статистика
    total_tags = len(PRICE_TAGS)
    
    # Информация о последнем обновлении
    last_update = max(tag['last_seen'] for tag in PRICE_TAGS) if PRICE_TAGS else "Нет данных"
    
    return render_template('index.html',
                         total_tags=total_tags,
                         last_update=last_update,
                         PRICE_TAGS=PRICE_TAGS, 
                         current_user=current_user,
                         user_role=user_role)

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    global current_user, user_role
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username]["password"] == password:
            current_user = username
            user_role = USERS[username]["role"]
            flash(f'Добро пожаловать, {username}!', 'success')
            return redirect('/')
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

# Выход
@app.route('/logout')
def logout():
    global current_user, user_role
    current_user = None
    user_role = None
    flash('Вы вышли из системы', 'info')
    return redirect('/login')

# Список всех ценников с сортировкой
@app.route('/tags')
def tags_list():
    if not current_user:
        return redirect('/login')
    
    tags = PRICE_TAGS.copy()
    
    # Фильтрация
    search = request.args.get('search', '')
    
    # Сортировка
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')
    
    if search:
        tags = [t for t in tags if search.lower() in t['name'].lower()]
    
    # Применяем сортировку
    tags = sort_tags(tags, sort_by, sort_order)
    
    return render_template('tags.html',
                         tags=tags,
                         search=search,
                         sort_by=sort_by,
                         sort_order=sort_order,
                         current_user=current_user,
                         user_role=user_role)

# Детальная информация о ценнике
@app.route('/tag/<int:tag_id>')
def tag_detail(tag_id):
    if not current_user:
        return redirect('/login')
    
    tag = next((t for t in PRICE_TAGS if t['id'] == tag_id), None)
    if not tag:
        flash('Ценник не найден', 'danger')
        return redirect('/tags')
    
    return render_template('tag_detail.html',
                         tag=tag,
                         current_user=current_user,
                         user_role=user_role)

# Редактирование ценника
@app.route('/tag/<int:tag_id>/edit', methods=['GET', 'POST'])
def edit_tag(tag_id):
    if not current_user:
        return redirect('/login')
    
    # Находим ценник
    tag_index = next((i for i, t in enumerate(PRICE_TAGS) if t['id'] == tag_id), None)
    if tag_index is None:
        flash('Ценник не найден', 'danger')
        return redirect('/tags')
    
    tag = PRICE_TAGS[tag_index]
    
    if request.method == 'POST':
        # Получаем данные из формы
        new_name = request.form['name'].strip()
        new_current_price = float(request.form['current_price'])
        new_weight = float(request.form['weight'])
        
        # Сохраняем старые значения для сравнения
        old_name = tag['name']
        old_price = tag['current_price']
        old_weight = tag['weight']
        
        # Определяем, какие поля изменились
        fields_changed = {
            'name': old_name != new_name,
            'current_price': old_price != new_current_price,
            'weight': old_weight != new_weight
        }
        
        # Обновляем данные в системе
        tag['name'] = new_name
        tag['current_price'] = new_current_price
        tag['weight'] = new_weight
        
        # Флаг, были ли изменения
        any_changes = any(fields_changed.values())
        
        if not any_changes:
            flash('Данные не изменились', 'info')
            return redirect(f'/tag/{tag_id}')
        
        # Формируем сообщение о сохранении
        changed_fields_list = []
        for field, changed in fields_changed.items():
            if changed:
                if field == 'name':
                    changed_fields_list.append('Название')
                elif field == 'current_price':
                    changed_fields_list.append('Цена')
                elif field == 'weight':
                    changed_fields_list.append('Вес')
        
        # Сообщение о сохраненных полях
        if changed_fields_list:
            flash(f'Изменения сохранены: {", ".join(changed_fields_list)}', 'success')
        
        # === ОТПРАВКА НА ESP32 (если есть изменения) ===
        try:
            print(f"\n{'='*60}")
            print(f"ОТПРАВКА НА ESP32 ({tag['esp_ip']})")
            print(f"{'='*60}")
            
            # Формируем данные для ESP32 (убраны ненужные поля)
            esp_data = {
                "device_id": str(tag_id),
                "product_name": tag['name'],
                "current_price": float(tag['current_price']),
                "weight": float(tag['weight'])
            }
            
            print(f"Данные для ESP32:")
            print(json.dumps(esp_data, ensure_ascii=False, indent=2))
            
            # Отправляем на ESP32
            send_result = esp_sender.send_to_esp(tag['esp_ip'], esp_data)
            
            if send_result['success']:
                print(f"УСПЕШНО ОТПРАВЛЕНО!")
                print(f"   IP: {tag['esp_ip']}")
                print(f"   Статус: HTTP {send_result.get('status_code', 'N/A')}")
                
                flash(f'📡 Отправлено на ESP32', 'success')
                
                # Обновляем время последнего обновления
                tag['last_seen'] = datetime.now().isoformat()
                
                # Обновляем батарею из ответа
                if 'response_data' in send_result:
                    resp = send_result['response_data']
                    if 'battery' in resp:
                        tag['battery_level'] = resp['battery']
                        
            else:
                print(f"ОШИБКА ОТПРАВКИ!")
                print(f"   IP: {tag['esp_ip']}")
                print(f"   Ошибка: {send_result.get('error', 'unknown')}")
                
                error_msg = send_result.get('message', 'Неизвестная ошибка')
                
                # Уточняем сообщение об ошибке
                if 'connection_error' in str(send_result.get('error', '')):
                    error_msg = f'Не удалось подключиться к ESP32'
                elif 'timeout' in str(send_result.get('error', '')):
                    error_msg = f'ESP32 не отвечает'
                
                flash(f'Ошибка отправки на ESP32: {error_msg}', 'warning')
            
            print(f"{'='*60}\n")
                
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
            import traceback
            traceback.print_exc()
            
            flash(f'Ошибка при отправке: {str(e)[:100]}', 'danger')
        
        return redirect(f'/tag/{tag_id}')
    
    # GET запрос - показываем форму
    return render_template('tag_edit.html',
                         tag=tag,
                         current_user=current_user,
                         user_role=user_role)

@app.route('/api/esp/test/<int:tag_id>', methods=['GET', 'POST'])
def test_esp_connection(tag_id):
    """API для тестирования соединения с ESP32"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    # Находим ценник
    tag = next((t for t in PRICE_TAGS if t['id'] == tag_id), None)
    if not tag:
        return jsonify({'error': 'Ценник не найден'}), 404
    
    # Если POST запрос - получаем endpoint из данных
    if request.method == 'POST':
        data = request.json or {}
        endpoint = data.get('endpoint', '/api/price')
    else:
        endpoint = '/api/price'
    
    print(f"\n{'='*60}")
    print(f"ТЕСТ СОЕДИНЕНИЯ С ESP32")
    print(f"{'='*60}")
    print(f"Ценник ID: {tag_id}")
    print(f"IP: {tag['esp_ip']}")
    print(f"Endpoint: {endpoint}")
    print(f"{'='*60}")
    
    # Тестируем соединение
    test_result = esp_sender.test_connection(
        ip_address=tag['esp_ip'],
        tag_id=str(tag_id),
        endpoint=endpoint
    )
    
    # Обновляем статус устройства
    if test_result['success']:
        tag['last_seen'] = datetime.now().isoformat()
        
        # Flash сообщение об успехе
        success_message = f"Соединение с ESP32 установлено! IP: {tag['esp_ip']}"
        if test_result.get('status_code'):
            success_message += f", Статус: HTTP {test_result['status_code']}"
        if test_result.get('response_data'):
            resp = test_result['response_data']
            if 'battery' in resp:
                tag['battery_level'] = resp['battery']
                success_message += f", Батарея: {resp['battery']}%"
        
        flash(success_message, 'success')
        print(f"УСПЕШНОЕ СОЕДИНЕНИЕ!")
    else:
        # Flash сообщение об ошибке
        error_message = f"Не удалось подключиться к ESP32 ({tag['esp_ip']})"
        flash(error_message, 'danger')
        print(f"ОШИБКА СОЕДИНЕНИЯ!")
    
    print(f"{'='*60}\n")
    
    return jsonify(test_result)

@app.route('/api/esp/send-test/<int:tag_id>', methods=['POST'])
def send_test_data_to_esp(tag_id):
    """Отправка тестовых данных на ESP32"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    tag = next((t for t in PRICE_TAGS if t['id'] == tag_id), None)
    if not tag:
        return jsonify({'error': 'Ценник не найден'}), 404
    
    # Данные для отправки (убраны ненужные поля)
    data = request.json or {}
    
    test_data = {
        "device_id": str(tag_id),
        "product_name": data.get('product_name', 'ТЕСТОВЫЙ ТОВАР'),
        "current_price": float(data.get('current_price', 99.99)),
        "weight": float(data.get('weight', 0.5))
    }
    
    result = esp_sender.send_to_esp(tag['esp_ip'], test_data)
    
    # Обновляем статус устройства
    if result['success']:
        tag['last_seen'] = datetime.now().isoformat()
        
        # Flash сообщение об успехе
        success_msg = f"Тестовые данные отправлены на ESP32! IP: {tag['esp_ip']}"
        if result.get('status_code'):
            success_msg += f", Статус: HTTP {result['status_code']}"
        flash(success_msg, 'success')
        
        # Обновляем батарею если есть
        if 'response_data' in result:
            resp = result['response_data']
            if 'battery' in resp:
                tag['battery_level'] = resp['battery']
    else:
        # Flash сообщение об ошибке
        error_msg = f"Ошибка отправки теста на ESP32 ({tag['esp_ip']})"
        flash(error_msg, 'danger')
    
    return jsonify(result)

# Добавляем новый endpoint для проверки статуса ESP32
@app.route('/api/esp/status/<int:tag_id>')
def esp_status(tag_id):
    """API для получения статуса ESP32 устройства"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    status = esp_connector.get_device_status(str(tag_id))
    return jsonify(status)

# Добавляем endpoint для сканирования сети
@app.route('/api/esp/scan')
def scan_esp_devices():
    """API для сканирования ESP32 устройств в сети"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    devices = esp_connector.scan_network()
    return jsonify({
        "scan_time": datetime.now().isoformat(),
        "devices_found": len(devices),
        "devices": devices
    })

# Добавляем endpoint для отправки команд дисплею
@app.route('/api/esp/command', methods=['POST'])
def send_esp_command():
    """API для отправки команд на ESP32"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    data = request.json
    tag_id = data.get('tag_id')
    command = data.get('command')
    params = data.get('params', {})
    
    if not tag_id or not command:
        return jsonify({'error': 'Не указаны tag_id или command'}), 400
    
    result = esp_connector.send_display_command(tag_id, command, params)
    return jsonify(result)

# Массовое обновление цен
@app.route('/batch-update', methods=['POST'])
def batch_update():
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    data = request.json
    updates = data.get('updates', [])
    
    results = []
    
    for update in updates:
        tag_id = update.get('tag_id')
        new_price = update.get('current_price')
        new_weight = update.get('weight')
        
        if not tag_id:
            results.append({
                "tag_id": tag_id,
                "status": "error",
                "message": "Отсутствует ID ценника"
            })
            continue
        
        tag_index = next((i for i, t in enumerate(PRICE_TAGS) if t['id'] == tag_id), None)
        
        if tag_index is None:
            results.append({
                "tag_id": tag_id,
                "status": "error",
                "message": "Ценник не найден"
            })
            continue
        
        tag = PRICE_TAGS[tag_index]
        
        # Обновляем данные
        if new_price is not None:
            tag['current_price'] = new_price
        
        if new_weight is not None:
            tag['weight'] = new_weight
        
        results.append({
            "tag_id": tag_id,
            "status": "success"
        })
        
        # Отправляем на ESP32
        try:
            price_data = {
                'name': tag['name'],
                'current_price': tag['current_price'],
                'weight': tag['weight']
            }
            
            esp_result = esp_connector.send_price_update(str(tag_id), price_data)
            
            if esp_result['success']:
                tag['last_seen'] = datetime.now().isoformat()
                
        except Exception as e:
            print(f"Ошибка отправки на ESP32: {e}")
    
    return jsonify({
        "status": "success",
        "message": f"Обновлено {len(results)} ценников",
        "results": results
    })

# API для получения данных
@app.route('/api/tags')
def api_tags():
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    return jsonify(PRICE_TAGS)

@app.route('/api/tag/<int:tag_id>')
def api_tag(tag_id):
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    tag = next((t for t in PRICE_TAGS if t['id'] == tag_id), None)
    if not tag:
        return jsonify({'error': 'Ценник не найден'}), 404
    
    return jsonify(tag)

@app.route('/api/stats')
def api_stats():
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    total_tags = len(PRICE_TAGS)
    
    return jsonify({
        'total_tags': total_tags,
        'last_update': datetime.now().isoformat()
    })

@app.route('/api/esp/send-direct', methods=['POST'])
def send_direct_to_esp():
    """Прямая отправка на указанный IP"""
    if not current_user:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    data = request.json
    ip_address = data.get('ip')
    esp_data = data.get('data')
    
    if not ip_address or not esp_data:
        return jsonify({'error': 'Не указаны IP или данные'}), 400
    
    result = esp_sender.send_to_esp(ip_address, esp_data)
    return jsonify(result)

# О проекте
@app.route('/about')
def about():
    return render_template('about.html',
                         current_user=current_user,
                         user_role=user_role)

if __name__ == '__main__':
    print("=" * 60)
    print("СИСТЕМА УПРАВЛЕНИЯ ЭЛЕКТРОННЫМИ ЦЕННИКАМИ")
    print("=" * 60)
    print("Веб-интерфейс: http://localhost:5000")
    print("Доступ: admin / admin123")
    print("=" * 60)
    print(f"Загружено {len(PRICE_TAGS)} ценников")
    print("=" * 60)
    print(f"IP адрес ESP32:")
    for tag in PRICE_TAGS:
        print(f"   {tag['id']}: {tag['esp_ip']}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)