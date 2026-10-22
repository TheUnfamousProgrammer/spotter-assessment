from django.urls import path

from planner import views

urlpatterns = [path("api/plan", views.plan)]
