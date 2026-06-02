import sqlite3
import random
import time
import threading
from flask import Flask, render_template, request, jsonify, session, g

app = Flask(__name__)
app.secret_key = 'clave-secreta-2024-unica'

DATABASE = 'lottery.db'
JACKPOT = 250000
TICKET_PRICE = 10000
MAX_TICKETS = 50
AD_COOLDOWN = 30

# ========== قاعدة البيانات ==========
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT,
                balance INTEGER DEFAULT 0,
                free_balance INTEGER DEFAULT 0,
                last_ad_time REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticket_number INTEGER NOT NULL,
                round_id INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                image TEXT,
                timestamp TEXT,
                status TEXT DEFAULT 'معلق'
            );
            CREATE TABLE IF NOT EXISTS pending_withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                account TEXT NOT NULL,
                amount INTEGER NOT NULL,
                timestamp TEXT,
                status TEXT DEFAULT 'معلق'
            );
            INSERT OR IGNORE INTO app_state (key, value) VALUES ('ticket_count', '0');
            INSERT OR IGNORE INTO app_state (key, value) VALUES ('lottery_active', '0');
            INSERT OR IGNORE INTO app_state (key, value) VALUES ('winner_id', '');
            INSERT OR IGNORE INTO app_state (key, value) VALUES ('winner_index', '-1');
        ''')
        db.commit()

# ========== دوال الحالة ==========
def get_state(key):
    db = get_db()
    row = db.execute('SELECT value FROM app_state WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else ''

def set_state(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)', (key, str(value)))
    db.commit()

def get_current_user():
    if 'user_id' in session:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        return dict(user) if user else None
    return None

# ========== التوجيهات ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def api_state():
    user = get_current_user()
    state = {
        'ticket_count': int(get_state('ticket_count')),
        'lottery_active': get_state('lottery_active') == '1',
        'winner_id': get_state('winner_id'),
        'winner_index': int(get_state('winner_index')),
        'jackpot': JACKPOT,
        'logged_in': user is not None,
        'user': None
    }
    if user:
        state['user'] = {
            'id': user['id'],
            'balance': user['balance'],
            'free_balance': user['free_balance'],
            'last_ad_time': user['last_ad_time']
        }
    return jsonify(state)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    if not phone or not password:
        return jsonify({'error': 'الرجاء ملء الحقول'}), 400
    db = get_db()
    if db.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone():
        return jsonify({'error': 'رقم الهاتف مسجل مسبقاً'}), 400
    db.execute('INSERT INTO users (phone, password, name) VALUES (?, ?, ?)', (phone, password, phone))
    db.commit()
    user_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    session['user_id'] = user_id
    return jsonify({'message': 'تم التسجيل'})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    if not phone or not password:
        return jsonify({'error': 'الرجاء ملء الحقول'}), 400
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE phone = ? AND password = ?', (phone, password)).fetchone()
    if not user:
        return jsonify({'error': 'بيانات خاطئة'}), 401
    session['user_id'] = user['id']
    return jsonify({'message': 'تم الدخول'})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم الخروج'})

@app.route('/api/buy', methods=['POST'])
def api_buy():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'سجل الدخول أولاً'}), 401

    db = get_db()
    try:
        with db:
            user_balance = db.execute('SELECT balance FROM users WHERE id = ?', (user['id'],)).fetchone()['balance']
            if user_balance < TICKET_PRICE:
                return jsonify({'error': 'رصيدك غير كافٍ'}), 400

            ticket_count = int(get_state('ticket_count'))
            if ticket_count >= MAX_TICKETS or get_state('lottery_active') == '1':
                return jsonify({'error': 'اكتملت البطاقات أو السحب جارٍ'}), 400

            db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (TICKET_PRICE, user['id']))
            new_number = ticket_count + 1
            db.execute('INSERT INTO tickets (user_id, ticket_number) VALUES (?, ?)', (user['id'], new_number))
            set_state('ticket_count', str(new_number))

            if new_number == MAX_TICKETS:
                threading.Thread(target=perform_lottery_draw).start()

        return jsonify({'message': f'تم شراء البطاقة رقم {new_number}', 'ticket_count': new_number})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def perform_lottery_draw():
    with app.app_context():
        db = get_db()
        try:
            tickets = db.execute('SELECT * FROM tickets WHERE round_id = 1').fetchall()
            if len(tickets) != MAX_TICKETS:
                return
            winner_ticket = random.choice(tickets)
            winner_id = winner_ticket['user_id']
            winner_index = list(tickets).index(winner_ticket)

            set_state('lottery_active', '1')
            set_state('winner_id', str(winner_id))
            set_state('winner_index', str(winner_index))

            db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (JACKPOT, winner_id))
            db.commit()

            time.sleep(5)
            db.execute('DELETE FROM tickets WHERE round_id = 1')
            set_state('ticket_count', '0')
            set_state('lottery_active', '0')
            set_state('winner_id', '')
            set_state('winner_index', '-1')
            db.commit()
        except Exception as e:
            print(f"خطأ في السحب: {e}")

@app.route('/api/deposit_request', methods=['POST'])
def deposit_request():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'تسجيل الدخول أولاً'}), 401
    data = request.json
    amount = data.get('amount')
    image = data.get('image')
    if not amount or amount <= 0:
        return jsonify({'error': 'مبلغ غير صحيح'}), 400
    db = get_db()
    db.execute('INSERT INTO pending_deposits (user_id, amount, image, timestamp) VALUES (?, ?, ?, ?)',
               (user['id'], amount, image, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    return jsonify({'message': 'تم إرسال الطلب للمراجعة'})

@app.route('/api/withdraw_request', methods=['POST'])
def withdraw_request():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'تسجيل الدخول أولاً'}), 401
    data = request.json
    account = data.get('account', '').strip()
    amount = data.get('amount')
    if not account or amount <= 0:
        return jsonify({'error': 'بيانات ناقصة'}), 400
    if amount > user['balance']:
        return jsonify({'error': 'رصيدك لا يكفي'}), 400
    db = get_db()
    db.execute('INSERT INTO pending_withdrawals (user_id, account, amount, timestamp) VALUES (?, ?, ?, ?)',
               (user['id'], account, amount, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    return jsonify({'message': 'تم إرسال طلب السحب للمراجعة'})

@app.route('/api/free_spin', methods=['POST'])
def free_spin():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'تسجيل الدخول أولاً'}), 401
    now = time.time()
    if now - user['last_ad_time'] < AD_COOLDOWN:
        remain = int(AD_COOLDOWN - (now - user['last_ad_time']))
        return jsonify({'error': f'انتظر {remain} ثانية'}), 429
    prizes = [500, 1000, 2000, 5000, 10000, 20000, 30000, 50000]
    prize = random.choice(prizes)
    db = get_db()
    db.execute('UPDATE users SET free_balance = free_balance + ?, last_ad_time = ? WHERE id = ?',
               (prize, now, user['id']))
    db.commit()
    return jsonify({'prize': prize, 'free_balance': user['free_balance'] + prize})

@app.route('/admin/approve_deposits', methods=['POST'])
def admin_approve_deposits():
    db = get_db()
    deposits = db.execute('SELECT * FROM pending_deposits WHERE status = ?', ('معلق',)).fetchall()
    for dep in deposits:
        db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (dep['amount'], dep['user_id']))
        db.execute('UPDATE pending_deposits SET status = ? WHERE id = ?', ('مؤكد', dep['id']))
    db.commit()
    return jsonify({'message': 'تم تأكيد الإيداعات'})

@app.route('/admin/approve_withdrawals', methods=['POST'])
def admin_approve_withdrawals():
    db = get_db()
    withdrawals = db.execute('SELECT * FROM pending_withdrawals WHERE status = ?', ('معلق',)).fetchall()
    for w in withdrawals:
        user = db.execute('SELECT balance FROM users WHERE id = ?', (w['user_id'],)).fetchone()
        if user and user['balance'] >= w['amount']:
            db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (w['amount'], w['user_id']))
            db.execute('UPDATE pending_withdrawals SET status = ? WHERE id = ?', ('مؤكد', w['id']))
        else:
            db.execute('UPDATE pending_withdrawals SET status = ? WHERE id = ?', ('مرفوض', w['id']))
    db.commit()
    return jsonify({'message': 'تمت معالجة طلبات السحب'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
