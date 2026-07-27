from django.urls import path

from . import views

urlpatterns = [
    path('', views.create_case, name='create_case'),
    path('cases/', views.MyCasesListView.as_view(), name='my_cases'),
    path('cases/<int:pk>/', views.CaseDetailView.as_view(), name='case_detail'),
    path('cases/<int:pk>/retry-sync/', views.retry_sync, name='retry_sync'),
]