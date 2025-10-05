from django.urls import path

from futbol.views import view

app_name = 'futbol'

urlpatterns = [
    path('futboll/', view,name='futbol'),
]
