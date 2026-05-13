import json
import csv
from datetime import date, datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Count
from django.utils.timezone import localtime, now
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model

from crm.models import Lead
from academic.models import Class, Student, Course, CourseRegistration 

User = get_user_model()

@login_required(login_url='/login/')
def kanban_view(request):
    if request.user.role == 'teacher':
        messages.error(request, 'LỖI PHÂN QUYỀN: Giáo viên không được phép truy cập Phễu tuyển sinh!')
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        current_path = request.get_full_path()
        
        if action == 'import_leads':
            if request.user.role not in ['admin'] and not request.user.is_superuser:
                messages.error(request, 'Bạn không có quyền Import dữ liệu!')
                return redirect(current_path)

            import_file = request.FILES.get('import_file')
            if not import_file:
                messages.error(request, 'Vui lòng chọn file để tải lên!')
                return redirect(current_path)

            if import_file.name.endswith('.csv'):
                try:
                    decoded_file = import_file.read().decode('utf-8-sig', errors='replace').splitlines()
                    reader = csv.reader(decoded_file)
                    
                    sales_users = list(User.objects.filter(role='sales', is_active=True))
                    if not sales_users:
                        messages.error(request, 'LỖI: Chưa có tài khoản Sales nào đang hoạt động để chia Data!')
                        return redirect(current_path)

                    success_count, duplicate_count, assign_idx = 0, 0, 0
                    next(reader, None) 
                    
                    for row in reader:
                        if len(row) >= 2:
                            parent_name = row[0].strip()
                            phone = row[1].strip().replace(' ', '')
                            
                            if parent_name and phone:
                                if not Lead.objects.filter(phone=phone).exists():
                                    lead_source = row[2].strip().lower() if len(row) >= 3 else 'other'
                                    assigned_user = sales_users[assign_idx % len(sales_users)]
                                    
                                    Lead.objects.create(
                                        parent_name=parent_name, phone=phone,
                                        lead_source=lead_source if lead_source in dict(Lead.SOURCE_CHOICES).keys() else 'other',
                                        status='new', assigned_to=assigned_user
                                    )
                                    success_count += 1
                                    assign_idx += 1 
                                else:
                                    duplicate_count += 1

                    messages.success(request, f'✅ Đã Import và chia đều {success_count} khách hàng. Bỏ qua {duplicate_count} khách bị trùng SĐT.')
                except Exception as e:
                    messages.error(request, f'Lỗi xử lý file: {str(e)}')
            else:
                messages.error(request, '⚠️ Hệ thống hiện chỉ hỗ trợ file định dạng CSV.')
            return redirect(current_path)

        elif action == 'add_lead':
            try:
                new_lead = Lead.objects.create(
                    parent_name=request.POST.get('parent_name'), phone=request.POST.get('phone'),
                    lead_source=request.POST.get('lead_source', 'other'), 
                    student_name=request.POST.get('student_name', '') or '', 
                    student_age=request.POST.get('student_age', 0) or 0, 
                    interested_course=request.POST.get('interested_course'),
                    preferred_schedule=request.POST.get('preferred_schedule', ''),
                    notes=request.POST.get('notes', ''), status='new', assigned_to=request.user 
                )
                
                if request.POST.get('save_action') == 'continue':
                    request.session['reopen_lead_id'] = new_lead.id
                    messages.success(request, 'Đã lưu khách mới! Vui lòng cập nhật chi tiết chăm sóc.')
                else:
                    messages.success(request, 'Đã thêm thành công một nhu cầu Khách hàng vào Phễu.')
            except Exception as e:
                messages.error(request, f'Lỗi hệ thống: {str(e)}')
            return redirect(current_path)

        elif action == 'convert_lead':
            lead_id = request.POST.get('lead_id')
            preferred_schedule = request.POST.get('preferred_schedule')
            
            if not preferred_schedule:
                messages.error(request, 'LỖI: Phải chốt lịch học mong muốn để bàn giao Học vụ!')
                return redirect(current_path)
            
            modules_bought = int(request.POST.get('modules_bought', 1) or 1)
            starting_module = int(request.POST.get('starting_module', 1) or 1)
            discount_percent = int(request.POST.get('discount_percent', 0) or 0)
            
            tuition_fee_str = request.POST.get('tuition_fee', '0').replace(',', '')
            tuition_fee = int(tuition_fee_str) if tuition_fee_str.isdigit() else 0
            
            try:
                lead = Lead.objects.get(id=lead_id)
                
                total_sessions_calculated = 0
                course_obj = None
                if lead.interested_course:
                    course_obj = Course.objects.filter(name__icontains=lead.interested_course).first()
                    if course_obj:
                        total_sessions_calculated = modules_bought * course_obj.sessions_per_module
                
                if total_sessions_calculated == 0:
                    total_sessions_calculated = modules_bought * 12

                current_time = localtime(now()).strftime("%H:%M - %d/%m/%Y")
                author = request.user.first_name or request.user.username 
                formatted_money = "{:,}".format(tuition_fee)
                
                won_note = f"[{current_time}] {author}: 🎉 Đã chốt {modules_bought} Học phần (Học từ HP {starting_module}). Thu {formatted_money} VNĐ.\n"
                
                lead.status = 'won'
                lead.modules_bought = modules_bought
                lead.starting_module = starting_module 
                lead.discount_percent = discount_percent
                lead.tuition_fee = tuition_fee
                lead.preferred_schedule = preferred_schedule 
                lead.notes = won_note + (lead.notes or "") 
                lead.save()
                
                # =========================================================
                # THUẬT TOÁN MỚI: TẠO 1 HỌC VIÊN CHUẨN + TẠO PHIẾU ĐĂNG KÝ (LOGIC 4 TRẠNG THÁI)
                # =========================================================
                student_name_to_check = lead.student_name or f"Con phụ huynh {lead.parent_name}"
                
                # 1. Tìm xem Bé này đã có Mã Học Viên chưa (Dựa vào SĐT + Tên)
                student, created = Student.objects.get_or_create(
                    lead__phone=lead.phone, 
                    full_name__iexact=student_name_to_check,
                    defaults={
                        'lead': lead,
                        'full_name': student_name_to_check,
                    }
                )
                
                # 2. Tạo một Phiếu đăng ký môn (CourseRegistration) cho bé
                if course_obj:
                    # Kiểm tra xem bé đã có phiếu của môn này chưa
                    existing_reg = CourseRegistration.objects.filter(student=student, course=course_obj).first()
                    
                    if existing_reg:
                        # Nếu có rồi -> Mua thêm -> Cộng dồn số buổi
                        existing_reg.total_sessions += total_sessions_calculated
                        existing_reg.remaining_sessions += total_sessions_calculated
                        existing_reg.starting_module = starting_module
                        
                        # CẬP NHẬT TRẠNG THÁI CHUẨN: Đẩy bé về trạng thái "Chờ lớp"
                        existing_reg.status = 'waiting'
                        existing_reg.save()
                    else:
                        # Nếu chưa có -> Tạo phiếu học môn mới, trạng thái mặc định là "waiting"
                        CourseRegistration.objects.create(
                            student=student,
                            course=course_obj,
                            total_sessions=total_sessions_calculated,
                            remaining_sessions=total_sessions_calculated,
                            starting_module=starting_module,
                            status='waiting' # <-- SỬA LỖI: Trạng thái chuẩn
                        )
                # =========================================================
                
                messages.success(request, f'🎉 CHỐT DEAL THÀNH CÔNG! Đã thu {formatted_money} VNĐ và đẩy sang cho Học vụ.')
            except Exception as e:
                messages.error(request, f'Lỗi chốt deal: {str(e)}')
            return redirect(current_path)

        elif action == 'add_note':
            lead_id = request.POST.get('lead_id')
            new_note = request.POST.get('new_note')
            follow_up_date = request.POST.get('follow_up_date')
            
            if lead_id and new_note:
                try:
                    lead = Lead.objects.get(id=lead_id)
                    current_time = localtime(now()).strftime("%H:%M - %d/%m/%Y")
                    author = request.user.first_name or request.user.username 
                    formatted_note = f"[{current_time}] {author}: {new_note}\n"
                    
                    if follow_up_date:
                        date_obj = datetime.strptime(follow_up_date, '%Y-%m-%d')
                        formatted_note += f"--> ⏰ Lịch hẹn tiếp theo: {date_obj.strftime('%d/%m/%Y')}\n"
                        if hasattr(lead, 'follow_up_date'):
                            lead.follow_up_date = date_obj
                    
                    lead.notes = formatted_note + "\n" + (lead.notes or "")
                    lead.save()
                    
                    request.session['reopen_lead_id'] = lead.id
                    messages.success(request, 'Đã cập nhật nhật ký chăm sóc!')
                except Exception as e:
                    messages.error(request, f'Lỗi: {str(e)}')
            return redirect(current_path)
        
        elif action == 'update_lead':
            lead_id = request.POST.get('lead_id')
            try:
                lead = Lead.objects.get(id=lead_id)
                lead.student_name = request.POST.get('student_name') or lead.student_name
                age_input = request.POST.get('student_age')
                if age_input:
                    lead.student_age = int(age_input)
                lead.interested_course = request.POST.get('interested_course') or lead.interested_course
                lead.preferred_schedule = request.POST.get('preferred_schedule') or lead.preferred_schedule
                lead.save()
                
                request.session['reopen_lead_id'] = lead.id
                messages.success(request, f'Đã cập nhật thông tin bổ sung cho hồ sơ của phụ huynh {lead.parent_name}.')
            except Exception as e:
                messages.error(request, f'Lỗi hệ thống: {str(e)}')
            return redirect(current_path)

        elif action == 'assign_lead':
            lead_id = request.POST.get('lead_id')
            assigned_user_id = request.POST.get('assigned_user_id')
            
            if lead_id:
                try:
                    lead = Lead.objects.get(id=lead_id)
                    current_time = localtime(now()).strftime("%H:%M - %d/%m/%Y")
                    actor = request.user.first_name or request.user.username
                    old_assignee = lead.assigned_to.first_name if lead.assigned_to else "Chưa phân bổ"

                    if assigned_user_id:
                        user_obj = User.objects.get(id=assigned_user_id)
                        lead.assigned_to = user_obj
                        new_assignee = user_obj.first_name or user_obj.username
                        msg_text = f'Đã bàn giao khách hàng {lead.parent_name} cho {new_assignee}!'
                        transfer_note = f"[{current_time}] {actor}: 🔄 Đã chuyển phụ trách từ [{old_assignee}] sang [{new_assignee}].\n"
                        lead.notes = transfer_note + (lead.notes or "")
                    else:
                        lead.assigned_to = request.user
                        msg_text = f'Bạn đã nhận chăm sóc khách hàng {lead.parent_name}!'
                        transfer_note = f"[{current_time}] {actor}: ✋ Đã tự nhận thẻ chăm sóc.\n"
                        lead.notes = transfer_note + (lead.notes or "")
                    
                    lead.save()
                    request.session['reopen_lead_id'] = lead.id
                    messages.success(request, msg_text)
                except Exception as e:
                    messages.error(request, f'Lỗi: {str(e)}')
            return redirect(current_path)

    # --- KHU VỰC GET VÀ RENDER GIAO DIỆN GIỮ NGUYÊN ---
    today_date = date.today()
    current_month_str = f"{today_date.month}-{today_date.year}"
    filter_month = request.GET.get('month', current_month_str) 
    search_query = request.GET.get('search', '').strip()
    
    default_assignee = 'my_leads' if request.user.role == 'sales' else 'all'
    assignee_filter = request.GET.get('assignee', default_assignee)

    base_query = Lead.objects.all()

    if assignee_filter == 'my_leads':
        base_query = base_query.filter(assigned_to=request.user)

    if search_query:
        base_query = base_query.filter(
            Q(parent_name__icontains=search_query) | 
            Q(phone__icontains=search_query) |
            Q(student_name__icontains=search_query)
        )

    if filter_month != 'all':
        try:
            m, y = map(int, filter_month.split('-'))
            base_query = base_query.filter(updated_at__month=m, updated_at__year=y)
        except:
            pass

    def get_source_breakdown(qs):
        source_dict = dict(Lead.SOURCE_CHOICES)
        qs_counts = qs.order_by().values('lead_source').annotate(count=Count('id'))
        return [{'name': source_dict.get(item['lead_source'], 'Khác'), 'count': item['count']} for item in qs_counts]

    leads_new = base_query.filter(status='new').order_by('-updated_at')
    leads_consulting = base_query.filter(status='consulting').order_by('-updated_at')
    leads_trial = base_query.filter(status='trial').order_by('-updated_at')
    leads_won = base_query.filter(status='won').order_by('-updated_at')
    leads_lost = base_query.filter(status='lost').order_by('-updated_at')

    kanban_columns = [
        {'id': 'new', 'title': 'Khách Mới', 'color': '#0dcaf0', 'leads': leads_new, 'sources': get_source_breakdown(leads_new)},
        {'id': 'consulting', 'title': 'Tư Vấn', 'color': '#ffc107', 'leads': leads_consulting, 'sources': get_source_breakdown(leads_consulting)},
        {'id': 'trial', 'title': 'Học Thử', 'color': '#fd7e14', 'leads': leads_trial, 'sources': get_source_breakdown(leads_trial)},
        {'id': 'won', 'title': 'Đã Chốt', 'color': '#198754', 'leads': leads_won, 'sources': get_source_breakdown(leads_won)},
        {'id': 'lost', 'title': 'Từ Chối', 'color': '#6c757d', 'leads': leads_lost, 'sources': get_source_breakdown(leads_lost)},
    ]

    all_leads = base_query.order_by('-updated_at')
    active_classes = Class.objects.filter(status='active')
    courses = Course.objects.all()
    sales_team = User.objects.filter(role__in=['sales', 'admin']).order_by('first_name')
    
    all_schedules = [
        "Thứ 2 (Sáng: 09h00 - 10h30)", "Thứ 2 (Sáng: 10h30 - 12h00)", "Thứ 2 (Chiều: 14h00 - 15h30)", "Thứ 2 (Chiều: 15h30 - 17h00)", "Thứ 2 (Tối: 18h00 - 19h30)", "Thứ 2 (Tối: 19h30 - 21h00)",
        "Thứ 3 (Sáng: 09h00 - 10h30)", "Thứ 3 (Sáng: 10h30 - 12h00)", "Thứ 3 (Chiều: 14h00 - 15h30)", "Thứ 3 (Chiều: 15h30 - 17h00)", "Thứ 3 (Tối: 18h00 - 19h30)", "Thứ 3 (Tối: 19h30 - 21h00)",
        "Thứ 4 (Sáng: 09h00 - 10h30)", "Thứ 4 (Sáng: 10h30 - 12h00)", "Thứ 4 (Chiều: 14h00 - 15h30)", "Thứ 4 (Chiều: 15h30 - 17h00)", "Thứ 4 (Tối: 18h00 - 19h30)", "Thứ 4 (Tối: 19h30 - 21h00)",
        "Thứ 5 (Sáng: 09h00 - 10h30)", "Thứ 5 (Sáng: 10h30 - 12h00)", "Thứ 5 (Chiều: 14h00 - 15h30)", "Thứ 5 (Chiều: 15h30 - 17h00)", "Thứ 5 (Tối: 18h00 - 19h30)", "Thứ 5 (Tối: 19h30 - 21h00)",
        "Thứ 6 (Sáng: 09h00 - 10h30)", "Thứ 6 (Sáng: 10h30 - 12h00)", "Thứ 6 (Chiều: 14h00 - 15h30)", "Thứ 6 (Chiều: 15h30 - 17h00)", "Thứ 6 (Tối: 18h00 - 19h30)", "Thứ 6 (Tối: 19h30 - 21h00)",
        "Thứ 7 (Sáng: 09h00 - 10h30)", "Thứ 7 (Sáng: 10h30 - 12h00)", "Thứ 7 (Chiều: 14h00 - 15h30)", "Thứ 7 (Chiều: 15h30 - 17h00)", "Thứ 7 (Tối: 18h00 - 19h30)", "Thứ 7 (Tối: 19h30 - 21h00)",
        "Chủ nhật (Sáng: 09h00 - 10h30)", "Chủ nhật (Sáng: 10h30 - 12h00)", "Chủ nhật (Chiều: 14h00 - 15h30)", "Chủ nhật (Chiều: 15h30 - 17h00)", "Chủ nhật (Tối: 18h00 - 19h30)", "Chủ nhật (Tối: 19h30 - 21h00)"
    ]
    
    month_choices = []
    for i in range(6):
        m = today_date.month - i
        y = today_date.year
        if m <= 0:
            m += 12
            y -= 1
        month_choices.append({'value': f"{m}-{y}", 'label': f"Tháng {m:02d}/{y}"})
    
    reopen_lead_id = request.session.pop('reopen_lead_id', None)
    
    return render(request, 'crm_kanban.html', {
        'all_leads': all_leads,  
        'kanban_columns': kanban_columns,
        'active_classes': active_classes,
        'search_query': search_query,
        'filter_month': filter_month,
        'assignee_filter': assignee_filter, 
        'month_choices': month_choices,
        'courses': courses,
        'all_schedules': all_schedules,
        'sales_team': sales_team, 
        'reopen_lead_id': reopen_lead_id 
    })

@csrf_exempt
@login_required(login_url='/login/')
def update_lead_status_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lead = Lead.objects.get(id=data.get('lead_id'))
            new_status = data.get('new_status')
            
            if lead.status == 'new' and new_status == 'consulting' and not lead.assigned_to:
                lead.assigned_to = request.user
            
            lead.status = new_status
            lead.save()
            return JsonResponse({'status': 'success', 'message': 'Đã cập nhật phễu!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required(login_url='/login/')
def get_available_schedules(request):
    all_schedules = [
        "Thứ 2 (Sáng: 09h00 - 10h30)", "Thứ 2 (Sáng: 10h30 - 12h00)", "Thứ 2 (Chiều: 14h00 - 15h30)", "Thứ 2 (Chiều: 15h30 - 17h00)", "Thứ 2 (Tối: 18h00 - 19h30)", "Thứ 2 (Tối: 19h30 - 21h00)",
        "Thứ 3 (Sáng: 09h00 - 10h30)", "Thứ 3 (Sáng: 10h30 - 12h00)", "Thứ 3 (Chiều: 14h00 - 15h30)", "Thứ 3 (Chiều: 15h30 - 17h00)", "Thứ 3 (Tối: 18h00 - 19h30)", "Thứ 3 (Tối: 19h30 - 21h00)",
        "Thứ 4 (Sáng: 09h00 - 10h30)", "Thứ 4 (Sáng: 10h30 - 12h00)", "Thứ 4 (Chiều: 14h00 - 15h30)", "Thứ 4 (Chiều: 15h30 - 17h00)", "Thứ 4 (Tối: 18h00 - 19h30)", "Thứ 4 (Tối: 19h30 - 21h00)",
        "Thứ 5 (Sáng: 09h00 - 10h30)", "Thứ 5 (Sáng: 10h30 - 12h00)", "Thứ 5 (Chiều: 14h00 - 15h30)", "Thứ 5 (Chiều: 15h30 - 17h00)", "Thứ 5 (Tối: 18h00 - 19h30)", "Thứ 5 (Tối: 19h30 - 21h00)",
        "Thứ 6 (Sáng: 09h00 - 10h30)", "Thứ 6 (Sáng: 10h30 - 12h00)", "Thứ 6 (Chiều: 14h00 - 15h30)", "Thứ 6 (Chiều: 15h30 - 17h00)", "Thứ 6 (Tối: 18h00 - 19h30)", "Thứ 6 (Tối: 19h30 - 21h00)",
        "Thứ 7 (Sáng: 09h00 - 10h30)", "Thứ 7 (Sáng: 10h30 - 12h00)", "Thứ 7 (Chiều: 14h00 - 15h30)", "Thứ 7 (Chiều: 15h30 - 17h00)", "Thứ 7 (Tối: 18h00 - 19h30)", "Thứ 7 (Tối: 19h30 - 21h00)",
        "Chủ nhật (Sáng: 09h00 - 10h30)", "Chủ nhật (Sáng: 10h30 - 12h00)", "Chủ nhật (Chiều: 14h00 - 15h30)", "Chủ nhật (Chiều: 15h30 - 17h00)", "Chủ nhật (Tối: 18h00 - 19h30)", "Chủ nhật (Tối: 19h30 - 21h00)"
    ]
    schedules = [{'value': s, 'label': s} for s in all_schedules]
    return JsonResponse({'status': 'success', 'data': schedules})

@login_required(login_url='/login/')
def get_course_details(request):
    course_name = request.GET.get('course_name')
    if not course_name:
        return JsonResponse({'status': 'error', 'message': 'Thiếu tên khóa học'})

    course = Course.objects.filter(name__icontains=course_name).first()
    if course:
        return JsonResponse({
            'status': 'success',
            'sessions_per_module': course.sessions_per_module,
            'price_per_module': course.price_per_module
        })
    return JsonResponse({'status': 'error', 'message': 'Không tìm thấy khóa học'})