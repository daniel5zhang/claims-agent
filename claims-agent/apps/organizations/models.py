from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.setdefault("is_active", True)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=128, unique=True)
    display_name = models.CharField(max_length=128, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    dingtalk_id = models.CharField(max_length=64, null=True, blank=True)
    wecom_id = models.CharField(max_length=64, null=True, blank=True)
    department = models.ForeignKey("Department", null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.display_name or self.username


class Organization(models.Model):
    name = models.CharField(max_length=256)
    dingtalk_org_id = models.CharField(max_length=64, null=True, blank=True)
    wecom_corp_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=256)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)


class Role(models.Model):
    """角色权限矩阵"""
    name = models.CharField(max_length=128, unique=True)  # 审核员 / 审核主管 / 规则管理员 / 系统管理员
    permissions = models.JSONField(default=list)
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=False)


class ReviewGroup(models.Model):
    """审核组"""
    name = models.CharField(max_length=256)
    members = models.ManyToManyField(User, related_name="review_groups")
    project = models.ForeignKey("policies.Project", null=True, blank=True, on_delete=models.SET_NULL)
    product_type = models.CharField(max_length=64, null=True, blank=True)
    pay_amount_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pay_amount_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    risk_levels = models.JSONField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)


class DataAccessPolicy(models.Model):
    """行级数据访问控制"""
    subject_type = models.CharField(max_length=32)  # user / group / department
    subject_id = models.CharField(max_length=64)
    scope_type = models.CharField(max_length=32)     # review_group / project / all
    scope_id = models.CharField(max_length=64, null=True, blank=True)
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class DisplayMaskConfig(models.Model):
    """展示层脱敏配置"""
    field_name = models.CharField(max_length=64)      # id_number / name / phone / diagnosis
    mask_type = models.CharField(max_length=32)       # full_hide / partial / role_based
    mask_pattern = models.CharField(max_length=64, null=True, blank=True)  # "310***1234"
    visible_roles = models.JSONField(default=list)    # 哪些角色可见原始值
