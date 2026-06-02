from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'my-secret-key-2024-unique'

# مسار قاعدة البيانات
DATABASE = '/tmp/lottery.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 100000
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            round_id INTEGER DEFAULT 1
        )
    ''')
    db.commit()
    db.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def state():
    if 'user_id' not in session:
        return jsonify({
            'logged_in': False,
            'user': None,
            'ticket_count': 0
        })
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not user:
        session.pop('user_id', None)
        db.close()
        return jsonify({
            'logged_in': False,
            'user': None,
            'ticket_count': 0
        })
    
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id = 1').fetchone()['c']
    db.close()
    
    return jsonify({
        'logged_in': True,
        'user': {
            'id': user['id'],
            'balance': user['balance']
        },
        'ticket_count': ticket_count
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
        
        # التحقق من عدم وجود المستخدم مسبقاً
        existing = db.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        if existing:
            db.close()
            return jsonify({'error': 'رقم الهاتف مسجل مسبقاً'})
        
        # إنشاء المستخدم
        db.execute(
            'INSERT INTO users (phone, password, balance) VALUES (?, ?, ?)',
            (phone, password, 100000)
        )
        db.commit()
        
        # الحصول على ID المستخدم الجديد
        user = db.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        user_id = user['id']
        db.close()
        
        # تسجيل الدخول
        session['user_id'] = user_id
        
        return jsonify({
            'message': 'تم التسجيل بنجاح',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': f'حدث خطأ: {str(e)}'})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        password = data.get('password', '').strip()
        
        if not phone or not password:
            return jsonify({'error': 'الرجاء ملء جميع الحقول'})
        
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE phone = ? AND password = ?',
            (phone, password)
        ).fetchone()
        db.close()
        
        if not user:
            return jsonify({'error': 'رقم الهاتف أو كلمة المرور غير صحيحة'})
        
        session['user_id'] = user['id']
        
        return jsonify({
            'message': 'تم تسجيل الدخول بنجاح',
            'user_id': user['id']
        })
        
    except Exception as e:
        return jsonify({'error': f'حدث خطأ: {str(e)}'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'تم تسجيل الخروج'})

@app.route('/api/buy', methods=['POST'])
def buy():
    if 'user_id' not in session:
        return jsonify({'error': 'يجب تسجيل الدخول أولاً'})
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if not user:
        db.close()
        return jsonify({'error': 'المستخدم غير موجود'})
    
    if user['balance'] < 10000:
        db.close()
        return jsonify({'error': 'رصيدك غير كافٍ (تحتاج 10,000 ل.س)'})
    
    ticket_count = db.execute('SELECT COUNT(*) as c FROM tickets WHERE round_id = 1').fetchone()['c']
    
    if ticket_count >= 50:
        db.close()
        return jsonify({'error': 'اكتملت البطاقات لهذه الجولة'})
    
    # خصم الرصيد وإضافة التذكرة
    db.execute('UPDATE users SET balance = balance - 10000 WHERE id = ?', (session['user_id'],))
    db.execute('INSERT INTO tickets (user_id, ticket_number) VALUES (?, ?)', (session['user_id'], ticket_count + 1))
    db.commit()
    
    new_count = ticket_count + 1
    new_balance = user['balance'] - 10000
    db.close()
    
    return jsonify({
        'message': f'تم شراء البطاقة رقم {new_count} بنجاح',
        'ticket_count': new_count,
        'balance': new_balance
    })

# تهيئة قاعدة البيانات عند بدء التشغيل
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
