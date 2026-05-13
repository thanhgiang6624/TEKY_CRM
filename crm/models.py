from django.db import models
from django.conf import settings

class Lead(models.Model):

    starting_module = models.IntegerField(default=1, verbose_name="Học phần bắt đầu")
    # Định nghĩa các bước trong Phễu bán hàng (Sales Funnel)
    STATUS_CHOICES = (
        ('new', 'Mới tiếp nhận'),
        ('consulting', 'Đang tư vấn'),
        ('trial', 'Đã hẹn học thử'),
        ('won', 'Thành công (Đã chốt)'),
        ('lost', 'Thất bại (Hủy)'),
    )

    # NÂNG CẤP: NGUỒN KHÁCH HÀNG (Đo lường Marketing)
    SOURCE_CHOICES = (
        ('facebook', 'Facebook Ads'),
        ('zalo', 'Zalo / Hotline'),
        ('website', 'Website Teky'),
        ('referral', 'Người quen giới thiệu'),
        ('event', 'Sự kiện / School Tour'),
        ('other', 'Nguồn khác'),
    )

    # 1. THÔNG TIN PHỤ HUYNH (Bắt buộc từ đầu)
    parent_name = models.CharField('Phụ huynh', max_length=100)
    phone = models.CharField('Số điện thoại', max_length=15)
    email = models.EmailField('Email', blank=True, null=True)
    lead_source = models.CharField('Nguồn', max_length=20, choices=SOURCE_CHOICES, default='facebook')
    
    # 2. THÔNG TIN HỌC SINH (Có thể bổ sung sau thông qua Form Cập nhật)
    student_name = models.CharField('Tên Học sinh', max_length=100, blank=True, null=True)
    student_age = models.IntegerField('Tuổi học sinh', blank=True, null=True)
    
    # ĐÃ GỠ BỎ CHOICES CỨNG ĐỂ TỰ ĐỘNG LOAD TỪ HỌC VỤ SANG
    interested_course = models.CharField(
        'Khóa học quan tâm', 
        max_length=100, 
        blank=True,
        null=True
    )
    
    # ĐÃ GỠ BỎ CHOICES CỨNG ĐỂ TỰ ĐỘNG LOAD TỪ HỌC VỤ SANG
    preferred_schedule = models.CharField(
        'Lịch học mong muốn', 
        max_length=150, 
        blank=True, 
        null=True
    )
    
    # 3. QUẢN LÝ TRẠNG THÁI & PHÂN CÔNG
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='new')
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        limit_choices_to={'role': 'sales'}, 
        verbose_name='Tư vấn viên phụ trách'
    )
    
    notes = models.TextField('Ghi chú tư vấn', blank=True)
    follow_up_date = models.DateField(null=True, blank=True, verbose_name="Ngày hẹn gọi lại")
    
    # =========================================================
    # 4. QUẢN LÝ SẢN PHẨM & TÀI CHÍNH (KHI CHỐT DEAL)
    # =========================================================
    modules_bought = models.IntegerField('Số học phần đăng ký', default=1, help_text="1 Học phần = 12 buổi = 5 triệu")
    discount_percent = models.IntegerField('Phần trăm giảm giá (%)', default=0)
    discount_amount = models.IntegerField('Giảm giá tiền mặt (VNĐ)', default=0)
    tuition_fee = models.CharField('Học phí thực thu (VNĐ)', max_length=50, null=True, blank=True)
    
    # =========================================================
    # 5. TRẠNG THÁI BÀN GIAO CHO HỌC VỤ
    # =========================================================
    is_transferred_to_academic = models.BooleanField('Đã chuyển giao Học vụ', default=False)
    
    # Tự động lưu vết thời gian
    created_at = models.DateTimeField('Ngày tạo', auto_now_add=True)
    updated_at = models.DateTimeField('Cập nhật lần cuối', auto_now=True)

    class Meta:
        verbose_name = 'Khách hàng tiềm năng'
        verbose_name_plural = 'Danh sách Khách hàng'

    def __str__(self):
        source_display = dict(self.SOURCE_CHOICES).get(self.lead_source, self.lead_source)
        return f"{self.parent_name} ({source_display})"