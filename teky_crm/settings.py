import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-gn35i4y6hf@pvh(dga^ie&8$+xosb=0^46t7eno$ipg=n$k-wb')

# SECURITY WARNING: don't run with debug turned on in production!
# Tự động tắt DEBUG khi đưa lên Render
DEBUG = 'RENDER' not in os.environ

ALLOWED_HOSTS = ['*']

# Tự động nhận diện tên miền của Render
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Application definition
INSTALLED_APPS = [
    'jazzmin', # BẮT BUỘC PHẢI ĐỂ Ở TRÊN CÙNG
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # CÁC APP CỦA DỰ ÁN:
    'accounts',
    'crm',
    'academic',
    'facility',
    'smartlab', # Đã bổ sung app này để tránh lỗi khi quét AI

    # THƯ VIỆN BỔ SUNG:
    'django.contrib.humanize',
    
    # [ĐÃ THÊM] THƯ VIỆN LƯU TRỮ ẢNH ĐÁM MÂY:
    'cloudinary_storage',
    'cloudinary',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # [BẮT BUỘC CHO RENDER] Xử lý static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'teky_crm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'teky_crm.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# [ĐÃ SỬA] Tự động nhận diện Database (Dùng PostgreSQL cục bộ nếu chạy ở máy, dùng DB của Render nếu ở trên mạng)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'teky_crm_db',
        'USER': 'postgres',
        'PASSWORD': '123456',  # Mật khẩu máy bạn
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# [BẮT BUỘC CHO RENDER] Cấu hình thư mục chứa file tĩnh khi build
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

AUTH_USER_MODEL = 'accounts.CustomUser'

JAZZMIN_SETTINGS = {
    "site_title": "TEKY CRM",
    "site_header": "Hệ thống Quản trị",
    "site_brand": "TEKY Admin",
    "welcome_sign": "Chào mừng đến với hệ thống Quản trị",
    "show_ui_builder": False, 
}

JAZZMIN_UI_TWEAKS = {
    "theme": "lumen", 
}


# ==========================================
# CẤU HÌNH CLOUDINARY LƯU TRỮ ẢNH VĨNH VIỄN
# ==========================================
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'Dán_Cloud_Name_Vào_Đây',
    'API_KEY': 'Dán_API_Key_Vào_Đây',
    'API_SECRET': 'Dán_API_Secret_Vào_Đây'
}

# Sử dụng cú pháp mới của Django để quản lý File Storage
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# (Tuỳ chọn: Nếu vẫn muốn giữ biến để lỡ sau này muốn code tham chiếu đến đường dẫn Local thì thêm lại 2 dòng này)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==========================================
# CẤU HÌNH KHÓA CHÍNH MẶC ĐỊNH (FIX WARNING W042)
# ==========================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'