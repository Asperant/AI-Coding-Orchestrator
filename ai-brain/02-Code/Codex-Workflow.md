# Codex Workflow

Codex ile kod yazarken standart akışım:

## 1. Görevi netleştir

Önce şu prompt kullanılır:

[[Codex-Task-Prompt]]

Amaç:
- Codex dosyaları incelesin
- mevcut yapıyı anlasın
- küçük plan çıkarsın
- hangi dosyaları değiştireceğini söylesin

## 2. Sadece küçük parçayı uygulat

Plan geldikten sonra sadece ilk küçük parçayı uygulat.

Kural:
- aynı anda büyük rewrite yok
- ilgisiz dosya değişikliği yok
- gereksiz dependency yok

## 3. Diff review yaptır

Kod değişikliğinden sonra şu prompt kullanılır:

[[Codex-Diff-Review-Prompt]]

Amaç:
- bug var mı?
- scope dışına çıkmış mı?
- güvenlik riski var mı?
- test eksik mi?

## 4. Checklist ile kontrol et

Sonra şu checklist kullanılır:

[[Code-Change-Checklist]]

## 5. Gerekirse notu AI-Brain’e kaydet

Eğer bu işten tekrar kullanılabilir bir bilgi çıktıysa, AI-Brain’e kaydedilir.

Örnek:
- yeni prompt
- mimari karar
- hata çözümü
- test checklisti
- ürün kararı