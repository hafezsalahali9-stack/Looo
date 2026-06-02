from flask import Flask, render_template, request, jsonify, session
import sqlite3
import random
import time
import threading
import os

app = Flask(__name__)
app.secret_key = 'my-secret-key-2024-unique'

DATABASE = '/tmp/lottery.db'
JACKPOT = 250000
TICKET_PRICE = 10000
MAX_TICKETS = 50
AD_COOLDOWN = 30

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
            balance INTEGER DEFAULT 100000,
            free_balance INTEGER DEFAULT 0,
            last_ad_time REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            round_id INTEGER DEFAULT 1
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
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO app_state (key, value) VALUES ('ticket_count', '0');
        INSERT OR IGNORE INTO app_state (key, value) VALUES ('lottery_active', '0');
        INSERT OR IGNORE INTO app_state (key, value) VALUES ('winner_id', '');
        INSERT OR IGNORE INTO app_state (key, value) VALUES ('winner_index', '-1');
    ''')
    db.commit()
    db.close()

def get_state(key):
    db = get_db()
    row = db.execute('SELECT value FROM app_state WHERE key = ?', (key,)).fetchone()
    val = row['value'] if row else ''
    db.close()
    return val

def set_state(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)', (key, str(value)))
    db.commit()
    db.close()

# ====================== صفحات الويب ======================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

# ====================== API المستخدم ======================

@app.route('/api/state')
def state():
    if 'user_id' not in session:
        return jsonify({
            'logged_in': False,
            'user': None,
            'ticket_count': int(get_state('ticket_count')),
            'lottery_active': get_state('lottery_active') == '1',
            'winner_id': get_state('winner_id'),
            'winner_index': int(get_state('winner_index')),
            'jackpot': JACKPOT
        })
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not user:
        session.pop('user_id', None)
        db.close()
        return jsonify({
            'logged_in': False,
            'user': None,
            'ticket_count': int(get_state('ticket_count')),
            'lottery_active': get_state('lottery_active') == '1',
            'winner_id': get_state('winner_id'),
            'winner_index': int(get_state('winner_index')),
            'jackpot': JACKPOT
        })
    
    ticket_count = int(get_state('ticket_count'))
    db.close()
    
    return jsonify({
        'logged_in': True,
        'user': {
            'id': user['id'],
            'balance': user['balance'],
            'free_balance': user['free_balance'],
            'last_ad_time': user['last_ad_time']
        },
        'ticket_count': ticket_count,
        'lottery_active': get_state('lottery_active') == '1',
        'winner_id': get_state('winner_id'),
        'winner_index': int(get_state('winner_index')),
        'jackpot': JACKPOT
    })

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        if not phone or not password:
            return jsonify({'error': 'الرجاء ملء جميع الحقول'})
        
        db = get_db()
        
        existing = db.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        if existing:
            db.close()
            return jsonify({'error': 'رقم الهاتف مسجل مسبقاً'})
        
        db.execute('INSERT INTO users (phone, password, balance) VALUES (?, ?, ?)', (phone, password, 100000))
        db.commit()
        
        user = db.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        session['user_id'] = user['id']
        db.close()
        
        return jsonify({'message': 'تم التسجيل بنجاح'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        if not phone or not password:
            return jsonify({'error': 'الرجاء ملء جميع الحقول'})
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE phone = ? AND password = ?', (phone, password)).fetchone()
        db.close()
        
        if not user:
            return jsonify({'error': 'بيانات خاطئة'})
        
        session['user_id'] = user['id']
        return jsonify({'message': 'تم الدخول'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم الخروج'})

@app.route('/api/buy', methods=['POST'])
def buy():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول أولاً'})
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if user['balance'] < TICKET_PRICE:
        db.close()
        return jsonify({'error': 'رصيد غير كاف'})
    
    ticket_count = int(get_state('ticket_count'))
    
    if ticket_count >= MAX_TICKETS or get_state('lottery_active') == '1':
        db.close()
        return jsonify({'error': 'اكتملت البطاقات'})
    
    db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (TICKET_PRICE, user['id']))
    new_number = ticket_count + 1
    db.execute('INSERT INTO tickets (user_id, ticket_number) VALUES (?, ?)', (user['id'], new_number))
    db.commit()
    set_state('ticket_count', str(new_number))
    db.close()
    
    if new_number == MAX_TICKETS:
        threading.Thread(target=perform_draw).start()
    
    return jsonify({'message': f'تم شراء البطاقة رقم {new_number}', 'ticket_count': new_number})

def perform_draw():
    time.sleep(2)
    db = get_db()
    tickets = db.execute('SELECT * FROM tickets WHERE round_id = 1').fetchall()
    
    if len(tickets) != MAX_TICKETS:
        db.close()
        return
    
    winner_ticket = random.choice(tickets)
    winner_id = winner_ticket['user_id']
    winner_index = list(tickets).index(winner_ticket)
    
    set_state('lottery_active', '1')
    set_state('winner_id', str(winner_id))
    set_state('winner_index', str(winner_index))
    
    db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (JACKPOT, winner_id))
    db.commit()
    
    time.sleep(6)
    
    db.execute('DELETE FROM tickets WHERE round_id = 1')
    db.commit()
    
    set_state('ticket_count', '0')
    set_state('lottery_active', '0')
    set_state('winner_id', '')
    set_state('winner_index', '-1')
    db.close()

@app.route('/api/deposit_request', methods=['POST'])
def deposit_request():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول أولاً'})
    
    data = request.get_json()
    amount = data.get('amount')
    image = data.get('image')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'مبلغ غير صحيح'})
    
    db = get_db()
    db.execute('INSERT INTO pending_deposits (user_id, amount, image, timestamp) VALUES (?, ?, ?, ?)',
               (session['user_id'], amount, image, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    
    return jsonify({'message': 'تم إرسال طلب الإيداع للمراجعة'})

@app.route('/api/withdraw_request', methods=['POST'])
def withdraw_request():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول أولاً'})
    
    data = request.get_json()
    account = data.get('account', '').strip()
    amount = data.get('amount')
    
    if not account or amount <= 0:
        return jsonify({'error': 'بيانات ناقصة'})
    
    db = get_db()
    user = db.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if user['balance'] < amount:
        db.close()
        return jsonify({'error': 'رصيدك لا يكفي'})
    
    db.execute('INSERT INTO pending_withdrawals (user_id, account, amount, timestamp) VALUES (?, ?, ?, ?)',
               (session['user_id'], account, amount, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    
    return jsonify({'message': 'تم إرسال طلب السحب للمراجعة'})

@app.route('/api/free_spin', methods=['POST'])
def free_spin():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول أولاً'})
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    now = time.time()
    
    if now - user['last_ad_time'] < AD_COOLDOWN:
        remain = int(AD_COOLDOWN - (now - user['last_ad_time']))
        db.close()
        return jsonify({'error': f'انتظر {remain} ثانية'})
    
    prizes = [500, 1000, 2000, 5000, 10000, 20000, 30000, 50000]
    prize = random.choice(prizes)
    
    db.execute('UPDATE users SET free_balance = free_balance + ?, last_ad_time = ? WHERE id = ?',
               (prize, now, user['id']))
    db.commit()
    db.close()
    
    return jsonify({'prize': prize})

# ====================== API الإدارة ======================

@app.route('/api/admin/deposits')
def admin_deposits():
    db = get_db()
    deps = db.execute('SELECT * FROM pending_deposits ORDER BY id DESC').fetchall()
    db.close()
    
    result = []
    for d in deps:
        result.append({
            'id': d['id'],
            'amount': d['amount'],
            'image': d['image'],
            'timestamp': d['timestamp'],
            'status': d['status']
        })
    return jsonify(result)

@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    db = get_db()
    wits = db.execute('SELECT * FROM pending_withdrawals ORDER BY id DESC').fetchall()
    db.close()
    
    result = []
    for w in wits:
        result.append({
            'id': w['id'],
            'amount': w['amount'],
            'account': w['account'],
            'timestamp': w['timestamp'],
            'status': w['status']
        })
    return jsonify(result)

@app.route('/admin/approve_deposits', methods=['POST'])
def approve_deposits():
    db = get_db()
    deposits = db.execute('SELECT * FROM pending_deposits WHERE status = ?', ('معلق',)).fetchall()
    
    for d in deposits:
        db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (d['amount'], d['user_id']))
        db.execute('UPDATE pending_deposits SET status = ? WHERE id = ?', ('مؤكد', d['id']))
    
    db.commit()
    db.close()
    
    return jsonify({'message': 'تم تأكيد جميع الإيداعات'})

@app.route('/admin/approve_withdrawals', methods=['POST'])
def approve_withdrawals():
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
    db.close()
    
    return jsonify({'message': 'تمت معالجة طلبات السحب'})

# ====================== بدء التطبيق ======================

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
