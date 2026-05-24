# AGENTS Improvement Checklist

Bir projedeki `AGENTS.md` dosyasını iyileştirirken bu checklist kullanılır.

## 1. Ürün ve stack net mi?

- [ ] Ürün ne yapıyor?
- [ ] Ana kullanıcı akışı belli mi?
- [ ] Tech stack yazıyor mu?
- [ ] Frontend/backend/AI/database parçaları açık mı?

## 2. AI davranış kuralları net mi?

- [ ] AI önce dosyaları incelemeli mi?
- [ ] Büyük değişikliklerden önce plan vermeli mi?
- [ ] İlgisiz dosyaları değiştirmemeli mi?
- [ ] Mevcut mimariye uymalı mı?
- [ ] Riskli alanları açıkça belirtmeli mi?

## 3. Key Files by Task var mı?

`AGENTS.md` içinde görev tipine göre ilk bakılacak dosyalar yazmalı.

Örnek:

- AI result flow:
- Authentication:
- Database:
- State management:
- UI flow:
- Privacy/camera:
- Payments:
- Ops/setup:

## 4. Riskli alanlar yazıyor mu?

- [ ] Auth
- [ ] Payment
- [ ] Database migration
- [ ] Supabase/Firebase rules
- [ ] User data
- [ ] Privacy
- [ ] Camera/microphone
- [ ] AI fallback behavior
- [ ] Legacy code paths

## 5. Operasyonel notlar var mı?

- [ ] Aktif API path’leri belirtilmiş mi?
- [ ] Legacy endpoint veya eski isimlendirme uyarısı var mı?
- [ ] Local/dev setup notu var mı?
- [ ] Server kapalıyken beklenen davranış belli mi?
- [ ] Rate limit / queue / background job davranışı belirtilmiş mi?

## 6. Fazla uzun mu?

- [ ] Kısa ve okunabilir mi?
- [ ] Codex’in hızlı kullanabileceği kadar pratik mi?
- [ ] Gereksiz teori veya uzun açıklama var mı?

## 7. Son kontrol

İyi bir `AGENTS.md` sadece genel kurallar vermez.

Şunları da söyler:

- bu proje nedir?
- AI nasıl davranmalı?
- hangi işte önce hangi dosyalara bakmalı?
- hangi risklere dikkat etmeli?
- hangi eski/aktif akışları karıştırmamalı?