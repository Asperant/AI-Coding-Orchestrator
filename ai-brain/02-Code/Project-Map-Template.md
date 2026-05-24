# Project Map Template

Bu şablon, her yazılım projesi için AI’ın projeyi hızlı ve doğru anlamasını sağlamak amacıyla kullanılır.

Amaç:
AI’ın kör şekilde kod yazmasını engellemek; hangi klasörün ne işe yaradığını, hangi görevde hangi dosyalara bakılması gerektiğini ve hangi alanların riskli olduğunu netleştirmektir.

Bir projede bu şablondan üretilen dosya genelde şu konumda tutulur:

```text
docs/project-map.md
```

---

## 1. Project overview

Bu proje ne yapıyor?

```text

```

---

## 2. Tech stack

Frontend:

```text

```

Backend:

```text

```

Database / storage:

```text

```

AI / ML:

```text

```

Other tools:

```text

```

---

## 3. Main folders

```text
folder/path -> purpose
```

Örnek:

```text
src/pages -> app screens and routes
src/components -> reusable UI components
src/services -> external services and API clients
src/context -> global state providers
server -> backend server
docs -> project documentation
```

---

## 4. Key files by task

AI bu bölümden hangi görevde önce hangi dosyalara bakacağını anlar.

### Feature work

```text

```

### Bug fixing

```text

```

### AI pipeline

```text

```

### Auth / user data

```text

```

### Database / storage

```text

```

### State management

```text

```

### UI / screens

```text

```

### Product copy

```text

```

### Testing

```text

```

### Setup / operations

```text

```

---

## 5. Active flows

Bu projede aktif olan ana akışlar.

Örnek:

```text
Home -> Permission -> Questions -> Analysis -> Result
```

Akışlar:

```text

```

---

## 6. Legacy or confusing areas

AI’ın karıştırmaması gereken eski, yarım, değişmiş veya isim olarak yanıltıcı alanlar.

```text

```

---

## 7. High-risk areas

Bu projede dikkatli dokunulması gereken alanlar.

```text
area -> why risky -> files
```

Örnek:

```text
camera permission -> privacy and user trust risk -> src/context/FaceTrackingContext.jsx
AI fallback -> result flow can break -> src/services/aiService.js
database rules -> user data exposure risk -> firebase rules / supabase policies
```

---

## 8. Do not change casually

AI’ın açık onay olmadan değiştirmemesi gereken dosya veya alanlar.

```text

```

---

## 9. Test focus

Bu projede her önemli değişiklikte kontrol edilmesi gereken test alanları.

```text

```

---

## 10. Notes for AI

Bu projede AI’ın özellikle hatırlaması gereken kısa notlar.

```text

```