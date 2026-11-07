"""نماذج قاعدة البيانات - AquaSmart DZ"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
ORDER_STATUSES = ["جديد", "قيد التجهيز", "قيد التوصيل", "تم التسليم", "ملغي"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship("Order", backref="user", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False)        # بالدينار الجزائري
    category = db.Column(db.String(50), default="خضروات")
    image_url = db.Column(db.String(300), default="")
    stock = db.Column(db.Integer, default=0)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, default=0)
    duration_hours = db.Column(db.Integer, default=10)
    image_url = db.Column(db.String(300), default="")


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"))
    course = db.relationship("Course")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    items = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(250))
    status = db.Column(db.String(30), default="جديد")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
