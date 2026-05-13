import os
import django
import random
from datetime import date, timedelta, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teky_crm.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from academic.models import Course, Student, Class, Enrollment, CourseRegistration
from crm.models import Lead

try:
    from facility.models import Device, BorrowLog
    has_facility = True
except ImportError:
    has_facility = False

User = get_user_model()

# --- TỪ ĐIỂN TÊN ---
HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
DEM_NAM = ["Văn", "Hữu", "Đức", "Công", "Quang", "Minh", "Xuân", "Ngọc", "Đình", "Hải", "Hoàng", "Nhật", "Quốc", "Thế"]
TEN_NAM = ["Anh", "Bảo", "Bình", "Cường", "Dũng", "Dương", "Đạt", "Duy", "Hải", "Hiếu", "Huy", "Hùng", "Khang", "Khánh", "Khoa", "Kiên", "Lâm", "Long", "Nam", "Phúc", "Quân", "Sơn", "Thành", "Thắng", "Thiện", "Tiến", "Tuấn", "Tùng", "Việt", "Vinh"]
DEM_NU = ["Thị", "Thu", "Ngọc", "Phương", "Minh", "Thanh", "Thúy", "Thảo", "Hồng", "Mai", "Kim", "Bích", "Hoài", "Diễm"]
TEN_NU = ["An", "Anh", "Châu", "Chi", "Diệp", "Dung", "Hà", "Hằng", "Hân", "Hoa", "Huyền", "Hương", "Lan", "Linh", "Ly", "Mai", "My", "Nga", "Ngân", "Nhi", "Nhung", "Oanh", "Quyên", "Quỳnh", "Tâm", "Thảo", "Thu", "Thủy", "Tiên", "Trang", "Trâm", "Trinh", "Tú", "Uyên", "Vân", "Vy", "Yến"]

def get_name(gender='random'):
    if gender == 'random': gender = random.choice(['M', 'F'])
    ho = random.choice(HO)
    if gender == 'M': return f"{ho} {random.choice(DEM_NAM)} {random.choice(TEN_NAM)}"
    return f"{ho} {random.choice(DEM_NU)} {random.choice(TEN_NU)}"

def generate_data():
    print("🚀 KHỞI TẠO HỆ THỐNG TEKY CRM (ĐA DẠNG TIẾN ĐỘ & MƯỢN TRẢ THIẾT BỊ)...")

    # 1. USERS & SALES
    print("\n👤 Đang tạo Users...")
    sales_users = []
    for role in ['admin', 'facility', 'teacher', 'sales']:
        # Tăng số lượng giáo viên lên để xếp lớp cho dễ
        num_users = 4 if role == 'teacher' else 2
        for i in range(1, num_users + 1):
            u, _ = User.objects.get_or_create(username=f"{role}0{i}", defaults={'role': role, 'first_name': get_name()})
            u.set_password("123")
            u.save()
            if role == 'sales': sales_users.append(u)

    # 2. COURSES (18 khóa)
    print("📚 Đang tạo Khóa học...")
    courses_map = {
        'mam_non': (4, 6, ['Robot Mầm non', 'Scratch Jr', 'Bé làm Game']),
        '1-3': (6, 9, ['Scratch Cơ bản', 'Scratch Nâng cao', 'Wedo 2.0']),
        '4-6': (9, 12, ['Python Cơ bản', 'Web HTML/CSS', 'EV3 Robotics']),
        '7-9': (12, 15, ['Python Nâng cao', 'C++ Cơ bản', 'App Inventor']),
        '10-12': (15, 18, ['AI Cơ bản', 'Data Science', 'Lập trình thi đấu']),
        'all': (6, 18, ['Đồ họa 2D', 'Video Editor', 'Office MOS'])
    }
    all_courses = []
    for group, (min_a, max_a, names) in courses_map.items():
        for i, n in enumerate(names):
            c, _ = Course.objects.get_or_create(code=f"{group.upper()}_{i}", defaults={'name': n, 'grade_group': group})
            all_courses.append({'obj': c, 'min': min_a, 'max': max_a})

    # 3. THIẾT BỊ
    all_devices = []
    if has_facility:
        print("💻 Đang tạo Thiết bị (Kho)...")
        for i in range(1, 16):
            d1, _ = Device.objects.get_or_create(name=f"Laptop Dell Inspiron {i:02d}")
            d2, _ = Device.objects.get_or_create(name=f"iPad Gen 9 {i:02d}")
            d3, _ = Device.objects.get_or_create(name=f"Wedo Kit 2.0 {i:02d}")
            d4, _ = Device.objects.get_or_create(name=f"EV3 Robotics Kit {i:02d}")
            all_devices.extend([d1, d2, d3, d4])

    # 4. QUY TẮC LỊCH HỌC
    night_times = ['18h00-19h30', '19h30-21h00']
    day_times = ['09h00-10h30', '10h30-12h00', '14h00-15h30', '15h30-17h00']
    
    time_labels_dict = dict(Class.TIME_CHOICES)
    day_labels_dict = dict(Class.DAY_CHOICES)

    def get_valid_schedule(grade_group):
        if grade_group == 'mam_non':
            day = random.choice(['T7', 'CN'])
            time = random.choice(day_times)
            return day, time
        
        is_weekend = random.choice([True, False])
        if is_weekend:
            day = random.choice(['T7', 'CN'])
            time = random.choice(day_times + night_times)
        else:
            day = random.choice(['T2', 'T3', 'T4', 'T5', 'T6'])
            time = random.choice(night_times) 
        return day, time

    # 5. LEADS & STUDENTS
    print("👨‍👩‍👧‍👦 Đang tạo 150 Lead & Học viên...")
    leads_count = 0
    multi_child_parents = 15
    multi_course_students = 15
    total_leads_target = 150
    
    source_options = [s[0] for s in Lead.SOURCE_CHOICES]

    while leads_count < total_leads_target:
        p_name = get_name()
        phone = f"09{random.randint(10000000, 99999999)}"
        sale = random.choice(sales_users)
        lead_source = random.choice(source_options)
        
        num_children = random.choice([2, 3]) if multi_child_parents > 0 else 1
        if num_children > 1: multi_child_parents -= 1

        for _ in range(num_children):
            if leads_count >= total_leads_target: break
            leads_count += 1
            
            s_name = get_name()
            age = random.randint(5, 17)
            status = random.choices(['new', 'consulting', 'trial', 'won', 'lost'], weights=[5, 10, 10, 65, 10])[0]
            
            suitable = [c for c in all_courses if c['min'] <= age <= c['max']]
            chosen_c = random.choice(suitable if suitable else all_courses)['obj']
            
            day_code, time_code = get_valid_schedule(chosen_c.grade_group)
            random_schedule = f"{day_labels_dict.get(day_code)} ({time_labels_dict.get(time_code)})"

            lead = Lead.objects.create(
                parent_name=p_name, student_name=s_name, phone=phone,
                student_age=age, interested_course=chosen_c.name,
                status=status, assigned_to=sale, lead_source=lead_source,
                preferred_schedule=random_schedule,
                modules_bought=random.choice([1, 3, 6, 12, 24]) if status == 'won' else 1
            )

            if status == 'won':
                student = Student.objects.create(
                    lead=lead, full_name=s_name, 
                    dob=date.today() - timedelta(days=age*365)
                )

                courses_to_buy = [chosen_c]
                num_courses = random.choice([2, 3]) if multi_course_students > 0 else 1
                
                if num_courses > 1: 
                    multi_course_students -= 1
                    extra_c_objs = [c['obj'] for c in suitable if c['obj'] != chosen_c]
                    if extra_c_objs:
                        sample_count = min(num_courses - 1, len(extra_c_objs))
                        courses_to_buy.extend(random.sample(extra_c_objs, sample_count))
                
                for course in courses_to_buy:
                    reg_status = random.choices(['waiting', 'reserved', 'dropped'], weights=[95, 3, 2])[0]
                    
                    CourseRegistration.objects.create(
                        student=student,
                        course=course,
                        status=reg_status,
                        total_sessions=lead.modules_bought * course.sessions_per_module,
                        remaining_sessions=lead.modules_bought * course.sessions_per_module,
                        starting_module=1
                    )
    
    # 6. TẠO LỚP ĐANG CHẠY
    # Tăng số lượng lớp lên 20-30 lớp để Giáo viên có nhiều lịch dạy
    print("🏫 Đang mở thật nhiều lớp học đang chạy...")
    teachers = list(User.objects.filter(role='teacher'))
    num_classes_to_create = random.randint(20, 30)

    for i in range(num_classes_to_create):
        waiting_regs = CourseRegistration.objects.filter(status='waiting')
        if not waiting_regs.exists(): break
        
        c_random = random.choice(waiting_regs).course
        day_code, time_code = get_valid_schedule(c_random.grade_group)
        
        eligible_registrations = CourseRegistration.objects.filter(course=c_random, status='waiting')
        if eligible_registrations.count() >= 2:
            
            target_module = random.randint(1, min(4, c_random.total_modules))
            completed_sessions = (target_module - 1) * c_random.sessions_per_module + random.randint(0, c_random.sessions_per_module - 1)
            start_date = date.today() - timedelta(weeks=completed_sessions)
            
            class_obj = Class.objects.create(
                course=c_random,
                teacher=random.choice(teachers) if teachers else None,
                day_of_week=day_code,
                time_slot=time_code,
                start_date=start_date, 
                status='active',
                completed_sessions=completed_sessions 
            )
            
            sample_size = min(eligible_registrations.count(), random.randint(2, 8))
            assigned_regs = random.sample(list(eligible_registrations), sample_size)
            
            for reg in assigned_regs:
                if reg.total_sessions < completed_sessions + 12:
                    reg.total_sessions = completed_sessions + 24
                    reg.remaining_sessions = reg.total_sessions
                
                st = reg.student
                Enrollment.objects.get_or_create(
                    student=st, 
                    enrolled_class=class_obj, 
                    defaults={'total_sessions': reg.remaining_sessions}
                )
                reg.status = 'studying'
                reg.save()

    # 7. TẠO LỚP MỒI (PENDING)
    print("🎯 Đang tạo các lớp mồi để test tab 'Có thể xếp ngay'...")
    waiting_for_perfect = CourseRegistration.objects.filter(status='waiting')[:15]
    
    for reg in waiting_for_perfect:
        pref_sched = reg.student.lead.preferred_schedule if reg.student.lead else ""
        day_code, time_code = None, None
        
        for code, label in Class.DAY_CHOICES:
            if label in pref_sched: 
                day_code = code; break
                
        for code, label in Class.TIME_CHOICES:
            if label in pref_sched: 
                time_code = code; break
                
        if day_code and time_code:
            Class.objects.get_or_create(
                course=reg.course,
                day_of_week=day_code,
                time_slot=time_code,
                defaults={
                    'status': 'pending', 
                    'start_date': date.today() + timedelta(days=7),
                    'teacher': None
                }
            )

    # 8. SINH DỮ LIỆU MƯỢN TRẢ THIẾT BỊ (MỚI)
    if has_facility and all_devices:
        print("📦 Đang tạo dữ liệu Lịch sử Mượn/Trả thiết bị...")
        active_classes = list(Class.objects.filter(status='active', teacher__isnull=False))
        
        # 8.1. Thiết bị ĐÃ MƯỢN VÀ ĐÃ TRẢ (Lịch sử cũ)
        for _ in range(50):
            target_class = random.choice(active_classes)
            device = random.choice(all_devices)
            
            # Chọn 1 ngày ngẫu nhiên trong quá khứ (từ 1 đến 30 ngày trước)
            past_days = random.randint(1, 30)
            borrow_time = timezone.now() - timedelta(days=past_days, hours=random.randint(1, 5))
            return_time = borrow_time + timedelta(hours=random.randint(1, 3))
            
            # Random xem đồ lúc trả có bị hỏng không
            is_broken = random.choice([True, False, False, False]) # Tỉ lệ hỏng 25%
            note = random.choice(["Bị xước vỏ", "Hết pin sập nguồn", "Gãy 1 bánh xe"]) if is_broken else ""
            
            # Buộc phải sửa thuộc tính auto_now_add bằng cách save thủ công sau khi create
            log = BorrowLog(
                device=device,
                borrower=target_class.teacher,
                for_class=target_class,
                status='returned',
                return_time=return_time,
                note=note
            )
            log.save()
            # Ghi đè borrow_time vì Django mặc định không cho truyền auto_now_add qua constructor
            BorrowLog.objects.filter(id=log.id).update(borrow_time=borrow_time)
            
            if is_broken:
                device.status = 'maintenance'
                device.save()

        # 8.2. Thiết bị ĐANG MƯỢN (Chưa trả)
        # Random một số giáo viên đang dạy sẽ cầm theo đồ nghề
        for _ in range(15):
            target_class = random.choice(active_classes)
            # Tìm thiết bị đang ở trạng thái 'ready'
            available_devices = [d for d in all_devices if d.status == 'ready']
            if not available_devices: break
            
            device = random.choice(available_devices)
            
            # Mượn cách đây vài tiếng (hoặc tối đa 1 ngày)
            borrow_time = timezone.now() - timedelta(hours=random.randint(1, 20))
            
            log = BorrowLog(
                device=device,
                borrower=target_class.teacher,
                for_class=target_class,
                status='borrowed'
            )
            log.save()
            BorrowLog.objects.filter(id=log.id).update(borrow_time=borrow_time)
            
            # Khóa thiết bị lại
            device.status = 'borrowed'
            device.save()

    print("\n✅ XONG! Dữ liệu mẫu (Phiên bản đầy đủ Mượn Trả) đã hoàn tất!")

if __name__ == '__main__':
    generate_data()