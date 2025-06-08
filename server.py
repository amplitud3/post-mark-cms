import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import random
import re
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
load_dotenv()  
import base64


UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_attachment(attachment):
    if not allowed_file(attachment['Name']):
        return None
    
    filename = f"{datetime.now().timestamp()}-{attachment['Name']}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(filepath, 'wb') as f:
        f.write(base64.b64decode(attachment['Content']))
    
    return filepath


ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "default_admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", generate_password_hash("default_password"))

# allowed senders from .env
ALLOWED_SENDERS = [email.strip() for email in 
                   os.getenv('ALLOWED_SENDERS', '').split(',') 
                   if email.strip()]

app = Flask(__name__)


app.secret_key = os.getenv("SECRET_KEY")  


# Database Setup
DATABASE = '.data/cms.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def generate_short_id():
    """Generate a unique 4-digit ID"""
    db = get_db()
    for _ in range(3):  # Max 3 attempts
        short_id = f"{random.randint(1000, 9999)}"
        if not db.execute('SELECT 1 FROM posts WHERE short_id = ?', (short_id,)).fetchone():
            return short_id
    raise ValueError("Could not generate unique short ID")

def migrate_db():
    """Handle database schema migrations"""
    db = get_db()
    try:
        
        db.execute("SELECT short_id, sender_email FROM posts LIMIT 1")
    except sqlite3.OperationalError:
        print("Running database migration...")
       
        db.execute("ALTER TABLE posts ADD COLUMN short_id TEXT UNIQUE")
        db.execute("ALTER TABLE posts ADD COLUMN sender_email TEXT")
        # Generate short_ids for existing posts
        posts = db.execute("SELECT id FROM posts").fetchall()
        for post in posts:
            db.execute(
                "UPDATE posts SET short_id = ?, sender_email = ? WHERE id = ?",
                (generate_short_id(), "migrated@example.com", post['id'])
            )
        db.commit()
        print("Migration completed successfully")

def init_db():
    """Initialize database with correct schema"""
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                short_id TEXT UNIQUE,
                subject TEXT,
                body TEXT,
                created_at TEXT,
                edited_at TEXT,
                sender_email TEXT
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT,
                file_path TEXT,
                original_name TEXT,
                FOREIGN KEY(post_id) REFERENCES posts(id)
            )
        ''')
        db.commit()
        migrate_db()  


init_db()


def parse_email_command(subject):
    match = re.match(r'^(EDIT|DELETE)\s+(\d{4})$', subject.strip())
    return (match.group(1), match.group(2)) if match else (None, None)

# Routes

@app.route('/debug-auth')
def debug_auth():
    return f"Username: {ADMIN_USERNAME}, Hash: {ADMIN_PASSWORD_HASH[:25]}..."

@app.route('/')
def home():
    db = get_db()
    posts = db.execute('SELECT * FROM posts ORDER BY created_at DESC').fetchall()
    return render_template('index.html', posts=posts)


@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.json:
        return jsonify(error="Invalid payload"), 400

    email_data = request.json
    sender = email_data.get('From', '')
    
    # sender verification
    if sender not in ALLOWED_SENDERS:
        return jsonify(error="Unauthorized sender"), 403

    subject = email_data.get('Subject', 'No subject')
    body = email_data.get('TextBody', '')
    attachments = request.json.get('Attachments', [])
    
 
    body = re.sub(r'<img[^>]+>', '', body)  
    
  
    image_html = ""
    for attachment in attachments[:3]: 
        if attachment['ContentType'].startswith('image/'):
            saved_path = save_attachment(attachment)
            if saved_path:
                rel_path = os.path.relpath(saved_path, 'static')
                image_html += f'''
                <div class="post-image">
                    <img src="/static/{rel_path}" 
                         alt="Attached image"
                         style="max-width: 100%; height: auto;">
                </div>'''

   
        
    full_content = image_html + f'<div class="post-text">{body}</div>'

    print(f"Image HTML: {body[-200:]}")  
  
    command, short_id = parse_email_command(subject)
    if command:
        return handle_command(command, short_id, body, sender)
    
    # new post creation
    try:
        new_post = {
            'id': str(random.getrandbits(128)),
            'short_id': generate_short_id(),
            'subject': subject,
            'body': full_content,
            'created_at': datetime.now().isoformat(),
            'edited_at': None,
            'sender_email': sender
        }
        
        db = get_db()
        db.execute(
            '''INSERT INTO posts 
            (id, short_id, subject, body, created_at, edited_at, sender_email) 
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            tuple(new_post.values())
        )
        db.commit()
        return jsonify(
            success=True, 
            short_id=new_post['short_id'],
            message=f"Post #{new_post['short_id']} created"
        )
    except Exception as e:
        return jsonify(error=str(e)), 500

def handle_command(command, short_id, body, sender):
    db = get_db()
    post = db.execute(
        'SELECT * FROM posts WHERE short_id = ? AND sender_email = ?',
        (short_id, sender)
    ).fetchone()

    if not post:
        return jsonify(error=f"Post #{short_id} not found or unauthorized"), 404

    try:
        if command == 'EDIT':
            db.execute(
                '''UPDATE posts 
                SET subject = ?, body = ?, edited_at = ? 
                WHERE short_id = ?''',
                (body.split('\n')[0], body, datetime.now().isoformat(), short_id)
            )
            action = "updated"
        elif command == 'DELETE':
            db.execute('DELETE FROM posts WHERE short_id = ?', (short_id,))
            action = "deleted"
        
        db.commit()
        return jsonify(
            success=True,
            message=f"Post #{short_id} {action} successfully"
        )
    except Exception as e:
        return jsonify(error=str(e)), 500

# Admin routes
@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    return render_template('login.html')

@app.route('/admin/login', methods=['POST'])
@app.route('/admin/login', methods=['POST'])
def admin_login():
    input_username = request.form.get('username')
    input_password = request.form.get('password')
    

    
    
    if (input_username == ADMIN_USERNAME and 
        check_password_hash(ADMIN_PASSWORD_HASH, input_password)):
        session['is_admin'] = True
        return redirect(url_for('home'))
        
    print(f"Input username: {input_username}")
    print(f"Input password: {input_password}")
    print(f"Stored hash: {ADMIN_PASSWORD_HASH}")
    print(f"Check result: {check_password_hash(ADMIN_PASSWORD_HASH, input_password)}")
    
    return render_template('login.html', error="Invalid credentials"), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Post management
@app.route('/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    db = get_db()
    db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    db.commit()
    return jsonify({"success": True})

@app.route('/edit/<post_id>', methods=['GET'])
def edit_post_form(post_id):
    if not session.get('is_admin'):
        return redirect(url_for('home'))
    
    db = get_db()
    post = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    return render_template('edit_post.html', post=post)

@app.route('/edit/<post_id>', methods=['POST'])
def save_edited_post(post_id):
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    
    db = get_db()
    db.execute(
        'UPDATE posts SET subject = ?, body = ?, edited_at = ? WHERE id = ?',
        (request.form['subject'], request.form['body'], datetime.now().isoformat(), post_id)
    )
    db.commit()
    return redirect(url_for('home'))

# Template filters
@app.template_filter('format_datetime')
def format_datetime(value):
    if not value:
        return ""
    dt = datetime.fromisoformat(value)
    return dt.strftime("%b %d, %Y at %H:%M")

if __name__ == '__main__':
    init_db()  
    app.run(host='0.0.0.0', port=3000)