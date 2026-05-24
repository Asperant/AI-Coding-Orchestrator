# Code Change Checklist

Bir kod değişikliği yaptıktan sonra şunları kontrol et:

## 1. Değişiklik net mi?
- [ ] Ne değiştiğini anlayabiliyorum.
- [ ] Gereksiz dosya değişmemiş.
- [ ] Değişiklik küçük ve incelenebilir.

## 2. Çalışma riski var mı?
- [ ] Loading state bozulmadı.
- [ ] Error state bozulmadı.
- [ ] Empty state bozulmadı.
- [ ] Kullanıcı hızlı hızlı tıklarsa bozulmuyor.
- [ ] İnternet yokken ne olacağı düşünülmüş.

## 3. Veri ve güvenlik
- [ ] Kullanıcı sadece kendi verisini görebiliyor.
- [ ] Supabase/RLS etkisi düşünülmüş.
- [ ] Gizli key veya token koda yazılmamış.
- [ ] Database değişikliği varsa migration etkisi düşünülmüş.

## 4. Test
- [ ] Manuel test adımları belli.
- [ ] En az bir başarı senaryosu test edildi.
- [ ] En az bir hata senaryosu test edildi.
- [ ] Geriye dönük bozulan bir şey var mı kontrol edildi.

## 5. AI review
- [ ] Değişiklik Code-Review-Prompt ile AI’ya inceletildi.
- [ ] Kritik veya yüksek riskli bulgu varsa çözülmeden geçilmedi.