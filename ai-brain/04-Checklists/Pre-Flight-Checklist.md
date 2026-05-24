# Pre-Flight Checklist

Bu checklist, AI herhangi bir kod değişikliği yapmadan önce kullanılır.

Amaç:
AI’ın aceleyle kod yazmasını engellemek, önce görevi ve riskleri anlamasını sağlamaktır.

## 1. Görev tipi

- [ ] Bu görev tipi belirlendi.
- [ ] Görev tipi [[Task-Type-Rules]] ile uyumlu kontrol edildi.
- [ ] Birden fazla görev tipi varsa en riskli olan önce ele alındı.

Görev tipi:

```text

```

## 2. Bağlam

- [ ] Projede `AGENTS.md` varsa okundu.
- [ ] Projede `docs/product-context.md` varsa okundu.
- [ ] Projede `docs/architecture.md` varsa okundu.
- [ ] Mevcut klasör yapısı incelendi.
- [ ] İlgili dosyalar belirlendi.

İlgili dosyalar:

```text

```

## 3. Mevcut davranış

- [ ] Mevcut davranış anlaşıldı.
- [ ] Beklenen davranış anlaşıldı.
- [ ] Eğer bug ise reproduce adımları belirlendi.
- [ ] Eğer feature ise kullanıcı amacı belirlendi.
- [ ] Eğer refactor ise davranışın değişmemesi gerektiği netleşti.

Kısa özet:

```text

```

## 4. Risk kontrolü

- [ ] Auth etkisi var mı?
- [ ] Payment etkisi var mı?
- [ ] Database/migration etkisi var mı?
- [ ] Supabase/Firebase rule etkisi var mı?
- [ ] Kullanıcı verisi etkisi var mı?
- [ ] Privacy/camera/microphone etkisi var mı?
- [ ] AI pipeline/fallback/queue etkisi var mı?
- [ ] Production secret/config etkisi var mı?

Risk notları:

```text

```

## 5. Plan

- [ ] Küçük implementation planı hazırlandı.
- [ ] Değişecek dosyalar listelendi.
- [ ] Gereksiz dosya değiştirilmeyeceği doğrulandı.
- [ ] Yeni dependency gerekip gerekmediği belirtildi.
- [ ] Büyük refactor yapılmayacağı doğrulandı.

Plan:

```text

```

## 6. Test düşüncesi

- [ ] Manuel test adımları düşünüldü.
- [ ] Başarı senaryosu düşünüldü.
- [ ] Hata senaryosu düşünüldü.
- [ ] Regression riski düşünüldü.
- [ ] Otomatik test ihtiyacı değerlendirildi.

Test notları:

```text

```

## Final Gate

AI kod yazmadan önce şu cümleyi netleştirmelidir:

```text
I understand the task, the relevant files, the risk areas, and the smallest safe change.
```

Bu cümle net değilse kod yazılmamalıdır.