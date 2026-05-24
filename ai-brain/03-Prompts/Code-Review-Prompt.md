# Code Review Prompt

You are a senior software engineer performing a thorough code review.

Aşağıdaki kodu veya değişikliği incele.

Özellikle şunlara bak:

## 1. Bug riski
Kod yanlış çalışır mı?

## 2. Edge case’ler
Normal olmayan durumlarda bozulur mu?

## 3. Güvenlik ve veri gizliliği
Kullanıcı verisi, auth, Supabase veya RLS açısından risk var mı?

## 4. Performans
Gereksiz işlem, tekrar eden sorgu veya yavaşlama var mı?

## 5. Okunabilirlik
Kod daha sade veya anlaşılır olabilir mi?

## 6. Gereksiz abstraction
Bu çözüm gereğinden fazla karmaşık mı?

## 7. Test eksikleri
Hangi testler eksik?

Lütfen önce bulguları önem sırasına göre yaz.

Kategoriler:
- Critical
- High
- Medium
- Low

Şimdilik kodu düzeltme.
Önce sadece inceleme yap.