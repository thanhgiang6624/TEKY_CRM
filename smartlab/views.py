import numpy as np
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone

import face_recognition
from academic.models import Student, StudentFace, Class, Attendance

@login_required(login_url='/login/')
def register_face_view(request):
    students = Student.objects.all().order_by('face_data', '-id')
    return render(request, 'smartlab_register_face.html', {'students': students})

@csrf_exempt
@require_POST
def register_face_api(request):
    try:
        student_id = request.POST.get('student_id')
        image_file = request.FILES.get('image')

        if not student_id or not image_file:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn học sinh và chụp ảnh!'})

        student = Student.objects.get(id=student_id)
        
        img = face_recognition.load_image_file(image_file)
        face_encodings = face_recognition.face_encodings(img)

        if len(face_encodings) == 0:
            return JsonResponse({'status': 'error', 'message': 'AI không tìm thấy khuôn mặt. Hãy bảo bé nhìn thẳng vào Camera!'})
        elif len(face_encodings) > 1:
            return JsonResponse({'status': 'error', 'message': 'Có nhiều người trong khung hình. Chỉ chụp riêng 1 bé!'})

        encoding = face_encodings[0]
        student_face, created = StudentFace.objects.get_or_create(student=student)
        student_face.set_encoding(encoding)
        student_face.image_reference = image_file 
        student_face.save()

        return JsonResponse({'status': 'success', 'message': f'Đã đăng ký thành công khuôn mặt cho: {student.full_name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required(login_url='/login/')
def ai_scanner_view(request):
    return render(request, 'smartlab_ai_scanner.html')

@csrf_exempt
@require_POST
def recognize_face_api(request):
    try:
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'status': 'error', 'message': 'Không nhận được ảnh'})

        img = face_recognition.load_image_file(image_file)
        unknown_encodings = face_recognition.face_encodings(img)

        if len(unknown_encodings) == 0:
            return JsonResponse({'status': 'empty', 'message': 'Không thấy ai trong khung hình'})

        unknown_encoding = unknown_encodings[0]

        registered_faces = StudentFace.objects.all()
        if not registered_faces:
             return JsonResponse({'status': 'error', 'message': 'Hệ thống chưa có dữ liệu khuôn mặt nào'})

        known_encodings = []
        students = []
        for face_record in registered_faces:
            encoding = face_record.get_encoding()
            if encoding is not None:
                known_encodings.append(encoding)
                students.append(face_record.student)

        matches = face_recognition.compare_faces(known_encodings, unknown_encoding, tolerance=0.45)
        face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)

        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            student = students[best_match_index]
            
            today = timezone.now().date()
            day_map = {0: 'T2', 1: 'T3', 2: 'T4', 3: 'T5', 4: 'T6', 5: 'T7', 6: 'CN'}
            today_str = day_map[today.weekday()]
            
            active_classes = Class.objects.filter(students=student, status='active', day_of_week=today_str)
            
            if not active_classes.exists():
                return JsonResponse({'status': 'warning', 'student_name': student.full_name, 'message': 'Bé không có lịch học hôm nay!'})

            messages_list = []
            for c in active_classes:
                att, created = Attendance.objects.get_or_create(
                    student=student, for_class=c, date=today,
                    defaults={'status': 'present', 'note': 'Điểm danh tự động bằng AI'}
                )
                if created:
                    messages_list.append(f'Lớp {c.class_code}: Thành công')
                else:
                    if att.status != 'present':
                        att.status = 'present'
                        att.note = 'Điểm danh tự động bằng AI'
                        att.save()
                        messages_list.append(f'Lớp {c.class_code}: Chuyển thành Có mặt')
                    else:
                        messages_list.append(f'Lớp {c.class_code}: Đã điểm danh rồi')

            return JsonResponse({
                'status': 'success', 
                'student_name': student.full_name,
                'message': " | ".join(messages_list)
            })
        else:
            return JsonResponse({'status': 'unknown', 'message': 'Khuôn mặt lạ, chưa đăng ký'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})