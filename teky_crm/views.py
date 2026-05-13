import json
import re
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.contrib.auth import get_user_model

from crm.models import Lead
from academic.models import Class, Student, Attendance, SessionAbsence, LessonContent
from facility.models import Device, BorrowLog

User = get_user_model()

@login_required(login_url='/login/')
def dashboard_view(request):
    user = request.user
    today_date = timezone.now().date()
    
    if user.role == 'teacher':
        # --- BƯỚC 1: LẤY CÁC LỚP CHÍNH THỨC CỦA GIÁO VIÊN ---
        main_classes = Class.objects.filter(teacher=user, status='active').select_related('course')
        
        # --- BƯỚC 2: LẤY CÁC ĐƠN XIN NGHỈ ĐÃ DUYỆT (ABSENCES) ---
        # Để loại bỏ buổi học này khỏi lịch
        my_absences = SessionAbsence.objects.filter(teacher=user, status='approved').values_list('target_class_id', 'absence_date')
        absence_set = set(my_absences)
        
        # --- BƯỚC 3: LẤY CÁC LỚP ĐƯỢC PHÂN CÔNG DẠY THAY (SUBSTITUTIONS) ---
        # Thông qua bảng SessionAbsence
        my_substitutions = SessionAbsence.objects.filter(substitute_teacher=user, status='approved').select_related('target_class', 'target_class__course')
        
        # Thêm cách lấy thông qua bảng LessonContent (nếu Admin xếp trực tiếp vào bài học)
        my_recorded_lessons = LessonContent.objects.filter(actual_teacher=user).select_related('for_class', 'for_class__course')
        
        classes_data = []
        
        # MỐC THỜI GIAN: Tính lịch cho 2 tháng qua và 1 tháng tới để nhẹ server
        start_date_range = today_date.replace(day=1) - timedelta(days=60)
        end_date_range = today_date.replace(day=1) + timedelta(days=60)
        
        day_map = {'T2': 0, 'T3': 1, 'T4': 2, 'T5': 3, 'T6': 4, 'T7': 5, 'CN': 6}
        
        # 1. THÊM LỚP CHÍNH THỨC VÀO LỊCH (Sinh các buổi học)
        for c in main_classes:
            raw_start = c.start_date if c.start_date else today_date
            target_weekday = day_map.get(c.day_of_week, 0)
            days_shift = target_weekday - raw_start.weekday()
            base_date = raw_start + timedelta(days=days_shift)
            
            # Chỉ sinh lịch nếu lớp đã có ngày khai giảng
            if not c.start_date: continue
            
            spm = c.course.sessions_per_module if c.course else 12
            total_s = c.course.total_sessions if c.course else 0
            
            starting_mod = getattr(c, 'starting_module', 1)
            start_offset = (starting_mod - 1) * spm
            
            # Lặp sinh ra danh sách ngày học
            for s in range(total_s):
                session_no = start_offset + s + 1
                session_date = base_date + timedelta(weeks=s)
                
                # Bỏ qua nếu nằm ngoài mốc hiển thị
                if session_date < start_date_range or session_date > end_date_range:
                    continue
                    
                # BỎ QUA nếu buổi này có trong danh sách Xin nghỉ (Absence)
                if (c.id, session_date) in absence_set:
                    continue
                    
                classes_data.append({
                    'id': c.id, 
                    'code': c.class_code, 
                    'course': c.course.name,
                    'day': c.day_of_week, 
                    'time': c.get_time_slot_display(), 
                    'student_count': c.students.count(), 
                    'session_date': session_date.strftime('%Y-%m-%d'), # TRƯỜNG QUAN TRỌNG MỚI
                    'is_substitute': False
                })
                
        # 2. THÊM LỚP DẠY THAY VÀO LỊCH (Từ SessionAbsence)
        for sub in my_substitutions:
            c = sub.target_class
            classes_data.append({
                'id': c.id, 
                'code': c.class_code, 
                'course': c.course.name if c.course else "Unknown",
                'day': c.day_of_week, 
                'time': c.get_time_slot_display(), 
                'student_count': c.students.count(), 
                'session_date': sub.absence_date.strftime('%Y-%m-%d'),
                'is_substitute': True # Đánh dấu là Dạy thay
            })
            
        # 3. THÊM LỚP DẠY THAY VÀO LỊCH (Từ LessonContent nếu có)
        recorded_dates_set = {data['session_date'] for data in classes_data}
        for rec in my_recorded_lessons:
            date_str = rec.date.strftime('%Y-%m-%d')
            # Nếu ngày này đã có trong lịch dạy thay rồi thì bỏ qua để tránh trùng
            if date_str in recorded_dates_set:
                continue
            c = rec.for_class
            classes_data.append({
                'id': c.id, 
                'code': c.class_code, 
                'course': c.course.name if c.course else "Unknown",
                'day': c.day_of_week, 
                'time': c.get_time_slot_display(), 
                'student_count': c.students.count(), 
                'session_date': date_str,
                'is_substitute': True # Đánh dấu là Dạy thay
            })

        return render(request, 'teky_teacher_dashboard.html', {'classes_data': classes_data})
    
    else:
        current_month_str = f"{today_date.month}-{today_date.year}"
        
        # --- NHẬN TÍN HIỆU TỪ BỘ LỌC ---
        filter_month = request.GET.get('month', current_month_str)
        facility_filter = request.GET.get('facility_filter', 'today') 
        sales_filter = request.GET.get('sales_filter', 'all')
        facility_staff_filter = request.GET.get('facility_staff_filter', 'all')
        
        month_choices = []
        for i in range(6):
            m = today_date.month - i
            y = today_date.year
            if m <= 0:
                m += 12
                y -= 1
            month_choices.append({'value': f"{m}-{y}", 'label': f"Tháng {m:02d}/{y}"})

        # --- LOAD DANH SÁCH NHÂN SỰ CHO DROPDOWN ---
        sales_users = User.objects.filter(role='sales', is_active=True)
        facility_users = User.objects.filter(role__in=['facility', 'admin', 'manager'], is_active=True)

        context = {
            'filter_month': filter_month,
            'facility_filter': facility_filter,
            'sales_filter': sales_filter,
            'facility_staff_filter': facility_staff_filter,
            'month_choices': month_choices,
            'sales_users': sales_users,
            'facility_users': facility_users,
        }

        # ====================================================================
        # A. DỮ LIỆU KINH DOANH (PHÂN QUYỀN CHẶT CHẼ TỐI ĐA)
        # ====================================================================
        if user.role in ['sales', 'admin', 'manager'] or user.is_superuser:
            
            if user.role in ['admin', 'manager'] or user.is_superuser:
                lead_query = Lead.objects.all()
                context['kpi_title'] = "KPI Toàn Trung tâm"
                
                # NÂNG CẤP: Lọc doanh thu theo từng bạn Sales
                if sales_filter != 'all' and sales_filter.isdigit():
                    lead_query = lead_query.filter(assigned_to_id=int(sales_filter))
                    selected_sale = sales_users.filter(id=int(sales_filter)).first()
                    if selected_sale:
                        context['kpi_title'] = f"KPI của: {selected_sale.first_name or selected_sale.username}"
            else:
                lead_query = Lead.objects.filter(assigned_to=user)
                context['kpi_title'] = "KPI của Tôi"

            if filter_month != 'all':
                try:
                    m, y = map(int, filter_month.split('-'))
                    lead_query = lead_query.filter(updated_at__month=m, updated_at__year=y)
                except:
                    pass

            total_leads_count = lead_query.count()
            won_leads_query = lead_query.filter(status='won')
            won_leads_count = won_leads_query.count()
            
            total_revenue = 0
            for lead in won_leads_query:
                if lead.tuition_fee:
                    try:
                        clean_fee = str(lead.tuition_fee).replace(',', '').replace('.', '').replace(' ', '')
                        total_revenue += int(clean_fee)
                    except ValueError:
                        pass
                else:
                    total_revenue += (lead.modules_bought * 5000000)

            context['total_leads'] = total_leads_count
            context['won_leads'] = won_leads_count
            context['total_revenue'] = total_revenue

            lead_data = lead_query.values('status').annotate(count=Count('status'))
            lead_status_dict = dict(Lead.STATUS_CHOICES)
            context['lead_labels'] = json.dumps([lead_status_dict.get(item['status'], item['status']) for item in lead_data])
            context['lead_counts'] = json.dumps([item['count'] for item in lead_data])

        # ====================================================================
        # B. DỮ LIỆU VẬN HÀNH
        # ====================================================================
        if user.role in ['facility', 'admin', 'manager'] or user.is_superuser:
            if facility_filter == 'week':
                start_of_week = today_date - timedelta(days=today_date.weekday())
                att_q = Attendance.objects.filter(date__gte=start_of_week)
                borrow_q = BorrowLog.objects.filter(borrow_time__date__gte=start_of_week)
                return_q = BorrowLog.objects.filter(return_time__date__gte=start_of_week)
            elif facility_filter == 'month':
                att_q = Attendance.objects.filter(date__year=today_date.year, date__month=today_date.month)
                borrow_q = BorrowLog.objects.filter(borrow_time__year=today_date.year, borrow_time__month=today_date.month)
                return_q = BorrowLog.objects.filter(return_time__year=today_date.year, return_time__month=today_date.month)
            elif facility_filter == 'year':
                att_q = Attendance.objects.filter(date__year=today_date.year)
                borrow_q = BorrowLog.objects.filter(borrow_time__year=today_date.year)
                return_q = BorrowLog.objects.filter(return_time__year=today_date.year)
            else: # today
                att_q = Attendance.objects.filter(date=today_date)
                borrow_q = BorrowLog.objects.filter(borrow_time__date=today_date)
                return_q = BorrowLog.objects.filter(return_time__date=today_date)

            # NÂNG CẤP: Lọc theo người trực cơ sở (Lọc BorrowLog nếu có trường user_id)
            if facility_staff_filter != 'all' and facility_staff_filter.isdigit():
                try:
                    # Chú ý: Nếu models của bạn tên trường khác 'user_id' thì hệ thống sẽ tự động bỏ qua để không sập web
                    borrow_q = borrow_q.filter(user_id=int(facility_staff_filter))
                    return_q = return_q.filter(user_id=int(facility_staff_filter))
                except:
                    pass 

            context['students_present'] = att_q.filter(status='present').count()
            context['students_absent'] = att_q.filter(status='absent').count()
            context['devices_borrowed'] = borrow_q.count()
            context['devices_returned'] = return_q.count()

            device_data = Device.objects.values('status').annotate(count=Count('status'))
            device_status_dict = dict(Device.STATUS_CHOICES)
            context['device_labels'] = json.dumps([device_status_dict.get(item['status'], item['status']) for item in device_data])
            context['device_counts'] = json.dumps([item['count'] for item in device_data])

        return render(request, 'teky_manager_dashboard.html', context)

@login_required(login_url='/login/')
def teacher_profile_view(request):
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            # MỚI THÊM: Cho phép cập nhật Tên
            first_name = request.POST.get('first_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                messages.error(request, 'Định dạng Email không hợp lệ!')
                return redirect(request.path)
            if phone and not re.match(r'^0\d{9}$', phone):
                messages.error(request, 'SĐT gồm 10 chữ số và bắt đầu bằng số 0!')
                return redirect(request.path)
            
            if first_name: user.first_name = first_name
            user.email = email
            user.phone = phone
            avatar = request.FILES.get('avatar')
            if avatar:
                user.avatar = avatar
            user.save()
            messages.success(request, 'Cập nhật thành công!')
            return redirect(request.path)
        elif action == 'change_password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Đổi mật khẩu thành công!')
                return redirect(request.path)
            else:
                for error in list(password_form.errors.values()):
                    messages.error(request, error)

    password_form = PasswordChangeForm(user)
    return render(request, 'teky_profile.html', {'password_form': password_form})