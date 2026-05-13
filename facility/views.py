import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from facility.models import Device, BorrowLog
from academic.models import Class

# ==========================================
# 1. GIAO DIỆN QUÉT MÃ QR (SMART LAB)
# ==========================================
@login_required(login_url='/login/')
def qr_scanner_view(request):
    active_classes = Class.objects.filter(teacher=request.user, status='active')
    my_borrowed_devices = BorrowLog.objects.filter(borrower=request.user, status='borrowed')
    
    return render(request, 'facility_qr_scanner.html', {
        'active_classes': active_classes,
        'my_borrowed_devices': my_borrowed_devices
    })

# ==========================================
# 2. API XỬ LÝ QUÉT MÃ QR TỪ CAMERA ĐIỆN THOẠI
# ==========================================
@csrf_exempt
@login_required(login_url='/login/')
def process_qr_scan(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_code = data.get('qr_code')
            class_id = data.get('class_id')
            note = data.get('note', '').strip()
            
            device = Device.objects.filter(device_code=qr_code).first()
            if not device:
                return JsonResponse({'status': 'error', 'message': 'Mã thiết bị không tồn tại!'})
            
            # MƯỢN ĐỒ
            if device.status == 'ready':
                if not class_id:
                    return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn Lớp học để mượn!'})
                
                target_class = Class.objects.get(id=class_id)
                BorrowLog.objects.create(
                    device=device, borrower=request.user, for_class=target_class, status='borrowed', note=note
                )
                device.status = 'borrowed'
                device.save()
                return JsonResponse({'status': 'success', 'message': f'Đã MƯỢN: {device.name}'})
            
            # TRẢ ĐỒ
            elif device.status == 'borrowed':
                active_log = BorrowLog.objects.filter(device=device, status='borrowed', borrower=request.user).first()
                if active_log:
                    active_log.status = 'returned'
                    active_log.return_time = timezone.now()
                    active_log.note = note
                    active_log.save()
                    
                    if note:
                        device.status = 'maintenance'
                        msg = f'Đã TRẢ & BÁO LỖI: {device.name}'
                    else:
                        device.status = 'ready'
                        msg = f'Đã TRẢ TỐT: {device.name}'
                        
                    device.save()
                    return JsonResponse({'status': 'success', 'message': msg})
                else:
                    return JsonResponse({'status': 'error', 'message': 'Thiết bị này do người khác mượn, bạn không thể trả thay!'})
                    
            return JsonResponse({'status': 'error', 'message': f'Thiết bị đang: {device.get_status_display()}'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ==========================================
# 3. GIAO DIỆN LỊCH SỬ MƯỢN TRẢ CỦA GIÁO VIÊN/HỌC VỤ
# ==========================================
@login_required(login_url='/login/')
def teacher_history_view(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')

    # PHÂN QUYỀN HIỂN THỊ DỮ LIỆU
    if request.user.role in ['facility', 'admin'] or request.user.is_superuser:
        logs = BorrowLog.objects.all().order_by('-borrow_time')
    else:
        logs = BorrowLog.objects.filter(borrower=request.user).order_by('-borrow_time')

    suggestions = list(set(
        list(logs.values_list('device__name', flat=True)) + 
        list(logs.values_list('device__device_code', flat=True))
    ))

    if status_filter in ['borrowed', 'returned']:
        logs = logs.filter(status=status_filter)

    if date_filter:
        logs = logs.filter(borrow_time__date=date_filter)

    if search_query:
        logs = logs.filter(
            Q(device__name__icontains=search_query) |
            Q(device__device_code__icontains=search_query) |
            Q(for_class__class_code__icontains=search_query) |
            Q(borrower__first_name__icontains=search_query) |
            Q(borrower__username__icontains=search_query)
        )

    paginator = Paginator(logs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'facility_history.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'suggestions': suggestions,
    })


# ==========================================
# 4. API XỬ LÝ MƯỢN TRẢ BẰNG TAY (NHẬP MÃ)
# ==========================================
@csrf_exempt
@login_required(login_url='/login/')
def manual_device_action_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            device_code = data.get('device_code')
            class_id = data.get('class_id')
            device = Device.objects.filter(device_code=device_code).first()
            if not device: return JsonResponse({'status': 'error', 'message': 'Mã thiết bị không tồn tại!'})
            
            if device.status == 'ready':
                if not class_id: return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn lớp!'})
                target_class = Class.objects.get(id=class_id)
                BorrowLog.objects.create(device=device, borrower=request.user, for_class=target_class, status='borrowed')
                device.status = 'borrowed'
                device.save()
                return JsonResponse({'status': 'success', 'message': f'Đã MƯỢN: {device.name}'})
            
            elif device.status == 'borrowed':
                active_log = BorrowLog.objects.filter(device=device, status='borrowed', borrower=request.user).first()
                if active_log:
                    active_log.status = 'returned'
                    active_log.return_time = timezone.now()
                    active_log.save()
                    device.status = 'ready'
                    device.save()
                    return JsonResponse({'status': 'success', 'message': f'Đã TRẢ: {device.name}'})
                else: return JsonResponse({'status': 'error', 'message': 'Người khác đang mượn!'})
            return JsonResponse({'status': 'error', 'message': f'Đang: {device.get_status_display()}'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ==================================================================
# 5. [MỚI THÊM] KHU VỰC QUẢN LÝ KHO CHO NHÂN VIÊN VẬN HÀNH (FACILITY)
# ==================================================================

@login_required(login_url='/login/')
def facility_device_management_view(request):
    if request.user.role not in ['facility', 'admin'] and not request.user.is_superuser:
        return HttpResponseForbidden("Bạn không có quyền truy cập Quản lý Kho!")

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')

    devices = Device.objects.all().order_by('-id')

    if search_query:
        devices = devices.filter(
            Q(device_code__icontains=search_query) | 
            Q(name__icontains=search_query)
        )

    if status_filter != 'all':
        devices = devices.filter(status=status_filter)

    stats = {
        'total': Device.objects.count(),
        'ready': Device.objects.filter(status='ready').count(),
        'borrowed': Device.objects.filter(status='borrowed').count(),
        'maintenance': Device.objects.filter(status='maintenance').count(),
        'lost': Device.objects.filter(status='lost').count(),
    }

    return render(request, 'facility_device_list.html', {
        'devices': devices,
        'search_query': search_query,
        'status_filter': status_filter,
        'stats': stats
    })

@csrf_exempt
@require_POST
@login_required(login_url='/login/')
def add_device_api(request):
    if request.user.role not in ['facility', 'admin'] and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện!'})
        
    try:
        name = request.POST.get('name')
        quantity = int(request.POST.get('quantity', 1))
        
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập tên thiết bị!'})
            
        added_count = 0
        for _ in range(quantity):
            Device.objects.create(name=name, status='ready')
            added_count += 1
            
        return JsonResponse({'status': 'success', 'message': f'Đã nhập kho thành công {added_count} thiết bị!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
@login_required(login_url='/login/')
def update_device_status_api(request):
    if request.user.role not in ['facility', 'admin'] and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện!'})
        
    try:
        device_id = request.POST.get('device_id')
        new_status = request.POST.get('status')
        
        device = Device.objects.get(id=device_id)
        
        if device.status == 'borrowed' or new_status == 'borrowed':
            return JsonResponse({'status': 'error', 'message': 'Trạng thái Đang mượn chỉ được thay đổi thông qua hệ thống Quét mã QR!'})
            
        device.status = new_status
        device.save()
        return JsonResponse({'status': 'success', 'message': f'Đã cập nhật trạng thái thiết bị {device.device_code}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required(login_url='/login/')
def get_device_history_api(request, device_id):
    if request.user.role not in ['facility', 'admin'] and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện!'})
        
    try:
        logs = BorrowLog.objects.filter(device_id=device_id).order_by('-borrow_time')[:10]
        data = []
        for log in logs:
            data.append({
                'borrower': log.borrower.first_name or log.borrower.username,
                'class_code': log.for_class.class_code,
                'borrow_time': log.borrow_time.strftime("%d/%m/%Y %H:%M") if log.borrow_time else '',
                'return_time': log.return_time.strftime("%d/%m/%Y %H:%M") if log.return_time else 'Chưa trả',
                'status': log.get_status_display()
            })
        return JsonResponse({'status': 'success', 'data': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})