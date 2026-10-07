import csv, io
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from .models import Order, OrderItem, Product

def stats():
    paid = Order.objects.filter(payment_status="paid")
    days = paid.annotate(d=TruncDate("created_at")).values("d").annotate(t=Sum("total")).order_by("d")
    top = (OrderItem.objects.filter(order__payment_status="paid").values("product__name")
           .annotate(q=Sum("quantity")).order_by("-q")[:5])
    return {"total": float(paid.aggregate(s=Sum("total"))["s"] or 0), "orders": Order.objects.count(),
            "days": [[str(x["d"]), float(x["t"])] for x in days][-14:],
            "top": [[x["product__name"], x["q"]] for x in top],
            "low": [list(x) for x in Product.objects.filter(stock__lt=5).values_list("name", "stock")]}

@staff_member_required
def dashboard(request):
    s = stats()
    return render(request, "shop/dashboard.html", {"s": s, "data": s})

@staff_member_required
def csv_export(request):
    r = HttpResponse(content_type="text/csv"); r["Content-Disposition"] = "attachment; filename=orders.csv"
    w = csv.writer(r); w.writerow(["id", "customer", "total_inr", "payment", "status", "created"])
    for o in Order.objects.select_related("user"):
        w.writerow([o.id, o.user.email, o.total, o.payment_status, o.order_status, o.created_at])
    return r

@staff_member_required
def pdf_export(request):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf); s = stats(); y = 800
    c.setFont("Helvetica-Bold", 16); c.drawString(50, y, "Smartshop sales report"); c.setFont("Helvetica", 11)
    for line in [f"Total sales: INR {s['total']:,.2f}", f"Orders: {s['orders']}", "Top sellers:"] + \
                [f"  {n}: {q} sold" for n, q in s["top"]] + ["Low stock:"] + [f"  {n}: {q} left" for n, q in s["low"]]:
        y -= 20; c.drawString(50, y, line)
    c.save()
    return HttpResponse(buf.getvalue(), content_type="application/pdf")
