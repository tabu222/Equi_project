from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.horses.urls")),
    path("api/", include("apps.medical.urls")),
    path("api/", include("apps.training.urls")),
    path("api/", include("apps.care.urls")),
]
