from django.urls import path

from . import views

urlpatterns = [
    path("auth/login/", views.login),
    path("auth/logout/", views.logout),
    path("auth/me/", views.me),
    path("auth/change-password/", views.change_password),

    path("grades/mine/", views.my_grades),
    path("grades/pending/", views.pending_grades),
    path("grades/integrity/", views.integrity_check),
    path("grades/<int:grade_id>/", views.update_grade),
    path("grades/<int:grade_id>/approve/", views.approve_grade),

    path("courses/", views.courses),
    path("courses/<int:course_id>/grades/", views.course_grades),

    path("audit/", views.audit_log),
    path("users/", views.users),
    path("users/<int:user_id>/unlock/", views.unlock_user),
    path("users/<int:user_id>/role/", views.change_role),
]
