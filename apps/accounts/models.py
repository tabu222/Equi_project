"""
COMMON / RBAC: Club, Role, Permission, RolePermission, [User], UserRole (horse_v2.sql).

Mọi model managed = False: bảng do horse_v2.sql tạo, Django chỉ đọc / ghi dữ liệu.
Khóa ngoại dùng DO_NOTHING vì database đã có FK tự chặn xóa sai.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class Club(models.Model):
    id = models.AutoField(primary_key=True, db_column="ClubID")
    club_name = models.CharField(max_length=150, unique=True, db_column="ClubName")
    address = models.CharField(max_length=255, null=True, blank=True, db_column="Address")
    phone = models.CharField(max_length=20, null=True, blank=True, db_column="Phone")
    email = models.CharField(max_length=100, null=True, blank=True, db_column="Email")
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")],
                              db_column="Status")
    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")

    class Meta:
        managed = False
        db_table = "Club"
        ordering = ["club_name"]

    def __str__(self):
        return self.club_name


class Role(models.Model):
    id = models.AutoField(primary_key=True, db_column="RoleID")
    code = models.CharField(max_length=40, unique=True, db_column="RoleCode")
    name = models.CharField(max_length=100, unique=True, db_column="RoleName")
    description = models.CharField(max_length=500, null=True, blank=True, db_column="Description")

    class Meta:
        managed = False
        db_table = "Role"
        ordering = ["id"]

    def __str__(self):
        return self.code


class AppPermission(models.Model):
    """dbo.Permission (đặt tên AppPermission để khỏi trùng với Permission có sẵn của Django)."""

    id = models.AutoField(primary_key=True, db_column="PermissionID")
    code = models.CharField(max_length=60, unique=True, db_column="PermissionCode")
    name = models.CharField(max_length=150, db_column="PermissionName")
    description = models.CharField(max_length=500, null=True, blank=True, db_column="Description")

    class Meta:
        managed = False
        db_table = "Permission"
        ordering = ["code"]

    def __str__(self):
        return self.code


class RolePermission(models.Model):
    pk = models.CompositePrimaryKey("role", "permission")
    role = models.ForeignKey(Role, on_delete=models.DO_NOTHING, db_column="RoleID", related_name="permission_links")
    permission = models.ForeignKey(
        AppPermission, on_delete=models.DO_NOTHING, db_column="PermissionID", related_name="role_links"
    )

    class Meta:
        managed = False
        db_table = "RolePermission"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email là bắt buộc")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


class User(AbstractBaseUser):
    """
    dbo.[User] dùng làm user của Django.
    - PasswordHash lưu chuỗi hash của Django (pbkdf2_sha256$...), tạo bằng set_password().
    - Bảng không có cột LastLogin nên bỏ field last_login.
    """

    class Status(models.TextChoices):
        ACTIVE = "Active"
        INACTIVE = "Inactive"
        SUSPENDED = "Suspended"

    id = models.AutoField(primary_key=True, db_column="UserID")
    club = models.ForeignKey(
        Club, on_delete=models.DO_NOTHING, null=True, blank=True, db_column="ClubID", related_name="members"
    )
    full_name = models.CharField(max_length=150, db_column="FullName")
    email = models.CharField(max_length=100, unique=True, db_column="Email")
    password = models.CharField(max_length=255, db_column="PasswordHash")
    phone = models.CharField(max_length=20, null=True, blank=True, db_column="Phone")
    address = models.CharField(max_length=255, null=True, blank=True, db_column="Address")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_column="Status")
    created_at = models.DateTimeField(default=timezone.now, db_column="CreatedAt")

    last_login = None

    roles = models.ManyToManyField(
        Role, through="UserRole", through_fields=("user", "role"), related_name="users", blank=True
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        managed = False
        db_table = "User"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @cached_property
    def role_codes(self) -> frozenset:
        return frozenset(self.roles.values_list("code", flat=True))

    @cached_property
    def permission_codes(self) -> frozenset:
        return frozenset(
            AppPermission.objects.filter(role_links__role__user_links__user=self)
            .values_list("code", flat=True)
            .distinct()
        )

    def has_role(self, *codes) -> bool:
        return bool(self.role_codes.intersection(codes))

    def has_perm(self, perm, obj=None) -> bool:
        """perm là PermissionCode trong dbo.Permission, ví dụ 'HORSE_REGISTER'."""
        return self.is_active and perm in self.permission_codes

    def has_perms(self, perm_list, obj=None) -> bool:
        return all(self.has_perm(p, obj) for p in perm_list)

    def has_module_perms(self, app_label) -> bool:
        return False


class UserRole(models.Model):
    pk = models.CompositePrimaryKey("user", "role")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column="UserID", related_name="role_links")
    role = models.ForeignKey(Role, on_delete=models.DO_NOTHING, db_column="RoleID", related_name="user_links")
    assigned_at = models.DateTimeField(default=timezone.now, db_column="AssignedAt")
    assigned_by = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, null=True, blank=True, db_column="AssignedBy", related_name="+"
    )

    class Meta:
        managed = False
        db_table = "UserRole"
