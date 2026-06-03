from flask import Flask, render_template, request, jsonify
import sqlite3, random, time, threading, string

app = Flask(__name__)
DATABASE = '/tmp/lottery.db'
TICKET_PRICE = 10000

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
            free_balance INTEGER DEFAULT 0
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
    if not token: return None
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE token=?', (token,)).fetchone()
    db.close()
    return u

def draw_scheduler():
    while True:
        time.sleep(10)
        db = get_db()
        last_draw = float(gs('last_draw') or 0)
        now = time.time()
        if now - last_draw >= 3600:
            current_round = int(gs('current_round'))
            tickets = db.execute('SELECT * FROM tickets WHERE round_id=0').fetchall()
            if tickets:
                total_value = len(tickets) * TICKET_PRICE
                jackpot = int(total_value * 0.75)
                winner_ticket = random.choice(tickets)
                db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (jackpot, winner_ticket['user_id']))
                db.execute('UPDATE tickets SET round_id = ? WHERE round_id = 0', (current_round,))
                ss('last_draw', str(now))
                ss('current_round', str(current_round + 1))
                ss('last_winner_id', str(winner_ticket['user_id']))
                ss('last_jackpot', str(jackpot))
                db.commit()
            else:
                ss('last_draw', str(now))
        db.close()

threading.Thread(target=draw_scheduler, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/api/state', methods=['POST'])
def api_state():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    last_draw = float(gs('last_draw') or 0)
    next_draw = last_draw + 3600
    now = time.time()
    seconds_remaining = max(0, int(next_draw - now))
    db = get_db()
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id=0').fetchone()['c']
    total_value = ticket_count * TICKET_PRICE
    expected_jackpot = int(total_value * 0.75)
    db.close()
    state = {
        'logged_in': user is not None,
        'user': None,
        'ticket_count': ticket_count,
        'expected_jackpot': expected_jackpot,
        'seconds_remaining': seconds_remaining
    }
    if user:
        state['user'] = {
            'balance': user['balance'],
            'free_balance': user['free_balance']
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
    if not u: db.close(); return jsonify({'error': 'بيانات خاطئة'})
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    db.execute('UPDATE users SET token=? WHERE id=?', (token, u['id']))
    db.commit()
    db.close()
    return jsonify({'message': 'تم الدخول', 'token': token})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم الخروج'})

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
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (TICKET_PRICE, user['id']))
    ticket_counter = int(gs('ticket_counter')) + 1
    ticket_number = ticket_counter
    db.execute('INSERT INTO tickets (user_id, ticket_number, timestamp, round_id) VALUES (?,?,?,0)',
               (user['id'], ticket_number, time.time()))
    db.commit()
    ss('ticket_counter', str(ticket_counter))
    db.close()
    return jsonify({'message': f'تم شراء البطاقة رقم {ticket_number}', 'ticket_number': ticket_number})

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
    return jsonify({'message': 'تم إرسال طلب الإيداع للمراجعة'})

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
    return jsonify({'message': 'تم إرسال طلب السحب للمراجعة'})

@app.route('/api/my_requests', methods=['POST'])
def my_requests():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    deposits = db.execute('SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 10', (user['id'],)).fetchall()
    withdrawals = db.execute('SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 10', (user['id'],)).fetchall()
    db.close()
    return jsonify({
        'deposits': [{'amount': d['amount'], 'timestamp': d['timestamp'], 'status': d['status']} for d in deposits],
        'withdrawals': [{'amount': w['amount'], 'account': w['account'], 'timestamp': w['timestamp'], 'status': w['status']} for w in withdrawals]
    })

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

@app.route('/admin/approve-deposits', methods=['GET', 'POST'])
def approve_deposits():
    db = get_db()
    for r in db.execute('SELECT * FROM deposits WHERE status="معلق"').fetchall():
        db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (r['amount'], r['user_id']))
        db.execute('UPDATE deposits SET status = "مؤكد" WHERE id = ?', (r['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'تم تأكيد الإيداعات'})

@app.route('/admin/approve-withdrawals', methods=['GET', 'POST'])
def approve_withdrawals():
    db = get_db()
    for r in db.execute('SELECT * FROM withdrawals WHERE status="معلق"').fetchall():
        u = db.execute('SELECT balance FROM users WHERE id = ?', (r['user_id'],)).fetchone()
        if u and u['balance'] >= r['amount']:
            db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (r['amount'], r['user_id']))
            db.execute('UPDATE withdrawals SET status = "مؤكد" WHERE id = ?', (r['id'],))
    db.commit()
    db.close()
    return jsonify({'message': 'تمت معالجة السحوبات'})

@app.route('/api/admin/reset_users', methods=['POST'])
def reset_users():
    data = request.get_json()
    if data.get('password') != 'reset123':
        return jsonify({'error': 'كلمة المرور غير صحيحة'})
    db = get_db()
    db.execute('DELETE FROM users')
    db.execute('DELETE FROM tickets')
    db.execute('DELETE FROM deposits')
    db.execute('DELETE FROM withdrawals')
    db.execute("UPDATE state SET value='0' WHERE key='ticket_counter'")
    db.execute("UPDATE state SET value='0' WHERE key='last_draw'")
    db.execute("UPDATE state SET value='1' WHERE key='current_round'")
    db.commit()
    db.close()
    return jsonify({'message': 'تم حذف جميع المستخدمين والتذاكر بنجاح'})

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
