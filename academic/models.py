import json
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from crm.models import Lead
from django.utils import timezone
from datetime import timedelta

class Course(models.Model):
    code = models.CharField('Mã khóa học', max_length=20, unique=True)
    name = models.CharField('Tên khóa học', max_length=100)
    
    GRADE_CHOICES = (
        ('mam_non', 'Mầm non (Dưới 6 tuổi)'),
        ('1-3', 'Khối Lớp 1-3 (6-8 tuổi)'),
        ('4-6', 'Khối Lớp 4-6 (9-11 tuổi)'),
        ('7-9', 'Khối Lớp 7-9 (12-14 tuổi)'),
        ('10-12', 'Khối Lớp 10-12 (15-18 tuổi)'),
        ('all', 'Mọi lứa tuổi (Không giới hạn)'),
    )
    grade_group = models.CharField('Độ tuổi phù hợp', max_length=20, choices=GRADE_CHOICES, default='all')
    
    total_modules = models.IntegerField('Tổng số Học phần', default=12)
    sessions_per_module = models.IntegerField('Số buổi / Học phần', default=12)
    price_per_module = models.IntegerField('Học phí / Học phần (VNĐ)', default=5000000)

    @property
    def total_sessions(self):
        return self.total_modules * self.sessions_per_module

    def __str__(self):
        return f"[{self.code}] {self.name}"

    class Meta:
        verbose_name = 'Khóa học'
        verbose_name_plural = '1. Danh mục Khóa học'

# =================================================================
# 1. BẢNG HỒ SƠ CON NGƯỜI (DUY NHẤT 1 MÃ HV CHO 1 BÉ)
# =================================================================
class Student(models.Model):
    lead = models.OneToOneField(Lead, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Từ Khách hàng')
    student_code = models.CharField('Mã Học viên', max_length=20, unique=True, blank=True)
    full_name = models.CharField('Tên Học viên', max_length=100)
    dob = models.DateField('Ngày sinh', null=True, blank=True)

    def get_parent_name(self):
        return self.lead.parent_name if self.lead else "N/A"
    get_parent_name.short_description = 'Phụ huynh'

    def get_phone(self):
        return self.lead.phone if self.lead else "N/A"
    get_phone.short_description = 'Số điện thoại'

    def save(self, *args, **kwargs):
        if not self.student_code:
            count = Student.objects.count() + 1
            self.student_code = f"HV{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_code} - {self.full_name}"

    class Meta:
        verbose_name = 'Học viên'
        verbose_name_plural = '2. Hồ sơ Học viên'

# =================================================================
# 2. BẢNG PHIẾU ĐĂNG KÝ MÔN (1 BÉ CÓ THỂ CÓ NHIỀU PHIẾU MÔN HỌC)
# =================================================================
class CourseRegistration(models.Model):
    STATUS_CHOICES = (
        ('waiting', 'Chờ xếp lớp'),
        ('studying', 'Đang học'), 
        ('reserved', 'Đang bảo lưu'),
        ('dropped', 'Đã nghỉ học'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='registrations', verbose_name="Học viên")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Môn học đăng ký")
    
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='waiting')
    total_sessions = models.IntegerField('Tổng số buổi đã mua', default=0)
    remaining_sessions = models.IntegerField('Số buổi còn lại', default=0)
    starting_module = models.IntegerField('Học phần bắt đầu', default=1)
    
    created_at = models.DateTimeField('Ngày đăng ký', auto_now_add=True)

    @property
    def is_out_of_tuition(self):
        return self.remaining_sessions <= 0

    def __str__(self):
        return f"{self.student.full_name} - {self.course.name}"

    class Meta:
        verbose_name = 'Phiếu đăng ký môn'
        verbose_name_plural = 'Phiếu đăng ký môn'

    @property
    def current_progress(self):
        if not self.course or self.course.sessions_per_module <= 0:
            return "N/A"
            
        spm = self.course.sessions_per_module
        consumed_sessions = self.total_sessions - self.remaining_sessions
        base_sessions = (self.starting_module - 1) * spm
        current_absolute_session = base_sessions + consumed_sessions
        
        current_module = (current_absolute_session // spm) + 1
        session_in_module = (current_absolute_session % spm) + 1
        
        if consumed_sessions == 0:
            return f"Chờ học: Học phần {self.starting_module}"
            
        return f"Đang học: HP {current_module} (Buổi {session_in_module}/{spm})"


class Class(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Sắp khai giảng'),
        ('active', 'Đang học'),
        ('completed', 'Đã kết thúc'),
    )
    
    DAY_CHOICES = (
        ('T2', 'Thứ 2'), ('T3', 'Thứ 3'), ('T4', 'Thứ 4'),
        ('T5', 'Thứ 5'), ('T6', 'Thứ 6'), ('T7', 'Thứ 7'), ('CN', 'Chủ nhật'),
    )

    TIME_CHOICES = (
        ('09h00-10h30', 'Sáng: 09h00 - 10h30'),
        ('10h30-12h00', 'Sáng: 10h30 - 12h00'),
        ('14h00-15h30', 'Chiều: 14h00 - 15h30'),
        ('15h30-17h00', 'Chiều: 15h30 - 17h00'),
        ('18h00-19h30', 'Tối: 18h00 - 19h30'),
        ('19h30-21h00', 'Tối: 19h30 - 21h00'),
    )
    
    class_code = models.CharField('Mã lớp', max_length=50, unique=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.RESTRICT, verbose_name='Khóa học')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'teacher'}, verbose_name='Giáo viên phụ trách'
    )

    teacher_assigned_date = models.DateField('Ngày tiếp nhận lớp', null=True, blank=True)
    day_of_week = models.CharField('Ngày học', max_length=2, choices=DAY_CHOICES, default='T7')
    time_slot = models.CharField('Ca học', max_length=20, choices=TIME_CHOICES, default='18h00-19h30')
    start_date = models.DateField('Ngày khai giảng', null=True, blank=True)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='pending')
    
    starting_module = models.IntegerField('Học phần Bắt đầu', default=1) 
    completed_sessions = models.IntegerField('Số buổi đã học (Tổng từ HP1)', default=0)

    students = models.ManyToManyField(Student, through='Enrollment', blank=True, related_name='classes', verbose_name='Danh sách Học viên')

    def clean(self):
        if self.status == 'active':
            if not self.teacher:
                raise ValidationError({'teacher': 'Lớp "Đang học" bắt buộc phải có Giáo viên.'})
            if not self.start_date:
                raise ValidationError({'start_date': 'Lớp "Đang học" phải có ngày khai giảng.'})

    def save(self, *args, **kwargs):
        if not self.class_code:
            count = Class.objects.count() + 1
            c_code = self.course.code if self.course else "CLASS"
            self.class_code = f"L-{c_code}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.class_code

    class Meta:
        verbose_name = 'Lớp học'
        verbose_name_plural = '3. Quản lý Lớp học'

    @property
    def current_progress(self):
        if not self.course or self.course.sessions_per_module <= 0:
            return "Chưa xác định"
            
        spm = self.course.sessions_per_module 
        if self.completed_sessions == 0:
            return f"Bắt đầu: Học phần {self.starting_module}"
            
        current_module = (self.completed_sessions // spm) + 1
        session_in_module = (self.completed_sessions % spm)
        
        if session_in_module == 0 and self.completed_sessions > 0:
            current_module -= 1
            session_in_module = spm
            
        return f"Đang dạy: Học phần {current_module} (Buổi {session_in_module}/{spm})"


# =================================================================
# BẢNG GHI DANH: NƠI CHỨA VÍ HỌC PHÍ VÀ TRẠNG THÁI CHO TỪNG LỚP
# =================================================================
class Enrollment(models.Model):
    STATUS_CHOICES = (
        ('studying', 'Đang học'),
        ('reserved', 'Đang bảo lưu'),
        ('dropped', 'Đã nghỉ học'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    enrolled_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='studying')
    
    total_sessions = models.IntegerField('Tổng số buổi mua cho lớp này', default=0)
    sessions_consumed_before_reserve = models.IntegerField('Số buổi đã học (Lưu khi bảo lưu)', default=0)
    reserve_date = models.DateField('Ngày bắt đầu bảo lưu', null=True, blank=True)

    class Meta:
        verbose_name = 'Ghi danh Lớp học'
        verbose_name_plural = 'Quản lý Ghi danh (Ví học phí)'
        unique_together = ('student', 'enrolled_class')

    @property
    def consumed_sessions(self):
        if self.status == 'reserved':
            return self.sessions_consumed_before_reserve
            
        if not self.enrolled_class.start_date: 
            return 0
            
        today = timezone.now().date()
        start_date = self.enrolled_class.start_date
        
        if today < start_date:
            return 0
            
        weeks_passed = (today - start_date).days // 7
        past_sessions = weeks_passed + 1
        
        max_sessions = self.enrolled_class.course.total_sessions
        if past_sessions > max_sessions:
            past_sessions = max_sessions
            
        return past_sessions

    @property
    def remaining_sessions(self):
        return self.total_sessions - self.consumed_sessions


class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Có mặt'),
        ('absent', 'Vắng mặt'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name='Học viên')
    for_class = models.ForeignKey(Class, on_delete=models.CASCADE, verbose_name='Lớp học')
    date = models.DateField('Ngày học', default=timezone.now)
    status = models.CharField('Trạng thái', max_length=25, choices=STATUS_CHOICES, default='present')
    note = models.CharField('Nhận xét buổi học', max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Điểm danh'
        verbose_name_plural = '4. Lịch sử Điểm danh'
        unique_together = ('student', 'for_class', 'date')

    def __str__(self):
        return f"{self.student.full_name} - {self.date} ({self.get_status_display()})"
    
class SessionAbsence(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt (Tìm người dạy thay)'),
        ('rejected', 'Từ chối'),
    )

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='absences', verbose_name='Giáo viên xin nghỉ')
    target_class = models.ForeignKey('Class', on_delete=models.CASCADE, verbose_name='Lớp học')
    absence_date = models.DateField('Ngày xin nghỉ')
    reason = models.TextField('Lý do nghỉ', max_length=500)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='pending')
    
    substitute_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='substitutions', verbose_name='Giáo viên dạy thay'
    )
    
    created_at = models.DateTimeField('Thời gian tạo', auto_now_add=True)

    class Meta:
        verbose_name = 'Đơn xin nghỉ 1 buổi'
        verbose_name_plural = '3. Xin nghỉ buổi (Tạm thời)'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.teacher.first_name} nghỉ lớp {self.target_class.class_code} (Ngày {self.absence_date})"

class ClassResignation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt (Rút khỏi lớp)'),
        ('rejected', 'Từ chối'),
    )

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Giáo viên')
    target_class = models.ForeignKey('Class', on_delete=models.CASCADE, verbose_name='Lớp học')
    reason = models.TextField('Lý do xin rút khỏi lớp', max_length=1000)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField('Thời gian tạo', auto_now_add=True)

    class Meta:
        verbose_name = 'Đơn xin thôi dạy'
        verbose_name_plural = '4. Xin thôi dạy (Rút lớp)'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.teacher.first_name} xin RÚT KHỎI lớp {self.target_class.class_code}"
    
class LessonContent(models.Model):
    for_class = models.ForeignKey(Class, on_delete=models.CASCADE, verbose_name='Lớp học')
    date = models.DateField('Ngày dạy')
    content = models.TextField('Nội dung bài học')
    
    actual_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'teacher'}, verbose_name='Giáo viên dạy thực tế'
    )

    class Meta:
        unique_together = ('for_class', 'date')

class ClassImage(models.Model):
    for_class = models.ForeignKey(Class, on_delete=models.CASCADE, verbose_name='Lớp học')
    date = models.DateField('Ngày dạy')
    image = models.ImageField(upload_to='class_images/')

class StudentFace(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='face_data')
    face_encoding = models.TextField('Mã hóa khuôn mặt', blank=True, null=True)
    image_reference = models.ImageField('Ảnh mẫu', upload_to='face_references/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_encoding(self, encoding_array):
        self.face_encoding = json.dumps(encoding_array.tolist())
        
    def get_encoding(self):
        import numpy as np
        if self.face_encoding:
            return np.array(json.loads(self.face_encoding))
        return None

    def __str__(self):
        return f"Face Data: {self.student.full_name}"

# =================================================================
# 3. BẢNG QUẢN LÝ NGÀY NGHỈ LỄ/ĐỘT XUẤT CỦA LỚP
# =================================================================
class ClassHoliday(models.Model):
    for_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='holidays', verbose_name='Lớp học')
    holiday_date = models.DateField('Ngày nghỉ')
    reason = models.CharField('Lý do nghỉ', max_length=255, default='Nghỉ lễ')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ngày nghỉ lớp học'
        verbose_name_plural = 'Quản lý Ngày nghỉ (Lùi lịch)'
        unique_together = ('for_class', 'holiday_date')

    def __str__(self):
        return f"[{self.for_class.class_code}] Nghỉ ngày {self.holiday_date.strftime('%d/%m/%Y')} - {self.reason}"