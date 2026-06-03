import os, hashlib, time, random, string, threading, sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')
DATABASE = '/tmp/lottery.db'
TICKET_PRICE = 10000
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
                db.commit()
            else:
                ss('last_draw', str(now))
        db.close()

threading.Thread(target=draw_scheduler, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/games')
def games():
    return render_template('games.html')

# --- لوحة الإدارة ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error='كلمة مرور خاطئة')
    if not session.get('admin'):
        return render_template('admin_login.html')
    return render_template('admin.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

# --- API ---
@app.route('/api/state', methods=['POST'])
def api_state():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    last_draw = float(gs('last_draw') or 0)
    seconds_remaining = max(0, int((last_draw + 3600) - time.time()))
    db = get_db()
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id=0').fetchone()['c']
    expected_jackpot = int(ticket_count * TICKET_PRICE * 0.75)
    db.close()
    if user:
        return jsonify({
            'logged_in': True,
            'user': {'balance': user['balance'], 'free_balance': user['free_balance']},
            'ticket_count': ticket_count,
            'expected_jackpot': expected_jackpot,
            'seconds_remaining': seconds_remaining
        })
    return jsonify({'logged_in': False, 'ticket_count': ticket_count, 'expected_jackpot': expected_jackpot, 'seconds_remaining': seconds_remaining})

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
    return jsonify({'message':f'تم شراء البطاقة رقم {counter}','ticket_number':counter})

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

# إدارة (محمية)
@app.route('/admin/approve-deposits')
def approve_deposits():
    if not session.get('admin'): return redirect('/admin')
    db = get_db()
    for d in db.execute('SELECT * FROM deposits WHERE status="معلق"').fetchall():
        db.execute('UPDATE users SET balance=balance+? WHERE id=?', (d['amount'], d['user_id']))
        db.execute('UPDATE deposits SET status="مؤكد" WHERE id=?', (d['id'],))
    db.commit()
    db.close()
    return jsonify({'message':'تم تأكيد الإيداعات'})

@app.route('/admin/approve-withdrawals')
def approve_withdrawals():
    if not session.get('admin'): return redirect('/admin')
    db = get_db()
    for w in db.execute('SELECT * FROM withdrawals WHERE status="معلق"').fetchall():
        u = db.execute('SELECT balance FROM users WHERE id=?', (w['user_id'],)).fetchone()
        if u and u['balance'] >= w['amount']:
            db.execute('UPDATE users SET balance=balance-? WHERE id=?', (w['amount'], w['user_id']))
            db.execute('UPDATE withdrawals SET status="مؤكد" WHERE id=?', (w['id'],))
    db.commit()
    db.close()
    return jsonify({'message':'تمت معالجة السحوبات'})

# الألعاب
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

@app.route('/api/roulette', methods=['POST'])
def roulette():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    cost = 1000
    bet = request.get_json().get('bet')
    db = get_db()
    if user['balance'] < cost: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (cost, user['id']))
    db.commit()
    outcomes = ['red']*18 + ['black']*18 + ['green']*2
    result = random.choice(outcomes)
    win = 0
    if bet == result:
        if bet == 'green': win = cost*14
        else: win = cost*2
    if win: db.execute('UPDATE users SET balance=balance+? WHERE id=?', (win, user['id']))
    db.commit()
    bal = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'result':result,'win':win,'balance':bal})

@app.route('/api/blackjack', methods=['POST'])
def blackjack():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    cost = 2000
    db = get_db()
    if user['balance'] < cost: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (cost, user['id']))
    db.commit()
    player = random.randint(17,21)
    dealer = random.randint(17,21)
    win = 0
    if player>21: result='lose'
    elif dealer>21 or player>dealer: result='win'; win=cost*2
    elif player==dealer: result='push'; win=cost
    else: result='lose'
    if win: db.execute('UPDATE users SET balance=balance+? WHERE id=?', (win, user['id']))
    db.commit()
    bal = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'player':player,'dealer':dealer,'result':result,'win':win,'balance':bal})

@app.route('/api/dice', methods=['POST'])
def dice():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    cost = 800
    choice = int(request.get_json().get('choice',1))
    db = get_db()
    if user['balance'] < cost: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (cost, user['id']))
    db.commit()
    roll = random.randint(1,6)
    win = 0
    if roll == choice: win = cost*5
    if win: db.execute('UPDATE users SET balance=balance+? WHERE id=?', (win, user['id']))
    db.commit()
    bal = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'dice':roll,'win':win,'balance':bal})

@app.route('/api/poker', methods=['POST'])
def poker():
    user = get_user_by_token(request.get_json().get('token',''))
    if not user: return jsonify({'error':'سجل الدخول'})
    cost = 5000
    db = get_db()
    if user['balance'] < cost: db.close(); return jsonify({'error':'رصيد غير كاف'})
    db.execute('UPDATE users SET balance=balance-? WHERE id=?', (cost, user['id']))
    db.commit()
    p = random.randint(1,10)
    d = random.randint(1,10)
    win = 0
    if p>d: win=cost*2
    elif p==d: win=cost
    if win: db.execute('UPDATE users SET balance=balance+? WHERE id=?', (win, user['id']))
    db.commit()
    bal = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'player':p,'dealer':d,'win':win,'balance':bal})

init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
