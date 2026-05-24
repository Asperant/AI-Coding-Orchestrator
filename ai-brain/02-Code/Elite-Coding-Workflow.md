
Bu dosya, AI ile kod yazarken takip edilecek ana mühendislik akışını tanımlar.

Amaç:
AI’ın sadece kod yazmasını değil; önce anlamasını, planlamasını, küçük değişiklik yapmasını, review etmesini, test düşünmesini ve öğrendiklerini kaydetmesini sağlamaktır.

## Core Principle

AI büyük ve kontrolsüz kod değişiklikleri yapmamalıdır.

Her kod görevi şu sırayla ilerlemelidir:

1. Understand
2. Inspect
3. Plan
4. Implement small
5. Review diff
6. Test
7. Record reusable knowledge

---

## 1. Understand

AI önce görevi anlamalıdır.

Kontrol etmesi gerekenler:

- Bu görev bir feature mı?
- Bug fix mi?
- Refactor mı?
- Test yazımı mı?
- Database değişikliği mi?
- UI değişikliği mi?
- AI pipeline değişikliği mi?
- Security/privacy riski var mı?

AI emin değilse varsayımını açıkça yazmalıdır.

---

## 2. Inspect

AI kod yazmadan önce ilgili dosyaları incelemelidir.

Kurallar:

- Mevcut mimariyi anlamadan yeni yapı önermemeli.
- Mevcut pattern’leri bozmamalı.
- Görevle ilgili dosyaları bulmalı.
- Projede varsa `AGENTS.md` dosyasını okumalı.
- Projede varsa `docs/architecture.md` ve `docs/product-context.md` dosyalarını okumalı.

---

## 3. Plan

AI kod yazmadan önce kısa ve uygulanabilir plan vermelidir.

Plan şunları içermelidir:

- Görev tipi
- İlgili dosyalar
- Beklenen değişiklik
- Riskli alanlar
- Test yaklaşımı
- Değişecek dosyalar

Plan küçük olmalıdır. Büyük rewrite planı varsayılan davranış değildir.

---

## 4. Implement Small

AI sadece küçük, güvenli ve incelenebilir değişiklik yapmalıdır.

Kurallar:

- Aynı anda çok fazla dosya değiştirme.
- İlgisiz dosyalara dokunma.
- Gereksiz dependency ekleme.
- Büyük refactor’u feature ile karıştırma.
- Var olan stil ve mimariye uy.
- Public API veya veri yapısı değişiyorsa açıkça belirt.

---

## 5. Review Diff

Kod değişikliğinden sonra AI kendi diff’ini review etmelidir.

Kontrol edilecekler:

- Scope dışına çıkıldı mı?
- Gereksiz abstraction eklendi mi?
- Edge case kaçtı mı?
- Security/privacy riski var mı?
- Database/auth/payment etkisi var mı?
- Test eksik mi?
- Kullanıcı akışı bozulabilir mi?

---

## 6. Test

AI her kod değişikliğinden sonra test düşünmelidir.

Minimum çıktı:

- Manuel test adımları
- Başarı senaryosu
- Hata senaryosu
- Regression riski
- Gerekirse otomatik test önerileri

---

## 7. Record Reusable Knowledge

Eğer görevden tekrar kullanılabilir bilgi çıktıysa AI-Brain’e kaydedilmelidir.

Kaydedilebilecek şeyler:

- Teknik karar
- Bug root cause
- Yeni prompt
- Yeni checklist
- Mimari ders
- Riskli dosya bilgisi
- Proje özelinde önemli davranış

Uygun notlar:

- [[Decision-Template]]
- [[Bug-Fix-Template]]
- [[Lessons-Learned]]
- [[Code-Change-Checklist]]
- [[AGENTS-Improvement-Checklist]]

---

## Definition

İyi AI kod yazma süreci şudur:

AI önce anlar, sonra inceler, sonra planlar, sonra küçük uygular, sonra review eder, sonra test eder, sonra öğrendiğini kaydeder.