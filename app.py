import os, hashlib, time, random, string, threading, sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'iChansy2024Secret!')
DATABASE = '/tmp/ichansy.db'
TICKET_PRICE = 10000
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin123')

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
            password_hash TEXT NOT NULL,
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
        INSERT OR IGNORE INTO state (key, value) VALUES ('draw_active', '0');
        INSERT OR IGNORE INTO state (key, value) VALUES ('draw_winner', '');
        INSERT OR IGNORE INTO state (key, value) VALUES ('draw_jackpot', '0');
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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_token(token):
    if not token: return None
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE token=?', (token,)).fetchone()
    db.close()
    return u

# ========== نظام السحب التلقائي ==========
def scheduler():
    while True:
        time.sleep(5)
        try:
            db = get_db()
            last = float(gs('last_draw') or 0)
            now = time.time()
            if now - last >= 3600:  # كل ساعة
                tickets = db.execute('SELECT * FROM tickets WHERE round_id=0').fetchall()
                if tickets:
                    total = len(tickets) * TICKET_PRICE
                    jackpot = int(total * 0.80)  # 80% من قيمة التذاكر
                    winner = random.choice(tickets)
                    
                    ss('draw_active', '1')
                    ss('draw_winner', str(winner['ticket_number']))
                    ss('draw_jackpot', str(jackpot))
                    
                    time.sleep(20)  # مدة دوران العجلة
                    
                    db.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (jackpot, winner['user_id']))
                    db.execute('UPDATE tickets SET round_id = ? WHERE round_id = 0', (int(gs('current_round')),))
                    ss('last_draw', str(now))
                    ss('current_round', str(int(gs('current_round')) + 1))
                    ss('draw_active', '0')
                    db.commit()
                else:
                    ss('last_draw', str(now))
            db.close()
        except:
            pass

threading.Thread(target=scheduler, daemon=True).start()

# ========== صفحات ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/games')
def games():
    return render_template('games.html')

# ========== لوحة الإدارة ==========
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return '<form method="POST"><input name="pass" placeholder="كلمة المرور"><button>دخول</button></form>'
    db = get_db()
    deps = db.execute('SELECT * FROM deposits ORDER BY id DESC LIMIT 20').fetchall()
    wits = db.execute('SELECT * FROM withdrawals ORDER BY id DESC LIMIT 20').fetchall()
    db.close()
    html = '<h1>لوحة الإدارة</h1><a href="/admin/logout">خروج</a>'
    html += '<h2>الإيداعات</h2>'
    for d in deps:
        html += f'<div>💰 {d["amount"]} - {d["status"]} <a href="/admin/approve-deposit/{d["id"]}">تأكيد</a></div>'
    html += '<h2>السحوبات</h2>'
    for w in wits:
        html += f'<div>💸 {w["amount"]} إلى {w["account"]} - {w["status"]} <a href="/admin/approve-withdrawal/{w["id"]}">تأكيد</a></div>'
    return html

@app.route('/admin', methods=['POST'])
def admin_login():
    if request.form.get('pass') == ADMIN_PASS:
        session['admin'] = True
        return redirect('/admin')
    return 'خطأ'

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

@app.route('/admin/approve-deposit/<int:did>')
def approve_deposit(did):
    if not session.get('admin'): return redirect('/admin')
    db = get_db()
    d = db.execute('SELECT * FROM deposits WHERE id=?', (did,)).fetchone()
    if d and d['status'] == 'معلق':
        db.execute('UPDATE users SET balance=balance+? WHERE id=?', (d['amount'], d['user_id']))
        db.execute('UPDATE deposits SET status="مؤكد" WHERE id=?', (did,))
        db.commit()
    db.close()
    return redirect('/admin')

@app.route('/admin/approve-withdrawal/<int:wid>')
def approve_withdrawal(wid):
    if not session.get('admin'): return redirect('/admin')
    db = get_db()
    w = db.execute('SELECT * FROM withdrawals WHERE id=?', (wid,)).fetchone()
    if w and w['status'] == 'معلق':
        u = db.execute('SELECT balance FROM users WHERE id=?', (w['user_id'],)).fetchone()
        if u and u['balance'] >= w['amount']:
            db.execute('UPDATE users SET balance=balance-? WHERE id=?', (w['amount'], w['user_id']))
            db.execute('UPDATE withdrawals SET status="مؤكد" WHERE id=?', (wid,))
            db.commit()
    db.close()
    return redirect('/admin')

# ========== API ==========
@app.route('/api/state', methods=['POST'])
def api_state():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    last = float(gs('last_draw') or 0)
    remaining = max(0, int((last + 3600) - time.time()))
    db = get_db()
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id=0').fetchone()['c']
    expected = int(ticket_count * TICKET_PRICE * 0.80)
    db.close()
    
    return jsonify({
        'logged_in': user is not None,
        'user': {'balance': user['balance'], 'free_balance': user['free_balance']} if user else None,
        'ticket_count': ticket_count,
        'expected_jackpot': expected,
        'seconds_remaining': remaining,
        'draw_active': gs('draw_active') == '1',
        'draw_winner': gs('draw_winner'),
        'draw_jackpot': gs('draw_jackpot')
    })

@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    ph = d.get('phone','').strip()
    pw = d.get('password','').strip()
    if not ph or not pw: return jsonify({'error':'املأ الحقول'})
    db = get_db()
    if db.execute('SELECT id FROM users WHERE phone=?', (ph,)).fetchone():
        db.close(); return jsonify({'error':'الرقم مسجل'})
    token = ''.join(random.choices(string.ascii_letters+string.digits, k=32))
    db.execute('INSERT INTO users (phone, password_hash, token) VALUES (?,?,?)', (ph, hash_password(pw), token))
    db.commit()
    db.close()
    return jsonify({'message':'تم التسجيل','token':token})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    ph = d.get('phone','').strip()
    pw = d.get('password','').strip()
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE phone=? AND password_hash=?', (ph, hash_password(pw))).fetchone()
    if not u: db.close(); return jsonify({'error':'بيانات خاطئة'})
    token = ''.join(random.choices(string.ascii_letters+string.digits, k=32))
    db.execute('UPDATE users SET token=? WHERE id=?', (token, u['id']))
    db.commit()
    db.close()
    return jsonify({'message':'تم الدخول','token':token})

@app.route('/api/buy', methods=['POST'])
def buy():
    data = request.get_json()
    user = get_user_by_token(data.get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    db = get_db()
    if user['balance'] < TICKET_PRICE: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (TICKET_PRICE, user['id']))
    counter = int(gs('ticket_counter')) + 1
    db.execute('INSERT INTO tickets (user_id, ticket_number, timestamp, round_id) VALUES (?,?,?,0)', (user['id'], counter, time.time()))
    db.commit()
    ss('ticket_counter', str(counter))
    db.close()
    return jsonify({'message':f'بطاقة #{counter}','ticket_number':counter})

@app.route('/api/my_tickets', methods=['POST'])
def my_tickets():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    db = get_db()
    tickets = db.execute('SELECT ticket_number FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 50', (user['id'],)).fetchall()
    db.close()
    return jsonify({'tickets':[t['ticket_number'] for t in tickets]})

@app.route('/api/deposit', methods=['POST'])
def deposit():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    amt = request.get_json().get('amount')
    img = request.get_json().get('image')
    if not amt or amt <= 0: return jsonify({'error':'مبلغ غير صحيح'})
    db = get_db()
    db.execute('INSERT INTO deposits (user_id, amount, image, timestamp) VALUES (?,?,?,?)', (user['id'], amt, img, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message':'تم إرسال طلب الإيداع'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    acc = request.get_json().get('account','').strip()
    amt = request.get_json().get('amount')
    if not acc or not amt or amt <= 0: return jsonify({'error':'بيانات ناقصة'})
    db = get_db()
    if user['balance'] < amt: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('INSERT INTO withdrawals (user_id, account, amount, timestamp) VALUES (?,?,?,?)', (user['id'], acc, amt, time.strftime('%Y-%m-%d %H:%M')))
    db.commit()
    db.close()
    return jsonify({'message':'تم إرسال طلب السحب'})

@app.route('/api/my_requests', methods=['POST'])
def my_requests():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    db = get_db()
    deps = db.execute('SELECT * FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 10', (user['id'],)).fetchall()
    wits = db.execute('SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 10', (user['id'],)).fetchall()
    db.close()
    return jsonify({
        'deposits':[{'amount':d['amount'],'timestamp':d['timestamp'],'status':d['status']} for d in deps],
        'withdrawals':[{'amount':w['amount'],'account':w['account'],'timestamp':w['timestamp'],'status':w['status']} for w in wits]
    })

# ========== الألعاب ==========
@app.route('/api/slots', methods=['POST'])
def slots():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    cost = 500
    db = get_db()
    if user['balance'] < cost: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (cost, user['id']))
    db.commit()
    sym = ['🍒','🍋','🍊','🍇','💎','⭐']
    res = [random.choice(sym) for _ in range(3)]
    win = 0
    if res[0]==res[1]==res[2]: win = cost*10
    elif res[0]==res[1] or res[1]==res[2] or res[0]==res[2]: win = cost*2
    if win: db.execute('UPDATE users SET balance=balance+? WHERE id=?', (win, user['id']))
    db.commit()
    bal = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'result':res,'win':win,'balance':bal})

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
