from django.urls import path

from . import views

urlpatterns = [
    path('', views.assistant, name='assistant'),
    path('new/', views.new_conversation, name='new_conversation'),
    path('ask/', views.ask, name='chatbot_ask'),
    path('rephrase/', views.rephrase, name='chatbot_rephrase'),
]