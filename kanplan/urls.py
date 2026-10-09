import os

from django.contrib import admin
from django.conf import settings
from django.urls import path, include, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    # KanPlan is self-hosted with no separate web server, so Django serves
    # board images itself (also with DEBUG off, e.g. in Docker). Rooted at
    # board_images/ so nothing else under MEDIA_ROOT is reachable; card
    # attachments are served by the owner-checked view_attachment instead.
    re_path(r'^media/board_images/(?P<path>.*)$', serve,
            {'document_root': os.path.join(settings.MEDIA_ROOT, 'board_images')}),
]

if settings.BROWSER_RELOAD:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
