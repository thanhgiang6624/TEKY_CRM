import json
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from academic.models import Class, Student, Enrollment, Attendance, SessionAbsence, ClassResignation, LessonContent, ClassImage, Course, CourseRegistration, ClassHoliday

User = get_user_model()

# ==============================================================================
# KHU VỰC 1: CÁC VIEW CỦA GIÁO VIÊN (TEACHER)
# ==============================================================================

@login_required(login_url='/login/')
def teacher_my_classes_view(request):
    my_classes = Class.objects.filter(teacher=request.user, status='active')
    return render(request, 'academic_teacher_my_classes.html', {'my_classes': my_classes})

@login_required(login_url='/login/')
def teacher_class_info_view(request, class_id):
    if request.user.role in ['admin', 'facility'] or request.user.is_superuser:
        target_class = get_object_or_404(Class, id=class_id)
    else:
        target_class = get_object_or_404(Class, id=class_id, teacher=request.user)
    
    if request.method == 'POST' and request.POST.get('action') == 'request_resignation':
        reason = request.POST.get('reason', '').strip()
        if reason:
            ClassResignation.objects.create(teacher=request.user, target_class=target_class, reason=reason)
            messages.success(request, f'Đã gửi yêu cầu xin thôi dạy lớp {target_class.class_code}.')
        else:
            messages.error(request, 'Vui lòng nhập rõ lý do xin thôi dạy!')
        return redirect(request.path)

    # TỰ ĐỘNG TÍNH TIẾN ĐỘ DỰA TRÊN THỜI GIAN THỰC TẾ
    today = timezone.now().date()
    calculated_completed = 0
    
    if target_class.start_date:
        for s in range(target_class.course.total_sessions):
            session_date = target_class.start_date + timedelta(weeks=s)
            if session_date <= today:
                calculated_completed += 1
            else:
                break
                
    if calculated_completed > target_class.completed_sessions:
        target_class.completed_sessions = min(calculated_completed, target_class.course.total_sessions)
        target_class.save()

    total = target_class.course.total_sessions
    completed = target_class.completed_sessions
    progress_percent = int((completed / total) * 100) if total > 0 else 0

    enrollments = Enrollment.objects.filter(enrolled_class=target_class).select_related('student', 'student__lead')

    return render(request, 'academic_teacher_class_info.html', {
        'target_class': target_class,
        'progress_percent': progress_percent,
        'enrollments': enrollments,
    })

@login_required(login_url='/login/')
def teacher_class_session_view(request, class_id):
    if request.user.role in ['admin', 'facility'] or request.user.is_superuser:
        target_class = get_object_or_404(Class, id=class_id)
    else:
        is_substitute = SessionAbsence.objects.filter(target_class_id=class_id, substitute_teacher=request.user, status='approved').exists()
        is_recorded = LessonContent.objects.filter(for_class_id=class_id, actual_teacher=request.user).exists()
        
        if not is_substitute and not is_recorded:
            target_class = get_object_or_404(Class, id=class_id, teacher=request.user)
        else:
            target_class = get_object_or_404(Class, id=class_id)
    
    if request.method == 'POST' and request.POST.get('action') == 'request_absence':
        absence_date = request.POST.get('absence_date')
        reason = request.POST.get('reason', '').strip()
        if absence_date and reason:
            SessionAbsence.objects.create(teacher=request.user, target_class=target_class, absence_date=absence_date, reason=reason)
            messages.success(request, f'Đã gửi đơn báo nghỉ lớp {target_class.class_code} (ngày {absence_date}).')
        else:
            messages.error(request, 'Vui lòng chọn ngày và nhập lý do nghỉ!')
        return redirect(f"{request.path}?date={absence_date}" if absence_date else request.path)

    date_str = request.GET.get('date')
    today = timezone.now().date()
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else today
    except ValueError:
        target_date = today

    can_edit = (target_date == today)
    attendances = Attendance.objects.filter(for_class=target_class, date=target_date)
    att_dict = {a.student_id: a for a in attendances}

    enrollments = Enrollment.objects.filter(enrolled_class=target_class, status='studying')
    student_data = []
    
    for enr in enrollments:
        att = att_dict.get(enr.student.id)
        student_data.append({
            'student': enr.student,
            'enrollment': enr,
            'status': att.status if att else 'absent',
            'note': att.note if att else ''
        })

    lesson_content = LessonContent.objects.filter(for_class=target_class, date=target_date).first()
    class_images = ClassImage.objects.filter(for_class=target_class, date=target_date)

    return render(request, 'academic_teacher_class_session.html', {
        'target_class': target_class, 
        'target_date': target_date,
        'student_data': student_data,
        'can_edit': can_edit,
        'today': today,
        'lesson_content': lesson_content,
        'class_images': class_images,
        'all_teachers': User.objects.filter(role='teacher', is_active=True)
    })


# ==============================================================================
# KHU VỰC 2: CÁC VIEW CỦA HỌC VỤ (OPERATOR)
# ==============================================================================

@login_required(login_url='/login/')
def student_list_view(request):
    if request.user.role == 'teacher':
        messages.error(request, 'LỖI PHÂN QUYỀN: Bạn không có quyền xem danh sách tổng!')
        return redirect('dashboard')

    search_query = request.GET.get('search', '').strip()
    class_filter = request.GET.get('class_id', '')
    status_filter = request.GET.get('status', '')

    students = Student.objects.all().order_by('-id')

    if search_query:
        students = students.filter(Q(full_name__icontains=search_query) | Q(student_code__icontains=search_query))

    if class_filter:
        try:
            target_class = Class.objects.get(id=class_filter)
            students = students.filter(id__in=target_class.students.values_list('id', flat=True))
        except Exception: pass

    today = timezone.now().date()
    day_map = {0: 'T2', 1: 'T3', 2: 'T4', 3: 'T5', 4: 'T6', 5: 'T7', 6: 'CN'}
    today_str = day_map[today.weekday()]

    if status_filter == 'has_class':
        students = students.filter(classes__day_of_week=today_str, classes__status='active').distinct()
    elif status_filter == 'present':
        students = students.filter(attendance__date=today, attendance__status='present').distinct()
    elif status_filter == 'absent':
        students = students.filter(classes__day_of_week=today_str, classes__status='active').exclude(attendance__date=today, attendance__status='present').distinct()

    paginator = Paginator(students, 15) 
    page_obj = paginator.get_page(request.GET.get('page'))

    current_student_ids = [s.id for s in page_obj]
    related_classes = Class.objects.filter(students__id__in=current_student_ids).distinct()
    today_attendances = dict(Attendance.objects.filter(student_id__in=current_student_ids, date=today).values_list('student_id', 'status'))

    for student in page_obj:
        student.my_classes = [c for c in related_classes if student in c.students.all()]
        student.has_class_today = any(c.day_of_week == today_str and c.status == 'active' for c in student.my_classes)
        student.today_status = today_attendances.get(student.id)

    return render(request, 'academic_student_list.html', {
        'page_obj': page_obj, 'search_query': search_query, 'class_filter': class_filter,
        'status_filter': status_filter, 'active_classes': Class.objects.filter(status='active'), 'today_str': today_str
    })


@login_required(login_url='/login/')
def student_360_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    enrollments = Enrollment.objects.filter(student=student)
    available_classes = Class.objects.filter(status__in=['active', 'pending']).exclude(students=student)
    today = timezone.now().date()
    
    day_map = {'T2': 0, 'T3': 1, 'T4': 2, 'T5': 3, 'T6': 4, 'T7': 5, 'CN': 6}

    class_data_list = []
    for enr in enrollments:
        cls = enr.enrolled_class
        raw_start = cls.start_date if cls.start_date else today
        
        target_weekday = day_map.get(cls.day_of_week, 0)
        days_shift = target_weekday - raw_start.weekday()
        start_date = raw_start + timedelta(days=days_shift)

        # LẤY DANH SÁCH CÁC NGÀY NGHỈ LỄ ĐỂ "NÉ" KHI TẠO LỊCH
        holidays = set(ClassHoliday.objects.filter(for_class=cls).values_list('holiday_date', flat=True))

        present_count, learned_count = 0, 0 
        modules_data = []

        reg = CourseRegistration.objects.filter(student=student, course=cls.course).first()
        
        class_start_mod = getattr(cls, 'starting_module', 1)
        student_start_mod = reg.starting_module if (reg and getattr(reg, 'starting_module', None)) else 1
        start_mod = max(class_start_mod, student_start_mod)

        sessions_per_mod = getattr(cls.course, 'sessions_per_module', 12)
        if sessions_per_mod <= 0: sessions_per_mod = 12
        
        modules_bought = max(1, enr.total_sessions // sessions_per_mod)
        
        end_mod = min(start_mod + modules_bought - 1, cls.course.total_modules)
        display_total_sessions = min(enr.total_sessions, cls.course.total_sessions)

        # THUẬT TOÁN TÍNH TOÁN NGÀY HỌC THỰC TẾ (TÍNH CẢ NGHỈ LỄ)
        current_date_pointer = start_date
        sessions_to_skip = (class_start_mod - 1) * sessions_per_mod
        
        # Tua nhanh ngày đến đúng học phần bắt đầu
        skipped = 0
        while skipped < sessions_to_skip:
            if current_date_pointer not in holidays:
                skipped += 1
            current_date_pointer += timedelta(weeks=1)

        for m in range(cls.course.total_modules):
            current_mod_no = m + 1
            
            if current_mod_no < start_mod or current_mod_no > end_mod:
                continue

            mod_history, mod_learned = [], 0
            for s in range(sessions_per_mod):
                absolute_session_no = m * sessions_per_mod + s + 1
                relative_session_no = s + 1 
                
                # Bỏ qua ngày lễ
                while current_date_pointer in holidays:
                    current_date_pointer += timedelta(weeks=1)
                
                session_date = current_date_pointer
                current_date_pointer += timedelta(weeks=1) # Tăng con trỏ cho buổi tiếp theo
                
                att_record = Attendance.objects.filter(student=student, for_class=cls, date=session_date).first()
                status = 'upcoming'
                
                if att_record: status = att_record.status
                elif session_date <= today and enr.status != 'reserved': status = 'absent' 

                if status == 'present': present_count += 1
                if session_date <= today and enr.status != 'reserved':
                    learned_count += 1
                    mod_learned += 1 

                lesson_info = LessonContent.objects.filter(for_class=cls, date=session_date).select_related('actual_teacher').first()
                
                teacher_name = "Chưa phân công"
                if lesson_info and lesson_info.actual_teacher:
                    teacher_name = lesson_info.actual_teacher.first_name or lesson_info.actual_teacher.username
                elif cls.teacher:
                    teacher_name = cls.teacher.first_name or cls.teacher.username

                mod_history.append({
                    'absolute_session_no': absolute_session_no, 
                    'session_no': relative_session_no,          
                    'date': session_date, 
                    'status': status,
                    'note': att_record.note if att_record else "",
                    'lesson_info': lesson_info,
                    'actual_teacher_name': teacher_name, 
                    'images': ClassImage.objects.filter(for_class=cls, date=session_date)
                })

            modules_data.append({
                'module_no': current_mod_no, 
                'name': f'Học phần {current_mod_no}', 
                'sessions': mod_history, 
                'is_active': False, 
                'mod_learned': mod_learned,
                'total_mod_sessions': sessions_per_mod
            })
        
        active_mod_set = False
        for mod in modules_data:
            if 0 < mod['mod_learned'] < mod['total_mod_sessions']:
                mod['is_active'] = True
                active_mod_set = True
                break
        
        if not active_mod_set:
            for mod in reversed(modules_data):
                if mod['mod_learned'] > 0:
                    mod['is_active'] = True
                    active_mod_set = True
                    break
                    
        if not active_mod_set and modules_data:
            if modules_data:
                modules_data[0]['is_active'] = True
        
        class_data_list.append({
            'enrollment': enr, 'class_obj': cls, 
            'total_sessions': display_total_sessions, 
            'present_count': present_count, 'learned_count': learned_count,
            'attendance_rate': int((present_count / learned_count) * 100) if learned_count > 0 else 0,
            'modules': modules_data,
        })

    return render(request, 'academic_student_360.html', {
        'student': student, 'class_data_list': class_data_list, 'available_classes': available_classes,
    })

@login_required(login_url='/login/')
def teacher_approvals_view(request):
    if request.user.role == 'teacher' and not request.user.is_superuser: return HttpResponseForbidden("Bạn không có quyền truy cập!")
    return render(request, 'academic_teacher_approvals.html', {
        'pending_absences': SessionAbsence.objects.filter(status='pending'),
        'pending_resignations': ClassResignation.objects.filter(status='pending'),
        'teachers': User.objects.filter(role='teacher', is_active=True),
    })


# ==============================================================================
# KHU VỰC 3: XỬ LÝ LÕI XẾP LỚP (REFACTORED VỚI COURSE REGISTRATION)
# ==============================================================================

@login_required(login_url='/login/')
def class_assignment_view(request):
    if request.user.role == 'teacher' and not request.user.is_superuser: 
        return HttpResponseForbidden("Bạn không có quyền truy cập!")
    
    waiting_registrations = CourseRegistration.objects.filter(status='waiting').select_related('student', 'student__lead', 'course')
    available_classes = Class.objects.filter(status__in=['active', 'pending']).select_related('course')
    
    for c in available_classes:
        if c.course and getattr(c.course, 'sessions_per_module', 0) > 0:
            modules_completed = getattr(c, 'completed_sessions', 0) // c.course.sessions_per_module
            c.current_module = getattr(c, 'starting_module', 1) + modules_completed
        else:
            c.current_module = getattr(c, 'starting_module', 1)

    perfect_match_regs = []
    waiting_regs = []

    for reg in waiting_registrations:
        student = reg.student
        
        age = student.lead.student_age if (student.lead and student.lead.student_age) else 0
        if age == 0: computed_grade_group = 'all'
        elif age < 6: computed_grade_group = 'mam_non'
        elif 6 <= age <= 8: computed_grade_group = '1-3'
        elif 9 <= age <= 11: computed_grade_group = '4-6'
        elif 12 <= age <= 14: computed_grade_group = '7-9'
        else: computed_grade_group = '10-12'

        raw_sched = student.lead.preferred_schedule if student.lead else ""
        pref_sched_norm = (raw_sched or "").replace(" ", "").lower()
        
        matching_classes = []
        for c in available_classes:
            course_match = c.course_id == reg.course_id
            grade_match = computed_grade_group == 'all' or c.course.grade_group in ['all', computed_grade_group]
            
            c_time_slot = c.time_slot or ""
            c_time_slot_display = c.get_time_slot_display() or ""
            class_sched_1 = f"{c.get_day_of_week_display()}({c_time_slot})".replace(" ", "").lower()
            class_sched_2 = f"{c.get_day_of_week_display()}({c_time_slot_display})".replace(" ", "").lower()
            
            sched_match = False
            if pref_sched_norm != "":
                sched_match = (class_sched_1 in pref_sched_norm) or (class_sched_2 in pref_sched_norm)
            
            if course_match and grade_match and (sched_match or pref_sched_norm == ""):
                matching_classes.append(c)
        
        reg.matching_classes = matching_classes
        reg.computed_grade_group = computed_grade_group
        reg.pref_sched = raw_sched
        
        if len(matching_classes) > 0:
            perfect_match_regs.append(reg)
        else:
            waiting_regs.append(reg)

    return render(request, 'academic_class_assignment.html', {
        'perfect_match_regs': perfect_match_regs, 
        'waiting_regs': waiting_regs,             
        'available_classes': available_classes, 
        'courses': Course.objects.all(),
    })

@csrf_exempt
@require_POST
def create_new_class_api(request):
    try:
        course_id = request.POST.get('course_id')
        day_of_week = request.POST.get('day_of_week')
        time_slot = request.POST.get('time_slot')
        reg_ids_str = request.POST.get('student_ids', '') 
        
        if not course_id or not day_of_week or not time_slot: 
            return JsonResponse({'status': 'error', 'message': 'Thiếu thông tin!'})
        
        course = Course.objects.get(id=course_id)
        new_class = Class.objects.create(
            course=course, 
            day_of_week=day_of_week, 
            time_slot=time_slot, 
            status='pending',
        )
        
        added_count = 0
        if reg_ids_str:
            reg_ids = [int(rid) for rid in reg_ids_str.split(',') if rid.strip()]
            if reg_ids:
                registrations = CourseRegistration.objects.filter(id__in=reg_ids, status='waiting')
                
                for reg in registrations: 
                    Enrollment.objects.create(
                        student=reg.student, 
                        enrolled_class=new_class, 
                        total_sessions=reg.remaining_sessions 
                    )
                    reg.status = 'studying'
                    reg.save()
                        
                added_count = registrations.count()
            
        return JsonResponse({'status': 'success', 'message': f'Đã mở thành công lớp {new_class.class_code} và ghép {added_count} học viên!'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
def assign_student_class_api(request):
    try:
        reg_id = request.POST.get('student_id') 
        target_class = Class.objects.get(id=request.POST.get('class_id'))
        
        registration = CourseRegistration.objects.get(id=reg_id, status='waiting')
        student = registration.student
        
        Enrollment.objects.get_or_create(
            student=student, 
            enrolled_class=target_class, 
            defaults={'total_sessions': registration.remaining_sessions}
        )
        
        registration.status = 'studying'
        registration.save()
            
        return JsonResponse({'status': 'success', 'message': f'Đã xếp {student.full_name} vào lớp {target_class.class_code}'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

# ==============================================================================
# KHU VỰC 4: CÁC API KHÁC
# ==============================================================================

@csrf_exempt
@require_POST
def process_teacher_request_api(request):
    try:
        req_type = request.POST.get('type')
        req_id = request.POST.get('id')
        action = request.POST.get('action')
        new_teacher_id = request.POST.get('new_teacher_id')
        
        if req_type == 'absence':
            obj = SessionAbsence.objects.get(id=req_id)
            if action == 'approve':
                obj.status = 'approved'
                if new_teacher_id:
                    new_teacher = User.objects.get(id=new_teacher_id)
                    obj.substitute_teacher = new_teacher
                    msg = f"Đã duyệt nghỉ và phân công {new_teacher.first_name} dạy thay!"
                    
                    LessonContent.objects.update_or_create(
                        for_class=obj.target_class,
                        date=obj.absence_date,
                        defaults={'actual_teacher': new_teacher}
                    )
                else:
                    msg = "Đã duyệt đơn xin nghỉ (Lớp trống)."
            else:
                obj.status = 'rejected'
                msg = "Đã từ chối đơn xin nghỉ!"
            obj.save()
            return JsonResponse({'status': 'success', 'message': msg})
            
        else: # resignation
            obj = ClassResignation.objects.get(id=req_id)
            if action == 'approve':
                obj.status = 'approved'
                obj.target_class.teacher = User.objects.get(id=new_teacher_id) if new_teacher_id else None
                obj.target_class.save()
                msg = "Đã duyệt đơn chuyển lớp vĩnh viễn!"
            else:
                obj.status = 'rejected'
                msg = "Đã từ chối đơn!"
            obj.save()
            return JsonResponse({'status': 'success', 'message': msg})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@login_required(login_url='/login/')
def toggle_attendance_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            target_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
            student_id, class_id, new_status = data.get('student_id'), data.get('class_id'), data.get('status')
            
            enr = Enrollment.objects.get(student_id=student_id, enrolled_class_id=class_id)
            if enr.remaining_sessions <= 0 and new_status == 'present':
                return JsonResponse({'status': 'error', 'message': 'Học viên đã HẾT PHÍ lớp này, không thể điểm danh!'})
            
            attendance, created = Attendance.objects.get_or_create(student_id=student_id, for_class_id=class_id, date=target_date, defaults={'status': new_status})
            if not created:
                attendance.status = new_status
                attendance.save()
            return JsonResponse({'status': 'success', 'message': 'Đã cập nhật điểm danh!'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
@login_required(login_url='/login/')
def save_student_note_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            attendance, created = Attendance.objects.get_or_create(student_id=data.get('student_id'), for_class_id=data.get('class_id'), date=datetime.strptime(data.get('date'), '%Y-%m-%d').date(), defaults={'status': 'present'})
            attendance.note = data.get('note')
            attendance.save()
            return JsonResponse({'status': 'success', 'message': 'Đã lưu nhận xét!'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
@login_required(login_url='/login/')
def teacher_quit_class_api(request):
    if request.method == 'POST':
        try:
            target_class = Class.objects.get(id=json.loads(request.body).get('class_id'), teacher=request.user)
            target_class.teacher = None
            target_class.save()
            return JsonResponse({'status': 'success', 'message': 'Đã gửi yêu cầu thôi dạy!'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
@require_POST
def upload_class_images_api(request):
    try:
        class_id, date_str, images = request.POST.get('class_id'), request.POST.get('date'), request.FILES.getlist('images')
        if not images: return JsonResponse({'status': 'error', 'message': 'Không có ảnh!'}, status=400)
        for img in images: ClassImage.objects.create(for_class_id=class_id, date=date_str, image=img)
        return JsonResponse({'status': 'success', 'message': f'Đã lưu thành công {len(images)} ảnh!'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required(login_url='/login/')
def save_lesson_content_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            actual_teacher_id = data.get('actual_teacher_id')
            if actual_teacher_id:
                teacher = User.objects.get(id=actual_teacher_id)
            else:
                teacher = request.user
                
            LessonContent.objects.update_or_create(
                for_class_id=data.get('class_id'), 
                date=datetime.strptime(data.get('date'), '%Y-%m-%d').date(), 
                defaults={
                    'content': data.get('content'),
                    'actual_teacher': teacher 
                }
            )
            return JsonResponse({'status': 'success', 'message': 'Đã lưu nội dung bài học!'})
        except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

# API ĐỔI GIÁO VIÊN DẠY THAY TRỰC TIẾP
@csrf_exempt
@require_POST
def assign_substitute_api(request):
    try:
        class_id = request.POST.get('class_id')
        date_str = request.POST.get('date')
        teacher_id = request.POST.get('teacher_id')
        
        target_class = Class.objects.get(id=class_id)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        sub_teacher = User.objects.get(id=teacher_id)
        
        # Ghi đè vào LessonContent luôn để hệ thống nhận diện đây là người dạy
        LessonContent.objects.update_or_create(
            for_class=target_class,
            date=target_date,
            defaults={'actual_teacher': sub_teacher}
        )
        return JsonResponse({'status': 'success', 'message': f'Đã đổi Giáo viên dạy thay thành {sub_teacher.first_name}!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

# API BÁO NGHỈ LỄ / LÙI LỊCH
@csrf_exempt
@require_POST
def add_class_holiday_api(request):
    try:
        class_id = request.POST.get('class_id')
        date_str = request.POST.get('date')
        reason = request.POST.get('reason', 'Nghỉ lễ')
        
        target_class = Class.objects.get(id=class_id)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        ClassHoliday.objects.get_or_create(
            for_class=target_class,
            holiday_date=target_date,
            defaults={'reason': reason}
        )
        return JsonResponse({'status': 'success', 'message': f'Đã báo nghỉ lớp {target_class.class_code}. Lịch học sẽ tự động lùi 1 tuần!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required(login_url='/login/')
def class_management_view(request):
    if request.user.role == 'teacher' and not request.user.is_superuser: 
        return HttpResponseForbidden("Bạn không có quyền truy cập!")
    
    search_query, status_filter = request.GET.get('search', '').strip(), request.GET.get('status', 'all')
    classes = Class.objects.filter(Q(class_code__icontains=search_query) | Q(course__name__icontains=search_query)) if search_query else Class.objects.all().order_by('-id')
    
    if status_filter != 'all': 
        classes = classes.filter(status=status_filter)
        
    for c in classes:
        if c.course and getattr(c.course, 'sessions_per_module', 0) > 0:
            modules_completed = getattr(c, 'completed_sessions', 0) // c.course.sessions_per_module
            c.current_module = getattr(c, 'starting_module', 1) + modules_completed
        else:
            c.current_module = getattr(c, 'starting_module', 1)

    return render(request, 'academic_class_management.html', {
        'classes': classes, 
        'teachers': User.objects.filter(role='teacher', is_active=True), 
        'search_query': search_query, 
        'status_filter': status_filter
    })

@csrf_exempt
@require_POST
def activate_class_api(request):
    try:
        class_id, teacher_id, start_date_str, start_module = request.POST.get('class_id'), request.POST.get('teacher_id'), request.POST.get('start_date'), int(request.POST.get('start_module', 1))
        if not teacher_id or not start_date_str: return JsonResponse({'status': 'error', 'message': 'Thiếu thông tin!'})
        
        target_class = Class.objects.get(id=class_id)
        target_class.teacher = User.objects.get(id=teacher_id)
        target_class.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        target_class.status = 'active' 
        
        target_class.starting_module = start_module
        if start_module > 1 and target_class.course:
            target_class.completed_sessions = (start_module - 1) * target_class.course.sessions_per_module
        else:
            target_class.completed_sessions = 0
            
        target_class.save()
        return JsonResponse({'status': 'success', 'message': f'Đã khai giảng lớp {target_class.class_code}!'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
def update_class_info_api(request):
    try:
        target_class = Class.objects.get(id=request.POST.get('class_id'))
        target_class.status = request.POST.get('status')
        target_class.day_of_week = request.POST.get('day_of_week')
        target_class.time_slot = request.POST.get('time_slot')
        
        teacher_id = request.POST.get('teacher_id')
        target_class.teacher = User.objects.get(id=teacher_id) if teacher_id else None
        
        starting_module_str = request.POST.get('starting_module')
        current_module_str = request.POST.get('current_module')
        
        if starting_module_str and starting_module_str.isdigit():
            target_class.starting_module = int(starting_module_str)
            
        if current_module_str and current_module_str.isdigit() and target_class.course:
            current_mod = int(current_module_str)
            target_class.completed_sessions = (current_mod - 1) * target_class.course.sessions_per_module
                
        target_class.save()
        return JsonResponse({'status': 'success', 'message': f'Cập nhật lớp {target_class.class_code} thành công!'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})
    
@csrf_exempt
@require_POST
def transfer_student_api(request):
    try:
        student, old_class, new_class = Student.objects.get(id=request.POST.get('student_id')), Class.objects.get(id=request.POST.get('old_class_id')), Class.objects.get(id=request.POST.get('new_class_id'))
        old_enr = Enrollment.objects.get(student=student, enrolled_class=old_class)
        leftover_sessions = old_enr.remaining_sessions
        old_enr.status = 'dropped'
        old_enr.save()
        Enrollment.objects.create(student=student, enrolled_class=new_class, total_sessions=leftover_sessions)
        return JsonResponse({'status': 'success', 'message': f'Đã chuyển học viên {student.full_name} và bảo toàn Ví học phí!'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
def reserve_student_api(request):
    try:
        enr = Enrollment.objects.get(student_id=request.POST.get('student_id'), enrolled_class_id=request.POST.get('class_id'))
        enr.sessions_consumed_before_reserve = enr.consumed_sessions
        enr.status, enr.reserve_date = 'reserved', timezone.now().date()
        enr.save()
        return JsonResponse({'status': 'success', 'message': 'Đã ĐÓNG BĂNG ví học phí thành công!'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

# ==============================================================================
# KHU VỰC 5: QUẢN LÝ BUỔI HỌC TỔNG QUAN (CHO ADMIN/OPERATOR)
# ==============================================================================

@login_required(login_url='/login/')
def session_management_view(request):
    if request.user.role == 'teacher' and not request.user.is_superuser: 
        return HttpResponseForbidden("Bạn không có quyền truy cập!")

    # Mặc định lấy ngày hôm nay
    today = timezone.now().date()
    filter_date_str = request.GET.get('date')
    
    try:
        target_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() if filter_date_str else today
    except ValueError:
        target_date = today

    day_map = {0: 'T2', 1: 'T3', 2: 'T4', 3: 'T5', 4: 'T6', 5: 'T7', 6: 'CN'}
    target_weekday_str = day_map[target_date.weekday()]

    # Kiểm tra xem ngày này có lớp nào khai báo nghỉ không
    holiday_class_ids = ClassHoliday.objects.filter(holiday_date=target_date).values_list('for_class_id', flat=True)

    # Lấy các lớp ACTIVE có lịch học đúng vào thứ của target_date và đã khai giảng trước hoặc bằng target_date
    active_classes = Class.objects.filter(
        status='active', 
        day_of_week=target_weekday_str,
        start_date__lte=target_date
    ).select_related('course', 'teacher')

    session_list = []

    for cls in active_classes:
        # Nếu lớp này đã khai báo nghỉ lễ trong ngày này thì đánh dấu
        is_holiday = cls.id in holiday_class_ids
        
        lesson_info = LessonContent.objects.filter(for_class=cls, date=target_date).select_related('actual_teacher').first()
        
        teacher_name = "Chưa phân công"
        is_substitute = False
        
        if lesson_info and lesson_info.actual_teacher:
            teacher_name = lesson_info.actual_teacher.first_name or lesson_info.actual_teacher.username
            if cls.teacher and lesson_info.actual_teacher != cls.teacher:
                is_substitute = True
        elif cls.teacher:
            teacher_name = cls.teacher.first_name or cls.teacher.username

        image_count = ClassImage.objects.filter(for_class=cls, date=target_date).count()

        total_students = cls.students.count()
        attendances = Attendance.objects.filter(for_class=cls, date=target_date)
        present_count = attendances.filter(status='present').count()
        note_count = attendances.exclude(note__isnull=True).exclude(note__exact='').count()

        if is_holiday:
            status = 'holiday'
        elif lesson_info and present_count > 0:
            status = 'completed'
        elif present_count > 0:
            status = 'missing_content'
        else:
            status = 'pending'

        session_list.append({
            'class_obj': cls,
            'teacher_name': teacher_name,
            'is_substitute': is_substitute,
            'lesson_info': lesson_info,
            'image_count': image_count,
            'total_students': total_students,
            'present_count': present_count,
            'note_count': note_count,
            'status': status
        })
        
    # Gửi cả danh sách Giáo viên để chọn đổi GV trực tiếp
    all_teachers = User.objects.filter(role='teacher', is_active=True)

    return render(request, 'academic_session_management.html', {
        'session_list': session_list,
        'target_date': target_date,
        'today': today,
        'all_teachers': all_teachers
    })