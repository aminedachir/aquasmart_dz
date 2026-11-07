"""AquaSmart DZ - تطبيق ويب بنمط تطبيق الجوال (PWA)"""
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   session, abort, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user, login_required,
                         current_user)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Product, Workshop, Order, OrderItem

import os
import uuid
from werkzeug.utils import secure_filename

# إعدادات رفع الملفات
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # الحد الأقصى 5 ميجابايت
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# تأكد من إنشاء مجلد الرفع إذا لم يكن موجوداً
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///aquasmart.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "يرجى تسجيل الدخول أولاً"

STATUS_AR = {"Pending": "قيد الانتظار", "Completed": "مكتمل"}


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def safe_next(target):
    if target and target.startswith("/") and not urlparse(target).netloc:
        return target
    return None


@app.template_filter("status_ar")
def status_ar(s):
    return STATUS_AR.get(s, s)


@app.context_processor
def inject_cart_count():
    return {"cart_count": sum(session.get("cart", {}).values())}


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


SPLASH_AUTO_REDIRECT_GUEST = False


@app.route("/")
def splash():
    logged = current_user.is_authenticated
    return render_template("splash.html", logged=logged,
        auto=logged or SPLASH_AUTO_REDIRECT_GUEST,
        target=url_for("home") if logged else url_for("login"))


# ===== تم تحديث دالة التسجيل هنا =====
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        confirm_pw = request.form.get("confirm_password")
        
        if User.query.filter_by(email=email).first():
            flash("البريد الإلكتروني مستخدم مسبقاً", "error")
        elif len(pw) < 6:
            flash("كلمة المرور يجب ألا تقل عن 6 أحرف", "error")
        elif pw != confirm_pw:
            flash("كلمتا المرور غير متطابقتين", "error")
        else:
            u = User(
                full_name=request.form["full_name"].strip(),
                phone=request.form["phone"].strip(),
                email=email,
                password_hash=generate_password_hash(pw),
                location=request.form.get("location", "").strip(),
                wilaya=request.form.get("wilaya", "").strip(),
                baladiya=request.form.get("baladiya", "").strip()
            )
            db.session.add(u)
            db.session.commit()
            login_user(u)
            flash("مرحباً بك في AquaSmart DZ!", "success")
            return redirect(url_for("home"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            login_user(u)
            return redirect(safe_next(request.args.get("next")) or url_for("home"))
        flash("البريد أو كلمة المرور غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    session.pop("cart", None)
    return redirect(url_for("login"))


# ============================ B) صفحات المستخدم ============================
@app.route("/home")
@login_required
def home():
    return render_template("home.html",
        products=Product.query.order_by(Product.id).limit(6).all(),
        workshops=Workshop.query.order_by(Workshop.id.desc()).limit(5).all())


@app.route("/products")
@login_required
def products():
    return render_template("products.html", products=Product.query.all())


@app.route("/workshops")
@login_required
def workshops():
    in_cart = {k for k in session.get("cart", {}) if k.startswith("w:")}
    return render_template("workshops.html", workshops=Workshop.query.order_by(Workshop.date).all(),
                           in_cart=in_cart)


def get_cart_rows():
    rows, total = [], 0.0
    for key, qty in session.get("cart", {}).items():
        kind, _, sid = key.partition(":")
        obj = db.session.get(Product if kind == "p" else Workshop, int(sid))
        if obj:
            rows.append(dict(key=key, kind=kind, obj=obj, qty=qty, price=obj.price,
                             name=obj.name if kind == "p" else obj.title,
                             image=obj.image_url))
            total += obj.price * qty
    return rows, total


@app.route("/cart/add/<kind>/<int:item_id>", methods=["POST"])
@login_required
def cart_add(kind, item_id):
    if kind not in ("p", "w"):
        abort(404)
    db.get_or_404(Product if kind == "p" else Workshop, item_id)
    cart, key = session.get("cart", {}), f"{kind}:{item_id}"
    if kind == "w":
        if key in cart:
            flash("هذه الورشة في سلتك بالفعل", "info")
        else:
            cart[key] = 1
            flash("تمت إضافة الورشة إلى السلة 🎓", "success")
    else:
        cart[key] = cart.get(key, 0) + 1
        flash("تمت إضافة المنتج إلى السلة 🛒", "success")
    session["cart"] = cart
    return redirect(url_for("products" if kind == "p" else "workshops"))


@app.route("/cart/remove/<key>", methods=["POST"])
@login_required
def cart_remove(key):
    cart = session.get("cart", {})
    cart.pop(key, None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart")
@login_required
def cart():
    rows, total = get_cart_rows()
    return render_template("cart.html", rows=rows, total=total)


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    rows, total = get_cart_rows()
    if not rows:
        flash("السلة فارغة", "error")
        return redirect(url_for("cart"))
    order = Order(user_id=current_user.id, total_price=total, status="Pending")
    for r in rows:
        order.items.append(OrderItem(
            product_id=r["obj"].id if r["kind"] == "p" else None,
            workshop_id=r["obj"].id if r["kind"] == "w" else None,
            quantity=r["qty"], price=r["price"], name=r["name"]))
    db.session.add(order)
    db.session.commit()
    session.pop("cart", None)
    flash("تم إرسال طلبك بنجاح ✅", "success")
    return redirect(url_for("profile"))


@app.route("/profile")
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("profile.html", orders=orders)


# ============================ C) لوحة المدير ============================
@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = [("المستخدمون", User.query.count(), "fa-users", "bg-ocean"),
             ("المنتجات", Product.query.count(), "fa-carrot", "bg-leaf"),
             ("الورشات", Workshop.query.count(), "fa-graduation-cap", "bg-mint !text-ocean"),
             ("الطلبات", Order.query.count(), "fa-basket-shopping", "bg-amber-500")]
    pending = Order.query.filter_by(status="Pending").count()
    return render_template("admin_dashboard.html", stats=stats, pending=pending,
        latest=Order.query.order_by(Order.created_at.desc()).limit(5).all())


@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin_users.html", users=User.query.all())


@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
@admin_required
def admin_user_delete(uid):
    u = db.get_or_404(User, uid)
    if u.id == current_user.id:
        flash("لا يمكنك حذف حسابك الخاص", "error")
    else:
        db.session.delete(u)
        db.session.commit()
        flash("تم حذف المستخدم وطلباته", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:uid>/toggle-admin", methods=["POST"])
@admin_required
def admin_user_toggle(uid):
    u = db.get_or_404(User, uid)
    if u.id == current_user.id:
        flash("لا يمكنك تغيير صلاحياتك بنفسك", "error")
    else:
        u.is_admin = not u.is_admin
        db.session.commit()
        flash("تم تحديث الصلاحية", "success")
    return redirect(url_for("admin_users"))


ENTITIES = {
    "products": dict(model=Product, title="المنتجات", icon="fa-carrot", label="name",
        fields=[("name", "الاسم", "text"), ("description", "الوصف", "textarea"),
                ("price", "السعر (د.ج)", "number"), ("image_url", "رابط الصورة", "text")]),
    "workshops": dict(model=Workshop, title="الورشات", icon="fa-graduation-cap", label="title",
        fields=[("title", "العنوان", "text"), ("description", "الوصف", "textarea"),
                ("price", "السعر (د.ج)", "number"), ("date", "التاريخ", "date"),
                ("image_url", "رابط الصورة", "text")]),
}


def entity_or_404(entity):
    return ENTITIES.get(entity) or abort(404)


@app.route("/admin/<entity>")
@admin_required
def admin_crud(entity):
    cfg = entity_or_404(entity)
    items = cfg["model"].query.all()
    jsmap = {i.id: {**{f: (str(getattr(i, f) or "") if k == "date" else getattr(i, f))
                       for f, _, k in cfg["fields"]}, "id": i.id} for i in items}
    return render_template("admin_crud.html", entity=entity, cfg=cfg, items=items, jsmap=jsmap)


@app.route("/admin/<entity>/save", methods=["POST"])
@admin_required
def admin_save(entity):
    cfg = entity_or_404(entity)
    iid = request.form.get("id")
    item = db.get_or_404(cfg["model"], int(iid)) if iid else cfg["model"]()
    
    try:
        for f, _, kind in cfg["fields"]:
            if f == "image_url":
                # التعامل مع رفع الصورة
                file = request.files.get("image_file")
                if file and file.filename and allowed_file(file.filename):
                    # إنشاء اسم فريد للصورة لتجنب التكرار
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    # حفظ مسار الصورة في قاعدة البيانات
                    setattr(item, f, url_for('static', filename=f'uploads/{filename}'))
                elif not iid:
                    # إذا كان إضافة جديدة ولم يتم رفع صورة، نضع صورة افتراضية
                    setattr(item, f, "https://placehold.co/600x400/cccccc/ffffff?text=No+Image")
            else:
                v = request.form.get(f, "").strip()
                if kind == "number":
                    v = float(v or 0)
                elif kind == "date":
                    v = date.fromisoformat(v) if v else date.today()
                setattr(item, f, v)
    except ValueError:
        flash("قيمة غير صالحة في النموذج", "error")
        return redirect(url_for("admin_crud", entity=entity))
        
    db.session.add(item)
    db.session.commit()
    flash("تم الحفظ بنجاح", "success")
    return redirect(url_for("admin_crud", entity=entity))


@app.route("/admin/<entity>/<int:iid>/delete", methods=["POST"])
@admin_required
def admin_delete(entity, iid):
    cfg = entity_or_404(entity)
    item = db.get_or_404(cfg["model"], iid)
    col = OrderItem.product_id if entity == "products" else OrderItem.workshop_id
    OrderItem.query.filter(col == iid).update({col.key: None})
    db.session.delete(item)
    db.session.commit()
    flash("تم الحذف", "success")
    return redirect(url_for("admin_crud", entity=entity))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    return render_template("admin_orders.html",
                           orders=Order.query.order_by(Order.created_at.desc()).all())


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    o = db.get_or_404(Order, oid)
    if request.form.get("status") in STATUS_AR:
        o.status = request.form["status"]
        db.session.commit()
        flash("تم تحديث حالة الطلب", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/<int:oid>/delete", methods=["POST"])
@admin_required
def admin_order_delete(oid):
    db.session.delete(db.get_or_404(Order, oid))
    db.session.commit()
    flash("تم حذف الطلب", "success")
    return redirect(url_for("admin_orders"))


# ============================ بيانات تجريبية ============================
def seed():
    if User.query.first():
        return
    img = lambda t, c: f"https://placehold.co/600x400/{c}/ffffff?text={t}"
    today = date.today()
    db.session.add_all([
        User(full_name="المدير", phone="0550000000", email="admin@aquasmart.dz", is_admin=True,
             location="الجزائر العاصمة", wilaya="الجزائر", baladiya="باب الوادي",
             password_hash=generate_password_hash("admin123")),
        User(full_name="مستخدم تجريبي", phone="0661111111", email="demo@aquasmart.dz",
             location="وهران", wilaya="وهران", baladiya="بئر الجير",
             password_hash=generate_password_hash("demo123")),
        Product(name="خس عضوي طازج", description="خس مزروع بمغذيات طبيعية.", price=150, image_url=img("Lettuce", "2E8B57")),
        Product(name="طماطم عنقودية", description="طماطم طازجة بدون مبيدات.", price=220, image_url=img("Tomato", "C0392B")),
        Product(name="نعناع طازج", description="حزمة نعناع عطرية.", price=80, image_url=img("Mint", "88D498")),
        Product(name="سمك البلطي", description="سمك بلطي مُربّى في مياه نظيفة (للكيلوغرام).", price=900, image_url=img("Tilapia", "0B4F6C")),
        Product(name="زريعة البلطي", description="زريعة صحية لبدء مشروعك (للعشرة).", price=600, image_url=img("Fingerlings", "0B4F6C")),
        Product(name="نظام أكوابونيك منزلي", description="نظام صغير متكامل للمنزل.", price=45000, image_url=img("Aquaponics", "2E8B57")),
        Workshop(title="أساسيات الأكوابونيك", description="دورة النيتروجين وتصميم النظام وإدارته.", price=6000, date=today + timedelta(days=10), image_url=img("Basics", "0B4F6C")),
        Workshop(title="تربية الأسماك بمياه نظيفة", description="جودة المياه والتغذية والصحة السمكية.", price=7500, date=today + timedelta(days=24), image_url=img("Fish", "2E8B57")),
        Workshop(title="مشروع أكوابونيك تجاري", description="دراسة الجدوى والتكاليف والتسويق في الجزائر.", price=12000, date=today + timedelta(days=40), image_url=img("Business", "88D498")),
    ])
    db.session.commit()


with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(debug=True)