from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path


def react_app(request):
    """Serve the React single-page app for every non-API URL."""
    index = settings.FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(open(index, "rb"), content_type="text/html")
    return HttpResponse(
        "Frontend not built. In development open http://localhost:5173 "
        "(npm run dev), or run 'npm run build' in the frontend folder.",
        content_type="text/plain",
    )


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include("portal.urls")),
    re_path(r"^(?!api/|django-admin/|static/).*$", react_app),
]