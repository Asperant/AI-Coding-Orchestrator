# AI Coding Command Library

Bu dosya, AI ile kod yazarken kullanılacak tekrar edilebilir komutları ve hangi durumda hangi akışın kullanılacağını tanımlar.

Amaç:
AI ile kodlama sürecini rastgele prompt yazmaktan çıkarıp standart, güvenli ve profesyonel bir komut sistemine dönüştürmektir.

---

## /onboard-project

Yeni veya mevcut bir projeyi AI engineering sistemine dahil etmek için kullanılır.

Uses:
- [[Project-Onboarding-Prompt]]
- [[AGENTS-Improvement-Checklist]]

Expected result:
- proje özeti
- mevcut AI-ready dosyalar
- eksik AI-ready dosyalar
- küçük onboarding planı

---

## /plan-feature

Yeni bir feature’a başlamadan önce kullanılır.

Uses:
- [[Feature-Spec-Prompt]]
- [[Elite-Coding-Workflow]]
- [[Task-Type-Rules]]
- [[Pre-Flight-Checklist]]

Expected result:
- kullanıcı amacı
- beklenen davranış
- veri ihtiyacı
- UI state’leri
- edge case’ler
- küçük implementation planı
- test planı

---

## /implement-small

Planlanmış bir işin sadece küçük bir parçasını uygulatmak için kullanılır.

Uses:
- [[Codex-Task-Prompt]]
- [[Pre-Flight-Checklist]]
- [[Definition-of-Done]]

Expected result:
- küçük ve sınırlı kod değişikliği
- değişen dosyalar
- risk notları
- manuel test adımları

Rules:
- büyük rewrite yok
- ilgisiz dosya değişikliği yok
- gereksiz dependency yok

---

## /review-diff

Yapılan değişikliği incelemek için kullanılır.

Uses:
- [[Codex-Diff-Review-Prompt]]
- [[Post-Flight-Review]]
- [[Definition-of-Done]]

Expected result:
- bug riskleri
- scope dışı değişiklikler
- security/privacy riskleri
- edge case’ler
- test eksikleri
- önerilen en küçük düzeltme

---

## /debug

Bir hata çözmek için kullanılır.

Uses:
- [[Debug-Prompt]]
- [[Task-Type-Rules]]
- [[Bug-Fix-Template]]
- [[Lessons-Learned]]

Expected result:
- beklenen davranış
- mevcut davranış
- en olası root cause
- doğrulama yolları
- minimal fix
- regression testleri
- gerekirse bug fix kaydı

---

## /safe-refactor

Davranışı değiştirmeden kodu iyileştirmek için kullanılır.

Uses:
- [[Task-Type-Rules]]
- [[Pre-Flight-Checklist]]
- [[Post-Flight-Review]]
- [[Definition-of-Done]]

Expected result:
- refactor amacı
- değişmeyecek davranış
- küçük kapsam
- test adımları
- regression riski

Rules:
- feature ekleme yok
- davranış değişikliği yok
- public API değişirse açık risk notu şart

---

## /write-tests

Test yazmak veya test planı çıkarmak için kullanılır.

Uses:
- [[Task-Type-Rules]]
- [[Code-Change-Checklist]]
- [[Definition-of-Done]]

Expected result:
- happy path
- error path
- empty/null input
- permission denied
- network/server failure
- rapid repeated action
- regression senaryoları

---

## /review-security

Auth, ödeme, database, kullanıcı verisi, camera/microphone, secret/config gibi riskli alanlarda kullanılır.

Uses:
- [[Task-Type-Rules]]
- [[Pre-Flight-Checklist]]
- [[Post-Flight-Review]]
- [[Definition-of-Done]]

Expected result:
- security/privacy riskleri
- data exposure riski
- secret leakage riski
- permission davranışı
- client/server boundary kontrolü
- önerilen en küçük güvenli düzeltme

---

## /save-decision

Teknik veya ürün kararı kaydetmek için kullanılır.

Uses:
- [[Decision-Template]]
- [[Lessons-Learned]]

Expected result:
- karar
- bağlam
- seçenekler
- seçilen yol
- trade-off’lar
- tekrar gözden geçirme tetikleyicisi

---

## /save-bugfix

Önemli bir bug çözümünü kalıcı hafızaya almak için kullanılır.

Uses:
- [[Bug-Fix-Template]]
- [[Lessons-Learned]]

Expected result:
- bug
- expected behavior
- actual behavior
- root cause
- fix
- changed files
- test
- lesson learned

---

## /save-lesson

Tekrar kullanılabilir bir öğrenimi AI-Brain’e kaydetmek için kullanılır.

Uses:
- [[Lessons-Learned]]

Expected result:
- context
- lesson
- future use

---

## Core Rule

Bu komutlar gerçek terminal komutu olmak zorunda değildir.

Bunlar kişisel AI çalışma komutlarıdır.

Bir kod görevi başladığında AI önce hangi komut/akışın uygun olduğunu belirlemelidir.