# AI Code Quality Rubric

Bu rubric, AI tarafından üretilen veya değiştirilen kodu değerlendirmek için kullanılır.

Amaç:
AI kodunu sadece “çalışıyor gibi görünüyor” seviyesinde değil; doğruluk, kapsam, güvenlik, test edilebilirlik ve ürün uyumu açısından değerlendirmektir.

---

## Scoring

Her kategori 1-5 arası puanlanır.

```text
1 = poor
2 = weak
3 = acceptable
4 = good
5 = excellent
```

---

## 1. Correctness

Kod beklenen davranışı doğru şekilde sağlıyor mu?

- 1: Yanlış veya kırık
- 2: Kısmen çalışıyor ama ciddi açıklar var
- 3: Temel davranış çalışıyor
- 4: Edge case’lerin çoğu düşünülmüş
- 5: Davranış net, sağlam ve edge case’ler iyi kapsanmış

Score:

```text

```

Notes:

```text

```

---

## 2. Scope Control

Değişiklik küçük ve sınırlı mı?

- 1: Çok fazla ilgisiz dosya değişmiş
- 2: Gereksiz büyük değişiklik var
- 3: Çoğunlukla sınırlı
- 4: İyi scope kontrolü var
- 5: Çok küçük, net ve review edilebilir

Score:

```text

```

Notes:

```text

```

---

## 3. Simplicity

Çözüm gereksiz karmaşık mı?

- 1: Aşırı karmaşık
- 2: Gereksiz abstraction var
- 3: Kabul edilebilir
- 4: Sade ve anlaşılır
- 5: En küçük güvenli çözüm

Score:

```text

```

Notes:

```text

```

---

## 4. Maintainability

Kod ileride sürdürülebilir mi?

- 1: Anlaşılması zor
- 2: Bakımı zor
- 3: Ortalama
- 4: Okunabilir ve düzenli
- 5: Mevcut mimariye çok iyi uyuyor

Score:

```text

```

Notes:

```text

```

---

## 5. Testability

Kod test edilebilir mi?

- 1: Test etmek çok zor
- 2: Test noktaları belirsiz
- 3: Manuel test edilebilir
- 4: Otomatik test için uygun
- 5: Test senaryoları net ve davranış iyi ayrılmış

Score:

```text

```

Notes:

```text

```

---

## 6. Security / Privacy

Güvenlik ve veri gizliliği açısından güvenli mi?

- 1: Kritik risk var
- 2: Belirgin riskler var
- 3: Açık risk görünmüyor ama sınırlı kontrol
- 4: Riskler düşünülmüş
- 5: Güvenlik/privacy açıkça değerlendirilmiş

Score:

```text

```

Notes:

```text

```

---

## 7. Product Fit

Kod ürün mantığı ve kullanıcı deneyimiyle uyumlu mu?

- 1: Ürün amacına ters
- 2: Kullanıcı deneyimini zayıflatıyor
- 3: Kabul edilebilir
- 4: Ürün akışına uyuyor
- 5: Ürün dili, akış ve kullanıcı güveni iyi korunmuş

Score:

```text

```

Notes:

```text

```

---

## 8. Performance

Performans açısından makul mü?

- 1: Belirgin performans sorunu var
- 2: Gereksiz maliyetli işlem var
- 3: Kabul edilebilir
- 4: Verimli
- 5: Performans etkisi düşünülmüş ve optimize edilmiş

Score:

```text

```

Notes:

```text

```

---

## 9. Documentation / Explainability

Değişiklik anlaşılır şekilde açıklanmış mı?

- 1: Ne değiştiği belirsiz
- 2: Yetersiz açıklama
- 3: Temel açıklama var
- 4: Net açıklama ve test adımları var
- 5: Riskler, testler ve bilgi kaydı ihtiyacı açıkça belirtilmiş

Score:

```text

```

Notes:

```text

```

---

## Final Score

```text
Correctness:
Scope Control:
Simplicity:
Maintainability:
Testability:
Security / Privacy:
Product Fit:
Performance:
Documentation / Explainability:

Total:
Average:
```

---

## Decision

```text
Approved
Approved with changes
Needs revision
Blocked
```

---

## AI behavior

After producing code, AI should be able to score its own output using this rubric.

For high-risk changes, another AI or reviewer should also score the output.

---

## Final rule

Good AI code is not just code that runs.

Good AI code is:

```text
correct, scoped, simple, maintainable, testable, secure, product-aligned, and explainable.
```