from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CaseViewSet, c_case_list, c_case_detail, c_supplement, dashboard_stats, sync_from_old_system

router = DefaultRouter()
router.register("cases", CaseViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", dashboard_stats),
    path("sync/", sync_from_old_system),
    # C端免认证路由
    path("c/cases/", c_case_list),
    path("c/cases/<uuid:pk>/", c_case_detail),
    path("c/cases/<uuid:pk>/supplement/", c_supplement),
]
