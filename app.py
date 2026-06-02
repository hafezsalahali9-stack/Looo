from flask import Flask, render_template, request, jsonify
import sqlite3, random, time, threading, string

app = Flask(__name__)
app.secret_key = 'secret-key-2024'
DB = '/tmp/lottery.db'

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DB)
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

def gs(k):
    db = get_db()
    r = db.execute('SELECT value FROM state WHERE key=?', (k,)).fetchone()
    db.close()
    return r['value'] if r else ''

def ss(k, v):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (k, str(v)))
    db.commit()
    db.close()

def get_user_by_token(token):
    if not token: return None
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE token=?', (token,)).fetchone()
    db.close()
    return u

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
    if not user:
        return jsonify({'logged_in': False, 'user': None, 'ticket_count': int(gs('tickets')),
                        'lottery_active': gs('active')=='1', 'winner_id': '', 'winner_index': -1})
    return jsonify({'logged_in': True,
                    'user': {'id': user['id'], 'balance': user['balance'],
                             'free_balance': user['free_balance'],
                             'last_spin_time': user['last_spin_time']},
                    'ticket_count': int(gs('tickets')),
                    'lottery_active': gs('active')=='1',
                    'winner_id': gs('winner_id'),
                    'winner_index': int(gs('winner_idx'))})

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
    if not u: db.close(); return jsonify({'error': 'بيانات خاطئة'})
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
    if u['balance'] < 10000: db.close(); return jsonify({'error': 'رصيد غير كاف'})
    tc = int(gs('tickets'))
    if tc >= 50 or gs('active') == '1': db.close(); return jsonify({'error': 'اكتملت البطاقات'})
    db.execute('UPDATE users SET balance=balance-10000 WHERE id=?', (user['id'],))
    nn = tc + 1
    db.execute('INSERT INTO tickets (user_id, ticket_number) VALUES (?,?)', (user['id'], nn))
    db.commit()
    ss('tickets', str(nn))
    db.close()
    if nn == 50: threading.Thread(target=draw).start()
    return jsonify({'message': f'تم شراء البطاقة رقم {nn}'})

def draw():
    time.sleep(2)
    db = get_db()
    tickets = db.execute('SELECT * FROM tickets').fetchall()
    if len(tickets) != 50: db.close(); return
    w = random.choice(tickets)
    ss('active', '1')
    ss('winner_id', str(w['user_id']))
    ss('winner_idx', str(list(tickets).index(w)))
    db.execute('UPDATE users SET balance=balance+250000 WHERE id=?', (w['user_id'],))
    db.commit()
    time.sleep(5)
    db.execute('DELETE FROM tickets')
    db.commit()
    ss('tickets', '0')
    ss('active', '0')
    ss('winner_id', '')
    ss('winner_idx', '-1')
    db.close()

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

@app.route('/api/admin/deposits')
def admin_deposits():
    db = get_db()
    rows = db.execute('SELECT * FROM deposits ORDER BY id DESC').fetchall()
    db.close()
    return jsonify([{'id': r['id'], 'amount': r['amount'], 'image': r['image'],
                     'timestamp': r['timestamp'], 'status': r['status']} for r in rows])

@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    db = get_db()
    rows = db.execute('SELECT * FROM withdrawals ORDER BY id DESC').fetchall()
    db.close()
    return jsonify([{'id': r['id'], 'amount': r['amount'], 'account': r['account'],
                     'timestamp': r['timestamp'], 'status': r['status']} for r in rows])

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
