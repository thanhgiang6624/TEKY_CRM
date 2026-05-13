from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    # Khai báo các quyền (Roles) cho trung tâm
    ROLE_CHOICES = (
        ('admin', 'Giám đốc / Quản trị viên'),
        ('sales', 'Tư vấn viên (CRM)'),
        ('teacher', 'Giáo viên (Academic)'),
        ('facility', 'Thủ kho (Thiết bị)'),
    )
    
    # Thêm các cột mới vào bảng User
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    # THÊM DÒNG NÀY: Khai báo cột lưu ảnh đại diện
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"