from django import forms
from django.contrib import admin
from django.shortcuts import render
from .models import Device, BorrowLog
from django.utils import timezone

# TẠO FORM ẢO ĐỂ CÓ Ô NHẬP SỐ LƯỢNG
class DeviceForm(forms.ModelForm):
    # Ô này không lưu vào DB, chỉ dùng để hỏi thủ kho muốn tạo bao nhiêu cái
    quantity = forms.IntegerField(label='Số lượng nhập kho', min_value=1, initial=1, 
                                  help_text='Nhập 100 nếu muốn tạo 100 thiết bị giống hệt nhau')
    class Meta:
        model = Device
        fields = '__all__'

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    form = DeviceForm
    list_display = ['device_code', 'name', 'purchase_date', 'status', 'qr_code_image']
    
    list_filter = ['status']
    search_fields = ['device_code', 'name']
    readonly_fields = ['device_code', 'qr_code_image']
    
    # -----------------------------------------------------
    # NGHIỆP VỤ 1: TẠO HÀNG LOẠT (BULK CREATE)
    # -----------------------------------------------------
    def save_model(self, request, obj, form, change):
        # Nếu đang là Tạo mới (chưa có ID)
        if not obj.pk:
            quantity = form.cleaned_data.get('quantity', 1)
            # Tạo thiết bị đầu tiên
            super().save_model(request, obj, form, change)
            # Nếu số lượng > 1, dùng vòng lặp tạo thêm bản sao
            for _ in range(quantity - 1):
                Device.objects.create(
                    name=obj.name,
                    status=obj.status,
                    purchase_date=obj.purchase_date
                )
        else:
            # Nếu chỉ là Sửa tên/trạng thái thì lưu bình thường
            super().save_model(request, obj, form, change)

    # -----------------------------------------------------
    # NGHIỆP VỤ 2: NÚT "IN TEM QR" (PRINT ACTION)
    # -----------------------------------------------------
    actions = ['print_qr_codes']

    @admin.action(description='🖨️ In Tem QR cho các Thiết bị đã chọn')
    def print_qr_codes(self, request, queryset):
        # Trích xuất dữ liệu của các thiết bị được tích chọn và ném sang trang in
        return render(request, 'print_qr.html', {'devices': queryset})

@admin.register(BorrowLog)
class BorrowLogAdmin(admin.ModelAdmin):
    # ... (Giữ nguyên như cũ) ...
    list_display = ['device', 'borrower', 'for_class', 'borrow_time', 'return_time', 'status']
    readonly_fields = ['borrow_time']
    
    def save_model(self, request, obj, form, change):
        if change and obj.status == 'returned' and not obj.return_time:
            obj.return_time = timezone.now()
        super().save_model(request, obj, form, change)