from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

# ==========================================
# KHU VỰC IMPORT VIEW ĐÃ ĐƯỢC CHIA TÁCH
# ==========================================

# 1. Kéo view từ file gốc (teky_crm)
from teky_crm.views import dashboard_view, teacher_profile_view

# 2. Kéo view từ app CRM
from crm.views import kanban_view, update_lead_status_api, get_available_schedules, get_course_details

# 3. Kéo view từ app Facility 
from facility.views import (
    teacher_history_view, manual_device_action_api,
    qr_scanner_view, process_qr_scan,
    facility_device_management_view, add_device_api, update_device_status_api, get_device_history_api 
)

# 4. Kéo view từ app Academic
from academic.views import (
    reserve_student_api, teacher_my_classes_view, teacher_class_info_view, teacher_class_session_view,
    student_list_view, student_360_view, 
    teacher_approvals_view, class_assignment_view, 
    process_teacher_request_api, assign_student_class_api,
    toggle_attendance_api, save_student_note_api, teacher_quit_class_api, transfer_student_api, update_class_info_api,
    upload_class_images_api, save_lesson_content_api, create_new_class_api,
    class_management_view, activate_class_api,
    session_management_view # ĐÃ BỔ SUNG
)

# 5. Kéo view từ app SmartLab (AI)
from smartlab.views import (
    register_face_view, register_face_api,
    ai_scanner_view, recognize_face_api
)


# ==========================================
# KHU VỰC ĐƯỜNG DẪN
# ==========================================
urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('admin/', admin.site.urls),

    path('', dashboard_view, name='dashboard'),
    path('kanban/', kanban_view, name='kanban'),
    path('smartlab/scanner/', qr_scanner_view, name='qr_scanner'),
    
    path('history/', teacher_history_view, name='history'),
    path('my-classes/', teacher_my_classes_view, name='my_classes'),
    path('profile/', teacher_profile_view, name='profile'),
    
    # GIAO DIỆN CHI TIẾT LỚP HỌC
    path('class/<int:class_id>/info/', teacher_class_info_view, name='class_info'),
    path('class/<int:class_id>/session/', teacher_class_session_view, name='class_session'),
    
    # =======================================================
    # BỔ SUNG: QUẢN LÝ THIẾT BỊ (HỌC VỤ/FACILITY)
    # =======================================================
    path('facility/devices/', facility_device_management_view, name='facility_device_management'),
    path('api/add-device/', add_device_api, name='api_add_device'),
    path('api/update-device-status/', update_device_status_api, name='api_update_device_status'),
    path('facility/api/device-history/<int:device_id>/', get_device_history_api, name='api_device_history'),
    
    # API CRM & SALES
    path('api/scan/', process_qr_scan, name='api_scan'),
    path('api/update_lead_status/', update_lead_status_api, name='api_update_lead'),
    path('api/get-schedules/', get_available_schedules, name='api_get_schedules'), 
    path('api/get-course-details/', get_course_details, name='api_get_course_details'),
    
    # API HỌC VỤ & GIÁO VIÊN
    path('api/attendance/', toggle_attendance_api, name='api_attendance'),
    path('api/save_note/', save_student_note_api, name='api_save_note'),
    path('api/manual_device_action/', manual_device_action_api, name='api_manual_device'),
    path('api/quit_class/', teacher_quit_class_api, name='api_quit_class'),
    path('api/upload_class_images/', upload_class_images_api, name='api_upload_class_images'),
    path('api/save_lesson_content/', save_lesson_content_api, name='api_save_lesson_content'),

    path('student/<int:student_id>/', student_360_view, name='student_360'),
    path('students/', student_list_view, name='student_list'),

    # ĐĂNG KÝ KHUÔN MẶT AI
    path('smartlab/register-face/', register_face_view, name='register_face'),
    path('api/register_face/', register_face_api, name='api_register_face'),
    path('smartlab/ai-scanner/', ai_scanner_view, name='ai_scanner'),
    path('api/recognize_face/', recognize_face_api, name='api_recognize_face'),
    
    # CÁC LINK XÉT DUYỆT & MỞ LỚP
    path('approvals/', RedirectView.as_view(url='/approvals/classes/', permanent=False)), 
    path('approvals/teachers/', teacher_approvals_view, name='teacher_approvals'),
    path('approvals/classes/', class_assignment_view, name='class_assignment'),
    
    path('classes/', class_management_view, name='class_management'),
    path('sessions/', session_management_view, name='session_management'), # ĐÃ BỔ SUNG LINK QUẢN LÝ BUỔI HỌC
    path('api/activate_class/', activate_class_api, name='api_activate_class'),
    
    path('api/process_request/', process_teacher_request_api, name='api_process_request'),
    path('api/assign_student/', assign_student_class_api, name='api_assign_student'),
    path('api/create_class/', create_new_class_api, name='api_create_class'),

    path('api/update_class_info/', update_class_info_api, name='api_update_class_info'),
    path('api/transfer_student/', transfer_student_api, name='api_transfer_student'),
    path('api/reserve_student/', reserve_student_api, name='api_reserve_student'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)