
Bu checklist, AI bir kod değişikliği yaptıktan sonra kullanılır.

Amaç:
AI’ın yaptığı değişikliği körlemesine kabul etmemek; scope, risk, test ve kalite açısından tekrar kontrol etmektir.

## 1. Değişiklik özeti

- [ ] Değişen dosyalar listelendi.
- [ ] Her dosyada ne değiştiği açıklandı.
- [ ] Değişikliğin amacı açıklandı.
- [ ] Beklenen davranış tekrar belirtildi.

Değişen dosyalar:

```text

```

Kısa özet:

```text

```

## 2. Scope kontrolü

- [ ] Sadece planlanan dosyalar değişti.
- [ ] İlgisiz dosyalara dokunulmadı.
- [ ] Gereksiz formatting değişikliği yapılmadı.
- [ ] Büyük refactor yapılmadı.
- [ ] Yeni dependency eklenmediyse açıkça belirtildi.
- [ ] Yeni dependency eklendiyse gerekçesi yazıldı.

Scope notları:

```text

```

## 3. Davranış kontrolü

- [ ] Beklenen davranış karşılandı.
- [ ] Eski davranış gereksiz yere bozulmadı.
- [ ] Loading state düşünüldü.
- [ ] Error state düşünüldü.
- [ ] Empty state düşünüldü.
- [ ] Rapid repeated action durumu düşünüldü.
- [ ] Network/server failure durumu düşünüldü.

Davranış notları:

```text

```

## 4. Risk kontrolü

- [ ] Auth riski yok veya açıklandı.
- [ ] Payment riski yok veya açıklandı.
- [ ] Database/migration riski yok veya açıklandı.
- [ ] Supabase/Firebase rule riski yok veya açıklandı.
- [ ] Kullanıcı verisi riski yok veya açıklandı.
- [ ] Privacy/camera/microphone riski yok veya açıklandı.
- [ ] AI pipeline/fallback/queue riski yok veya açıklandı.
- [ ] Secret/config sızıntısı yok.

Risk notları:

```text

```

## 5. Test kontrolü

- [ ] Manuel test adımları verildi.
- [ ] Başarı senaryosu belirtildi.
- [ ] Hata senaryosu belirtildi.
- [ ] Regression riski belirtildi.
- [ ] Otomatik test gerekiyorsa önerildi.
- [ ] Test çalıştırılamadıysa nedeni açıklandı.

Test notları:

```text

```

## 6. Öğrenme kontrolü

- [ ] Bu değişiklikten tekrar kullanılabilir bilgi çıktı mı?
- [ ] Teknik karar kaydı gerekiyor mu?
- [ ] Bug fix kaydı gerekiyor mu?
- [ ] Lessons Learned güncellenmeli mi?
- [ ] AGENTS.md veya docs güncellenmeli mi?

Kaydedilecek bilgi:

```text

```

## Final Gate

AI kod değişikliğinden sonra şu cümleyi netleştirmelidir:

```text
The change is scoped, reviewed, testable, and any reusable knowledge has been identified.
```

Bu cümle net değilse değişiklik tamamlanmış sayılmamalıdır.