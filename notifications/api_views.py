from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from notifications.services import mark_all_read, unread_count


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        qs = Notification.objects.filter(recipient=self.request.user).select_related("actor", "post")
        if self.request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(is_read=False)
        return qs


@extend_schema(request=None, responses={200: NotificationSerializer})
class NotificationReadView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Notification.objects.all()

    def post(self, request, pk: int):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.mark_read()
        return Response(NotificationSerializer(notification).data)


@extend_schema(request=None, responses={200: OpenApiResponse(description="Unread notification count")})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count_view(request):
    """Polled by the navbar; swap for a websocket push without touching clients."""
    return Response({"unread_count": unread_count(request.user)})


@extend_schema(request=None, responses={200: OpenApiResponse(description="Number of notifications marked read")})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read_view(request):
    return Response({"updated": mark_all_read(request.user)}, status=status.HTTP_200_OK)
