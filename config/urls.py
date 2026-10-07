from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from shop import views
urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/")),
    path("admin/", admin.site.urls),
    path("dashboard/", views.dashboard),
    path("dashboard/orders.csv", views.csv_export),
    path("dashboard/report.pdf", views.pdf_export),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
