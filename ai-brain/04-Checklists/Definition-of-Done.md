# Definition of Done

Bu dosya, AI ile yapılan bir kod görevinin gerçekten tamamlanmış sayılması için gereken koşulları tanımlar.

Amaç:
AI’ın sadece “kodu yazdım” demesini engellemek; değişikliğin anlaşılmış, sınırlandırılmış, test edilmiş ve kaydedilebilir hale gelmesini sağlamaktır.

## 1. Görev anlaşıldı

- [ ] Görev tipi belirlendi.
- [ ] Kullanıcı amacı veya teknik amaç netleşti.
- [ ] Beklenen davranış açıklandı.
- [ ] İlgili dosyalar incelendi.
- [ ] Riskli alanlar belirlendi.

## 2. Değişiklik kontrollü yapıldı

- [ ] Sadece gerekli dosyalar değiştirildi.
- [ ] İlgisiz dosyalara dokunulmadı.
- [ ] Gereksiz refactor yapılmadı.
- [ ] Gereksiz dependency eklenmedi.
- [ ] Mevcut mimari ve stil takip edildi.

## 3. Davranış doğrulandı

- [ ] Başarı senaryosu tanımlandı.
- [ ] Hata senaryosu tanımlandı.
- [ ] Loading/empty/error state düşünüldü.
- [ ] Rapid repeated action düşünüldü.
- [ ] Network/server failure düşünüldü.
- [ ] Eski davranışın bozulma riski değerlendirildi.

## 4. Riskler kontrol edildi

- [ ] Auth riski yok veya açıklandı.
- [ ] Payment riski yok veya açıklandı.
- [ ] Database/migration riski yok veya açıklandı.
- [ ] Supabase/Firebase rule riski yok veya açıklandı.
- [ ] Kullanıcı verisi riski yok veya açıklandı.
- [ ] Privacy/camera/microphone riski yok veya açıklandı.
- [ ] AI pipeline/fallback/queue riski yok veya açıklandı.
- [ ] Secret/config sızıntısı yok.

## 5. Test planı hazır

- [ ] Manuel test adımları yazıldı.
- [ ] En az bir başarı senaryosu var.
- [ ] En az bir hata senaryosu var.
- [ ] Regression riski belirtildi.
- [ ] Otomatik test ihtiyacı değerlendirildi.
- [ ] Test çalıştırılamadıysa nedeni açıklandı.

## 6. Review yapıldı

- [ ] Diff review yapıldı.
- [ ] Scope kontrol edildi.
- [ ] Edge case kontrol edildi.
- [ ] Güvenlik/privacy kontrol edildi.
- [ ] Gereksiz complexity kontrol edildi.
- [ ] Test eksikleri kontrol edildi.

## 7. Bilgi kaydı düşünüldü

- [ ] Teknik karar kaydı gerekiyor mu kontrol edildi.
- [ ] Bug fix kaydı gerekiyor mu kontrol edildi.
- [ ] Lessons Learned güncellenmeli mi kontrol edildi.
- [ ] AGENTS.md veya docs güncellenmeli mi kontrol edildi.
- [ ] Tekrar kullanılabilir bilgi varsa AI-Brain’e kaydedildi veya önerildi.

## Done statement

Bir görev ancak şu cümle doğruysa bitmiş sayılır:

```text
This task is understood, scoped, implemented, reviewed, testable, and any reusable knowledge has been identified.
```

Bu cümle doğru değilse görev tamamlanmış sayılmaz.