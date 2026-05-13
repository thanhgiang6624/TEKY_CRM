from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Max
from .models import Lead

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    # 1. DANH SÁCH BÊN NGOÀI
    # ĐÃ THÊM 'lead_source' VÀO ĐÂY
    list_display = ['parent_name', 'phone', 'lead_source', 'total_leads_count', 'assigned_to', 'created_at']
    
    # Cho phép lọc theo nguồn luôn cho tiện
    list_filter = ['status', 'lead_source', 'interested_course', 'assigned_to']
    search_fields = ['parent_name', 'phone', 'student_name']
    
    readonly_fields = ['created_at', 'updated_at', 'family_navigation']
    
    # 2. BỐ CỤC BÊN TRONG
    fieldsets = (
        ('Thông tin Phụ huynh', {
            # ĐÃ THÊM 'lead_source' VÀO TRONG FORM NÀY
            'fields': ('parent_name', 'phone', 'email', 'lead_source', 'family_navigation')
        }),
        ('Thông tin Học sinh', {
            'fields': ('student_name', 'student_age', 'interested_course')
        }),
        ('Quản lý Tư vấn', {
            'fields': ('status', 'assigned_to', 'notes')
        }),
        ('Lịch sử', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # =========================================================================
    # THUẬT TOÁN GOM NHÓM DANH SÁCH NGOÀI (1 SĐT = 1 DÒNG)
    # =========================================================================
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Chỉ gom nhóm ở ngoài danh sách, tránh lỗi khi vào trong chi tiết
        if request.resolver_match and request.resolver_match.url_name == 'crm_lead_changelist':
            latest_ids = qs.values('phone').annotate(max_id=Max('id')).values('max_id')
            return qs.filter(id__in=latest_ids)
        return qs

    # =========================================================================
    # CỘT LIÊN KẾT BÊN NGOÀI (THÊM HIỆU ỨNG NGỌN LỬA 🔥 CHO KHÁCH VIP)
    # =========================================================================
    def total_leads_count(self, obj):
        count = Lead.objects.filter(phone=obj.phone).count()
        
        if count >= 3:
            # Khách VIP: Từ 3 thẻ trở lên -> Có ngọn lửa và màu đỏ gradient nổi bật
            return format_html('<span style="background: linear-gradient(45deg, #ff6b6b, #c0392b); color: white; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; box-shadow: 0 2px 4px rgba(192,57,43,0.4);">{} thẻ🔥</span>', count)
        elif count == 2:
            # Khách Tiềm năng: 2 thẻ -> Màu đỏ tiêu chuẩn
            return format_html('<span style="background-color: #e74c3c; color: white; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px;">2 thẻ</span>')
        
        # Khách Bình thường: 1 thẻ -> Màu xám nhạt
        return format_html('<span style="color: #7f8c8d; border: 1px solid #ccc; padding: 3px 10px; border-radius: 12px; font-size: 12px;">1 thẻ</span>')
    
    total_leads_count.short_description = 'Liên kết'

    # =========================================================================
    # MENU ĐIỀU HƯỚNG CÁC CON (FULL WIDTH TRONG TAB PHỤ HUYNH)
    # =========================================================================
    def family_navigation(self, obj):
        all_leads = Lead.objects.filter(phone=obj.phone).order_by('-id')
        
        html = '''
        <style>
            .field-family_navigation label { display: none !important; }
            .field-family_navigation > div { flex: 0 0 100% !important; max-width: 100% !important; margin-left: 0 !important; padding-left: 0 !important; }
        </style>
        <div style="width: 100%; padding-top: 15px; margin-top: 10px; border-top: 1px dashed #ccc;">
            <h6 style="font-weight: bold; color: #2c3e50; margin-bottom: 15px; text-transform: uppercase;">Danh sách Thẻ (Hồ sơ các con)</h6>
            <div style="display: flex; flex-direction: column; gap: 10px;">
        '''
        
        for lead in all_leads:
            color = "green" if lead.status == 'won' else "red" if lead.status == 'lost' else "#e67e22"
            status_name = dict(Lead.STATUS_CHOICES).get(lead.status, lead.status)
            
            if lead.id == obj.id:
                action_btn = '<span style="background: #3498db; color: white; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 4px rgba(52,152,219,0.3);">📍 ĐANG SỬA THẺ NÀY</span>'
                bg_color = "#f4f9ff"
                border_color = "#3498db"
            else:
                edit_url = f"/admin/crm/lead/{lead.id}/change/"
                action_btn = f'<a href="{edit_url}" style="background: #f39c12; color: white; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; text-decoration: none; box-shadow: 0 2px 4px rgba(243,156,18,0.3);">SỬA THẺ NÀY ➔</a>'
                bg_color = "#ffffff"
                border_color = "#e2e8f0"

            html += f'''
                <div style="border: 1px solid {border_color}; border-left: 4px solid {border_color}; padding: 15px; border-radius: 6px; background: {bg_color}; display: flex; justify-content: space-between; align-items: center;">
                    <div style="line-height: 1.5;">
                        <div style="font-size: 15px;">Bé: <b style="color: #2c3e50;">{lead.student_name or 'Chưa cập nhật'}</b> <span style="color: #7f8c8d; font-size: 13px;">({lead.student_age or '?'} tuổi)</span></div>
                        <div style="font-size: 13px; margin-top: 4px;">Môn đăng ký: <b style="color: #e74c3c;">{lead.interested_course or 'Chưa xác định'}</b></div>
                        <div style="font-size: 13px; margin-top: 4px;">Trạng thái: <span style="color: {color}; font-weight: bold;">{status_name}</span></div>
                    </div>
                    <div>
                        {action_btn}
                    </div>
                </div>
            '''
        html += '</div></div>'
        return mark_safe(html)
    family_navigation.short_description = ''