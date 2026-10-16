from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """
    GET /api/health - kiểm tra backend và database (giống API health của repo Java cũ).
    200 {"backend": "UP", "database": "UP"}   | 503 {"backend": "UP", "database": "DOWN"}
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_up = cursor.fetchone()[0] == 1
    except DatabaseError:
        database_up = False
    return Response(
        {"backend": "UP", "database": "UP" if database_up else "DOWN"},
        status=status.HTTP_200_OK if database_up else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
