# GEREKLİ YENİ KÜTÜPHANELER
import math
from datetime import datetime, date, timedelta

# MEVCUT KÜTÜPHANELER
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import re
import secrets
import string
import sqlalchemy
from sqlalchemy import func, case
from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError


# =================================================================
# === YENİ ALGORİTMA SABİTLERİ ===
# =================================================================
# Zaman Çürümesi Formülü için Yerçekimi Sabiti. Yükseldikçe eski gönderiler daha hızlı düşer.
GRAVITY = 1.8
# Takipçi bonusu için logaritmik çarpam.
FOLLOWER_BONUS_MULTIPLIER = 0.5


# Flask uygulamasını başlat
app = Flask(__name__)

# --- Uygulama Yapılandırması ---
app.config['SECRET_KEY'] = 'cok_guclu_ve_kimsenin_tahmin_edemeyecegi_bir_anahtar_buraya_gelecek' # KESİNLİKLE DEĞİŞTİR!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER_BASE'] = os.path.join(app.root_path, 'static/uploads')
app.config['PROFILE_PICS_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER_BASE'], 'profile_pics')
app.config['POST_MEDIA_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER_BASE'], 'post_media')

instance_path = os.path.join(app.root_path, 'instance')
os.makedirs(instance_path, exist_ok=True)
os.makedirs(app.config['PROFILE_PICS_FOLDER'], exist_ok=True)
os.makedirs(app.config['POST_MEDIA_FOLDER'], exist_ok=True)

app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['ALLOWED_VIDEO_EXTENSIONS'] = {'mp4', 'mov', 'avi', 'mkv'}
app.config['ALLOWED_FILE_EXTENSIONS'] = app.config['ALLOWED_IMAGE_EXTENSIONS'].union(app.config['ALLOWED_VIDEO_EXTENSIONS'])

db = SQLAlchemy(app)

UPLOAD_FOLDER = 'static/uploads/blinks' # Blink'ler için ayrı bir yükleme klasörü
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['BLINK_UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'} # Desteklenen dosya türleri

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === PREMIUM PLAN SABİT YAPISI ===
PREMIUM_PLANS = {
    'lite': {'name': 'Lite', 'price': 49, 'currency': 'TL', 'content_limit': 50, 'community_limit': 1, 'description': 'Lite plan ile ayda 50 içerik ve 1 premium topluluk oluşturabilirsiniz.'},
    'plus': {'name': 'Plus', 'price': 119, 'currency': 'TL', 'content_limit': 200, 'community_limit': 3, 'description': 'Plus plan ile ayda 200 içerik ve 3 premium topluluk oluşturabilirsiniz.'},
    'infinity': {'name': 'Infinity', 'price': 149, 'currency': 'TL', 'content_limit': None, 'community_limit': None, 'description': 'Infinity plan ile sınırsız içerik ve topluluk oluşturabilirsiniz.', 'recommended': True}
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Dosya uzantısını kontrol eden yardımcı fonksiyonlar
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_FILE_EXTENSIONS']
def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_IMAGE_EXTENSIONS']
def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_VIDEO_EXTENSIONS']

# Anahtar oluşturmak için yardımcı fonksiyon
def generate_key(length=16):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for i in range(length))


# =================================================================
# === YENİ ALGORİTMA YARDIMCI FONKSİYONLARI ===
# =================================================================
def _calculate_follower_bonus(follower_count):
    if follower_count < 10: return 0.0
    return math.log10(follower_count) * FOLLOWER_BONUS_MULTIPLIER

def _calculate_vote_power(user, base_vote_score):
    days_since_joined = (datetime.utcnow() - user.date_joined).days
    seniority_factor = 0.5 if 1 <= days_since_joined <= 5 else 0.7
    premium_bonus = 1.5 if user.role == 'premium' else 0.0
    follower_bonus = _calculate_follower_bonus(user.get_follower_count())
    return (base_vote_score * seniority_factor) + premium_bonus + follower_bonus

# --- Veritabanı Modelleri (Tanımlama Sırası Önemli!) ---

# Slugify ve benzersiz slug üretici yardımcı fonksiyonlar
import unicodedata
def slugify(value):
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-zA-Z0-9\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value


def slugify(text):
    text = str(text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

def create_unique_blog_slug(title):
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "blog-post"
    slug = base_slug
    counter = 1
    while InfinityNetworkBlog.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def generate_unique_network_slug(name):
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    while InfinityNetwork.query.filter_by(slug=slug).first() is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

class InfinityNetworkBlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey('infinity_network.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User')
    likes = db.relationship('InfinityNetworkBlogLike', backref='blog', lazy=True, cascade='all, delete-orphan')

class InfinityNetworkBlogLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey('infinity_network_blog.id'), nullable=False)
    # 1 for like, -1 for dislike
    reaction = db.Column(db.Integer, nullable=False) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'blog_id', name='_user_blog_reaction_uc'),)
# YENİ: InfinityNetwork Modeli
class InfinityNetwork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    logo = db.Column(db.String(120), nullable=True)
    theme_color = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship('InfinityNetworkPost', backref='network', lazy=True, cascade='all, delete-orphan')
    # YENİ: invite_code alanı kaldırıldı, bunun yerine invite ilişkisi kullanılacak.
    invites = db.relationship('InfinityNetworkInvite', backref='network', lazy=True, cascade='all, delete-orphan')
    blogs = db.relationship('InfinityNetworkBlog', backref='network', lazy=True, cascade='all, delete-orphan')



# YENİ: Davet Modeli
class InfinityNetworkInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey('infinity_network.id'), nullable=False)
    code = db.Column(db.String(16), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class InfinityNetworkMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey('infinity_network.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_moderator = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='infinity_network_memberships')
    network = db.relationship('InfinityNetwork', backref='members')

class InfinityNetworkPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network_id = db.Column(db.Integer, db.ForeignKey('infinity_network.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_file = db.Column(db.String(120), nullable=True)
    video_file = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='infinity_network_posts')

# ... (Diğer tüm modelleriniz burada değişmeden kalır) ...
user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('badge_id', db.Integer, db.ForeignKey('badge.id'), primary_key=True)
)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    follower_user = db.relationship('User', foreign_keys=[follower_id], backref=db.backref('following_links', lazy='dynamic'))
    followed_user = db.relationship('User', foreign_keys=[followed_id], backref=db.backref('follower_links', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('follower_id', 'followed_id', name='_follower_followed_uc'),)

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon_class = db.Column(db.String(50), nullable=True)
    min_followers = db.Column(db.Integer, nullable=False)

class RegistrationKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_code = db.Column(db.String(64), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)
    is_reusable = db.Column(db.Boolean, nullable=False, default=False)
    used_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='registration_keys', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    bio = db.Column(db.Text, nullable=True, default='Bir şeyler değişmek üzere. Hazır mısın? Başla... biyografinden.')
    date_joined = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    profile_image = db.Column(db.String(120), nullable=False, default='default_profile.jpg')
    cover_image = db.Column(db.String(120), nullable=False, default='default_cover.jpg')
    posts = db.relationship('Post', backref='author', lazy=True)
    website_url = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    expertise_areas = db.Column(db.Text, nullable=True)
    spotify_url = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='basic')
    planType = db.Column(db.String(20), nullable=True)
    planExpiry = db.Column(db.Date, nullable=True)
    followed = db.relationship('Follow', foreign_keys=[Follow.follower_id], backref='follower', lazy='dynamic', cascade='all, delete-orphan')
    followers = db.relationship('Follow', foreign_keys=[Follow.followed_id], backref='followed', lazy='dynamic', cascade='all, delete-orphan')
    badges = db.relationship('Badge', secondary='user_badges', lazy='dynamic', backref=db.backref('users', lazy='dynamic'))
    received_notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref='recipient', lazy='dynamic', cascade='all, delete-orphan')
    sent_notifications = db.relationship('Notification', foreign_keys='Notification.sender_id', backref='sender', lazy='dynamic')
    lifted_posts = db.relationship('Lift', backref='lifter', lazy='dynamic', cascade='all, delete-orphan')

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(f)
            db.session.commit()
            create_follow_notification(self, user)
            db.session.commit()
    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f: db.session.delete(f); db.session.commit()
    def is_following(self, user):
        return self.followed.filter_by(followed_id=user.id).first() is not None
    def get_follower_count(self):
        return self.followers.count()
    def get_followed_count(self):
        return self.followed.count()
    def get_echo_topic_count(self):
        return Post.query.filter_by(user_id=self.id, post_type='echo').filter(Post.echo_topic != None, Post.echo_topic != '').distinct(Post.echo_topic).count()
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def has_badge(self, badge_name):
        return any(badge.name == badge_name for badge in self.badges)
    def get_blue_tick_html(self):
        blue_tick_badge = Badge.query.filter_by(name='Mavi Tik').first()
        if blue_tick_badge and blue_tick_badge in self.badges:
            return '<i class="fas fa-check-circle blue-tick-icon" title="Doğrulanmış Hesap"></i>'
        return ''
    def has_lifted(self, post):
        return Lift.query.filter(Lift.user_id == self.id, Lift.post_id == post.id).count() > 0
    def is_lifted_by_current_user(self, post):
        return Lift.query.filter_by(user_id=self.id, post_id=post.id).first() is not None

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=True)
    image_file = db.Column(db.String(120), nullable=True)
    video_file = db.Column(db.String(120), nullable=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post_obj', lazy=True, cascade='all, delete-orphan')
    post_type = db.Column(db.String(10), nullable=False, default='media')
    echo_topic = db.Column(db.String(100), nullable=True)
    rises = db.Column(db.Integer, nullable=False, default=0) # Sadece görsel sayaç için tutuluyor
    fades = db.Column(db.Integer, nullable=False, default=0) # Sadece görsel sayaç için tutuluyor
    echo_rises_received = db.relationship('EchoRise', backref='echo_post', lazy=True, cascade='all, delete-orphan')
    echo_fades_received = db.relationship('EchoFade', backref='echo_post', lazy=True, cascade='all, delete-orphan')
    lifts = db.relationship('Lift', backref='post', lazy=True, cascade='all, delete-orphan')
    trend_score = db.Column(db.Float, nullable=False, default=0.0, index=True)

class Lift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_post_lift_uc'),)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    date_liked = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_post_uc'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.relationship('User', backref='comments', lazy=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    like_id = db.Column(db.Integer, db.ForeignKey('like.id'), nullable=True)
    lift_id = db.Column(db.Integer, db.ForeignKey('lift.id'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    post_related_obj = db.relationship('Post', foreign_keys=[post_id])
    comment_related_obj = db.relationship('Comment', foreign_keys=[comment_id])
    like_related_obj = db.relationship('Like', foreign_keys=[like_id])
    lift_related_obj = db.relationship('Lift', foreign_keys=[lift_id])

class EchoRise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    score = db.Column(db.Float, nullable=False, default=0.0)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_echorise_uc'),)

class EchoFade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    score = db.Column(db.Float, nullable=False, default=0.0)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_echofade_uc'),)

# ... (Diğer tüm modelleriniz burada değişmeden kalır) ...
class InnerEcho(db.Model):
    __tablename__ = 'inner_echo'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    type = db.Column(db.String(10), nullable=False, default='echo')
    visibility = db.Column(db.String(20), nullable=False, default='public')
    user = db.relationship('User', backref='echo_lifts')

class InnerClip(db.Model):
    __tablename__ = 'inner_clip'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    visibility = db.Column(db.String(20), nullable=False, default='public')
    user = db.relationship('User', backref='inner_clips')

class InnerEchoLift(db.Model):
    __tablename__ = 'inner_echo_lift'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    echo_id = db.Column(db.Integer, db.ForeignKey('inner_echo.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'echo_id', name='_user_echo_lift_uc'),)

class InnerClipLift(db.Model):
    __tablename__ = 'inner_clip_lift'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    clip_id = db.Column(db.Integer, db.ForeignKey('inner_clip.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'clip_id', name='_user_clip_lift_uc'),)
    user = db.relationship('User', backref='clip_lifts')

class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    members = db.relationship('CommunityMembership', back_populates='community', cascade='all, delete-orphan')
    posts = db.relationship('CommunityPost', back_populates='community', cascade='all, delete-orphan')

class PremiumCommunity(db.Model):
    __tablename__ = 'premium_community'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    members = db.relationship('PremiumCommunityMembership', back_populates='community', cascade='all, delete-orphan')
    posts = db.relationship('PremiumCommunityPost', back_populates='community', cascade='all, delete-orphan')

class PremiumCommunityMembership(db.Model):
    __tablename__ = 'premium_community_membership'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey('premium_community.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='premium_community_memberships')
    community = db.relationship('PremiumCommunity', back_populates='members')

class PremiumCommunityPost(db.Model):
    __tablename__ = 'premium_community_post'
    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey('premium_community.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(120), nullable=True)
    video_file = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    community = db.relationship('PremiumCommunity', back_populates='posts')
    user = db.relationship('User', backref='premium_community_posts')

class LikePremiumCommunityPost(db.Model):
    __tablename__ = 'like_premium_community_post'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('premium_community_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_premium_post_uc'),)

class PremiumCommunityPostComment(db.Model):
    __tablename__ = 'premium_community_post_comment'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('premium_community_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    post = db.relationship('PremiumCommunityPost', backref='comments')

class CommunityMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey('community.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='community_memberships')
    community = db.relationship('Community', back_populates='members')

class CommunityPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey('community.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(120), nullable=True)
    video_file = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    community = db.relationship('Community', back_populates='posts')
    user = db.relationship('User', backref='community_posts')

class CommunityPostComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    post = db.relationship('CommunityPost', backref='comments')

class Blink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='blinks', lazy=True)
    image_url = db.Column(db.String(200), nullable=True) # Resim veya video URL'si
    video_url = db.Column(db.String(200), nullable=True) # Video URL'si
    text_content = db.Column(db.String(500), nullable=True) # Metin içeriği
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    # Blink'in 24 saat içinde geçerli olup olmadığını kontrol eden özellik
    @property
    def is_active(self):
        return datetime.utcnow() - self.timestamp < timedelta(hours=24)

    def __repr__(self):
        return f'<Blink {self.id} by User {self.user_id}>'

# --- Context Processors ve Template Filters ---
# app.py dosyasındaki mevcut inject_premium_context fonksiyonunu bununla değiştirin

# app.py'de MEVCUT inject_premium_context FONKSİYONUNU BUNUNLA DEĞİŞTİRİN

@app.context_processor
def inject_premium_context():
    is_premium = False
    is_infinity = False
    infinity_network = None
    membered_networks = []

    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        is_premium = getattr(current_user, 'role', None) == 'premium'
        is_infinity = getattr(current_user, 'planType', None) == 'infinity'
        
        if is_infinity:
            try:
                infinity_network = InfinityNetwork.query.filter_by(user_id=current_user.id).first()
            except Exception:
                infinity_network = None
        
        memberships = InfinityNetworkMember.query.filter_by(user_id=current_user.id).options(joinedload(InfinityNetworkMember.network)).all()
        if memberships:
            owned_network_id = infinity_network.id if infinity_network else -1
            membered_networks = [m.network for m in memberships if m.network.id != owned_network_id]

    return dict(
        PREMIUM_PLANS=PREMIUM_PLANS, 
        is_premium=is_premium, 
        is_infinity=is_infinity, 
        infinity_network=infinity_network,
        membered_networks=membered_networks
    )

@app.template_filter('process_tags')
def process_tags_filter(text):
    return process_content_for_tags(text)

@app.context_processor
def inject_unread_notifications_count():
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(unread_notifications_count=unread_count)
    return dict(unread_notifications_count=0)

# --- Yardımcı Bildirim ve Rozet Fonksiyonları (değişmedi) ---
def create_follow_notification(follower_user, followed_user):
    message = f"{follower_user.username} seni takip etmeye başladı!"
    notification = Notification(user_id=followed_user.id, sender_id=follower_user.id, notification_type='follow', message=message)
    db.session.add(notification)
def create_like_notification(liker_user, post_obj):
    if liker_user.id == post_obj.author.id: return
    message = f"{liker_user.username} gönderini beğendi."
    notification = Notification(user_id=post_obj.author.id, sender_id=liker_user.id, post_id=post_obj.id, notification_type='like', message=message)
    db.session.add(notification)
def create_comment_notification(commenter_user, post_obj, comment_obj):
    if commenter_user.id == post_obj.author.id: return
    message = f"{commenter_user.username} gönderine yorum yaptı: '{comment_obj.content[:20]}...'"
    notification = Notification(user_id=post_obj.author.id, sender_id=commenter_user.id, post_id=post_obj.id, comment_id=comment_obj.id, notification_type='comment', message=message)
    db.session.add(notification)
def create_echo_rise_notification(riser_user, echo_post_obj):
    if riser_user.id == echo_post_obj.author.id: return
    message = f"{riser_user.username} Echo gönderini 'Rise'ladı."
    notification = Notification(user_id=echo_post_obj.author.id, sender_id=riser_user.id, post_id=echo_post_obj.id, notification_type='echo_rise', message=message)
    db.session.add(notification)
def create_echo_fade_notification(fader_user, echo_post_obj):
    if fader_user.id == echo_post_obj.author.id: return
    message = f"{fader_user.username} Echo gönderini 'Fade'ledi."
    notification = Notification(user_id=echo_post_obj.author.id, sender_id=fader_user.id, post_id=echo_post_obj.id, notification_type='echo_fade', message=message)
    db.session.add(notification)
def create_lift_notification(lifter_user, post_obj, lift_obj):
    if lifter_user.id == post_obj.author.id: return
    message = f"{lifter_user.username} gönderini Lift etti."
    notification = Notification(user_id=post_obj.author.id, sender_id=lifter_user.id, post_id=post_obj.id, lift_id=lift_obj.id, notification_type='lift', message=message)
    db.session.add(notification)

def update_user_badges(user_id):
    user = User.query.get(user_id)
    if not user: return
    follower_count = user.get_follower_count()
    echo_topic_count = user.get_echo_topic_count()
    current_badge_objects = user.badges.all()
    current_badge_names = {badge.name for badge in current_badge_objects}
    all_badges = Badge.query.order_by(Badge.min_followers).all()
    for badge in all_badges:
        should_have_badge = False
        if badge.name in ['Sosyal Yeni Başlayan', 'Popüler Vatandaş', 'Topluluk Lideri', 'Socento Fenomeni']:
            if follower_count >= badge.min_followers: should_have_badge = True
        elif badge.name in ['Whisper', 'Resonance', 'Echo Storm']:
            if echo_topic_count >= badge.min_followers: should_have_badge = True
        elif badge.name in ['Mavi Tik', 'Envy Circle']: continue
        has_badge = badge.name in current_badge_names
        if should_have_badge and not has_badge: user.badges.append(badge)
        elif not should_have_badge and has_badge:
            badge_to_remove = next((b for b in current_badge_objects if b.name == badge.name), None)
            if badge_to_remove: user.badges.remove(badge_to_remove)
    db.session.commit()

def process_content_for_tags(content):
    if not content: return ""
    def replace_mention(match):
        username = match.group(1)
        user = User.query.filter_by(username=username).first()
        blue_tick_html = user.get_blue_tick_html() if user else ''
        return f'<a href="/profile/{username}" class="mention-link">@{username}{blue_tick_html}</a>'
    content = re.sub(r'-([a-zA-Z0-9_]+)', lambda m: f'<a href="/echoes/topic/{m.group(1).lower()}" class="echo-topic-link">-{m.group(1)}</a>', content)
    content = re.sub(r'#(\w+)', r'<a href="/search?query=%23\1" class="hashtag-link">#\1</a>', content)
    content = re.sub(r'@(\w+)', replace_mention, content)
    return content

# =================================================================
# === ROTALAR BÖLÜMÜ ===
# =================================================================

POSTS_PER_PAGE = 5
ECHOES_PER_PAGE = 10

# --- Ana İskelet ve Yönlendirme Rotaları ---
@app.route('/')
@login_required
def home():
    initial_feed_type = request.args.get('feed', 'posts')
    recommended_users = User.query.filter(User.id != current_user.id).order_by(User.date_joined.desc()).limit(5).all()
    top_users = User.query.outerjoin(Follow, User.id == Follow.followed_id).group_by(User.id).order_by(func.count(Follow.id).desc()).filter(User.id != current_user.id).limit(5).all()
    all_content = [post.content for post in Post.query.filter(Post.post_type == 'media', Post.content != None).all()]
    hashtag_counts = {}
    for content in all_content:
        for hashtag in re.findall(r'#(\w+)', content):
            hashtag_counts[hashtag.lower()] = hashtag_counts.get(hashtag.lower(), 0) + 1
    top_hashtags = sorted(hashtag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    trending_topics = []
    
    # HATA AYIKLAMA SATIRLARI
    # print(f"DEBUG: Type of datetime.utcnow: {type(datetime.utcnow)}")
    # print(f"DEBUG: Type of timedelta: {type(timedelta)}")
    # print(f"DEBUG: Type of desc: {type(desc)}") # Bu satırı yoruma alabilirsiniz, çünkü artık sqlalchemy.desc kullanıyoruz
    # print(f"DEBUG: Type of Blink.query.filter: {type(Blink.query.filter)}")


    all_blinks_query = Blink.query.filter(Blink.timestamp >= datetime.utcnow() - timedelta(hours=24)).order_by(sqlalchemy.desc(Blink.timestamp))

    # Kendi Blink'leri
    current_user_blinks = all_blinks_query.filter_by(user_id=current_user.id).options(joinedload(Blink.user)).all()

    # Takip edilenlerin Blink'leri
    following_user_ids = [f.followed.id for f in current_user.followed.all()]
    followed_blinks_raw = []
    if following_user_ids:
        followed_blinks_raw = all_blinks_query.filter(Blink.user_id.in_(following_user_ids)).options(joinedload(Blink.user)).all()

    all_active_blinks = current_user_blinks + followed_blinks_raw

    # Burada her kullanıcının aktif Blinkler'ini gruplayıp serileştiriyoruz
    blinks_for_template = {}
    
    # Kendi Blinkler'iniz
    user_blinks_list = [b for b in current_user_blinks if b.is_active]
    if user_blinks_list:
        blinks_for_template[current_user.id] = []
        for blink in user_blinks_list:
            blinks_for_template[current_user.id].append({
                'id': blink.id,
                'user_id': blink.user_id,
                'image_url': blink.image_url,
                'video_url': blink.video_url,
                'text_content': blink.text_content,
                'timestamp': blink.timestamp.isoformat(), # Tarihi string olarak sakla
                'username': blink.user.username,
                'profile_picture_url': url_for('static', filename='uploads/profile_pics/' + blink.user.profile_image) # Kullanıcının profil fotoğrafı URL'si
            })


    # Takip edilenlerin Blinkler'i
    for blink in all_active_blinks:
        if blink.user_id not in blinks_for_template and blink.is_active: # Kendi blinklerimizi tekrar eklememek için
            # Kullanıcının tüm aktif blinkler'ini çek
            user_all_blinks = all_blinks_query.filter_by(user_id=blink.user_id).options(joinedload(Blink.user)).all() # Burada da user'ı yükle
            for b in user_all_blinks:
                if b.is_active:
                    if blink.user_id not in blinks_for_template:
                        blinks_for_template[blink.user_id] = []
                    blinks_for_template[blink.user_id].append({
                        'id': b.id,
                        'user_id': b.user_id,
                        'image_url': b.image_url,
                        'video_url': b.video_url,
                        'text_content': b.text_content,
                        'timestamp': b.timestamp.isoformat(),
                        'username': b.user.username,
                        'profile_picture_url': url_for('static', filename='uploads/profile_pics/' + b.user.profile_image)
                    })
    
    # Kendi Blinkleriniz ile takip ettiklerinizin Blinkler'ini birleştirin
    final_blinks_for_display = {}
    
    # Önce kendi Blinkler'inizi ekleyin
    if current_user.id in blinks_for_template:
        final_blinks_for_display[current_user.id] = blinks_for_template[current_user.id]

    # Ardından takip edilenlerin Blinkler'ini ekleyin (kendi Blinkler'inizi üzerine yazmadan)
    for user_id, blinks_list in blinks_for_template.items():
        if user_id != current_user.id and user_id not in final_blinks_for_display:
            final_blinks_for_display[user_id] = blinks_list

    # Template'e gönderilecek son Blinkler, artık serileştirilmiş durumda
    blinks=final_blinks_for_display # Değişken adını blinks olarak ayarlayın


    return render_template('home.html', 
                            initial_feed=initial_feed_type,
                            recommended_users=recommended_users, 
                            top_users=top_users, 
                            top_hashtags=top_hashtags,
                            trending_topics=trending_topics,
                            blinks=blinks) # Değişkeni buraya geçiyoruz

# --- Infinity Network Rotaları ---

@app.route('/join_network/<code>')
@login_required
def join_network(code):
    invite = InfinityNetworkInvite.query.filter_by(code=code, is_used=False).first()
    if not invite:
        flash('Geçersiz veya kullanılmış davet kodu.', 'danger')
        return redirect(url_for('home'))
    network = InfinityNetwork.query.get(invite.network_id)
    if not network:
        flash('Ağ bulunamadı.', 'danger')
        return redirect(url_for('home'))
    if network.user_id == current_user.id:
        flash('Kendi ağınıza katılamazsınız.', 'info')
        return redirect(url_for('my_network_slug', slug=network.slug))
    existing = InfinityNetworkMember.query.filter_by(network_id=network.id, user_id=current_user.id).first()
    if existing:
        flash('Zaten bu ağa üyesiniz.', 'info')
        return redirect(url_for('my_network_slug', slug=network.slug))
    try:
        new_member = InfinityNetworkMember(network_id=network.id, user_id=current_user.id)
        db.session.add(new_member)
        invite.is_used = True
        db.session.commit()
        flash(f"{network.name} ağına başarıyla katıldınız!", 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Ağa katılırken bir hata oluştu.', 'danger')
    return redirect(url_for('my_network_slug', slug=network.slug))

@app.route('/my_network')
@login_required
def my_network_redirect():
    if not current_user.is_authenticated or getattr(current_user, 'planType', None) != 'infinity':
        flash('Bu sayfa sadece Infinity plan kullanıcılarına açıktır.', 'warning')
        return redirect(url_for('upgrade_plan'))
    network = InfinityNetwork.query.filter_by(user_id=current_user.id).first()
    if network:
        return redirect(url_for('my_network_slug', slug=network.slug))
    else:
        return redirect(url_for('create_network'))

@app.route('/my_network/<slug>')
@login_required
def my_network_slug(slug):
    if not current_user.is_authenticated or getattr(current_user, 'planType', None) != 'infinity':
        flash('Bu sayfa sadece Infinity plan kullanıcılarına açıktır.', 'warning')
        return redirect(url_for('upgrade_plan'))
    network = InfinityNetwork.query.filter_by(slug=slug).first_or_404()
    is_owner = (network.user_id == current_user.id)
    is_member = InfinityNetworkMember.query.filter_by(network_id=network.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_member):
        flash('Bu ağa erişim yetkiniz yok.', 'danger')
        return redirect(url_for('home'))

    latest_invite = None
    if is_owner:
        latest_invite = InfinityNetworkInvite.query.filter_by(network_id=network.id, is_used=False).order_by(InfinityNetworkInvite.created_at.desc()).first()

    invite_status = request.args.get('invite_status')
    members = InfinityNetworkMember.query.filter_by(network_id=network.id).all()
    moderators = [m for m in members if getattr(m, 'is_moderator', False)]
    posts = InfinityNetworkPost.query.filter_by(network_id=network.id).order_by(InfinityNetworkPost.created_at.desc()).all()
    announcements = getattr(network, 'announcements', [])
    polls = getattr(network, 'polls', [])

    return render_template('infinity_network_home.html', 
                            network=network, 
                            members=members, 
                            moderators=moderators, 
                            posts=posts, 
                            announcements=announcements, 
                            polls=polls, 
                            invite_status=invite_status,
                            latest_invite=latest_invite)

# app.py'ye EKLENECEK YENİ BLOG ROTALARI

@app.route('/my_network/<slug>/blog/create', methods=['POST'])
@login_required
def create_blog_post(slug):
    network = InfinityNetwork.query.filter_by(slug=slug, user_id=current_user.id).first_or_404()
    title = request.form.get('title')
    content = request.form.get('content')

    if not title or not content:
        flash('Başlık ve içerik alanları boş bırakılamaz.', 'danger')
        return redirect(url_for('my_network_slug', slug=network.slug))

    blog_slug = create_unique_blog_slug(title)
    new_blog = InfinityNetworkBlog(
        network_id=network.id,
        author_id=current_user.id,
        title=title,
        content=content,
        slug=blog_slug
    )
    db.session.add(new_blog)
    db.session.commit()
    flash('Blog yazınız başarıyla yayınlandı!', 'success')
    return redirect(url_for('view_blog_post', blog_slug=blog_slug))

@app.route('/blog/<blog_slug>')
@login_required
def view_blog_post(blog_slug):
    blog = InfinityNetworkBlog.query.filter_by(slug=blog_slug).options(joinedload(InfinityNetworkBlog.author)).first_or_404()
    network = blog.network
    
    is_member = InfinityNetworkMember.query.filter_by(network_id=network.id, user_id=current_user.id).first() is not None
    is_owner = network.user_id == current_user.id

    if not (is_member or is_owner):
        flash('Bu blog yazısını görüntüleme yetkiniz yok.', 'danger')
        return redirect(url_for('home'))

    user_reaction_obj = InfinityNetworkBlogLike.query.filter_by(user_id=current_user.id, blog_id=blog.id).first()
    user_reaction = user_reaction_obj.reaction if user_reaction_obj else 0
    
    like_count = InfinityNetworkBlogLike.query.filter_by(blog_id=blog.id, reaction=1).count()
    dislike_count = InfinityNetworkBlogLike.query.filter_by(blog_id=blog.id, reaction=-1).count()

    return render_template('blog_post_detail.html', blog=blog, user_reaction=user_reaction, like_count=like_count, dislike_count=dislike_count)

@app.route('/blog/<int:blog_id>/react', methods=['POST'])
@login_required
def react_to_blog(blog_id):
    blog = InfinityNetworkBlog.query.get_or_404(blog_id)
    network = blog.network
    is_member = InfinityNetworkMember.query.filter_by(network_id=network.id, user_id=current_user.id).first() is not None
    is_owner = network.user_id == current_user.id

    if not (is_member or is_owner):
        return jsonify({'success': False, 'error': 'Permission denied'}), 403

    reaction_type = request.json.get('reaction')
    reaction_value = 1 if reaction_type == 'like' else -1
    existing_reaction = InfinityNetworkBlogLike.query.filter_by(user_id=current_user.id, blog_id=blog_id).first()

    if existing_reaction:
        if existing_reaction.reaction == reaction_value:
            db.session.delete(existing_reaction)
        else:
            existing_reaction.reaction = reaction_value
    else:
        new_reaction = InfinityNetworkBlogLike(user_id=current_user.id, blog_id=blog_id, reaction=reaction_value)
        db.session.add(new_reaction)
    
    db.session.commit()
    like_count = InfinityNetworkBlogLike.query.filter_by(blog_id=blog.id, reaction=1).count()
    dislike_count = InfinityNetworkBlogLike.query.filter_by(blog_id=blog.id, reaction=-1).count()

    return jsonify({'success': True, 'like_count': like_count, 'dislike_count': dislike_count})


# YENİ ROTA: Davet Kodu Oluşturma
@app.route('/my_network/<slug>/generate_invite', methods=['POST'])
@login_required
def generate_network_invite_code(slug):
    network = InfinityNetwork.query.filter_by(slug=slug).first_or_404()
    if network.user_id != current_user.id:
        flash('Sadece kendi ağınız için davet kodu oluşturabilirsiniz.', 'danger')
        return redirect(url_for('home'))
    
    # Mevcut kullanılmamış kodları geçersiz kıl (sil)
    InfinityNetworkInvite.query.filter_by(network_id=network.id, is_used=False).delete()
    
    code = generate_key(16)
    while InfinityNetworkInvite.query.filter_by(code=code).first():
        code = generate_key(16)
        
    new_invite = InfinityNetworkInvite(network_id=network.id, code=code)
    db.session.add(new_invite)
    db.session.commit()
    
    flash('Yeni tek kullanımlık davet kodu oluşturuldu! (Eski kodlar geçersiz kılındı)', 'success')
    return redirect(url_for('my_network_slug', slug=network.slug))

# ... (Diğer tüm rotalarınız burada değişmeden kalır) ...

# --- Infinity Ağ Oluşturma ---
@app.route('/create_network', methods=['GET', 'POST'])
@login_required
def create_network():
    if getattr(current_user, 'planType', None) != 'infinity':
        flash('Sadece Infinity plan kullanıcıları ağ oluşturabilir.', 'warning')
        return redirect(url_for('upgrade_plan'))
    network = InfinityNetwork.query.filter_by(user_id=current_user.id).first()
    if network:
        return redirect(url_for('my_network_slug', slug=network.slug))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        theme_color = request.form.get('theme_color')
        logo_file = request.files.get('logo')
        logo_filename = None
        if logo_file and logo_file.filename:
            logo_filename = secure_filename(logo_file.filename)
            logo_file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], logo_filename))
        slug = generate_unique_network_slug(name or f"{current_user.username} Infinity Ağı")
        new_network = InfinityNetwork(
            user_id=current_user.id,
            name=name or f"{current_user.username} Infinity Ağı",
            description=description,
            theme_color=theme_color,
            logo=logo_filename,
            slug=slug
        )
        db.session.add(new_network)
        db.session.commit()
        flash('Infinity ağınız başarıyla oluşturuldu!', 'success')
        return redirect(url_for('my_network_slug', slug=slug))
    return render_template('create_infinity_network.html')

@app.route('/my_network/<slug>/new_post', methods=['POST'])
@login_required
def infinity_network_new_post(slug):
    network = InfinityNetwork.query.filter_by(slug=slug).first_or_404()
    is_owner = (network.user_id == current_user.id)
    is_member = InfinityNetworkMember.query.filter_by(network_id=network.id, user_id=current_user.id).first() is not None

    if not (is_owner or is_member):
        flash('Bu ağda gönderi oluşturma yetkiniz yok.', 'danger')
        return redirect(url_for('home'))

    content = request.form.get('content')
    media_file = request.files.get('media_file')
    image_filename = None
    video_filename = None

    if not content and not (media_file and media_file.filename):
        flash('Gönderi içeriği veya medya dosyası boş olamaz.', 'warning')
        return redirect(url_for('my_network_slug', slug=network.slug))

    if media_file and allowed_file(media_file.filename):
        if allowed_image_file(media_file.filename):
            image_filename = secure_filename(media_file.filename)
            media_file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], image_filename))
        elif allowed_video_file(video_file.filename):
            video_filename = secure_filename(video_file.filename)
            media_file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], video_filename))

    new_post = InfinityNetworkPost(
        network_id=network.id,
        user_id=current_user.id,
        content=content,
        image_file=image_filename,
        video_file=video_filename
    )
    db.session.add(new_post)
    db.session.commit()
    
    flash('Ağ gönderiniz başarıyla oluşturuldu!', 'success')
    return redirect(url_for('my_network_slug', slug=network.slug))

@app.route('/echoes_page')
@login_required
def echoes_page_redirect():
    return redirect(url_for('home', feed='echoes'))

@app.route('/clips_page')
@login_required
def clips_page_redirect():
    return redirect(url_for('home', feed='clips'))


# --- YENİ AJAX İÇERİK YÜKLEME ROTASI (ALGORİTMA GÜNCELLENDİ) ---
@app.route('/load_feed/<string:feed_type>')
@login_required
def load_feed(feed_type):
    page = request.args.get('page', 1, type=int)

    if feed_type == 'posts':
        liked_subquery = db.session.query(Like.post_id).filter(Like.user_id == current_user.id).subquery()
        lifted_subquery = db.session.query(Lift.post_id).filter(Lift.user_id == current_user.id).subquery()
        posts_pagination = db.session.query(Post, (Post.id.in_(liked_subquery)).label('is_liked'), (Post.id.in_(lifted_subquery)).label('is_lifted')).filter(Post.post_type == 'media').order_by(Post.date_posted.desc()).options(joinedload(Post.author), joinedload(Post.likes), joinedload(Post.comments), joinedload(Post.lifts)).paginate(page=page, per_page=POSTS_PER_PAGE, error_out=False)
        posts_with_state = []
        for post, is_liked, is_lifted in posts_pagination.items:
            post.is_liked_by_current_user = is_liked
            post.is_lifted_by_current_user = is_lifted
            posts_with_state.append(post)
        return render_template('_posts_feed.html', posts=posts_with_state, pagination=posts_pagination)

    elif feed_type == 'echoes':
        hours_since_posted = (func.julianday('now') - func.julianday(Post.date_posted)) * 24.0
        final_score_formula = Post.trend_score / func.pow(hours_since_posted + 2, GRAVITY)
        risen_subquery = db.session.query(EchoRise.post_id).filter(EchoRise.user_id == current_user.id).subquery()
        faded_subquery = db.session.query(EchoFade.post_id).filter(EchoFade.user_id == current_user.id).subquery()
        echoes_pagination = db.session.query(
            Post,
            (Post.id.in_(risen_subquery)).label('is_risen'),
            (Post.id.in_(faded_subquery)).label('is_faded')
        ).filter(
            Post.post_type == 'echo'
        ).order_by(
            final_score_formula.desc(), Post.date_posted.desc()
        ).options(
            joinedload(Post.author),
            joinedload(Post.comments)
        ).paginate(page=page, per_page=ECHOES_PER_PAGE, error_out=False)
        echoes_with_state = []
        for echo, is_risen, is_faded in echoes_pagination.items:
            echo.is_risen_by_current_user = is_risen
            echo.is_faded_by_current_user = is_faded
            echoes_with_state.append(echo)
        return render_template('_echoes_feed.html', echoes_posts=echoes_with_state, pagination=echoes_pagination)
        
    elif feed_type == 'clips':
        video_posts = Post.query.filter(Post.video_file != None, Post.video_file != '', Post.post_type == 'media').order_by(func.random()).all()
        return render_template('_clips_feed.html', video_posts=video_posts)

    return jsonify({'error': 'Invalid feed type'}), 400


# --- ECHO OYLAMA ROTALARI (ALGORİTMA GÜNCELLENDİ) ---
@app.route('/echo/<int:echo_id>/rise', methods=['POST'])
@login_required
def rise_echo(echo_id):
    echo_post = Post.query.get_or_404(echo_id)
    if echo_post.post_type != 'echo':
        return jsonify({'success': False, 'error': 'Not an echo post'}), 400
    existing_rise = EchoRise.query.filter_by(user_id=current_user.id, post_id=echo_id).first()
    existing_fade = EchoFade.query.filter_by(user_id=current_user.id, post_id=echo_id).first()
    if existing_fade:
        echo_post.trend_score -= existing_fade.score
        echo_post.fades = max(0, echo_post.fades - 1)
        db.session.delete(existing_fade)
    if existing_rise:
        echo_post.trend_score -= existing_rise.score
        echo_post.rises = max(0, echo_post.rises - 1)
        db.session.delete(existing_rise)
        create_echo_rise_notification(current_user, echo_post)
    else:
        vote_power = _calculate_vote_power(current_user, 2.0)
        echo_post.trend_score += vote_power
        echo_post.rises += 1
        new_rise = EchoRise(user_id=current_user.id, post_id=echo_id, score=vote_power)
        db.session.add(new_rise)
        create_echo_rise_notification(current_user, echo_post)
    db.session.commit()
    return jsonify({'success': True, 'risen': not existing_rise, 'faded': False, 'rise_count': echo_post.rises, 'fade_count': echo_post.fades})

@app.route('/echo/<int:echo_id>/fade', methods=['POST'])
@login_required
def fade_echo(echo_id):
    echo_post = Post.query.get_or_404(echo_id)
    if echo_post.post_type != 'echo':
        return jsonify({'success': False, 'error': 'Not an echo post'}), 400
    existing_rise = EchoRise.query.filter_by(user_id=current_user.id, post_id=echo_id).first()
    existing_fade = EchoFade.query.filter_by(user_id=current_user.id, post_id=echo_id).first()
    if existing_rise:
        echo_post.trend_score -= existing_rise.score
        echo_post.rises = max(0, echo_post.rises - 1)
        db.session.delete(existing_rise)
    if existing_fade:
        echo_post.trend_score -= existing_fade.score
        echo_post.fades = max(0, echo_post.fades - 1)
        db.session.delete(existing_fade)
        create_echo_fade_notification(current_user, echo_post)
    else:
        vote_power = _calculate_vote_power(current_user, -1.0)
        echo_post.trend_score += vote_power
        echo_post.fades += 1
        new_fade = EchoFade(user_id=current_user.id, post_id=echo_id, score=vote_power)
        db.session.add(new_fade)
        create_echo_fade_notification(current_user, echo_post)
    db.session.commit()
    return jsonify({'success': True, 'faded': not existing_fade, 'risen': False, 'rise_count': echo_post.rises, 'fade_count': echo_post.fades})

# ... (Diğer tüm rotalarınız burada değişmeden kalır) ...
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        registration_key = request.form.get('registration_key')
        if not all([username, email, password]):
            flash('Lütfen tüm alanları doldurun.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta zaten kullanılıyor.', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        if registration_key:
            key_record = RegistrationKey.query.filter_by(key_code=registration_key).first()
            if key_record and (not key_record.is_used or key_record.is_reusable):
                key_record.is_used = True
                key_record.used_by_user_id = new_user.id
                key_record.used_at = datetime.utcnow()
                blue_tick_badge = Badge.query.filter_by(name='Mavi Tik').first()
                if blue_tick_badge: new_user.badges.append(blue_tick_badge)
                flash('Hesabınız başarıyla oluşturuldu ve mavi tik kazandınız!', 'success')
            else:
                flash('Geçersiz veya kullanılmış mavi tik anahtarı.', 'warning')
        else:
            flash('Hesabınız başarıyla oluşturuldu!', 'success')
        envy_circle_badge = Badge.query.filter_by(name='Envy Circle').first()
        if envy_circle_badge: new_user.badges.append(envy_circle_badge)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Giriş başarısız. Kullanıcı adı veya şifre yanlış.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        content = request.form.get('content')
        image_file = request.files.get('image_file')
        video_file = request.files.get('video_file')
        post_image_filename, post_video_filename = None, None
        post_type = 'media'
        if not content and not image_file and not video_file:
            flash('Lütfen bir içerik veya medya dosyası sağlayın.', 'danger')
            return redirect(url_for('new_post'))
        if image_file and video_file:
            flash('Sadece bir dosya türü (resim veya video) yükleyebilirsiniz.', 'danger')
            return redirect(url_for('new_post'))
        if image_file and allowed_image_file(image_file.filename):
            post_image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], post_image_filename))
        if video_file and allowed_video_file(video_file.filename):
            post_video_filename = secure_filename(video_file.filename)
            video_file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], post_video_filename))
        if not post_image_filename and not post_video_filename:
            post_type = 'echo'
        post = Post(content=content, image_file=post_image_filename, video_file=post_video_filename, post_type=post_type, author=current_user)
        db.session.add(post)
        db.session.commit()
        if post_type == 'echo' and content:
            match = re.search(r'^-([a-zA-Z0-9_]+)', content)
            if match:
                post.echo_topic = match.group(1).lower()
                db.session.commit()
                update_user_badges(current_user.id)
            return redirect(url_for('echoes_page_redirect'))
        flash('Gönderiniz başarıyla oluşturuldu!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='Yeni Gönderi')

@app.route('/create_blink', methods=['GET', 'POST'])
@login_required
def create_blink():
    if request.method == 'POST':
        text_content = request.form.get('text_content')
        file = request.files.get('media_file') # 'media_file' HTML formdaki input'un name'i olmalı
        image_url = None
        video_url = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['BLINK_UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # Dosya uzantısına göre resim mi video mu olduğunu ayır
            if filename.rsplit('.', 1)[1].lower() in {'mp4', 'mov'}:
                video_url = url_for('static', filename=f'uploads/blinks/{filename}')
            else:
                image_url = url_for('static', filename=f'uploads/blinks/{filename}')
        elif not text_content: # Ne dosya ne de metin varsa
            flash('Blink için metin veya medya eklemelisiniz.', 'danger')
            return redirect(url_for('home'))

        new_blink = Blink(user_id=current_user.id,
                          image_url=image_url,
                          video_url=video_url,
                          text_content=text_content)
        db.session.add(new_blink)
        db.session.commit()
        flash('Blink başarıyla oluşturuldu!', 'success')
        return redirect(url_for('home'))
    return render_template('create_blink.html') # Bu template'i sonra oluşturacağız

@app.route('/delete_blink/<int:blink_id>', methods=['POST'])
@login_required
def delete_blink(blink_id):
    blink = Blink.query.get_or_404(blink_id)
    if blink.user_id != current_user.id and not current_user.is_admin: # Admin yetkiniz varsa
        flash('Bu Blink\'i silme yetkiniz yok.', 'danger')
        return redirect(url_for('home'))

    # Dosyayı sunucudan da silmek isterseniz
    if blink.image_url:
        try:
            os.remove(os.path.join(app.root_path, blink.image_url.replace('/static/', 'static/')))
        except FileNotFoundError:
            pass # Dosya bulunamazsa hata vermemesi için
    if blink.video_url:
        try:
            os.remove(os.path.join(app.root_path, blink.video_url.replace('/static/', 'static/')))
        except FileNotFoundError:
            pass

    db.session.delete(blink)
    db.session.commit()
    flash('Blink başarıyla silindi.', 'success')
    return redirect(url_for('home'))

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    if post.post_type == 'echo': 
        return redirect(url_for('echo_detail', echo_id=post.id))
    if request.method == 'POST':
        comment_content = request.form.get('comment_content')
        if comment_content:
            comment = Comment(content=comment_content, user_id=current_user.id, post_id=post.id)
            db.session.add(comment)
            db.session.commit()
            create_comment_notification(current_user, post, comment)
            db.session.commit()
            return redirect(url_for('post_detail', post_id=post.id))
    comments = Comment.query.filter_by(post_id=post.id).order_by(Comment.date_posted.desc()).all()
    user_liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
    user_lifted = Lift.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
    return render_template('post_detail.html', title=post.title, post=post, comments=comments, user_liked=user_liked, user_lifted=user_lifted)

@app.route('/profile/<string:username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    media_posts = Post.query.filter_by(user_id=user.id, post_type='media').order_by(Post.date_posted.desc()).all()
    echo_posts = Post.query.filter_by(user_id=user.id, post_type='echo').order_by(Post.date_posted.desc()).all()
    lifted_joins = user.lifted_posts.options(joinedload(Lift.post)).order_by(Lift.timestamp.desc()).all()
    unique_lifted_posts = {}
    lifted_videos = []
    lifted_posts = []
    for lift in lifted_joins:
        post = lift.post
        if post and post.id not in unique_lifted_posts:
            unique_lifted_posts[post.id] = post
            if post.video_file:
                lifted_videos.append(post)
            else:
                lifted_posts.append(post)
    update_user_badges(user.id)
    return render_template('profile.html', user=user, posts=media_posts, echo_posts=echo_posts, lifted_videos=lifted_videos, lifted_posts=lifted_posts)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        current_user.website_url = request.form.get('website_url')
        current_user.location = request.form.get('location')
        current_user.expertise_areas = request.form.get('expertise_areas')
        current_user.spotify_url = request.form.get('spotify_url')
        for file_type in ['profile_image', 'cover_image']:
            if file_type in request.files:
                file = request.files[file_type]
                if file.filename != '' and allowed_image_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
                    setattr(current_user, file_type, filename)
        db.session.commit()
        flash('Profiliniz başarıyla güncellendi!', 'success')
        return redirect(url_for('profile', username=current_user.username))
    return render_template('edit_profile.html', title='Profili Düzenle', user=current_user)

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.post_type == 'echo':
        return jsonify({'success': False, 'error': 'Echo posts cannot be liked this way'}), 400
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'success': True, 'liked': False, 'count': len(post.likes), 'like_count': len(post.likes)})
    else:
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        create_like_notification(current_user, post)
        db.session.commit()
        return jsonify({'success': True, 'liked': True, 'count': len(post.likes), 'like_count': len(post.likes)})

@app.route('/post/<int:post_id>/lift', methods=['POST'])
@login_required
def lift_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        lift = Lift.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if lift:
            db.session.delete(lift)
            db.session.commit()
            return jsonify({'success': True, 'lifted': False, 'lift_count': len(post.lifts), 'count': len(post.lifts)})
        else:
            new_lift = Lift(user_id=current_user.id, post_id=post_id)
            db.session.add(new_lift)
            db.session.commit()
            create_lift_notification(current_user, post, new_lift)
            db.session.commit()
            return jsonify({'success': True, 'lifted': True, 'lift_count': len(post.lifts), 'count': len(post.lifts)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/follow/<string:username>', methods=['POST'])
@login_required
def follow_user(username):
    user_to_follow = User.query.filter_by(username=username).first_or_404()
    if user_to_follow.id != current_user.id:
        if not current_user.is_following(user_to_follow):
            current_user.follow(user_to_follow)
            create_follow_notification(current_user, user_to_follow)
            update_user_badges(user_to_follow.id)
            update_user_badges(current_user.id)
            db.session.commit()
            return jsonify({'success': True, 'following': True, 'count': user_to_follow.get_follower_count()})
    return jsonify({'success': False, 'error': 'Cannot follow yourself or already following'})

@app.route('/unfollow/<string:username>', methods=['POST'])
@login_required
def unfollow_user(username):
    user_to_unfollow = User.query.filter_by(username=username).first_or_404()
    if user_to_unfollow.id != current_user.id:
        if current_user.is_following(user_to_unfollow):
            current_user.unfollow(user_to_unfollow)
            update_user_badges(user_to_unfollow.id)
            update_user_badges(current_user.id)
            db.session.commit()
            return jsonify({'success': True, 'following': False, 'count': user_to_unfollow.get_follower_count()})
    return jsonify({'success': False, 'error': 'Cannot unfollow yourself or not following'})
    
@app.route('/search/hashtag/<string:hashtag>')
@login_required
def search_hashtag(hashtag):
    posts = Post.query.filter(Post.content.ilike(f'%#{hashtag}%'), Post.post_type == 'media').order_by(Post.date_posted.desc()).all()
    return render_template('search_results.html', title=f'#{hashtag} Sonuçları', query=f'#{hashtag}', users=[], posts=posts, echoes=[])

@app.route('/echoes/topic/<string:topic>')
@login_required
def echoes_topic(topic):
    echoes = Post.query.options(joinedload(Post.author)).filter(Post.post_type == 'echo', func.lower(Post.echo_topic) == func.lower(topic)).order_by(Post.date_posted.desc()).all()
    user_risen_ids, user_faded_ids = set(), set()
    if echoes:
        post_ids = [post.id for post in echoes]
        rises = EchoRise.query.filter(EchoRise.user_id == current_user.id, EchoRise.post_id.in_(post_ids)).all()
        user_risen_ids = {rise.post_id for rise in rises}
        fades = EchoFade.query.filter(EchoFade.user_id == current_user.id, EchoFade.post_id.in_(post_ids)).all()
        user_faded_ids = {fade.post_id for fade in fades}
    return render_template('echoes_topic_results.html', title=f'-{topic}', query=f'-{topic}', echoes=echoes, topic_name=topic, user_risen_ids=user_risen_ids, user_faded_ids=user_faded_ids)

@app.route('/search')
@login_required
def search():
    query = request.args.get('query', '')
    if not query: return render_template('search_results.html', title='Arama', query='', users=[], posts=[], echoes=[])
    if query.startswith('-'): return redirect(url_for('echoes_topic', topic=query[1:]))
    if query.startswith('#'): return redirect(url_for('search_hashtag', hashtag=query[1:]))
    search_term = f'%{query}%'
    users = User.query.filter(User.username.ilike(search_term)).all()
    posts_results = Post.query.filter(Post.post_type == 'media', Post.content.ilike(search_term)).order_by(Post.date_posted.desc()).all()
    echoes_results = Post.query.filter(Post.post_type == 'echo', Post.content.ilike(search_term)).order_by(Post.date_posted.desc()).all()
    if current_user.is_authenticated:
        for post in posts_results:
            post.is_liked_by_current_user = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
            post.is_lifted_by_current_user = Lift.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
        for echo in echoes_results:
            echo.is_risen_by_current_user = EchoRise.query.filter_by(user_id=current_user.id, post_id=echo.id).first() is not None
            echo.is_faded_by_current_user = EchoFade.query.filter_by(user_id=current_user.id, post_id=echo.id).first() is not None
    return render_template('search_results.html', title=f'Arama: {query}', query=query, users=users, posts=posts_results, echoes=echoes_results)

@app.route('/notifications')
@login_required
def notifications():
    all_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', title='Bildirimler', notifications=all_notifications)

@app.route('/profile/<string:username>/followers')
@login_required
def user_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers_list = [f.follower_user for f in user.followers.all()]
    return render_template('followers_following.html', title=f'{username} Takipçileri', user=user, users_list=followers_list, list_type='followers')

@app.route('/profile/<string:username>/following')
@login_required
def user_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following_list = [f.followed_user for f in user.followed.all()]
    return render_template('followers_following.html', title=f'{username} Takip Edilenler', user=user, users_list=following_list, list_type='following')

@app.route('/echo_detail/<int:echo_id>', methods=['GET', 'POST'])
@login_required
def echo_detail(echo_id):
    echo_post = Post.query.get_or_404(echo_id)
    if echo_post.post_type != 'echo': return redirect(url_for('home'))
    if request.method == 'POST':
        comment_content = request.form.get('comment_content')
        if comment_content:
            comment = Comment(content=comment_content, user_id=current_user.id, post_id=echo_post.id)
            db.session.add(comment)
            db.session.commit()
            create_comment_notification(current_user, echo_post, comment)
            db.session.commit()
            return redirect(url_for('echo_detail', echo_id=echo_post.id))
    comments = Comment.query.filter_by(post_id=echo_post.id).order_by(Comment.date_posted.desc()).all()
    user_risen = EchoRise.query.filter_by(user_id=current_user.id, post_id=echo_id).first() is not None
    user_faded = EchoFade.query.filter_by(user_id=current_user.id, post_id=echo_id).first() is not None
    return render_template('echo_detail.html', title=echo_post.content[:30], echo_post=echo_post, comments=comments, user_risen=user_risen, user_faded=user_faded)

# ... (Tüm Topluluk ve Premium Rotalarınız burada değişmeden kalır) ...
@app.route('/communities')
@login_required
def communities():
    return redirect(url_for('premium_communities'))
@app.route('/community/<int:community_id>')
@login_required
def community_page(community_id):
    flash('Premium topluluklara göz atabilirsiniz.', 'info')
    return redirect(url_for('premium_communities'))
@app.route('/create_community', methods=['GET', 'POST'])
@login_required
def create_community():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        category = request.form.get('category')
        cover_image = None
        file = request.files.get('cover_image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
            cover_image = filename
        community = Community(name=name, description=description, category=category, cover_image=cover_image, creator_id=current_user.id)
        db.session.add(community)
        db.session.commit()
        membership = CommunityMembership(user_id=current_user.id, community_id=community.id)
        db.session.add(membership)
        db.session.commit()
        flash('Topluluk başarıyla oluşturuldu!', 'success')
        return redirect(url_for('community_page', community_id=community.id))
    return render_template('create_community.html')
@app.route('/community/<int:community_id>/join')
@login_required
def join_community(community_id):
    community = Community.query.get_or_404(community_id)
    if not CommunityMembership.query.filter_by(user_id=current_user.id, community_id=community.id).first():
        membership = CommunityMembership(user_id=current_user.id, community_id=community.id)
        db.session.add(membership)
        db.session.commit()
        flash('Topluluğa katıldınız!', 'success')
    return redirect(url_for('community_page', community_id=community.id))
@app.route('/community/<int:community_id>/leave')
@login_required
def leave_community(community_id):
    membership = CommunityMembership.query.filter_by(user_id=current_user.id, community_id=community_id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash('Topluluktan ayrıldınız.', 'info')
    return redirect(url_for('community_page', community_id=community_id))
@app.route('/community/<int:community_id>/post', methods=['POST'])
@login_required
def community_post(community_id):
    community = Community.query.get_or_404(community_id)
    content = request.form.get('content')
    image_file, video_file = None, None
    image = request.files.get('image_file')
    video = request.files.get('video_file')
    if image and allowed_image_file(image.filename):
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['POST_MEDIA_FOLDER'], filename))
        image_file = filename
    if video and allowed_video_file(video.filename):
        filename = secure_filename(video.filename)
        video.save(os.path.join(app.config['POST_MEDIA_FOLDER'], filename))
        video_file = filename
    post = CommunityPost(community_id=community.id, user_id=current_user.id, content=content, image_file=image_file, video_file=video_file)
    db.session.add(post)
    db.session.commit()
    flash('Toplulukta paylaşım yapıldı!', 'success')
    return redirect(url_for('community_page', community_id=community.id))
@app.route('/community_post_comments/<int:post_id>')
@login_required
def community_post_comments(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    comments = CommunityPostComment.query.filter_by(post_id=post.id).order_by(CommunityPostComment.created_at.desc()).all()
    return render_template('_community_post_comments.html', post=post, comments=comments)
@app.route('/community_post_comment/<int:post_id>', methods=['POST'])
@login_required
def community_post_comment(post_id):
    post = CommunityPost.query.get_or_404(post_id)
    content = request.form.get('content')
    if content and content.strip():
        comment = CommunityPostComment(post_id=post.id, user_id=current_user.id, content=content.strip())
        db.session.add(comment)
        db.session.commit()
        flash('Yorumunuz eklendi!', 'success')
    return redirect(url_for('community_post_comments', post_id=post.id))

def register_premium_community_routes(app):
    @app.route('/premium_community_post/<int:post_id>/like', methods=['POST'])
    @login_required
    def like_premium_community_post(post_id):
        post = PremiumCommunityPost.query.get_or_404(post_id)
        like = LikePremiumCommunityPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if like:
            db.session.delete(like)
            db.session.commit()
            return jsonify({'success': True, 'liked': False, 'count': LikePremiumCommunityPost.query.filter_by(post_id=post_id).count()})
        else:
            new_like = LikePremiumCommunityPost(user_id=current_user.id, post_id=post_id)
            db.session.add(new_like)
            db.session.commit()
            return jsonify({'success': True, 'liked': True, 'count': LikePremiumCommunityPost.query.filter_by(post_id=post_id).count()})
    @app.route('/premium_community_post/<int:post_id>/comment', methods=['POST'])
    @login_required
    def comment_premium_community_post(post_id):
        post = PremiumCommunityPost.query.get_or_404(post_id)
        content = request.json.get('content')
        if not content or len(content.strip()) < 1:
            return jsonify({'success': False, 'error': 'Yorum boş olamaz.'}), 400
        comment = PremiumCommunityPostComment(user_id=current_user.id, post_id=post_id, content=content.strip())
        db.session.add(comment)
        db.session.commit()
        return jsonify({'success': True, 'comment': {'id': comment.id, 'user': current_user.username, 'content': comment.content, 'created_at': comment.created_at.strftime('%d %B %Y, %H:%M')}})
    @app.route('/premium_community/<int:community_id>/join', methods=['POST'])
    @login_required
    def join_premium_community(community_id):
        if current_user.role != 'premium':
            flash('Premium topluluklara katılmak için premium olmalısınız.', 'warning')
            return redirect(url_for('upgrade_plan'))
        community = PremiumCommunity.query.get_or_404(community_id)
        plan_type = current_user.planType
        plan_info = PREMIUM_PLANS.get(plan_type)
        if not plan_info:
            flash('Premium planınız bulunamadı. Lütfen planınızı kontrol edin.', 'danger')
            return redirect(url_for('upgrade_plan'))
        limit = plan_info.get('community_limit')
        user_membership_count = PremiumCommunityMembership.query.filter_by(user_id=current_user.id).count()
        if limit is not None and user_membership_count >= limit:
            flash(f"{plan_info['name']} planı ile en fazla {limit} premium topluluğa katılabilirsiniz.", 'warning')
            return redirect(url_for('premium_community_page', community_id=community_id))
        existing = PremiumCommunityMembership.query.filter_by(user_id=current_user.id, community_id=community.id).first()
        if existing:
            flash('Zaten bu topluluğun üyesisiniz.', 'info')
            return redirect(url_for('premium_community_page', community_id=community_id))
        membership = PremiumCommunityMembership(user_id=current_user.id, community_id=community.id)
        db.session.add(membership)
        db.session.commit()
        flash('Topluluğa başarıyla katıldınız!', 'success')
        return redirect(url_for('premium_community_page', community_id=community_id))
    @app.route('/premium_communities')
    @login_required
    def premium_communities():
        if current_user.role != 'premium':
            flash('Premium topluluklara erişmek için premium olmalısınız.', 'warning')
            return redirect(url_for('upgrade_plan'))
        all_premium_communities = PremiumCommunity.query.order_by(PremiumCommunity.created_at.desc()).all()
        plan_type = current_user.planType
        plan_info = PREMIUM_PLANS.get(plan_type)
        limit = plan_info.get('community_limit') if plan_info else None
        user_community_count = PremiumCommunity.query.filter_by(creator_id=current_user.id).count()
        is_limit_reached = limit is not None and user_community_count >= limit
        return render_template('premium_communities.html', communities=all_premium_communities, is_limit_reached=is_limit_reached)
    @app.route('/premium_community/<int:community_id>')
    @login_required
    def premium_community_page(community_id):
        if current_user.role != 'premium':
            flash('Premium topluluklara erişmek için premium olmalısınız.', 'warning')
            return redirect(url_for('upgrade_plan'))
        community = PremiumCommunity.query.get_or_404(community_id)
        posts = PremiumCommunityPost.query.filter_by(community_id=community.id).order_by(PremiumCommunityPost.created_at.desc()).all()
        is_member = PremiumCommunityMembership.query.filter_by(user_id=current_user.id, community_id=community.id).first() is not None
        enriched_posts = []
        for post in posts:
            is_liked = LikePremiumCommunityPost.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
            likes = LikePremiumCommunityPost.query.filter_by(post_id=post.id).all()
            comments = PremiumCommunityPostComment.query.filter_by(post_id=post.id).all()
            post.is_liked_by_current_user = is_liked
            post.likes = likes
            post.comments = comments
            enriched_posts.append(post)
        return render_template('premium_community_page.html', community=community, posts=enriched_posts, is_member=is_member)
    @app.route('/create_premium_community', methods=['GET', 'POST'])
    @login_required
    def create_premium_community():
        if current_user.role != 'premium':
            flash('Premium topluluk oluşturmak için premium olmalısınız.', 'warning')
            return redirect(url_for('upgrade_plan'))
        plan_type = current_user.planType
        plan_info = PREMIUM_PLANS.get(plan_type)
        if not plan_info:
            flash('Premium planınız bulunamadı. Lütfen planınızı kontrol edin.', 'danger')
            return redirect(url_for('upgrade_plan'))
        limit = plan_info.get('community_limit')
        user_community_count = PremiumCommunity.query.filter_by(creator_id=current_user.id).count()
        if limit is not None and user_community_count >= limit:
            flash(f"{plan_info['name']} planı ile en fazla {limit} premium topluluk oluşturabilirsiniz.", 'warning')
            return redirect(url_for('premium_communities'))
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            category = request.form.get('category')
            cover_image = None
            file = request.files.get('cover_image')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
                cover_image = filename
            community = PremiumCommunity(name=name, description=description, category=category, cover_image=cover_image, creator_id=current_user.id)
            db.session.add(community)
            db.session.commit()
            membership = PremiumCommunityMembership(user_id=current_user.id, community_id=community.id)
            db.session.add(membership)
            db.session.commit()
            flash('Premium topluluk başarıyla oluşturuldu!', 'success')
            return redirect(url_for('premium_community_page', community_id=community.id))
        return render_template('create_premium_community.html')
def register_inner_network_routes(app):
    from functools import wraps
    def premium_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'premium':
                flash('Bu alana erişim için planınızı yükseltin.', 'warning')
                return redirect(url_for('upgrade_plan'))
            return f(*args, **kwargs)
        return decorated_function
        
    @app.route('/inner-network', methods=['GET'])
    @login_required
    @premium_required
    def inner_network_home():
        premium_ids = [uid for uid, in db.session.query(User.id).filter_by(role='premium').all()]
        echoes = InnerEcho.query.filter(InnerEcho.user_id.in_(premium_ids)).options(joinedload(InnerEcho.user)).all()
        clips = InnerClip.query.filter(InnerClip.user_id.in_(premium_ids)).options(joinedload(InnerClip.user)).all()
        all_content = echoes + clips
        all_content.sort(key=lambda x: x.created_at, reverse=True)
        return render_template('inner_network_home.html', posts=all_content)
    
    @app.route('/inner-network/new-echo', methods=['POST'])
    @login_required
    @premium_required
    def new_inner_echo():
        content = request.form.get('content')
        if not content or len(content.strip()) < 2:
            flash('Echo içeriği çok kısa.', 'warning')
            return redirect(url_for('inner_network_home'))
        echo = InnerEcho(user_id=current_user.id, content=content.strip())
        db.session.add(echo)
        db.session.commit()
        flash('Premium Echo başarıyla paylaşıldı!', 'success')
        return redirect(url_for('inner_network_home'))
    @app.route('/inner-network/new-clip', methods=['POST'])
    @login_required
    @premium_required
    def new_inner_clip():
        description = request.form.get('description')
        file = request.files.get('clip_file')
        if not file or file.filename == '':
            flash('Video dosyası seçmelisiniz.', 'warning')
            return redirect(url_for('inner_network_home'))
        if not allowed_video_file(file.filename):
            flash('Geçersiz video dosyası.', 'danger')
            return redirect(url_for('inner_network_home'))
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['POST_MEDIA_FOLDER'], filename)
        file.save(save_path)
        video_url = url_for('static', filename='uploads/post_media/' + filename)
        clip = InnerClip(user_id=current_user.id, description=description, video_url=video_url)
        db.session.add(clip)
        db.session.commit()
        flash('Premium Klip başarıyla yüklendi!', 'success')
        return redirect(url_for('inner_network_home'))
    @app.route('/premium_community/<int:community_id>/new_post', methods=['POST'])
    @login_required
    def new_premium_community_post(community_id):
        if current_user.role != 'premium':
            flash('Premium topluluklara paylaşım için premium olmalısınız.', 'warning')
            return redirect(url_for('premium_community_page', community_id=community_id))
        community = PremiumCommunity.query.get_or_404(community_id)
        is_member = PremiumCommunityMembership.query.filter_by(user_id=current_user.id, community_id=community.id).first()
        if not is_member:
            flash('Bu topluluğa üye olmalısınız.', 'warning')
            return redirect(url_for('premium_community_page', community_id=community_id))
        content = request.form.get('content')
        file = request.files.get('media_file')
        image_file, video_file = None, None
        if file and file.filename:
            if allowed_image_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], filename))
                image_file = filename
            elif allowed_video_file(file.filename):
                filename = secure_filename(file.filename)
                video.save(os.path.join(app.config['POST_MEDIA_FOLDER'], filename))
                video_file = filename
            else:
                flash('Geçersiz dosya türü.', 'danger')
                return redirect(url_for('premium_community_page', community_id=community_id))
        post = PremiumCommunityPost(user_id=current_user.id, community_id=community.id, content=content, image_file=image_file, video_file=video_file)
        db.session.add(post)
        db.session.commit()
        flash('Topluluk paylaşımı başarıyla gönderildi!', 'success')
        return redirect(url_for('premium_community_page', community_id=community_id))
    @app.route('/upgrade-plan', methods=['GET', 'POST'])
    @login_required
    def upgrade_plan():
        if current_user.role == 'premium' and current_user.planType:
            return redirect(url_for('inner_network_home'))
        if request.method == 'POST':
            planType = request.form.get('planType')
            if planType in PREMIUM_PLANS:
                current_user.role = 'premium'
                current_user.planType = planType
                current_user.planExpiry = datetime.utcnow().date() + timedelta(days=30)
                db.session.commit()
                flash('Planınız başarıyla yükseltildi!', 'success')
                return redirect(url_for('inner_network_home'))
            else:
                flash('Geçersiz plan seçimi.', 'danger')
        return render_template('upgrade_plan.html', plans=PREMIUM_PLANS, user=current_user)
    @app.route('/locked_premium')
    @login_required
    def locked_premium():
        return render_template('locked_premium.html')
def clean_expired_blinks():
    with app.app_context(): # Flask uygulama bağlamı içinde çalışmalı
        print("Süresi dolan Blinkler temizleniyor...")
        # Süresi dolmuş Blinkler (24 saatten eski)
        expired_blinks = Blink.query.filter(Blink.timestamp < datetime.utcnow() - timedelta(hours=24)).all()
        for blink in expired_blinks:
            # Dosyayı da sunucudan silmek isterseniz
            if blink.image_url and 'uploads/blinks' in blink.image_url:
                try:
                    # url_for ile oluşturulan path'i gerçek dosya sistemindeki path'e çevir
                    relative_path = blink.image_url.replace(url_for('static', filename=''), '')
                    full_path = os.path.join(app.root_path, 'static', relative_path)
                    os.remove(full_path)
                    print(f"Silindi: {full_path}")
                except FileNotFoundError:
                    print(f"Dosya bulunamadı: {full_path}")
                except Exception as e:
                    print(f"Dosya silinirken hata oluştu {full_path}: {e}")
            if blink.video_url and 'uploads/blinks' in blink.video_url:
                try:
                    relative_path = blink.video_url.replace(url_for('static', filename=''), '')
                    full_path = os.path.join(app.root_path, 'static', relative_path)
                    os.remove(full_path)
                    print(f"Silindi: {full_path}")
                except FileNotFoundError:
                    print(f"Dosya bulunamadı: {full_path}")
                except Exception as e:
                    print(f"Dosya silinirken hata oluştu {full_path}: {e}")
            db.session.delete(blink)
        db.session.commit()
        print(f"{len(expired_blinks)} adet Blink temizlendi.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        badges_to_create = {
            'Sosyal Yeni Başlayan': ('50 takipçiye ulaştı.', 'fas fa-leaf', 50),
            'Popüler Vatandaş': ('100 takipçiye ulaştı.', 'fas fa-star', 100),
            'Topluluk Lideri': ('500 takipçiye ulaştı.', 'fas fa-crown', 500),
            'Socento Fenomeni': ('1000 takipçiye ulaştı.', 'fas fa-fire', 1000),
            'Envy Circle': ('Socento\'ya yeni katılanlara özel rozet.', 'fa-regular fa-circle', 0),
            'Mavi Tik': ('Doğrulanmış hesap.', 'fas fa-check-circle', 0),
            'Whisper': ('10 benzersiz Echo konu başlığı açtı.', 'fas fa-comment-dots', 10),
            'Resonance': ('50 benzersiz Echo konu başlığı açtı.', 'fas fa-volume-up', 50),
            'Echo Storm': ('100 benzersiz Echo konu başlığı açtı.', 'fas fa-wind', 100),
        }
        for name, (desc, icon, val) in badges_to_create.items():
            if not Badge.query.filter_by(name=name).first():
                db.session.add(Badge(name=name, description=desc, icon_class=icon, min_followers=val))
        db.session.commit()

        ADMIN_KEY_CODE = "ADMINGEMINI2025"
        if not RegistrationKey.query.filter_by(key_code=ADMIN_KEY_CODE).first():
            db.session.add(RegistrationKey(key_code=ADMIN_KEY_CODE, is_reusable=True))
            db.session.commit()

        register_premium_community_routes(app)
        register_inner_network_routes(app)
if __name__ == '__main__':
    # Buraya APScheduler importunu ekleyin (dosyanın en üstündeki diğer import'ların yanına da ekleyebilirsiniz):
    from apscheduler.schedulers.background import BackgroundScheduler

    # Zamanlayıcıyı başlatma ve görevi ekleme
    scheduler = BackgroundScheduler()
    # clean_expired_blinks fonksiyonunu her saatte bir çalıştırmak için
    scheduler.add_job(func=clean_expired_blinks, trigger="interval", hours=1)
    scheduler.start() # Zamanlayıcıyı başlat

    print("Uygulama çalışıyor ve Blink temizleme görevi planlandı.")


    app.run(debug=True)
