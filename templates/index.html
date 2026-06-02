from flask import Flask, render_template, request, jsonify
import sqlite3, random, time, threading, string

app = Flask(__name__)
DATABASE = '/tmp/lottery.db'
TICKET_PRICE = 10000
JACKPOT_PERCENT = 0.75
SLOT_COST = 500
ROULETTE_COST = 1000
BLACKJACK_COST = 2000
POKER_COST = 5000
DICE_COST = 800

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
    if not token: return None
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE token=?', (token,)).fetchone()
    db.close()
    return u

# ====================== جدولة السحب كل ساعة ======================
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
                jackpot = int(total_value * JACKPOT_PERCENT)
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

# ====================== التوجيهات ======================
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

# ====================== ألعاب الكازينو ======================
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
        return jsonify({'error': f'رصيد غير كافٍ (تحتاج {SLOT_COST} ل.س)'})
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (SLOT_COST, user['id']))
    db.commit()
    symbols = ['🍒','🍋','🍊','🍇','💎','⭐']
    result = [random.choice(symbols) for _ in range(3)]
    win = 0
    if result[0]==result[1]==result[2]:
        win = SLOT_COST * 10
    elif result[0]==result[1] or result[1]==result[2] or result[0]==result[2]:
        win = SLOT_COST * 2
    if win > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'result': result, 'win': win, 'balance': new_balance})

@app.route('/api/roulette', methods=['POST'])
def roulette():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    bet = data.get('bet')
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < ROULETTE_COST:
        db.close()
        return jsonify({'error': f'رصيد غير كافٍ (تحتاج {ROULETTE_COST} ل.س)'})
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (ROULETTE_COST, user['id']))
    db.commit()
    outcomes = ['red']*18 + ['black']*18 + ['green']*2
    result = random.choice(outcomes)
    win = 0
    if bet == result:
        if bet == 'green':
            win = ROULETTE_COST * 14
        else:
            win = ROULETTE_COST * 2
    if win > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'result': result, 'win': win, 'balance': new_balance})

@app.route('/api/blackjack', methods=['POST'])
def blackjack():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < BLACKJACK_COST:
        db.close()
        return jsonify({'error': f'رصيد غير كافٍ (تحتاج {BLACKJACK_COST} ل.س)'})
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (BLACKJACK_COST, user['id']))
    db.commit()
    player = random.randint(17, 21)
    dealer = random.randint(17, 21)
    win = 0
    if player > 21:
        result = 'lose'
    elif dealer > 21 or player > dealer:
        result = 'win'
        win = BLACKJACK_COST * 2
    elif player == dealer:
        result = 'push'
        win = BLACKJACK_COST
    else:
        result = 'lose'
    if win > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'player': player, 'dealer': dealer, 'result': result, 'win': win, 'balance': new_balance})

@app.route('/api/dice', methods=['POST'])
def dice():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < DICE_COST:
        db.close()
        return jsonify({'error': f'رصيد غير كافٍ (تحتاج {DICE_COST} ل.س)'})
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (DICE_COST, user['id']))
    db.commit()
    choice = int(data.get('choice', 1))
    dice_roll = random.randint(1,6)
    win = 0
    if dice_roll == choice:
        win = DICE_COST * 5
    if win > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'dice': dice_roll, 'win': win, 'balance': new_balance})

@app.route('/api/poker', methods=['POST'])
def poker():
    data = request.get_json()
    token = data.get('token', '') if data else ''
    user = get_user_by_token(token)
    if not user: return jsonify({'error': 'سجل الدخول'})
    db = get_db()
    u = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()
    if u['balance'] < POKER_COST:
        db.close()
        return jsonify({'error': f'رصيد غير كافٍ (تحتاج {POKER_COST} ل.س)'})
    db.execute('UPDATE users SET balance = balance - ? WHERE id=?', (POKER_COST, user['id']))
    db.commit()
    player_hand = random.randint(1,10)
    dealer_hand = random.randint(1,10)
    win = 0
    if player_hand > dealer_hand:
        win = POKER_COST * 2
    elif player_hand == dealer_hand:
        win = POKER_COST
    if win > 0:
        db.execute('UPDATE users SET balance = balance + ? WHERE id=?', (win, user['id']))
        db.commit()
    new_balance = db.execute('SELECT balance FROM users WHERE id=?', (user['id'],)).fetchone()['balance']
    db.close()
    return jsonify({'player': player_hand, 'dealer': dealer_hand, 'win': win, 'balance': new_balance})

# ====================== تصفير الحسابات ======================
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
