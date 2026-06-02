from flask import Flask, render_template, request, jsonify
import sqlite3, random, time, threading, string, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret-2024'

DATABASE = '/tmp/lottery.db'
TICKET_PRICE = 10000
JACKPOT_PERCENT = 0.75
SLOT_COST = 500  # تكلفة دورة السلوتس

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            token TEXT,
            balance INTEGER DEFAULT 0,
            free_balance INTEGER DEFAULT 0,
            last_spin_time REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            round_id INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            image TEXT,
            timestamp TEXT,
            status TEXT DEFAULT 'معلق'
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account TEXT NOT NULL,
            amount INTEGER NOT NULL,
            timestamp TEXT,
            status TEXT DEFAULT 'معلق'
        );
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO state (key, value) VALUES ('ticket_counter', '0');
        INSERT OR IGNORE INTO state (key, value) VALUES ('last_draw', '0');
        INSERT OR IGNORE INTO state (key, value) VALUES ('current_round', '1');
    ''')
    db.commit()
    db.close()

def gs(key):
    db = get_db()
    r = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
    db.close()
    return r['value'] if r else ''

def ss(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, str(value)))
    db.commit()
    db.close()

def get_user_by_token(token):
    if not token:
        return None
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE token=?', (token,)).fetchone()
    db.close()
    return u

# ====================== نظام السحب كل ساعة ======================
def draw_scheduler():
    while True:
        time.sleep(10)  # فحص كل 10 ثوان
        try:
            db = get_db()
            last_draw = float(gs('last_draw') or 0)
            now = time.time()
            # السحب بعد مرور ساعة (3600 ثانية) من آخر سحب
            if now - last_draw >= 3600:
                current_round = int(gs('current_round'))
                # جلب جميع التذاكر غير المسحوبة (round_id = 0)
                tickets = db.execute('SELECT * FROM tickets WHERE round_id=0').fetchall()
                if tickets:
                    total_tickets = len(tickets)
                    total_value = total_tickets * TICKET_PRICE
                    jackpot = int(total_value * JACKPOT_PERCENT)
                    # اختيار فائز
                    winner_ticket = random.choice(tickets)
                    winner_id = winner_ticket['user_id']
                    # إضافة الجائزة للرصيد
                    db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (jackpot, winner_id))
                    # تحديث حالة التذاكر بأنها استُخدمت في هذه الجولة
                    db.execute('UPDATE tickets SET round_id = ? WHERE round_id = 0', (current_round,))
                    # تحديث عدادات الحالة
                    ss('last_draw', str(now))
                    ss('current_round', str(current_round + 1))
                    # سجل الفائز مؤقتاً (يمكن إظهاره في الصفحة)
                    ss('last_winner_id', str(winner_id))
                    ss('last_jackpot', str(jackpot))
                    db.commit()
                else:
                    # لا توجد تذاكر، نحدّث الوقت فقط لعدم تكرار السحب بدون تذاكر
                    ss('last_draw', str(now))
                db.close()
        except Exception as e:
            print("Draw error:", e)

# بدء خيط جدولة السحب
threading.Thread(target=draw_scheduler, daemon=True).start()

# ====================== روابط الويب ======================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/games')
def games():
    return render_template('games.html')

@app.route('/api/state', methods=['POST'])
def api_state():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    last_draw = float(gs('last_draw') or 0)
    next_draw = last_draw + 3600
    now = time.time()
    seconds_remaining = max(0, int(next_draw - now))
    # حساب عدد التذاكر وقيمة الجائزة المتوقعة
    db = get_db()
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id=0').fetchone()['c']
    total_value = ticket_count * TICKET_PRICE
    expected_jackpot = int(total_value * JACKPOT_PERCENT)
    db.close()

    state = {
        'logged_in': user is not None,
        'user': None,
        'ticket_count': ticket_count,
        'expected_jackpot': expected_jackpot,
        'seconds_remaining': seconds_remaining,
        'last_winner_id': gs('last_winner_id'),
        'last_jackpot': gs('last_jackpot')
    }
    if user:
        state['user'] = {
            'id': user['id'],
            'balance': user['balance'],
            'free_balance': user['free_balance'],
            'last_spin_time': user['last_spin_time']
        }
    return jsonify(state)

@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    ph = d.get('phone', '').strip()
    pw = d.get('password', '').strip()
    if not ph or not pw: return jsonify({'error': 'املأ الحقول'})
    db = get_db()
    if db.execute('SELECT id FROM users WHERE phone=?', (ph,)).fetchone():
        db.close()
        return jsonify({'error': 'الرقم مسجل'})
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    db.execute('INSERT INTO users (phone, password, token) VALUES (?,?,?)', (ph, pw, token))
    db.commit()
    db.close()
    return jsonify({'message': 'تم التسجيل', 'token': token})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    ph = d.get('phone', '').strip()
    pw = d.get('password', '').strip()
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE phone=? AND password=?', (ph, pw)).fetchone()
    if not u:
        db.close()
        return jsonify({'error': 'بيانات خاطئة'})
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    db.execute('UPDATE users SET token=? WHERE id=?', (token, u['id']))
    db.commit()
    db.close()
    return jsonify({'message': 'تم الدخول', 'token': token})

@app.route('/api/buy', methods=['POST'])
def buy():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < TICKET_PRICE:
        db.close()
        return jsonify({'error': 'رصيد غير كاف'})
    # خصم المبلغ وإصدار تذكرة
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (TICKET_PRICE, user['id']))
    ticket_counter = int(gs('ticket_counter')) + 1
    ticket_number = ticket_counter
    db.execute('INSERT INTO tickets (user_id, ticket_number, timestamp, round_id) VALUES (?,?,?,0)',
               (user['id'], ticket_number, time.time()))
    db.commit()
    ss('ticket_counter', str(ticket_counter))
    db.close()
    return jsonify({'message': f'تم شراء البطاقة رقم {ticket_number}', 'ticket_number': ticket_number})

@app.route('/api/spin', methods=['POST'])
def spin():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
    now = time.time()
    if u['last_spin_time'] and (now - u['last_spin_time']) < 60:
        remain = int(60 - (now - u['last_spin_time']))
        db.close()
        return jsonify({'error': f'انتظر {remain} ثانية'})
    prizes = [10, 15, 20, 25, 30, 40, 50, 75, 100]
    prize = random.choice(prizes)
    db.execute('UPDATE users SET free_balance=free_balance+?, last_spin_time=? WHERE id=?',
               (prize, now, user['id']))
    db.commit()
    db.close()
    return jsonify({'prize': prize})

@app.route('/api/deposit', methods=['POST'])
def deposit():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    amt = data.get('amount')
    img = data.get('image')
    if not amt or amt <= 0: return jsonify({'error': 'مبلغ غير صحيح'})
    db = get_db()
    db.execute('INSERT INTO deposits (user_id, amount, image, timestamp) VALUES (?,?,?,?)',
               (user['id'], amt, img, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message': 'تم إرسال طلب الإيداع'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    acc = data.get('account', '').strip()
    amt = data.get('amount')
    if not acc or not amt or amt <= 0: return jsonify({'error': 'بيانات ناقصة'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < amt: db.close(); return jsonify({'error': 'رصيد غير كاف'})
    db.execute('INSERT INTO withdrawals (user_id, account, amount, timestamp) VALUES (?,?,?,?)',
               (user['id'], acc, amt, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message': 'تم إرسال طلب السحب'})

# ====================== لعبة السلوتس (حقيقية بالرصيد) ======================
@app.route('/api/slots', methods=['POST'])
def slots():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < SLOT_COST:
        db.close()
        return jsonify({'error': 'رصيد غير كافٍ للعب (تحتاج ' + str(SLOT_COST) + ' ل.س)'})
    # خصم تكلفة الدورة
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (SLOT_COST, user['id']))
    db.commit()
    # محاكاة نتيجة السلوتس
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '⭐']
    result = [random.choice(symbols) for _ in range(3)]
    win_amount = 0
    if result[0] == result[1] == result[2]:
        win_amount = SLOT_COST * 10  # جائزة كبرى
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        win_amount = SLOT_COST * 2   # تطابق رمزين
    if win_amount > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win_amount, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'result': result, 'win': win_amount, 'balance': new_balance})

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
