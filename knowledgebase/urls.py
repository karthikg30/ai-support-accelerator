from django.urls import path

from . import views

urlpatterns = [
    path('', views.kb_home, name='kb_home'),
    path('category/<str:category>/', views.kb_category, name='kb_category'),
    path('article/<str:code>/', views.kb_article, name='kb_article'),
]