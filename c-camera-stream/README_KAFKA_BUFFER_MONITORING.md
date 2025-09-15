# Kafka Buffer Error Monitoring

## Tổng quan

Hệ thống hiện đã được cập nhật để theo dõi và xử lý lỗi buffer của Kafka. Khi Kafka gặp lỗi buffer liên tục trong 1 phút, container sẽ tự động restart để khôi phục.

## Cơ chế hoạt động

### 1. Theo dõi lỗi buffer

- System theo dõi các lỗi buffer trong Kafka producer
- Các từ khóa lỗi được theo dõi: `buffer`, `memory`, `queue full`, `producer queue is full`
- Thời gian threshold: 60 giây (có thể cấu hình)

### 2. Logging

- **🟡 Cảnh báo**: Khi phát hiện lỗi buffer đầu tiên
- **🟡 Theo dõi**: Cập nhật thời gian lỗi tiếp tục
- **✅ Khôi phục**: Khi lỗi được giải quyết
- **🔴 Critical**: Khi lỗi vượt quá threshold (1 phút)

### 3. Xử lý lỗi

- Khi lỗi buffer kéo dài > 60 giây: Throw `KafkaBufferException`
- Application exit với code 1
- Docker tự động restart container (với `restart: unless-stopped`)

## Cấu hình

### Environment Variables

Thêm vào file `.env` để tùy chỉnh:

```env
# Kafka Buffer Monitoring (optional)
KAFKA_BUFFER_ERROR_THRESHOLD_SECONDS=60
```

### Docker Restart Policy

Trong `docker-compose.yml`:

```yaml
services:
  camera-stream:
    restart: unless-stopped # Đã có sẵn
```

## Monitoring & Logs

### Log messages quan trọng

1. **Buffer error detected**:

```
🟡 Kafka buffer error detected. Starting timer. Error: [error details]
```

2. **Buffer error ongoing**:

```
🟡 Kafka buffer error ongoing for X.Xs. Consecutive errors: N
```

3. **Buffer error resolved**:

```
✅ Kafka buffer errors resolved after X.Xs. Total consecutive errors: N
```

4. **Critical - Force restart**:

```
🔴 CRITICAL: Kafka buffer errors persisted beyond threshold - forcing container restart
```

### Structured logging

Logs bao gồm thông tin chi tiết:

- Error duration
- Consecutive error count
- Frame dimensions
- Motion area
- Compression details

## Testing

### Test buffer error simulation

```python
# Trong send_message(), có thể test bằng cách:
# raise Exception("producer queue is full")  # Simulate buffer error
```

### Monitor logs

```bash
# Theo dõi logs real-time
docker-compose logs -f camera-stream

# Tìm kiếm buffer errors
docker-compose logs camera-stream | grep -E "(buffer|queue full|memory)"
```

## Troubleshooting

### Nếu container restart liên tục

1. Kiểm tra Kafka connection
2. Tăng buffer size trong Kafka config:

   ```python
   'buffer.memory': 268435456,  # 256MB thay vì 128MB
   'batch.size': 3145728,       # 3MB thay vì 1.5MB
   ```

3. Giảm frequency gửi message:
   ```env
   INTERVAL_SECONDS=10  # Tăng từ 5 giây
   ```

### Debug logs

Enable debug logging:

```env
DEBUG_LEVEL=DEBUG
```

## Benefits

1. **Automatic Recovery**: Container tự động restart khi gặp vấn đề
2. **Detailed Monitoring**: Logs chi tiết về buffer errors
3. **Configurable**: Có thể tùy chỉnh threshold time
4. **Non-blocking**: Không ảnh hưởng đến normal operations
5. **Docker Integration**: Tích hợp sẵn với Docker restart policy
