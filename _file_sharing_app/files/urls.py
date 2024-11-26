from django.urls import path
from .views import FileUploadView, FileRetrieveView, FileUpdateView, FileDeleteView, FilePermissionView

urlpatterns = [
    path('upload/', FileUploadView.as_view(), name='file-upload'),
    path('<int:pk>/', FileRetrieveView.as_view(), name='file-retrieve'),
    path('<int:pk>/update/', FileUpdateView.as_view(), name='file-update'),
    path('<int:pk>/delete/', FileDeleteView.as_view(), name='file-delete'),
    path('<int:pk>/share/', FilePermissionView.as_view(), name='file-share'),
]
