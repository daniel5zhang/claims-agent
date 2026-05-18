"""案件 API 视图"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import Case, Attachment
from .serializers import CaseListSerializer, CaseDetailSerializer
from .intake.manual_adapter import ManualAdapter
from .intake.old_system_adapter import OldSystemAdapter


class CaseViewSet(viewsets.ModelViewSet):
    queryset = Case.objects.all().order_by("-created_at")
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "list":
            return CaseListSerializer
        return CaseDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        claim_type = self.request.query_params.get("claim_type")
        if claim_type:
            qs = qs.filter(claim_type=claim_type)
        return qs

    @action(detail=True, methods=["post"])
    def audit(self, request, id=None):
        """触发单案件审核"""
        case = self.get_object()
        if case.status == "running":
            return Response({"error": "案件已在审核中"}, status=400)
        policy_ids = list(case.policy_links.values_list("policy_id", flat=True))
        case.status = "running"
        case.agent_started_at = timezone.now()
        case.save()
        from apps.audit.tasks import run_audit_task
        run_audit_task(str(case.id), policy_ids)
        return Response({"status": "queued", "case_id": str(case.id)})

    @action(detail=True, methods=["post"])
    def cancel(self, request, id=None):
        """软撤销"""
        case = self.get_object()
        case.status = "cancelled"
        case.cancelled_at = timezone.now()
        case.cancelled_by = request.user
        case.save()
        return Response({"status": "cancelled"})

    @action(detail=True, methods=["post"])
    def supplement(self, request, id=None):
        """补材提交 — 重新触发审核"""
        case = self.get_object()
        if case.status not in ["supplement_required", "completed"]:
            return Response({"error": "当前状态不支持补材"}, status=400)
        case.status = "running"
        case.save()
        return Response({"status": "resumed"})

    @action(detail=True, methods=["post"])
    def intervene(self, request, id=None):
        """人工介入"""
        case = self.get_object()
        opinion = request.data.get("opinion", "")
        action_type = request.data.get("action", "continue")
        # TODO Phase 10: 注入 Agent 上下文
        return Response({"status": action_type, "opinion": opinion})

    @action(detail=False, methods=["post"])
    def batch_audit(self, request):
        """批量审核"""
        case_ids = request.data.get("case_ids", [])
        if not case_ids:
            return Response({"error": "case_ids required"}, status=400)
        Case.objects.filter(id__in=case_ids, status="pending").update(
            status="running", agent_started_at=timezone.now()
        )
        return Response({"queued": len(case_ids)})

    @action(detail=False, methods=["post"])
    @csrf_exempt
    def sync(self, request):
        """从旧系统同步案件"""
        project_id = request.data.get("project_id", "")
        case_ids = request.data.get("case_ids", [])
        from .intake.old_system_adapter import OldSystemAdapter
        adapter = OldSystemAdapter()
        filters = {}
        if project_id: filters["project_id"] = project_id
        if case_ids: filters["case_ids"] = case_ids
        try:
            cases = adapter.ingest(**filters)
            return Response({"synced": len(cases), "cases": CaseListSerializer(cases, many=True).data})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def c_case_list(request):
    """C端案件列表 — 免认证"""
    qs = Case.objects.all().order_by("-created_at")[:50]
    return Response(CaseListSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def c_case_detail(request, pk):
    """C端案件详情 — 免认证"""
    try:
        case = Case.objects.get(id=pk)
        return Response(CaseDetailSerializer(case).data)
    except Case.DoesNotExist:
        return Response({"error": "not found"}, status=404)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def c_supplement(request, pk):
    """C端补材提交 — 免认证"""
    return Response({"status": "received", "case_id": pk})


class AttachmentViewSet(viewsets.ModelViewSet):
    queryset = Attachment.objects.all()

    def perform_create(self, serializer):
        f = self.request.FILES["file"]
        # 校验大小
        if f.size > 50 * 1024 * 1024:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("单文件不超过 50MB")
        storage_path = f"cases/{self.kwargs['case_pk']}/{f.name}"
        from .services.attachment_storage import get_storage
        storage = get_storage()
        storage.save(storage_path, f.read())
        serializer.save(case_id=self.kwargs["case_pk"], storage_path=storage_path,
                        file_name=f.name, file_size=f.size, mime_type=f.content_type)

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """Dashboard 统计数据"""
    from django.db.models import Count
    total = Case.objects.count()
    statuses = {r['status']: r['count'] for r in Case.objects.values('status').annotate(count=Count('id'))}
    return Response({
        "total": total,
        "pending": statuses.get("pending", 0),
        "running": statuses.get("running", 0),
        "completed": statuses.get("completed", 0),
        "supplement_required": statuses.get("supplement_required", 0),
        "manual_review": statuses.get("manual_review", 0),
        "error": statuses.get("error", 0),
        "cancelled": statuses.get("cancelled", 0),
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@csrf_exempt
def sync_from_old_system(request):
    """从旧系统同步案件"""
    project_id = request.data.get("project_id", "")
    case_ids = request.data.get("case_ids", [])
    from .intake.old_system_adapter import OldSystemAdapter
    adapter = OldSystemAdapter()
    filters = {}
    if project_id:
        filters["project_id"] = project_id
    if case_ids:
        filters["case_ids"] = case_ids
    try:
        cases = adapter.ingest(**filters)
        return Response({"synced": len(cases), "cases": CaseListSerializer(cases, many=True).data})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
