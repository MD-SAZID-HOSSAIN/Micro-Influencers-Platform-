"""URLconf for the 'deny by default' test: a view that sets no permissions."""
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class UnlistedView(APIView):
    def get(self, request):
        return Response({"secret": True})


urlpatterns = [path("unlisted/", UnlistedView.as_view())]
