import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth.models import User
from shop.models import Product
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@shop.in", "admin123")
if not Product.objects.exists():
    for n, c, p, s, k in [("Aero Headphones","Audio",2999,14,98),("Trail Backpack","Outdoor",1999,3,80),("Pulse Watch","Wearables",8999,22,92),
        ("Beam Speaker","Audio",1499,2,75),("Summit Bottle","Outdoor",599,60,60),("Loop Keyboard","Desk",3499,18,70)]:
        Product.objects.create(name=n, category=c, price=p, stock=s, sold=k, description=f"{n} - great value.")
print("Seeded. Admin login: admin / admin123")
