# Task Type Rules

Bu dosya, AI’ın kodlama görevlerini doğru tipe ayırmasını ve her görev tipinde doğru mühendislik davranışını izlemesini sağlar.

## Core Rule

AI her kod görevine başlamadan önce görev tipini belirlemelidir.

Bir görev birden fazla tipe ait olabilir. Bu durumda AI en riskli tipi önce ele almalıdır.

Örnek:
- UI + auth değişikliği varsa auth riski önceliklidir.
- Feature + database değişikliği varsa database riski önceliklidir.
- Refactor + behavior change varsa artık sadece refactor değildir.

---

## 1. Feature

Yeni özellik ekleme görevidir.

AI şunları yapmalı:

- Kullanıcı amacını netleştirmeli
- Beklenen davranışı yazmalı
- UI state’lerini düşünmeli
- Veri ihtiyacını belirlemeli
- Edge case’leri çıkarmalı
- Küçük implementation planı vermeli

Kontrol soruları:

- Kullanıcı bu özellikle ne yapacak?
- Başarı durumu nedir?
- Loading, empty, error, success state var mı?
- Hangi dosyalar değişecek?
- Bu özellik eski akışı bozabilir mi?

---

## 2. Bug Fix

Var olan hatayı düzeltme görevidir.

AI şunları yapmalı:

- Beklenen davranışı yazmalı
- Mevcut davranışı yazmalı
- Root cause bulmaya çalışmalı
- Reproduce adımlarını istemeli veya çıkarmalı
- En küçük güvenli fix’i önermeli
- Regression riskini belirtmeli

Kontrol soruları:

- Hata nasıl tekrar üretilir?
- Asıl sebep ne?
- Fix başka bir davranışı bozabilir mi?
- Aynı hatayı önleyecek test var mı?

---

## 3. Refactor

Davranışı değiştirmeden kodu iyileştirme görevidir.

AI şunları yapmalı:

- Davranış değişmeyeceğini açıkça belirtmeli
- Refactor kapsamını küçük tutmalı
- Public API değiştirirse bunu risk olarak yazmalı
- Test adımlarını vermeli
- Feature eklememeli

Kontrol soruları:

- Davranış gerçekten aynı mı kalıyor?
- Bu refactor neden gerekli?
- Daha küçük yapılabilir mi?
- İlgisiz dosya değişti mi?

---

## 4. Test Writing

Test ekleme veya test planı çıkarma görevidir.

AI şunları yapmalı:

- Happy path
- Error path
- Empty/null input
- Permission denied
- Network failure
- Rapid repeated action
- Regression scenario

Kontrol soruları:

- Hangi davranış garanti altına alınıyor?
- Testler implementation detayına mı, davranışa mı bağlı?
- Kritik edge case’ler var mı?

---

## 5. Database Change

Database, migration, schema, RLS, index veya data model değişikliğidir.

AI şunları yapmalı:

- Migration etkisini yazmalı
- Rollback riskini belirtmeli
- Access control / RLS düşünmeli
- Index ihtiyacını değerlendirmeli
- Data backfill gerekip gerekmediğini sormalı
- Client-side varsayımları kontrol etmeli

Kontrol soruları:

- Eski data ne olacak?
- Kullanıcı sadece kendi verisini görebiliyor mu?
- Migration güvenli mi?
- Rollback mümkün mü?
- Query performansı etkilenir mi?

---

## 6. UI Change

Ekran, component, layout veya kullanıcı akışı değişikliğidir.

AI şunları yapmalı:

- Loading state düşünmeli
- Empty state düşünmeli
- Error state düşünmeli
- Disabled state düşünmeli
- Mobile responsive davranışı düşünmeli
- Accessibility riskini belirtmeli

Kontrol soruları:

- Kullanıcı hızlı tıklarsa ne olur?
- Veri gelmezse ne görünür?
- Hata olursa ne görünür?
- Küçük ekranda bozulur mu?

---

## 7. AI Pipeline Change

AI servisleri, promptlar, inference, queue, fallback, result generation veya model entegrasyonu değişikliğidir.

AI şunları yapmalı:

- Aktif AI path’i doğrulamalı
- Legacy path’leri karıştırmamalı
- Fallback davranışını belirtmeli
- Timeout davranışını düşünmeli
- Queue/rate limit etkisini düşünmeli
- Kullanıcıya gösterilen sonuç dilini kontrol etmeli

Kontrol soruları:

- AI servisi kapalıysa ne olur?
- Model cevap vermezse ne olur?
- Fallback var mı?
- Aynı anda çok istek gelirse ne olur?
- Legacy endpoint aktif sanılıyor mu?
- Output kullanıcıya uygun ve güvenli mi?

---

## 8. Security / Privacy Change

Auth, kullanıcı verisi, secret, token, camera, microphone, payment veya permission içeren görevdir.

AI şunları yapmalı:

- Secret/key sızıntısı var mı bakmalı
- Kullanıcı verisi minimizasyonunu düşünmeli
- Permission davranışını yazmalı
- Client/server boundary’yi kontrol etmeli
- Sensitive data logging riskini belirtmeli

Kontrol soruları:

- Kullanıcı başka kullanıcının verisine erişebilir mi?
- Gizli anahtar client’a düşüyor mu?
- Loglarda hassas veri var mı?
- Kamera/mikrofon izni kullanıcıya açık anlatılıyor mu?
- Production config güvenli mi?

---

## 9. Performance Change

Performans, render, network, query, caching veya model latency ile ilgili görevdir.

AI şunları yapmalı:

- Yavaş path’i belirlemeli
- Gereksiz render veya tekrar sorgu var mı bakmalı
- Cache etkisini düşünmeli
- Large data durumunu kontrol etmeli
- Ölçüm önerisi vermeli

Kontrol soruları:

- Neyi hızlandırıyoruz?
- Nasıl ölçeceğiz?
- Değişiklik correctness’ı bozuyor mu?
- Cache stale data yaratır mı?

---

## 10. Documentation Change

Dokümantasyon, README, setup, guide veya AI-Brain notu güncellemesidir.

AI şunları yapmalı:

- Kısa ve pratik yazmalı
- Repo gerçekliğine bağlı kalmalı
- Güncel olmayan bilgi eklememeli
- Kodla çelişen dokümantasyon oluşturmamalı

Kontrol soruları:

- Bu bilgi gerçekten doğru mu?
- Yeni başlayan biri bunu kullanabilir mi?
- Komutlar çalışır mı?
- Legacy bilgi açıkça işaretli mi?

---

## Priority Rule

Bir görev birden fazla tipe giriyorsa öncelik sırası:

1. Security / Privacy
2. Database Change
3. AI Pipeline Change
4. Auth / Payment related changes
5. Bug Fix
6. Feature
7. Refactor
8. UI Change
9. Test Writing
10. Documentation Change

## Final Rule

AI görev tipini belirlemeden kod yazmamalıdır.