from rest_framework import serializers
from .models import Case, ClaimReport, Attachment, PolicyLink


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "file_name", "attachment_type", "file_size", "mime_type", "created_at"]


class PolicyLinkSerializer(serializers.ModelSerializer):
    policy_no = serializers.CharField(source="policy.policy_no", read_only=True)
    product_name = serializers.CharField(source="policy.product.product_name", read_only=True)

    class Meta:
        model = PolicyLink
        fields = ["id", "policy", "policy_no", "product_name", "source"]


class CaseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ["id", "case_no", "insured_name", "diagnosis", "claim_type",
                  "status", "priority", "report_date", "created_at"]


class CaseDetailSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    policy_links = PolicyLinkSerializer(many=True, read_only=True)
    report = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = "__all__"

    def get_report(self, obj):
        if hasattr(obj, "report"):
            return {
                "report_person_name": obj.report.report_person_name,
                "insured_relation": obj.report.insured_relation,
                "report_person_phone": obj.report.report_person_phone,
            }
        return None


class CaseCreateSerializer(serializers.ModelSerializer):
    """手工录入新案件"""
    report_person_name = serializers.CharField(write_only=True)
    report_person_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Case
        fields = ["insured_name", "id_number", "phone", "diagnosis",
                  "hospital_name", "claim_mode", "claim_type",
                  "report_person_name", "report_person_phone"]

    def create(self, validated_data):
        validated_data.pop("report_person_name", None)
        validated_data.pop("report_person_phone", None)
        # 由 ManualAdapter 处理
        from .intake.manual_adapter import ManualAdapter
        adapter = ManualAdapter()
        return adapter.normalize(validated_data)
