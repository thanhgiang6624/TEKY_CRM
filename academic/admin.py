from django.contrib import admin
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Course, Student, CourseRegistration, Class, Enrollment, SessionAbsence, ClassResignation

# =========================================================
# 1. QUẢN LÝ ĐƠN TỪ CỦA GIÁO VIÊN
# =========================================================
@admin.register(SessionAbsence)
class SessionAbsenceAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'target_class', 'absence_date', 'status', 'created_at')
    list_filter = ('status', 'absence_date', 'target_class')
    search_fields = ('teacher__first_name', 'teacher__last_name', 'target_class__class_code')
    actions = ['approve_requests', 'reject_requests']

    @admin.action(description='✔️ DUYỆT các đơn đã chọn')
    def approve_requests(self, request, queryset):
        updated = queryset.update(status='approved')
        self.message_user(request, f'Đã duyệt thành công {updated} đơn xin nghỉ!', messages.SUCCESS)

    @admin.action(description='❌ TỪ CHỐI các đơn đã chọn')
    def reject_requests(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'Đã từ chối {updated} đơn xin nghỉ!', messages.WARNING)

@admin.register(ClassResignation)
class ClassResignationAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'target_class', 'status', 'created_at')
    list_filter = ('status', 'target_class')
    search_fields = ('teacher__first_name', 'teacher__last_name', 'target_class__class_code')
    actions = ['approve_requests', 'reject_requests']

    @admin.action(description='✔️ DUYỆT ĐƠN & Tự động gỡ GV khỏi lớp')
    def approve_requests(self, request, queryset):
        updated = queryset.update(status='approved')
        for req in queryset:
            target_class = req.target_class
            target_class.teacher = None 
            target_class.save()
        self.message_user(request, f'Đã duyệt {updated} đơn và gỡ giáo viên khỏi danh sách lớp!', messages.SUCCESS)

    @admin.action(description='❌ TỪ CHỐI các đơn đã chọn')
    def reject_requests(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'Đã từ chối {updated} đơn xin thôi dạy!', messages.WARNING)


# =========================================================
# 2. QUẢN LÝ DANH MỤC KHÓA HỌC
# =========================================================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'grade_group', 'total_modules', 'sessions_per_module', 'get_total_sessions', 'price_per_module']
    search_fields = ['code', 'name']
    list_filter = ['grade_group']

    def get_total_sessions(self, obj):
        return f"{obj.total_sessions} buổi"
    get_total_sessions.short_description = 'Tổng số buổi'

# =========================================================
# 3. QUẢN LÝ HỌC VIÊN & PHIẾU ĐĂNG KÝ MÔN 
# =========================================================

class CourseRegistrationInline(admin.TabularInline):
    model = CourseRegistration
    extra = 0
    # XÓA HOÀN TOÀN is_assigned KHỎI ĐÂY
    fields = ('course', 'status', 'starting_module', 'total_sessions', 'remaining_sessions')

class StudentEnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    verbose_name = "Lớp đang tham gia"
    verbose_name_plural = "Thông tin Lớp học thực tế (Chỉ xem)"
    
    # VIỆT HÓA CỘT LỚP HỌC (get_class_vn)
    fields = ('get_class_vn', 'status', 'total_sessions', 'get_consumed', 'get_remaining')
    readonly_fields = ('get_class_vn', 'status', 'total_sessions', 'get_consumed', 'get_remaining')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False
        
    def get_class_vn(self, obj):
        return obj.enrolled_class.class_code
    get_class_vn.short_description = "Lớp học"
    
    def get_consumed(self, obj):
        return obj.consumed_sessions
    get_consumed.short_description = "Số buổi đã học"
    
    def get_remaining(self, obj):
        return obj.remaining_sessions
    get_remaining.short_description = "Còn lại trong lớp"

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    # CẬP NHẬT CỘT: Thêm Nguồn, Đếm 4 trạng thái chuẩn
    list_display = [
        'student_code', 'full_name', 'get_parent_name', 'get_phone', 
        'get_lead_source', # <-- NGUỒN TỪ KHÁCH HÀNG
        'get_total_courses', 
        'get_studying_count', 'get_waiting_count', 
        'get_reserved_count', 'get_dropped_count'
    ]
    search_fields = ['student_code', 'full_name', 'lead__parent_name', 'lead__phone']
    
    # BỘ LỌC CHUẨN MỚI
    list_filter = ['registrations__status', 'registrations__course']
    
    inlines = [CourseRegistrationInline, StudentEnrollmentInline]
    
    fieldsets = (
        ('Thông tin cá nhân (Hồ sơ Con người)', {
            'fields': ('student_code', 'full_name', 'dob', 'lead')
        }),
    )

    # Hàm móc Nguồn từ Lead sang
    def get_lead_source(self, obj):
        if obj.lead:
            return obj.lead.get_lead_source_display()
        return "N/A"
    get_lead_source.short_description = "Nguồn"

    def get_total_courses(self, obj):
        count = obj.registrations.count()
        if count >= 3:
            return format_html('<span style="color: #dc2626; font-weight:bold; border: 1px solid #fca5a5; background: #fee2e2; border-radius: 8px; padding: 3px 8px;">{} môn 🔥</span>', count)
        elif count > 0:
            return format_html('<span style="color: #2563eb; font-weight:bold; border: 1px solid #bfdbfe; background: #eff6ff; border-radius: 8px; padding: 3px 8px;">{} môn</span>', count)
        return format_html('<span style="color: #94a3b8; font-weight:bold;">0 môn</span>')
    get_total_courses.short_description = "Đăng ký"

    # THUẬT TOÁN ĐẾM 4 TRẠNG THÁI (Theo đúng Models mới)
    def get_studying_count(self, obj):
        count = obj.registrations.filter(status='studying').count()
        return format_html('<span style="color: #16a34a; font-weight:bold; font-size: 14px;">{}</span>', count) if count else "-"
    get_studying_count.short_description = "Đang học"

    def get_waiting_count(self, obj):
        count = obj.registrations.filter(status='waiting').count()
        return format_html('<span style="color: #ea580c; font-weight:bold; font-size: 14px;">{}</span>', count) if count else "-"
    get_waiting_count.short_description = "Chờ lớp"

    def get_reserved_count(self, obj):
        count = obj.registrations.filter(status='reserved').count()
        return format_html('<span style="color: #ca8a04; font-weight:bold; font-size: 14px;">{}</span>', count) if count else "-"
    get_reserved_count.short_description = "Bảo lưu"

    def get_dropped_count(self, obj):
        count = obj.registrations.filter(status='dropped').count()
        return format_html('<span style="color: #dc2626; font-weight:bold; font-size: 14px;">{}</span>', count) if count else "-"
    get_dropped_count.short_description = "Nghỉ"


# =========================================================
# 4. QUẢN LÝ LỚP HỌC (GIỮ NGUYÊN)
# =========================================================
class ClassEnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['class_code', 'course', 'get_schedule_display', 'teacher', 'get_student_count', 'get_progress_vn', 'status']
    list_filter = ['status', 'course', 'day_of_week', 'teacher']
    search_fields = ['class_code']
    
    inlines = [ClassEnrollmentInline]
    
    def get_schedule_display(self, obj):
        day = dict(Class.DAY_CHOICES).get(obj.day_of_week, obj.day_of_week)
        time = dict(Class.TIME_CHOICES).get(obj.time_slot, obj.time_slot)
        return f"{day} ({time})"
    get_schedule_display.short_description = 'Lịch học'

    def get_student_count(self, obj):
        count = obj.students.count()
        return format_html('<span style="color: #2980b9; font-weight:bold;">{} HV</span>', count)
    get_student_count.short_description = 'Sĩ số'
    
    def get_progress_vn(self, obj):
        return obj.current_progress
    get_progress_vn.short_description = 'Tiến độ hiện tại'