from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Listing, Exchange, Message, Review, CreditTransaction, MessageRequest
from datetime import datetime
import os

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def get_avatar_url(user):
    seed = user.avatar_seed or user.name
    style = user.avatar_style or 'adventurer'
    return f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}"

app.jinja_env.globals['get_avatar_url'] = get_avatar_url

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_messages = Message.query.filter_by(
            receiver_id=current_user.id, is_read=False
        ).count()
        pending_requests = MessageRequest.query.filter_by(
            receiver_id=current_user.id, status='pending'
        ).count()
        total_notifications = unread_messages + pending_requests
        return dict(
            unread_messages=unread_messages,
            pending_requests=pending_requests,
            total_notifications=total_notifications
        )
    return dict(unread_messages=0, pending_requests=0, total_notifications=0)

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

    # Get exchange ids already reviewed by current user
    reviewed_exchange_ids = [
        r.exchange_id for r in Review.query.filter_by(reviewer_id=current_user.id).all()
    ]
    return render_template('dashboard.html',
        my_listings=my_listings,
        exchanges=exchanges,
        transactions=transactions,
        reviewed_exchange_ids=reviewed_exchange_ids
    )

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

# ── Edit Listing ─────────────────────────────────────────
@app.route('/listing/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing(id):
    listing = db.session.get(Listing, id)
    if not listing or listing.user_id != current_user.id:
        flash('You can only edit your own listings.', 'danger')
        return redirect(url_for('board'))
    if request.method == 'POST':
        listing.type = request.form['type']
        listing.category = request.form['category']
        listing.title = request.form['title']
        listing.description = request.form['description']
        listing.credits = int(request.form['credits'])
        db.session.commit()
        flash('Listing updated successfully!', 'success')
        return redirect(url_for('view_listing', id=listing.id))
    return render_template('edit_listing.html', listing=listing)

# ── Delete Listing ────────────────────────────────────────
@app.route('/listing/<int:id>/delete')
@login_required
def delete_listing(id):
    listing = db.session.get(Listing, id)
    if not listing or listing.user_id != current_user.id:
        flash('You can only delete your own listings.', 'danger')
        return redirect(url_for('board'))
    db.session.delete(listing)
    db.session.commit()
    flash('Listing deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

# ── View Listing & Send Exchange Request ────────────────
@app.route('/listing/<int:id>', methods=['GET', 'POST'])
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

        # Increment exchange count
        listing.exchange_count = (listing.exchange_count or 0) + 1

        db.session.add(CreditTransaction(
            user_id=requester.id,
            amount=-listing.credits,
            reason=f'Exchange with {current_user.name} for "{listing.title}"'
        ))
        db.session.add(CreditTransaction(
            user_id=current_user.id,
            amount=listing.credits,
            reason=f'Exchange with {requester.name} for "{listing.title}"'
        ))
        db.session.commit()
        flash('Exchange completed! Credits transferred.', 'success')
    return redirect(url_for('dashboard'))

# ── Submit Review ─────────────────────────────────────────
@app.route('/exchange/<int:id>/review', methods=['GET', 'POST'])
@login_required
def submit_review(id):
    exchange = db.session.get(Exchange, id)
    if not exchange or exchange.status != 'completed':
        flash('Exchange not completed yet.', 'danger')
        return redirect(url_for('dashboard'))

    # Only helper or requester can review
    if current_user.id not in [exchange.helper_id, exchange.requester_id]:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    # Determine who is being reviewed
    if current_user.id == exchange.helper_id:
        reviewee_id = exchange.requester_id
    else:
        reviewee_id = exchange.helper_id

    # Check if already reviewed
    existing = Review.query.filter_by(
        exchange_id=id, reviewer_id=current_user.id
    ).first()
    if existing:
        flash('You already reviewed this exchange.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        review = Review(
            exchange_id=id,
            reviewer_id=current_user.id,
            reviewee_id=reviewee_id,
            rating=int(request.form['rating']),
            comment=request.form['comment']
        )
        db.session.add(review)
        db.session.commit()
        flash('Review submitted! Thank you.', 'success')
        return redirect(url_for('dashboard'))

    reviewee = db.session.get(User, reviewee_id)
    return render_template('submit_review.html', exchange=exchange, reviewee=reviewee)

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
        current_user.avatar_seed = request.form.get('avatar_seed', current_user.name)
        current_user.avatar_style = request.form.get('avatar_style', 'adventurer')
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile', id=current_user.id))
    return render_template('edit_profile.html')
# ── Messages ─────────────────────────────────────────────
@app.route('/messages')
@login_required
def messages():
    received = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.sent_at.desc()).all()
    sent = Message.query.filter_by(sender_id=current_user.id).order_by(Message.sent_at.desc()).all()
    # Mark all as read
    Message.query.filter_by(receiver_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('messages.html', messages=received, sent=sent)

@app.route('/messages/send/<int:receiver_id>', methods=['GET', 'POST'])
@login_required
def send_message(receiver_id):
    # Block messaging yourself
    if receiver_id == current_user.id:
        flash('You cannot send a message to yourself.', 'danger')
        return redirect(url_for('messages'))

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        flash('User not found.', 'danger')
        return redirect(url_for('messages'))

    # Check if request is accepted or if current user already sent a request
    existing = MessageRequest.query.filter_by(
        sender_id=current_user.id, receiver_id=receiver_id
    ).first()
    accepted = MessageRequest.query.filter_by(
        sender_id=current_user.id, receiver_id=receiver_id, status='accepted'
    ).first()
    # Also check reverse — if receiver sent accepted request to current user
    reverse_accepted = MessageRequest.query.filter_by(
        sender_id=receiver_id, receiver_id=current_user.id, status='accepted'
    ).first()

    can_message = accepted or reverse_accepted

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'send_request':
            if existing:
                flash('Message request already sent. Wait for acceptance.', 'danger')
            else:
                msg_request = MessageRequest(
                    sender_id=current_user.id,
                    receiver_id=receiver_id
                )
                db.session.add(msg_request)
                db.session.commit()
                flash('Message request sent!', 'success')
            return redirect(url_for('send_message', receiver_id=receiver_id))

        if action == 'send_message':
            if not can_message:
                flash('Request not accepted yet.', 'danger')
                return redirect(url_for('send_message', receiver_id=receiver_id))
            msg = Message(
                sender_id=current_user.id,
                receiver_id=receiver_id,
                body=request.form['body']
            )
            db.session.add(msg)
            db.session.commit()
            flash('Message sent!', 'success')
            return redirect(url_for('messages'))

    # Load conversation if accepted
    conversation = []
    if can_message:
        conversation = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
            ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.sent_at.asc()).all()

    return render_template('send_message.html',
        receiver=receiver,
        existing_request=existing,
        can_message=can_message,
        conversation=conversation
    )

@app.route('/messages/requests')
@login_required
def message_requests():
    requests_received = MessageRequest.query.filter_by(
        receiver_id=current_user.id, status='pending'
    ).all()
    return render_template('message_requests.html', requests=requests_received)

@app.route('/messages/requests/<int:req_id>/<action>')
@login_required
def handle_request(req_id, action):
    req = db.session.get(MessageRequest, req_id)
    if req and req.receiver_id == current_user.id:
        if action == 'accept':
            req.status = 'accepted'
            db.session.commit()
            flash('Message request accepted!', 'success')
        elif action == 'decline':
            req.status = 'declined'
            db.session.commit()
            flash('Message request declined.', 'danger')
    return redirect(url_for('message_requests'))

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
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False)