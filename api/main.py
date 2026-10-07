import os, asyncio, smtplib, datetime as dt
from email.message import EmailMessage
from dotenv import load_dotenv
import jwt
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from passlib.hash import django_pbkdf2_sha256 as dj
from pydantic import BaseModel
from sqlalchemy import create_engine, func, or_
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(ROOT, ".env"))
SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret")
FRONT = os.getenv("FRONTEND_URL", "http://localhost:5500")
STRIPE_KEY, WHSEC = os.getenv("STRIPE_SECRET_KEY"), os.getenv("STRIPE_WEBHOOK_SECRET")

# Reuse the tables Django created (run `migrate` first)
engine = create_engine(f"sqlite:///{ROOT}/db.sqlite3", connect_args={"check_same_thread": False})
B = automap_base(); B.prepare(autoload_with=engine)
_need = ("auth_user", "shop_product", "shop_cartitem", "shop_order", "shop_orderitem", "shop_payment", "shop_notification")
_miss = [t for t in _need if t not in B.classes]
if _miss: raise SystemExit("Database tables missing: " + ", ".join(_miss) + ". Run `python setup_project.py` first.")
User, Product, Cart, Order, Item, Payment, Notif = (B.classes[t] for t in
    ("auth_user", "shop_product", "shop_cartitem", "shop_order", "shop_orderitem", "shop_payment", "shop_notification"))

app = FastAPI(title="Smartshop API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
os.makedirs(f"{ROOT}/media", exist_ok=True)
app.mount("/media", StaticFiles(directory=f"{ROOT}/media"), name="media")
oauth = OAuth2PasswordBearer(tokenUrl="/auth/login")
subs = {}  # user id -> set of asyncio queues (live WebSocket connections)
async def push(uid, data):
    for q in subs.get(uid, ()): q.put_nowait(data)

def get_db():
    with Session(engine) as s: yield s

def role_of(u): return "admin" if u.is_superuser else "staff" if u.is_staff else "customer"
def make_token(u):
    return jwt.encode({"sub": str(u.id), "role": role_of(u), "exp": dt.datetime.utcnow() + dt.timedelta(days=1)}, SECRET, "HS256")

def current_user(token: str = Depends(oauth), db: Session = Depends(get_db)):
    try: uid = int(jwt.decode(token, SECRET, ["HS256"])["sub"])
    except Exception: raise HTTPException(401, "Invalid or expired token")
    u = db.get(User, uid)
    if not u: raise HTTPException(401, "User not found")
    return u

def require(*roles):
    def dep(u=Depends(current_user)):
        if role_of(u) not in roles: raise HTTPException(403, "Not allowed for your role")
        return u
    return dep

def send_email(to, subject, body):
    host = os.getenv("SMTP_HOST")
    if not host or not to: return print(f"[email -> {to}] {subject}: {body}")
    m = EmailMessage(); m["To"], m["From"], m["Subject"] = to, os.getenv("SMTP_USER"), subject; m.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587))) as s:
        s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)

def notify(db, user, typ, msg):
    db.add(Notif(user_id=user.id, type=typ, message=msg, is_read=False, created_at=dt.datetime.now()))
    send_email(user.email, f"Smartshop: {typ}", msg)

def pjson(p):
    return {"id": p.id, "name": p.name, "description": p.description, "category": p.category, "price": float(p.price),
            "stock": p.stock, "sold": p.sold, "image": f"/media/{p.image}" if p.image else None}

# ---------- Auth ----------
class Reg(BaseModel): name: str; email: str; password: str
@app.post("/auth/register")
def register(r: Reg, db: Session = Depends(get_db)):
    r.email = r.email.strip().lower()
    if "@" not in r.email or len(r.password) < 6: raise HTTPException(400, "Enter a valid email and a password of at least 6 characters")
    if db.query(User).filter_by(username=r.email).first(): raise HTTPException(400, "Email already registered")
    u = User(username=r.email, email=r.email, first_name=r.name, last_name="", password=dj.hash(r.password),
             is_superuser=False, is_staff=False, is_active=True, date_joined=dt.datetime.now())
    db.add(u); db.commit(); return {"token": make_token(u), "role": "customer"}

@app.post("/auth/login")
def login(f: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ident = f.username.strip().lower()
    u = db.query(User).filter(or_(User.username == ident, User.email == ident)).first()
    if not u or not dj.verify(f.password, u.password): raise HTTPException(400, "Wrong email or password")
    return {"access_token": make_token(u), "token_type": "bearer", "role": role_of(u)}

class A0(BaseModel): id_token: str
@app.post("/auth/auth0")  # Google/Facebook through Auth0
def auth0(b: A0, db: Session = Depends(get_db)):
    dom, aud = os.getenv("AUTH0_DOMAIN"), os.getenv("AUTH0_AUDIENCE")
    if not dom: raise HTTPException(501, "Set AUTH0_DOMAIN and AUTH0_AUDIENCE in .env")
    key = jwt.PyJWKClient(f"https://{dom}/.well-known/jwks.json").get_signing_key_from_jwt(b.id_token).key
    c = jwt.decode(b.id_token, key, ["RS256"], audience=aud, issuer=f"https://{dom}/")
    if not c.get("email"): raise HTTPException(400, "Your social account has no email address")
    u = db.query(User).filter_by(username=c["email"]).first()
    if not u:
        u = User(username=c["email"], email=c["email"], first_name=c.get("name", ""), last_name="", password="!",
                 is_superuser=False, is_staff=False, is_active=True, date_joined=dt.datetime.now()); db.add(u); db.commit()
    return {"access_token": make_token(u), "token_type": "bearer", "role": role_of(u)}

@app.get("/me")
def me(u=Depends(current_user)): return {"id": u.id, "name": u.first_name, "email": u.email, "role": role_of(u)}

# ---------- Products ----------
@app.get("/products")
def products(category: str = None, q: str = None, min_price: float = None, max_price: float = None,
             sort: str = "popularity", db: Session = Depends(get_db)):
    qs = db.query(Product)
    if category: qs = qs.filter(Product.category == category)
    if q: qs = qs.filter(Product.name.ilike(f"%{q}%"))
    if min_price is not None: qs = qs.filter(Product.price >= min_price)
    if max_price is not None: qs = qs.filter(Product.price <= max_price)
    qs = qs.order_by({"price_asc": Product.price.asc(), "price_desc": Product.price.desc()}.get(sort, Product.sold.desc()))
    return [pjson(p) for p in qs]

# ---------- Cart ----------
class CartIn(BaseModel): product_id: int; quantity: int = 1
@app.get("/cart")
def get_cart(u=Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Cart, Product).join(Product, Product.id == Cart.product_id).filter(Cart.user_id == u.id).all()
    items = [{"product": pjson(p), "quantity": c.quantity} for c, p in rows]
    return {"items": items, "total": sum(i["product"]["price"] * i["quantity"] for i in items)}

@app.post("/cart")
async def add_cart(b: CartIn, u=Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Product, b.product_id)
    if not p or p.stock < 1: raise HTTPException(400, "Product is out of stock")
    row = db.query(Cart).filter_by(user_id=u.id, product_id=p.id).first()
    if row: row.quantity = max(1, min(p.stock, row.quantity + b.quantity))
    else: db.add(Cart(user_id=u.id, product_id=p.id, quantity=max(1, b.quantity)))
    db.commit(); await push(u.id, {"type": "cart"}); return get_cart(u, db)

@app.delete("/cart/{product_id}")
async def del_cart(product_id: int, u=Depends(current_user), db: Session = Depends(get_db)):
    db.query(Cart).filter_by(user_id=u.id, product_id=product_id).delete(); db.commit()
    await push(u.id, {"type": "cart"}); return get_cart(u, db)

# ---------- Checkout & payments ----------
def settle(db, order_id, ok, txn=""):
    o = db.get(Order, order_id)
    if not o or o.payment_status == "paid": return
    u = db.get(User, o.user_id)
    pay = db.query(Payment).filter_by(order_id=order_id).first()
    if ok:
        o.payment_status, o.order_status = "paid", "processing"
        for it in db.query(Item).filter_by(order_id=order_id):
            p = db.get(Product, it.product_id); p.stock = max(0, p.stock - it.quantity); p.sold += it.quantity
        db.query(Cart).filter_by(user_id=o.user_id).delete()
        notify(db, u, "order_confirmation", f"Payment received. Order #{o.id} (Rs {float(o.total):,.2f}) is confirmed.")
    else:
        o.payment_status = "failed"
        notify(db, u, "payment_failed", f"Payment for order #{o.id} failed. Please try again.")
    if pay: pay.status, pay.transaction_id = ("success" if ok else "failed"), txn or pay.transaction_id
    db.commit()

@app.post("/checkout")
def checkout(simulate: str = None, u=Depends(current_user), db: Session = Depends(get_db)):
    cart = get_cart(u, db)
    if not cart["items"]: raise HTTPException(400, "Your cart is empty")
    for i in cart["items"]:
        if i["product"]["stock"] < i["quantity"]:
            raise HTTPException(400, f"Only {i['product']['stock']} of {i['product']['name']} left in stock")
    now = dt.datetime.now()
    o = Order(user_id=u.id, total=cart["total"], payment_status="pending", order_status="pending", created_at=now)
    db.add(o); db.flush()
    for i in cart["items"]:
        db.add(Item(order_id=o.id, product_id=i["product"]["id"], quantity=i["quantity"], price=i["product"]["price"]))
    if not STRIPE_KEY:  # demo mode
        db.add(Payment(order_id=o.id, amount=cart["total"], payment_method="demo", transaction_id=f"demo_{o.id}",
                       status="pending", created_at=now)); db.flush()
        ok = simulate != "fail"; settle(db, o.id, ok)
        return {"order_id": o.id, "mode": "demo", "status": "paid" if ok else "failed"}
    import stripe; stripe.api_key = STRIPE_KEY
    s = stripe.checkout.Session.create(mode="payment", customer_email=u.email, metadata={"order_id": str(o.id)},
        payment_intent_data={"metadata": {"order_id": str(o.id)}},
        line_items=[{"quantity": i["quantity"], "price_data": {"currency": "inr", "unit_amount": int(i["product"]["price"] * 100),
                     "product_data": {"name": i["product"]["name"]}}} for i in cart["items"]],
        success_url=f"{FRONT}?paid=1", cancel_url=f"{FRONT}?cancelled=1")
    db.add(Payment(order_id=o.id, amount=cart["total"], payment_method="stripe", transaction_id=s.id, status="pending", created_at=now))
    db.commit(); return {"order_id": o.id, "mode": "stripe", "checkout_url": s.url}

@app.post("/payments/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    import stripe; stripe.api_key = STRIPE_KEY
    try: ev = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature"), WHSEC)
    except Exception: raise HTTPException(400, "Invalid signature")
    obj = ev["data"]["object"]; oid = int((obj.get("metadata") or {}).get("order_id") or 0)
    if not oid: return {"ok": True}
    if ev["type"] == "checkout.session.completed": settle(db, oid, True, obj.get("payment_intent") or "")
    elif ev["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed", "payment_intent.payment_failed"): settle(db, oid, False)
    return {"ok": True}

# ---------- Orders & notifications ----------
def ojson(o, db):
    its = db.query(Item, Product).join(Product, Product.id == Item.product_id).filter(Item.order_id == o.id).all()
    return {"id": o.id, "total": float(o.total), "payment_status": o.payment_status, "order_status": o.order_status,
            "created_at": str(o.created_at), "items": [{"name": p.name, "quantity": i.quantity, "price": float(i.price)} for i, p in its]}

@app.get("/orders")
def orders(u=Depends(current_user), db: Session = Depends(get_db)):
    return [ojson(o, db) for o in db.query(Order).filter_by(user_id=u.id).order_by(Order.id.desc())]

@app.get("/admin/orders")  # RBAC demo: staff/admin only
def all_orders(u=Depends(require("admin", "staff")), db: Session = Depends(get_db)):
    return [ojson(o, db) for o in db.query(Order).order_by(Order.id.desc())]

@app.get("/notifications")
def notifs(u=Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": n.id, "type": n.type, "message": n.message, "is_read": bool(n.is_read), "created_at": str(n.created_at)}
            for n in db.query(Notif).filter_by(user_id=u.id).order_by(Notif.id.desc()).limit(50)]

@app.post("/notifications/{nid}/read")
def read_notif(nid: int, u=Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notif, nid)
    if n and n.user_id == u.id: n.is_read = True; db.commit()
    return {"ok": True}

@app.websocket("/ws/notifications")  # order, payment and cart events (also changes made in Django admin)
async def ws(sock: WebSocket, token: str):
    try: uid = int(jwt.decode(token, SECRET, ["HS256"])["sub"])
    except Exception: return await sock.close(code=4401)
    await sock.accept()
    q = asyncio.Queue(); subs.setdefault(uid, set()).add(q)
    with Session(engine) as db: last = db.query(func.max(Notif.id)).filter_by(user_id=uid).scalar() or 0
    try:
        while True:
            try: await sock.send_json(await asyncio.wait_for(q.get(), 2))
            except asyncio.TimeoutError: pass
            with Session(engine) as db:
                for n in db.query(Notif).filter(Notif.user_id == uid, Notif.id > last).order_by(Notif.id):
                    last = n.id; await sock.send_json({"id": n.id, "type": n.type, "message": n.message})
    except (WebSocketDisconnect, RuntimeError): pass
    finally: subs.get(uid, set()).discard(q)
