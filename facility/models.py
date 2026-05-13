from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from academic.models import Class
from django.utils.html import mark_safe
from django.utils import timezone # THÊM THƯ VIỆN NÀY ĐỂ LẤY NGÀY HIỆN TẠI

class Device(models.Model):
    STATUS_CHOICES = (
        ('ready', 'Sẵn sàng'),
        ('borrowed', 'Đang mượn'),
        ('maintenance', 'Đang bảo trì'),
        ('lost', 'Thất lạc/Hỏng'),
    )
    
    # SỬA 1: Đổi tiêu đề cho gọn
    device_code = models.CharField('Mã Thiết Bị', max_length=50, unique=True, blank=True)
    name = models.CharField('Tên thiết bị', max_length=100)
    status = models.CharField('Trạng thái', max_length=20, choices=STATUS_CHOICES, default='ready')
    
    # SỬA 2: Tự động lấy ngày hiện tại khi thêm mới
    purchase_date = models.DateField('Ngày mua', default=timezone.now, null=True, blank=True)

    def qr_code_image(self):
        big_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={self.device_code}"
        small_url = f"https://api.qrserver.com/v1/create-qr-code/?size=60x60&data={self.device_code}"
        
        # Nhúng code tạo Popup (Modal) làm mờ nền
        script = """
        <script>
        if(!document.getElementById('qrModal')) {
            document.body.insertAdjacentHTML('beforeend', `
            <div id="qrModal" style="display:none; position:fixed; z-index:9999; left:0; top:0; width:100%; height:100%; background-color:rgba(0,0,0,0.7); align-items:center; justify-content:center; backdrop-filter: blur(5px);">
                <div style="background:#fff; padding:20px; border-radius:10px; text-align:center; position:relative; box-shadow: 0 5px 15px rgba(0,0,0,0.5);">
                    <span onclick="document.getElementById('qrModal').style.display='none'" style="position:absolute; top:5px; right:15px; font-size:28px; font-weight:bold; cursor:pointer; color:red;">&times;</span>
                    <h4 id="qrModalTitle" style="margin-top:0; color:#0d6efd; font-weight:bold;"></h4>
                    <img id="qrModalImg" src="" style="width:300px; height:300px; margin-top:10px; border: 2px dashed #ccc; padding: 10px;" />
                    <p style="margin-top:10px; color:#555;">(Quét bằng Camera điện thoại)</p>
                </div>
            </div>`);
            
            // Bấm ra ngoài vùng ảnh thì tự đóng Popup
            document.getElementById('qrModal').addEventListener('click', function(e){
                if(e.target === this) this.style.display = 'none';
            });
        }
        function showQR(url, code) {
            document.getElementById('qrModalImg').src = url;
            document.getElementById('qrModalTitle').innerText = 'MÃ: ' + code;
            document.getElementById('qrModal').style.display = 'flex';
        }
        </script>
        """
        
        # Nút ảnh thu nhỏ, bấm vào sẽ gọi hàm showQR ở trên
        return mark_safe(f'{script}<img src="{small_url}" onclick="showQR(\'{big_url}\', \'{self.device_code}\')" style="width:60px; height:60px; border:1px solid #ccc; border-radius:5px; padding:2px; cursor:pointer; transition:0.2s;" title="Bấm để phóng to" onmouseover="this.style.transform=\'scale(1.1)\'" onmouseout="this.style.transform=\'scale(1)\'" />')
    
    qr_code_image.short_description = 'Mã QR'

    def save(self, *args, **kwargs):
        if not self.device_code:
            last_device = Device.objects.all().order_by('id').last()
            next_id = last_device.id + 1 if last_device else 1
            self.device_code = f"TB{next_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.device_code}] {self.name}"

    class Meta:
        verbose_name = 'Thiết bị'
        verbose_name_plural = '1. Kho Thiết bị Smart Lab'


# 2. BẢNG NHẬT KÝ MƯỢN TRẢ (Phiếu xuất/nhập)
class BorrowLog(models.Model):
    STATUS_CHOICES = (
        ('borrowed', 'Đang mượn'),
        ('returned', 'Đã trả'),
    )
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE, verbose_name='Thiết bị')
    
    # Giáo viên nào mượn?
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.RESTRICT,
        limit_choices_to={'role': 'teacher'},
        verbose_name='Giáo viên mượn'
    )
    
    # LIÊN KẾT CHẶT CHẼ: Mượn cho Lớp nào đang khai giảng?
    for_class = models.ForeignKey(
        Class, 
        on_delete=models.RESTRICT, 
        limit_choices_to={'status': 'active'}, # Chỉ cho mượn đồ đối với lớp đang học
        verbose_name='Sử dụng cho Lớp'
    )
    
    borrow_time = models.DateTimeField('Thời gian mượn', auto_now_add=True)
    return_time = models.DateTimeField('Thời gian trả', null=True, blank=True)
    status = models.CharField('Trạng thái phiếu', max_length=20, choices=STATUS_CHOICES, default='borrowed')
    note = models.CharField('Ghi chú tình trạng', max_length=255, blank=True, null=True)

    # LUẬT NGHIỆP VỤ TỰ ĐỘNG KHOÁ KHO
    def clean(self):
        # Nếu đang tạo phiếu mượn MỚI mà thiết bị không 'ready' -> Chặn lại
        if not self.pk and self.status == 'borrowed':
            if self.device.status != 'ready':
                raise ValidationError({'device': f'LỖI: Thiết bị {self.device.name} hiện không có sẵn trong kho!'})

    def save(self, *args, **kwargs):
        # 1. Khi Phiếu mượn được tạo -> Cập nhật thiết bị thành 'Đang mượn'
        if getattr(self, '_state', None) and self._state.adding and self.status == 'borrowed':
            self.device.status = 'borrowed'
            self.device.save()
            
        # 2. Khi Phiếu mượn được update thành 'Đã trả' -> Trả thiết bị về 'Sẵn sàng'
        elif self.pk:
            old_log = BorrowLog.objects.get(pk=self.pk)
            if old_log.status == 'borrowed' and self.status == 'returned':
                self.device.status = 'ready'
                self.device.save()
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Phiếu: {self.borrower} mượn {self.device.device_code}"

    class Meta:
        verbose_name = 'Phiếu mượn trả'
        verbose_name_plural = '2. Lịch sử Mượn/Trả'