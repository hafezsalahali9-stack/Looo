from flask import Flask, render_template, request, jsonify, session
import sqlite3
import random
import time
import threading

app = Flask(__name__)
app.secret_key = 'my-secret-key-2024'

DATABASE = '/tmp/lottery.db'

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
            ticket_number INTEGER NOT NULL
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
        INSERT OR IGNORE INTO state (key, value) VALUES ('tickets', '0');
        INSERT OR IGNORE INTO state (key, value) VALUES ('active', '0');
        INSERT OR IGNORE INTO state (key, value) VALUES ('winner_id', '');
        INSERT OR IGNORE INTO state (key, value) VALUES ('winner_idx', '-1');
    ''')
    db.commit()
    db.close()

def get_state(k):
    db = get_db()
    r = db.execute('SELECT value FROM state WHERE key=?', (k,)).fetchone()
    db.close()
    return r['value'] if r else ''

def set_state(k, v):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (k, str(v)))
    db.commit()
    db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/state')
def api_state():
    if 'user_id' not in session:
        return jsonify({
            'logged_in': False, 'user': None,
            'ticket_count': int(get_state('tickets')),
            'lottery_active': get_state('active') == '1',
            'winner_id': '', 'winner_index': -1
        })
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.close()
    if not u:
        session.pop('user_id', None)
        return jsonify({'logged_in': False, 'user': None, 'ticket_count': 0})
    return jsonify({
        'logged_in': True,
        'user': {'id': u['id'], 'balance': u['balance'], 'free_balance': u['free_balance'], 'last_ad_time': u['last_ad_time']},
        'ticket_count': int(get_state('tickets')),
        'lottery_active': get_state('active') == '1',
        'winner_id': get_state('winner_id'),
        'winner_index': int(get_state('winner_idx'))
    })

@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    phone = d.get('phone', '').strip()
    pwd = d.get('password', '').strip()
    if not phone or not pwd:
        return jsonify({'error': 'املأ الحقول'})
    db = get_db()
    if db.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone():
        db.close()
        return jsonify({'error': 'الرقم مسجل'})
    db.execute('INSERT INTO users (phone, password) VALUES (?,?)', (phone, pwd))
    db.commit()
    uid = db.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone()['id']
    db.close()
    session['user_id'] = uid
    return jsonify({'message': 'تم التسجيل'})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    phone = d.get('phone', '').strip()
    pwd = d.get('password', '').strip()
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE phone=? AND password=?', (phone, pwd)).fetchone()
    db.close()
    if not u:
        return jsonify({'error': 'بيانات خاطئة'})
    session['user_id'] = u['id']
    return jsonify({'message': 'تم الدخول'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم الخروج'})

@app.route('/api/buy', methods=['POST'])
def buy():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if u['balance'] < 10000:
        db.close()
        return jsonify({'error': 'رصيد غير كاف'})
    tc = int(get_state('tickets'))
    if tc >= 50 or get_state('active') == '1':
        db.close()
        return jsonify({'error': 'اكتملت البطاقات'})
    db.execute('UPDATE users SET balance=balance-10000 WHERE id=?', (session['user_id'],))
    nn = tc + 1
    db.execute('INSERT INTO tickets (user_id, ticket_number) VALUES (?,?)', (session['user_id'], nn))
    db.commit()
    set_state('tickets', str(nn))
    db.close()
    if nn == 50:
        threading.Thread(target=draw).start()
    return jsonify({'message': f'تم شراء البطاقة رقم {nn}'})

def draw():
    time.sleep(2)
    db = get_db()
    tickets = db.execute('SELECT * FROM tickets').fetchall()
    if len(tickets) != 50:
        db.close()
        return
    w = random.choice(tickets)
    set_state('active', '1')
    set_state('winner_id', str(w['user_id']))
    set_state('winner_idx', str(list(tickets).index(w)))
    db.execute('UPDATE users SET balance=balance+250000 WHERE id=?', (w['user_id'],))
    db.commit()
    time.sleep(5)
    db.execute('DELETE FROM tickets')
    db.commit()
    set_state('tickets', '0')
    set_state('active', '0')
    set_state('winner_id', '')
    set_state('winner_idx', '-1')
    db.close()

@app.route('/api/deposit', methods=['POST'])
def deposit():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول'})
    d = request.get_json()
    amt = d.get('amount')
    img = d.get('image')
    if not amt or amt <= 0:
        return jsonify({'error': 'مبلغ غير صحيح'})
    db = get_db()
    db.execute('INSERT INTO deposits (user_id, amount, image, timestamp) VALUES (?,?,?,?)',
               (session['user_id'], amt, img, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message': 'تم إرسال طلب الإيداع'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول'})
    d = request.get_json()
    acc = d.get('account', '').strip()
    amt = d.get('amount')
    if not acc or not amt or amt <= 0:
        return jsonify({'error': 'بيانات ناقصة'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if u['balance'] < amt:
        db.close()
        return jsonify({'error': 'رصيد غير كاف'})
    db.execute('INSERT INTO withdrawals (user_id, account, amount, timestamp) VALUES (?,?,?,?)',
               (session['user_id'], acc, amt, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message': 'تم إرسال طلب السحب'})

@app.route('/api/spin', methods=['POST'])
def spin():
    if 'user_id' not in session:
        return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    now = time.time()
    if now - u['last_ad_time'] < 30:
        db.close()
        return jsonify({'error': f'انتظر {int(30 - (now - u["last_ad_time"]))} ثانية'})
    prize = random.choice([500, 1000, 2000, 5000, 10000, 20000, 30000, 50000])
    db.execute('UPDATE users SET free_balance=free_balance+?, last_ad_time=? WHERE id=?', (prize, now, session['user_id']))
    db.commit()
    db.close()
    return jsonify({'prize': prize})

@app.route('/api/admin/deposits')
def admin_deposits():
    db = get_db()
    rows = db.execute('SELECT * FROM deposits ORDER BY id DESC').fetchall()
    db.close()
    return jsonify([{'id': r['id'], 'amount': r['amount'], 'image': r['image'], 'timestamp': r['timestamp'], 'status': r['status']} for r in rows])

@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    db = get_db()
    rows = db.execute('SELECT * FROM withdrawals ORDER BY id DESC').fetchall()
    db.close()
    return jsonify([{'id': r['id'], 'amount': r['amount'], 'account': r['account'], 'timestamp': r['timestamp'], 'status': r['status']} for r in rows])

@app.route('/admin/approve-deposits', methods=['POST'])
def approve_deposits():
    db = get_db()
    for r in db.execute('SELECT * FROM deposits WHERE status="معلق"').fetchall():
        db.execute('UPDATE users SET balance=balance+? WHERE id=?', (r['amount'], r['user_id']))
        db.execute('UPDATE deposits SET status="مؤكد" WHERE id=?', (r['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'تم تأكيد الإيداعات'})

@app.route('/admin/approve-withdrawals', methods=['POST'])
def approve_withdrawals():
    db = get_db()
    for r in db.execute('SELECT * FROM withdrawals WHERE status="معلق"').fetchall():
        u = db.execute('SELECT balance FROM users WHERE id=?', (r['user_id'],)).fetchone()
        if u and u['balance'] >= r['amount']:
            db.execute('UPDATE users SET balance=balance-? WHERE id=?', (r['amount'], r['user_id']))
            db.execute('UPDATE withdrawals SET status="مؤكد" WHERE id=?', (r['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'تمت معالجة السحوبات'})

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
