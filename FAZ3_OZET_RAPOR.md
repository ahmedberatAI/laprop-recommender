# FAZ 3: Refactoring (DRY + Modülerlik) - Özet Rapor

## Tarih: 2026-02-07

---

## 1. SSD Parsing Birleştir (DRY İhlali Giderildi)

**Sorun:** `parse_ssd_gb()` (normalize.py) ve `clean_ssd_value()` (clean.py) neredeyse aynı 27 satır aday-skorlama mantığını tekrarlıyordu.

**Çözüm:** Ortak mantık `_pick_best_ssd(text)` fonksiyonuna çıkarıldı (normalize.py). Her iki fonksiyon artık buna delege ediyor.

**Sonuç:**
- `clean_ssd_value`: 36 satır → 15 satır (**%58 azalma**)
- `parse_ssd_gb`: 27 satır → 4 satır
- Duplikasyon **tamamen ortadan kalktı**
- 382 test geçiyor, 0 regression

---

## 2. GPU Normalizasyon Pipeline Optimize Et

**Sorun:** `normalize_gpu_model()` → `get_gpu_score()` zincirinde regex'ler iki kez çalıştırılıyordu (çift `.apply()`).

**Çözüm:** `gpu_normalize_and_score(gpu_text)` fonksiyonu oluşturuldu (engine.py). `clean.py`'de tek `.apply()` çağrısı ile hem normalize hem skor tek pass'ta hesaplanıyor.

**Sonuç:**
- `clean.py`'de 2 ayrı `.apply()` → 1 tek `.apply()` + 2 lambda çıkarım
- `normalize_gpu_model` import'u `clean.py`'den kaldırıldı (unused)
- 382 test geçiyor, 0 regression

---

## 3. Magic Number'ları Sabitlere Çıkar

**Sorun:** `engine.py`'de 100+ magic number (skor eşikleri, ağırlıklar, bonus/penalty'ler, tier skorları) sabit olarak kod içine gömülmüştü.

**Çözüm:** `src/laprop/config/scoring_constants.py` oluşturuldu (145 satır). Tüm skorlama sabitleri buraya taşındı:

| Kategori | Sabit Sayısı |
|----------|-------------|
| CPU suffix/fallback | 8 |
| GPU skor sabitleri | 19 |
| Fiyat hesaplama | 3 |
| Perf karışım oranları | 6 |
| RAM/SSD tier skorları | 12 |
| Pil skoru | 12 |
| Taşınabilirlik | 7 |
| OS çarpanları | 7 |
| Dev profil | 25+ |
| Filtre eşikleri | 15 |
| **Toplam** | **~115 sabit** |

**Sonuç:**
- `engine.py`'deki gerçek skorlama magic number'ları **tamamen** `scoring_constants.py`'ye taşındı
- Kalan sayılar: regex pattern'lar, hardware model tanımlayıcıları (A770, RTX 4050, vb.) ve dict key'ler — bunlar doğası gereği magic number değil
- Tek yerden ayarlanabilir, test edilebilir yapı
- 382 test geçiyor, 0 regression

---

## 4. Design Profile Hesaplama Birleştir (Bonus)

**Sorun:** `filter_by_usage()` içindeki design GPU/RAM hint işleme mantığı inline olarak 12 satır yer kaplıyordu.

**Çözüm:** `_apply_design_hints(filtered, preferences, gpu_vals, ram_vals)` helper fonksiyonu çıkarıldı. `filter_by_usage` design bloğu 4 satıra indi.

**Sonuç:**
- Daha okunabilir `filter_by_usage` fonksiyonu
- 382 test geçiyor, 0 regression

---

## Başarı Kriterleri Kontrolü

| Kriter | Hedef | Sonuç | Durum |
|--------|-------|-------|-------|
| SSD kod azaltımı | ≥%50 | %58 | ✅ |
| GPU tek pass | Evet | Evet | ✅ |
| Magic number engine.py'de | <5 | ~0 (scoring) | ✅ |
| Tüm testler geçiyor | 382 | 382 passed | ✅ |
| Coverage ≥%60 | %60 | %63.4 | ✅ |

---

## Coverage Detayı

| Modül | Önceki | Sonrası |
|-------|--------|---------|
| engine.py | %81.6 | %84.7 |
| normalize.py | %92.1 | %92.2 |
| clean.py | %85.2 | %86.4 |
| scoring_constants.py | - | %100 |
| **Toplam** | **%61.6** | **%63.4** |

---

## Değişen Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `src/laprop/config/scoring_constants.py` | **YENİ** - Tüm skorlama sabitleri |
| `src/laprop/recommend/engine.py` | Magic number → sabit referans, `gpu_normalize_and_score()`, `_apply_design_hints()` |
| `src/laprop/processing/normalize.py` | `_pick_best_ssd()` ortak fonksiyon, `parse_ssd_gb()` sadeleştirildi |
| `src/laprop/processing/clean.py` | `clean_ssd_value()` → `_pick_best_ssd()` delegasyonu, GPU tek pass |
| `src/laprop/__init__.py` | `_pick_best_ssd` export eklendi |
