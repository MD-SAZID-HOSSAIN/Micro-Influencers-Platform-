from django.urls import path

from .views import MarkAllReadView, MarkReadView, NotificationListView

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", MarkAllReadView.as_view(), name="notifications-read-all"),
    path("notifications/<int:pk>/read/", MarkReadView.as_view(), name="notification-read"),
]
