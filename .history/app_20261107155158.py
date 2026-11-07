"""AquaSmart DZ - تطبيق ويب بنمط تطبيق الجوال (PWA)
التشغيل:  pip install -r requirements.txt  ثم  python app.py
المدير: admin@aquasmart.dz / admin123
"""
from functools import wraps
from urllib.parse import urlparse
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   session, abort, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user, login_required,
                         current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Product, Course, Enrollment, Order, ORDER_STATUSES

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-me-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///aquasmart.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "يرجى تسجيل الدخول أولاً"


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if not current_user.is_admin:
            abort(403)
        return f(*a, **kw)
    return wrapper


def safe_next(target):
    """يمنع إعادة التوجيه إلى مواقع خارجية (Open Redirect)."""
    if target and target.startswith("/") and not urlparse(target).netloc:
        return target
    return None


@app.context_processor
def inject_globals():
    return {"cart_count": sum(session.get("cart", {}).values())}


# --------------------------- PWA ---------------------------
@app.route("/sw.js")
def service_worker():
    """يُقدَّم من الجذر ليكون نطاقه (scope) كامل الموقع."""
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


# --------------------------- الصفحات العامة ---------------------------
@app.route("/")
def splash():
    """الصفحة الأولى (عامة): شاشة البداية. تقرّر JS بعد 2.5 ثانية إلى أين تنتقل."""
    target = url_for("home") if current_user.is_authenticated else url_for("login")
    return render_template("splash.html", target=target)


@app.route("/home")
@login_required
def home():
    return render_template("home.html", products=Product.query.limit(6).all())


@app.route("/products")
@login_required
def products():
    items = Product.query.all()
    jsmap = {p.id: dict(id=p.id, name=p.name, description=p.description,
                        price=p.price, category=p.category,
                        image_url=p.image_url, stock=p.stock) for p in items}
    return render_template("products.html", products=items, jsmap=jsmap)


@app.route("/courses")
@login_required
def courses():
    enrolled = set()
    if current_user.is_authenticated:
        enrolled = {e.course_id for e in Enrollment.query.filter_by(user_id=current_user.id)}
    return render_template("courses.html", courses=Course.query.all(), enrolled=enrolled)


@app.route("/enroll/<int:cid>", methods=["POST"])
@login_required
def enroll(cid):
    Course.query.get_or_404(cid)
    if not Enrollment.query.filter_by(user_id=current_user.id, course_id=cid).first():
        db.session.add(Enrollment(user_id=current_user.id, course_id=cid))
        db.session.commit()
        flash("تم تسجيلك في الدورة بنجاح 🌱", "success")
    return redirect(url_for("courses"))


@app.route("/account")
@login_required
def account():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("account.html", enrollments=enrollments, orders=orders)


# --------------------------- المصادقة ---------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("البريد الإلكتروني مستخدم مسبقاً", "error")
        elif len(pw) < 6:
            flash("كلمة المرور يجب ألا تقل عن 6 أحرف", "error")
        else:
            u = User(name=request.form["name"].strip(), email=email,
                     password_hash=generate_password_hash(pw))
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
            # بعد النجاح: /home (أو الصفحة المحمية التي كان يحاول فتحها)
            return redirect(safe_next(request.args.get("next")) or url_for("home"))
        flash("البريد أو كلمة المرور غير صحيحة", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --------------------------- السلة ---------------------------
@app.route("/cart/add/<int:pid>", methods=["POST"])
@login_required
def cart_add(pid):
    Product.query.get_or_404(pid)
    cart = session.get("cart", {})
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    session["cart"] = cart
    flash("تمت الإضافة إلى السلة 🛒", "success")
    return redirect(request.referrer or url_for("products"))


@app.route("/cart/remove/<int:pid>", methods=["POST"])
@login_required
def cart_remove(pid):
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart", methods=["GET", "POST"])
@login_required
def cart():
    rows, total = [], 0
    for pid, qty in session.get("cart", {}).items():
        p = db.session.get(Product, int(pid))
        if p:
            rows.append((p, qty))
            total += p.price * qty
    if request.method == "POST":
        if rows:
            db.session.add(Order(user_id=current_user.id,
                items="، ".join(f"{p.name} × {q}" for p, q in rows), total=total,
                phone=request.form["phone"], address=request.form["address"]))
            db.session.commit()
            session.pop("cart", None)
            flash("تم إرسال طلبك بنجاح ✅", "success")
            return redirect(url_for("account"))
    return render_template("cart.html", rows=rows, total=total)


# --------------------------- لوحة التحكم (بطاقات للجوال) ---------------------------
ENTITIES = {
    "products": dict(model=Product, title="المنتجات", icon="fa-carrot", name="name",
        sub=lambda i: f"{i.category} • {i.price:g} د.ج • مخزون {i.stock}",
        fields=[("name", "الاسم", "text"), ("description", "الوصف", "textarea"),
                ("price", "السعر (د.ج)", "number"), ("category", "التصنيف", "text"),
                ("stock", "المخزون", "number"), ("image_url", "رابط الصورة", "text")]),
    "courses": dict(model=Course, title="الدورات", icon="fa-graduation-cap", name="title",
        sub=lambda i: f"{i.price:g} د.ج • {i.duration_hours} ساعة",
        fields=[("title", "العنوان", "text"), ("description", "الوصف", "textarea"),
                ("price", "السعر (د.ج)", "number"), ("duration_hours", "المدة (ساعة)", "number"),
                ("image_url", "رابط الصورة", "text")]),
}
INT_FIELDS = {"stock", "duration_hours"}


@app.route("/admin")
@admin_required
def admin_dashboard():
    stats = [("المنتجات", Product.query.count(), "fa-carrot", "bg-leaf"),
             ("الدورات", Course.query.count(), "fa-graduation-cap", "bg-ocean"),
             ("المستخدمون", User.query.count(), "fa-users", "bg-mint !text-ocean"),
             ("الطلبات", Order.query.count(), "fa-basket-shopping", "bg-amber-500")]
    latest = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, latest=latest)


@app.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin/users.html", users=User.query.all())


@app.route("/admin/orders")
@admin_required
def admin_orders():
    return render_template("admin/orders.html", statuses=ORDER_STATUSES,
                           orders=Order.query.order_by(Order.created_at.desc()).all())


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    o = Order.query.get_or_404(oid)
    if request.form["status"] in ORDER_STATUSES:
        o.status = request.form["status"]
        db.session.commit()
        flash("تم تحديث حالة الطلب", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/<entity>")
@admin_required
def admin_list(entity):
    cfg = ENTITIES.get(entity) or abort(404)
    return render_template("admin/list.html", entity=entity, cfg=cfg, items=cfg["model"].query.all())


@app.route("/admin/<entity>/new", methods=["GET", "POST"])
@app.route("/admin/<entity>/<int:iid>/edit", methods=["GET", "POST"])
@admin_required
def admin_form(entity, iid=None):
    cfg = ENTITIES.get(entity) or abort(404)
    item = cfg["model"].query.get_or_404(iid) if iid else None
    if request.method == "POST":
        item = item or cfg["model"]()
        for f, _, kind in cfg["fields"]:
            v = request.form.get(f, "").strip()
            if kind == "number":
                v = int(float(v or 0)) if f in INT_FIELDS else float(v or 0)
            setattr(item, f, v)
        db.session.add(item)
        db.session.commit()
        flash("تم الحفظ بنجاح", "success")
        return redirect(url_for("admin_list", entity=entity))
    return render_template("admin/form.html", entity=entity, cfg=cfg, item=item)


@app.route("/admin/<entity>/<int:iid>/delete", methods=["POST"])
@admin_required
def admin_delete(entity, iid):
    cfg = ENTITIES.get(entity) or abort(404)
    db.session.delete(cfg["model"].query.get_or_404(iid))
    db.session.commit()
    flash("تم الحذف", "success")
    return redirect(url_for("admin_list", entity=entity))


# --------------------------- بيانات تجريبية ---------------------------
def seed():
    if User.query.first():
        return
    img = lambda t, c: f"https://placehold.co/600x400/{c}/ffffff?text={t}"
    db.session.add_all([
        User(name="المدير", email="admin@aquasmart.dz", is_admin=True,
             password_hash=generate_password_hash("admin123")),
        User(name="مستخدم تجريبي", email="demo@aquasmart.dz",
             password_hash=generate_password_hash("demo123")),
        Product(name="خس عضوي طازج", description="خس مزروع بمغذيات طبيعية من النظام المائي.", price=150, category="خضروات", stock=40, image_url=img("Lettuce", "2E8B57")),
        Product(name="طماطم عنقودية", description="طماطم طازجة بدون مبيدات.", price=220, category="خضروات", stock=60, image_url=img("Tomato", "C0392B")),
        Product(name="نعناع طازج", description="حزمة نعناع عطرية.", price=80, category="أعشاب", stock=30, image_url=img("Mint", "88D498")),
        Product(name="سمك البلطي", description="سمك بلطي مُربّى في مياه نظيفة (للكيلوغرام).", price=900, category="أسماك", stock=25, image_url=img("Tilapia", "0B4F6C")),
        Product(name="زريعة البلطي", description="زريعة صحية لبدء مشروعك (للعشرة).", price=600, category="أسماك", stock=100, image_url=img("Fingerlings", "0B4F6C")),
        Product(name="نظام أكوابونيك منزلي", description="نظام صغير متكامل للمنزل أو الشرفة.", price=45000, category="أنظمة", stock=5, image_url=img("Aquaponics", "2E8B57")),
        Course(title="أساسيات الأكوابونيك", description="دورة النيتروجين وتصميم النظام وإدارته.", price=6000, duration_hours=12, image_url=img("Basics", "0B4F6C")),
        Course(title="تربية الأسماك بمياه نظيفة", description="جودة المياه والتغذية والصحة السمكية.", price=7500, duration_hours=16, image_url=img("Fish", "2E8B57")),
        Course(title="مشروع أكوابونيك تجاري", description="دراسة الجدوى والتكاليف والتسويق في الجزائر.", price=12000, duration_hours=24, image_url=img("Business", "88D498")),
    ])
    db.session.commit()


with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(debug=True)