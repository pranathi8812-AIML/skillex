from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Listing, Exchange, Message, Review, CreditTransaction
from datetime import datetime
import os

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ── Home ────────────────────────────────────────────────
@app.route('/')
def home():
    listings = Listing.query.filter_by(status='open').order_by(Listing.created_at.desc()).limit(6).all()
    return render_template('home.html', listings=listings)

# ── Register ────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        ward = request.form['ward']

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        user = User(name=name, email=email, password=hashed, ward=ward)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# ── Login ───────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

# ── Logout ──────────────────────────────────────────────
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ── Dashboard ───────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    my_listings = Listing.query.filter_by(user_id=current_user.id).order_by(Listing.created_at.desc()).all()
    exchanges = Exchange.query.filter(
        (Exchange.helper_id == current_user.id) | (Exchange.requester_id == current_user.id)
    ).order_by(Exchange.created_at.desc()).all()
    transactions = CreditTransaction.query.filter_by(user_id=current_user.id).order_by(CreditTransaction.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', my_listings=my_listings, exchanges=exchanges, transactions=transactions)

# ── Skill Board ─────────────────────────────────────────
@app.route('/board')
def board():
    category = request.args.get('category', '')
    ward = request.args.get('ward', '')
    type_ = request.args.get('type', '')

    query = Listing.query.filter_by(status='open')
    if category:
        query = query.filter_by(category=category)
    if ward:
        query = query.filter_by(ward=ward)
    if type_:
        query = query.filter_by(type=type_)

    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template('board.html', listings=listings, category=category, ward=ward, type_=type_)

# ── Post a Listing ──────────────────────────────────────
@app.route('/post', methods=['GET', 'POST'])
@login_required
def post_listing():
    if request.method == 'POST':
        listing = Listing(
            user_id=current_user.id,
            type=request.form['type'],
            category=request.form['category'],
            title=request.form['title'],
            description=request.form['description'],
            credits=int(request.form['credits']),
            ward=current_user.ward
        )
        db.session.add(listing)
        db.session.commit()
        flash('Listing posted successfully!', 'success')
        return redirect(url_for('board'))
    return render_template('post_listing.html')

# ── View Listing & Send Exchange Request ────────────────
@app.route('/listing/<int:id>', methods=['GET', 'POST'])
@login_required
def view_listing(id):
    listing = db.session.get(Listing, id)
    if request.method == 'POST':
        if current_user.credits < listing.credits:
            flash('Not enough credits.', 'danger')
            return redirect(url_for('view_listing', id=id))
        exchange = Exchange(
            listing_id=listing.id,
            helper_id=listing.user_id,
            requester_id=current_user.id
        )
        db.session.add(exchange)
        db.session.commit()
        flash('Exchange request sent!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('listing.html', listing=listing)

# ── Complete Exchange ────────────────────────────────────
@app.route('/exchange/<int:id>/complete')
@login_required
def complete_exchange(id):
    exchange = db.session.get(Exchange, id)
    if exchange and exchange.helper_id == current_user.id:
        exchange.status = 'completed'
        exchange.completed_at = datetime.utcnow()

        requester = db.session.get(User, exchange.requester_id)
        listing = db.session.get(Listing, exchange.listing_id)

        requester.credits -= listing.credits
        current_user.credits += listing.credits
        listing.status = 'closed'

        db.session.add(CreditTransaction(user_id=requester.id, amount=-listing.credits, reason=f'Exchange #{exchange.id}'))
        db.session.add(CreditTransaction(user_id=current_user.id, amount=listing.credits, reason=f'Exchange #{exchange.id}'))
        db.session.commit()
        flash('Exchange completed! Credits transferred.', 'success')
    return redirect(url_for('dashboard'))

# ── Profile ─────────────────────────────────────────────
@app.route('/profile/<int:id>')
def profile(id):
    user = db.session.get(User, id)
    listings = Listing.query.filter_by(user_id=id).all()
    reviews = Review.query.filter_by(reviewee_id=id).all()
    return render_template('profile.html', user=user, listings=listings, reviews=reviews)

# ── Edit Profile ─────────────────────────────────────────
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.bio = request.form['bio']
        current_user.ward = request.form['ward']

        file = request.files.get('photo')
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                file.save(upload_path)
                current_user.photo = filename
            except Exception:
                pass  # Skip photo upload on read-only filesystems like Vercel

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile', id=current_user.id))
    return render_template('edit_profile.html')

# ── Messages ─────────────────────────────────────────────
@app.route('/messages')
@login_required
def messages():
    received = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.sent_at.desc()).all()
    return render_template('messages.html', messages=received)

@app.route('/messages/send/<int:receiver_id>', methods=['GET', 'POST'])
@login_required
def send_message(receiver_id):
    receiver = db.session.get(User, receiver_id)
    if request.method == 'POST':
        msg = Message(sender_id=current_user.id, receiver_id=receiver_id, body=request.form['body'])
        db.session.add(msg)
        db.session.commit()
        flash('Message sent!', 'success')
        return redirect(url_for('messages'))
    return render_template('send_message.html', receiver=receiver)

# ── Leaderboard ──────────────────────────────────────────
@app.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(User.credits.desc()).limit(10).all()
    return render_template('leaderboard.html', users=users)

# ── Admin ────────────────────────────────────────────────
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    users = User.query.all()
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    exchanges = Exchange.query.all()
    return render_template('admin.html', users=users, listings=listings, exchanges=exchanges)

# ── Run ──────────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)