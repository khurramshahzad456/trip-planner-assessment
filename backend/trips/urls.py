from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("hos/assumptions/", views.AssumptionsView.as_view(), name="hos-assumptions"),
    path("geocode/autocomplete/", views.AutocompleteView.as_view(), name="geocode-autocomplete"),
    path("trips/", views.TripListView.as_view(), name="trip-list"),
    path("trips/plan/", views.TripPlanView.as_view(), name="trip-plan"),
    path("trips/<uuid:pk>/", views.TripDetailView.as_view(), name="trip-detail"),
]
