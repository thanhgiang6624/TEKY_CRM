from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    # 1. Các cột sẽ hiển thị ở màn hình danh sách bên ngoài
    list_display = ['username', 'first_name', 'last_name', 'role', 'phone', 'is_staff']
    
    # 2. Thêm các ô nhập liệu (role, phone) vào màn hình chỉnh sửa chi tiết
    fieldsets = UserAdmin.fieldsets + (
        ('Thông tin TEKY', {'fields': ('role', 'phone')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)