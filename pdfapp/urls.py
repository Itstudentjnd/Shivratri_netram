from django.shortcuts import render
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("success/", lambda request: render(request, "success.html"), name="success_page"),
    path("login_view/",views.login_view, name="login_view"),
    path("logout_view/",views.logout_view, name="logout_view"),
    path("", views.index, name="index"),
    path('issue-vehicle-pass/', views.issue_vehicle_pass, name='issue_vehicle_pass'),
    path('admin-vehicle-passes/', views.admin_vehicle_passes, name='admin_vehicle_passes'),
    path('update-pass-status/<int:pass_id>/<str:status>/', views.update_pass_status, name='update_pass_status'),
    path("generate_pass_image/<int:pass_id>/", views.generate_pass_image, name="generate_pass_image"),
    # path('press-pass-form/', views.press_pass_form, name='press_pass_form'),
    # path('issue-press-pass/', views.issue_press_pass, name='issue_press_pass'),
    # path('update-status/<int:record_id>/<str:action>/', views.update_status, name='update_status'),
    # path("download/press-pass/<int:record_id>/", views.generate_press_pass, name="download_press_pass"),
    # path("download/vehicle-pass/<int:pass_id>/", views.generate_pass_image, name="download_vehicle_pass"),
    path('check_status/', views.check_pass_status, name='check_status'),
    path('export_vehicle_passes/', views.export_vehicle_passes, name='export_vehicle_passes'),  # ✅ New export URL
    
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
