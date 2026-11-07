"""نماذج قاعدة البيانات - AquaSmart DZ"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False) # الاسم واللقب
    phone = db.Column(db.String(20), nullable=False)      # رقم الهاتف
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    location = db.Column(db.String(250), default="")      # الموقع الجغرافي
    wilaya = db.Column(db.String(100), default="")        # الولاية
    baladiya = db.Column(db.String(100), default="")      # البلدية
    is_admin = db.Column(db.Boolean, default=False)
    # عند حذف المستخدم تُحذف طلباته أيضاً
    orders = db.relationship("Order", backref="user", cascade="all, delete-orphan")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(300), default="")


class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, default=0)
    date = db.Column(db.Date)
    image_url = db.Column(db.String(300), default="")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey("workshop.id"), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    name = db.Column(db.String(150))

    @property
    def kind_ar(self):
        return "ورشة" if self.workshop_id else "منتج"