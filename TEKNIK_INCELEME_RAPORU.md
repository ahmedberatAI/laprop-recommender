# Laptop Recommender (Laprop) - Kapsamli Teknik Inceleme Raporu

**Tarih:** 2026-02-06
**Proje:** recommender_2 (Laprop Recommender)
**Inceleme Yapan:** Claude Code Technical Auditor
**Versiyon:** 0.0.0 (pyproject.toml)

---

## YONETICI OZETI

Laprop, Turkiye pazarindaki laptop fiyat/performans verilerini web scraping ile toplayip, kullanici tercihlerine gore skor tabanli oneri ureten bir Python projesidir. Proje fonksiyonel olarak calisan, detayli bir skorlama motoruna sahiptir; ancak mimari dagilma, test eksikligi, guvenlik aciklari ve dokumantasyon yetersizligi gibi onemli teknik borclar tasimaktadir.

**Genel Puan: 5.5 / 10**

---

## 1. PROJE GENELI ANALIZ

### 1.1 Proje Yapisi ve Dosya Organizasyonu

```
recommender_2/
+-- src/laprop/           # Ana paket (iyi yapilandirilmis)
|   +-- app/              # CLI + main entry
|   +-- config/           # Ayarlar, kurallar, benchmark'lar
|   +-- ingestion/        # Veri toplama orkestrasyonu
|   +-- processing/       # Temizleme, normalizasyon, dogrulama
|   +-- recommend/        # Oneri motoru
|   +-- storage/          # Depo yonetimi
|   +-- utils/            # Yardimci araclar
+-- amazon_scraper.py     # KOK DIZINDE - paket disinda
+-- incehesap_scraper.py  # KOK DIZINDE - paket disinda
+-- vatan_scraper.py      # KOK DIZINDE - paket disinda
+-- price_collect.py      # KOK DIZINDE - paket disinda
+-- streamlit_app.py      # KOK DIZINDE - paket disinda
+-- tests/                # Minimum test (3 dosya)
+-- data/                 # CSV ciktilari
+-- raw/                  # Ham HTML (1,386 dosya)
```

**Sorunlar:**
- Scraper dosyalari (`amazon_scraper.py`, `incehesap_scraper.py`, `vatan_scraper.py`) kok dizinde duruyor, `src/laprop/ingestion/sources/` altindaki stub dosyalar ise neredeyse bos (87-91 byte). Scraper'lar paket mimarisine entegre edilmemis.
- `streamlit_app.py` kok dizinde - `src/laprop/app/` altinda olmali.
- `laprop/__init__.py` (774 byte) kok dizinde ayri bir modul olarak var - `src/laprop/__init__.py` ile karisiklik yaratir.
- `raw/` dizini 1,386 HTML dosyasi iceriyor (toplam 1,665 dosya) - `.gitignore` ile dislanmis olsa da lokal disk alanini gereksiz kullaniyor.
- 7 adet Markdown rapor dosyasi kok dizinde (CLAUDE_CODE_ANALYSIS_REPORT.md, CURRENT_STATUS.md vb.) - organizasyonsuz.

### 1.2 Kullanilan Teknolojiler

| Teknoloji | Kullanim | Versiyon |
|-----------|----------|----------|
| Python | Ana dil | >= 3.9 |
| Pandas | Veri isleme | pinlenmemis |
| NumPy | Sayisal hesaplamalar | pinlenmemis |
| Streamlit | Web UI | pinlenmemis |
| BeautifulSoup4 | HTML parsing | pinlenmemis |
| Requests | HTTP istemci | pinlenmemis |
| urllib3 | HTTP alt katman | pinlenmemis |

**Kritik Sorun:** `requirements.txt` hicbir versiyon pinlemiyor:
```
streamlit
pandas
numpy
requests
beautifulsoup4
urllib3
```
Bu, farkli ortamlarda farkli davranislara yol acabilir (reproducibility sorunu).

### 1.3 Kod Mimarisi ve Design Pattern'ler

**Olumlu:**
- `src/laprop/` altinda katmanli mimari (config / ingestion / processing / recommend / storage / app)
- Tek sorumluluk prensibine kismen uygun modul ayirimi
- Konfigurasyonlar (`rules.py`, `settings.py`) ayri tutulmus

**Olumsuz:**
- **God Module Anti-Pattern:** `cli.py` tek dosyada 47KB (tahminen ~800+ satir), NLP parsing, kullanici etkilesimi, simülasyon ve goruntuleme islevlerini bir arada barindiriyor.
- **Flat Public API Anti-Pattern:** `src/laprop/__init__.py` (228 satir) 90+ private fonksiyonu (`_cpu_suffix`, `_has_dgpu`, `_score_ssd_candidate` vb.) `__all__`'a ekleyerek dis dunyaya sunuyor. Private fonksiyonlar (`_` on-ek) public API'de olmamali.
- **Scraper'lar paket disinda:** `ingestion/sources/` stub'lari bos, gercek scraper'lar kok dizinde ayri script olarak duruyor.
- **Pickle tabanli cache:** `laptop_cache.pkl` guvenlik riski (arbitrary code execution) ve fragil (Python versiyon uyumsuzlugu).

### 1.4 Dependency Yonetimi

`pyproject.toml` minimal:
```toml
[project]
name = "laprop"
version = "0.0.0"
requires-python = ">=3.9"
```
- `dependencies` alani yok - `pip install .` calistiginda bagimliliklar kurulmaz.
- `requirements.txt` var ama versiyonlar pinlenmemis.
- Dev/test bagimliliklari (pytest) hicbir yerde tanimli degil.

---

## 2. KOD KALITESI DEGERLENDIRMESI

### 2.1 Kod Okunabilirligi ve Maintainability

**Olumlu:**
- Fonksiyon ve degisken isimleri genellikle aciklayici (`get_cpu_score`, `normalize_gpu_model`, `filter_by_usage`)
- Turkce yorumlar hedef kitleye uygun
- `safe_print()` ile encoding sorunlarina karsi onlem alinmis

**Olumsuz:**

1. **Bare except kullanimi (Kritik):**

```python
# src/laprop/processing/read.py:91-92
except:
    pass
```
```python
# src/laprop/app/cli.py:103
except:
    pass
```
```python
# src/laprop/processing/read.py:162-163
except:
    pass
```
```python
# src/laprop/app/cli.py:710-711
except:
    pass
```

En az 6 yerde bare `except: pass` var. Bu, `KeyboardInterrupt`, `SystemExit`, `MemoryError` gibi kritik hatalari bile yutarak debug'u imkansizlastirir.

**Olmasi gereken:**
```python
except Exception as e:
    logger.warning(f"Cache yuklenemedi: {e}")
```

2. **Magic Number'lar:**

```python
# src/laprop/recommend/engine.py:166
score += min(1.0, ram / p['min_ram']) * 20   # 20 puan
parts += 20
```
```python
# src/laprop/recommend/engine.py:300
mid_bonus = max(0, (1 - distance_from_mid) * 4)
price_score = min(100, price_score * 0.95 + mid_bonus)
```

Skorlama motorundaki sabit degerler (20, 15, 4, 0.95, 25 vb.) sabitlere cikarilmamis. Herhangi bir degisiklik icin 776 satirlik dosyayi taramak gerekiyor.

3. **Asiri uzun fonksiyonlar:**

| Dosya | Fonksiyon | Satir Sayisi (tahmini) |
|-------|-----------|------------------------|
| `engine.py` | `calculate_score()` | ~210 satir |
| `engine.py` | `compute_dev_fit()` | ~105 satir |
| `engine.py` | `filter_by_usage()` | ~120 satir |
| `clean.py` | `clean_data()` | ~250 satir |
| `cli.py` | `get_user_preferences()` | ~130 satir |

Bu fonksiyonlar "Extract Method" refactoring ile parcalanmali.

### 2.2 Kod Tekrarlari (DRY Ihlalleri)

1. **`parse_ssd_gb()` ve `clean_ssd_value()` neredeyse ayni:**

`src/laprop/processing/normalize.py:380-406` (`parse_ssd_gb`):
```python
def parse_ssd_gb(title: str) -> Optional[int]:
    s = _normalize_title_text(title)
    candidates: List[Tuple[int, int]] = []
    for gb, start, end in _extract_capacity_candidates(s):
        if not _is_valid_ssd_value(gb): continue
        score = _score_ssd_candidate(s, start, end, gb)
        candidates.append((score, gb))
    for gb, start, end in _extract_no_unit_ssd_candidates(s):
        if gb not in SSD_COMMON_GB: continue
        score = _score_ssd_candidate(s, start, end, gb) + 3
        candidates.append((score, gb))
    # ... ayni secim mantigi
```

`src/laprop/processing/clean.py:63-98` (`clean_ssd_value`):
```python
def clean_ssd_value(storage_str):
    s = _normalize_title_text(storage_str)
    candidates: List[Tuple[int, int]] = []
    for gb, start, end in _extract_capacity_candidates(s):
        if not _is_valid_ssd_value(gb): continue
        score = _score_ssd_candidate(s, start, end, gb)
        candidates.append((score, gb))
    for gb, start, end in _extract_no_unit_ssd_candidates(s):
        if gb not in SSD_COMMON_GB: continue
        score = _score_ssd_candidate(s, start, end, gb) + 3
        candidates.append((score, gb))
    # ... ayni secim mantigi
```

Iki fonksiyon neredeyse birebir ayni. Tek bir `_pick_best_ssd(text)` fonksiyonuna refactor edilmeli.

2. **GPU normalizasyonu iki kez yapiliyor:**

- `normalize_gpu()` (normalize.py:168) - basliktan GPU cikarir
- `normalize_gpu_model()` (normalize.py:6) - GPU metnini normalize eder
- Sonra `clean_data()` icinde:
  ```python
  df['gpu'] = df.apply(lambda r: normalize_gpu(r.get('name'), r.get('brand')), axis=1)
  df['gpu_norm'] = df['gpu'].apply(normalize_gpu_model)
  ```
  `normalize_gpu` -> `normalize_gpu_model` zinciri, regex islemlerini iki kez calistiriyor.

3. **`_prompt_design_details()` ve `parse_design_profile_from_text()` ayni GPU hint / RAM hint mantigi:**

```python
# cli.py:67-78 (_prompt_design_details)
if any(k in chosen_keys for k in ['3d']): gpu_hint = 'high'
elif any(k in chosen_keys for k in ['video', 'cad']): gpu_hint = 'mid'
else: gpu_hint = 'low'

# cli.py:433-440 (parse_design_profile_from_text)
if '3d' in profiles: gpu_hint = 'high'
elif any(k in profiles for k in ['video', 'cad']): gpu_hint = 'mid'
else: gpu_hint = 'low'
```

### 2.3 Naming Conventions

- Genel olarak PEP 8 uyumlu: snake_case fonksiyonlar, UPPER_CASE sabitler
- Tutarsizliklar:
  - `_normalize_title_text` vs `normalize_cpu` (bazi private, bazilari public)
  - Turkce-Ingilizce karisik docstring'ler: `"""Gelismis CPU skorlama"""` + `"""Normalize GPU from product title"""` ayni dosyada
  - Degisken isimleri bazen tek harf: `s`, `t`, `m`, `p` (okunabilirligi dusurur)

### 2.4 Yorum ve Dokumantasyon Kalitesi

- `cli.py:753-796` satirlarinda 40+ satirlik "ALGORITMA NOTLARI" yorum blogu var - bu bir comment, kod degil. Ya dokumanasyona tasinmali ya da gercek islevsellige donusturulmeli.
- Bircok fonksiyonun docstring'i eksik veya tek satirlik
- Type hint kullanimi tutarsiz: bazi fonksiyonlar tam tip notu var (`def parse_screen_size(value: Any) -> Optional[float]`), bazilari hic yok (`def clean_price(price_str)`)

---

## 3. FONKSIYONELLIK ANALIZI

### 3.1 Mevcut Ozellikler ve Calisma Durumlari

| Ozellik | Durum | Not |
|---------|-------|-----|
| Web scraping (Amazon) | Calisiyor | 33KB script, kok dizinde |
| Web scraping (Incehesap) | Calisiyor | 41KB script, kok dizinde |
| Web scraping (Vatan) | Calisiyor | 34KB script, kok dizinde |
| Veri temizleme/normalizasyon | Calisiyor | Kapsamli regex parsing |
| Skorlama motoru | Calisiyor | 5 kullanim profili |
| CLI arayuz | Calisiyor | Interaktif terminal |
| Streamlit Web UI | Calisiyor | Temel islevsellik |
| Simulasyon sistemi | Calisiyor | 100 senaryo |
| CSV export | Calisiyor | Sonuc indirme |

### 3.2 Eksik veya Yarim Kalan Ozellikler

1. **Benchmark entegrasyonu eksik:** `benchmarks.py` benchmark CSV dosyalarini okumak icin altyapi sunuyor ama dosyalar (`bench_gpu.csv`, `bench_cpu.csv`) mevcut degil ve skorlama motorunda kullanilmiyor. Tum GPU/CPU skorlamasi hardcoded dictionary'lerle yapiliyor.

2. **Ingestion source stub'lari bos:**
   ```python
   # src/laprop/ingestion/sources/vatan.py (87 byte)
   # Icerik: sadece bos dosya veya minimal placeholder
   ```
   Gercek scraper mantigi kok dizindeki dosyalarda.

3. **`explain.py` bos:**
   ```python
   # src/laprop/recommend/explain.py (59 byte)
   # Icerik: bos veya placeholder
   ```
   Oneri aciklamasi modulu implement edilmemis.

4. **`merge.py` bos:**
   ```python
   # src/laprop/processing/merge.py (53 byte)
   ```

5. **`validate_record()` cok sinirli:** Sadece RAM > 128 ve ekran boyutu araligi kontrolu yapiyor. Fiyat mantigi, CPU/GPU tutarliligi, URL format dogrulamasi yok.

### 3.3 Hata Yonetimi ve Edge Case'ler

**Kritik sorunlar:**

1. **Bare except: pass pattern'i** (6+ yer) - yukarida detaylandirildi.

2. **`get_recommendations` icinde `iterrows()` kullanimi:**
   ```python
   # engine.py:736-739
   scores, breakdowns = [], []
   for _, row in filtered.iterrows():
       score, breakdown = calculate_score(row, preferences)
   ```
   `iterrows()` her satir icin Series olusturur, buyuk veri setlerinde cok yavas.

3. **`filter_by_usage` icinde gevsetme mantigi tutarsiz:**
   ```python
   # engine.py:651-662
   if len(filtered) < 5 and len(df) > 5:
       if usage_key == 'gaming':
           return df[df['gpu_score'] >= 5.0]
   ```
   Bu gevsetme, tum onceki filtreleri (butce, RAM, SSD) bypass ediyor - kullanici beklemeyecegi sonuclar alabilir.

4. **`_filter_sources` icinde potansiyel performans sorunu:**
   ```python
   # streamlit_app.py:62-63
   mask = pd.Series([False] * len(df), index=df.index)
   for src in selected:
       mask = mask | urls.str.contains(pattern, na=False)
   ```
   Her dongude yeni Series olusturuluyor. `|=` operatoru kullanilmali.

### 3.4 Kullanici Deneyimi (UX)

**Streamlit UI:**
- Temiz sidebar layout
- Kullanim profili secimi acik ve anlasilir
- Turkce arayuz hedef kitleye uygun
- Follow-up sorulari (oyun secimi, tasarim profili) iyi dusunulmus

**Eksikler:**
- Yukleme durumu gostergesi yeterli degil (sadece spinner)
- Sonuclarda sayfalama yok - 50 sonuc tek tabloda
- Hata mesajlari kullaniciya yeterli rehberlik saglamiyor
- Karanlık tema / tema secenegi yok
- Grafik/chart gorsellestirme eksik (fiyat dagilimi, skor karsilastirmasi)

---

## 4. PERFORMANS VE OPTIMIZASYON

### 4.1 Performans Darbogazlari

1. **`iterrows()` kullanimi (Yuksek etki):**

   `engine.py:736-739` ve `engine.py:749-758`'de iki kez `iterrows()` kullaniliyor. Pandas dokumantasyonu bunu performans icin kesinlikle onermez.

   **Mevcut:**
   ```python
   for _, row in filtered.iterrows():
       score, breakdown = calculate_score(row, preferences)
       scores.append(score)
   ```

   **Onerilen:** `df.apply()` veya vektorize hesaplama.

2. **`clean_data()` icinde 7 kez `.apply(lambda)` cagiriliyor:**

   ```python
   df['brand'] = df['name'].apply(extract_brand)                    # 1
   df['cpu'] = df.apply(lambda r: normalize_cpu(...), axis=1)       # 2
   df['gpu'] = df.apply(lambda r: normalize_gpu(...), axis=1)       # 3
   df['gpu'] = df['gpu'].apply(lambda x: ...)                       # 4
   ram_from_title = title_series.apply(parse_ram_gb)                 # 5
   ssd_from_title = title_series.apply(parse_ssd_gb)                # 6
   df['os'] = df.apply(detect_os, axis=1)                           # 7
   ```

   Her `.apply()` Python-level dongu calistirir. Regex islemleri icin `str.extract()` ve vektorize islemler kullanilabilir.

3. **Ram/SSD swap mantigi O(n) dongu:**

   ```python
   # clean.py:239
   for idx in df.index:
       ram_val = new_ram.at[idx]
       ssd_val = new_ssd.at[idx]
       # ... 30+ satir islem
   ```

   Bu dongu vektorize edilmeli.

4. **Pickle cache potansiyel sorun:**

   `load_data()` her cagrildiginda 3 CSV okuyup birlestiriyor, sonra pickle'a dump ediyor. Buyuk veri setlerinde yavas. Parquet veya SQLite daha verimli olur.

### 4.2 Memory Riski

- `raw/` dizininde 1,386 HTML dosyasi var. Scraper'lar butun sayfalari bellege aliyorsa potansiyel sorun.
- `laptop_cache.pkl` tum DataFrame'i pickle'a dump ediyor - buyuk veri setlerinde bellek tukenmesi mumkun.
- `_iter_existing_keys()` tum mevcut anahtarlari bir `Set`'e yukluyor (`repository.py:42`).

### 4.3 Lazy Loading Firsatlari

- Benchmark dosyalari (`benchmarks.py:83-84`) modul import aninda yukleniyor:
  ```python
  GPU_BENCH = _safe_load_bench(BENCH_GPU_PATH)
  CPU_BENCH = _safe_load_bench(BENCH_CPU_PATH)
  ```
  Kullanilmasa bile her import'ta disk I/O yapiliyor.

- `__init__.py` 90+ sembol import ediyor - modul import suresi gereksiz uzun.

---

## 5. GUVENLIK DEGERLENDIRMESI

### 5.1 Kritik Guvenlik Aciklari

1. **Pickle Deserialization (KRITIK):**

   ```python
   # read.py:75-76
   with open(CACHE_FILE, 'rb') as f:
       df = pickle.load(f)
   ```

   `pickle.load()` arbitrary code execution riski tasir. Eger bir saldirgan `laptop_cache.pkl` dosyasini degistirirse, rastgele kod calistirilabilir.

   **Cozum:** `pickle` yerine `parquet`, `json` veya `feather` formati kullanilmali.

2. **Subprocess Injection Riski (ORTA):**

   ```python
   # orchestrator.py:56-64
   cmd = [sys.executable, str(script_path)]
   if name == "amazon":
       cmd += ["--output", output_paths["amazon"]]
   ```

   `script_path` degeri `SCRAPERS` dictionary'sinden geliyor ve kullanicidan alinmiyor, ancak `output_paths` degeri dosya sistemi yolunu iceriyor. Path traversal riski dusuk ama var.

3. **Streamlit'te subprocess cagrisi (YUKSEK):**

   ```python
   # streamlit_app.py:351-358
   result = subprocess.run(
       [sys.executable, "recommender.py", "--run-scrapers"],
       cwd=str(REPO_ROOT),
       capture_output=True,
       text=True,
   )
   ```

   `ALLOW_SCRAPE_UI` env var'i ile korunmus olsa da, bu bir web uygulamasindan subprocess calistirmaktir. Production'da kesinlikle kapatilmali.

4. **Bare except: pass guvenlik riski:**

   ```python
   # read.py:91-92
   except:
       pass
   ```

   Pickle yuklemesindeki hata sessizce yutuluyuor. Bozuk veya manipule edilmis cache dosyasi farkedilmeyebilir.

### 5.2 Input Validasyon Eksiklikleri

- `clean_price()` icinde bare `except:` kullanimi (`clean.py:116-117`)
- Scraper ciktilari dogrudan CSV'ye yaziliyor, sanitizasyon sinirli
- URL dogrulama yok - scraper'lar herhangi bir URL'den veri cekebilir

### 5.3 Hassas Veri Yonetimi

- `.gitignore` `*.csv`, `*.pkl`, `*.jsonl` dosyalarini disliyor (iyi)
- Log dosyalari da dislanmis (iyi)
- Ancak `.epey_profile/` (tarayici profili) git'te gorulmus (git status'ta `D` - silinmis ama gecmiste commit edilmis olabilir)

---

## 6. TEST KAPSAMI

### 6.1 Mevcut Test Durumu

| Test Dosyasi | Icerik | Kapsam |
|-------------|--------|--------|
| `test_scraper_smoke.py` | Scraper `--help` flag'i + parse fixture | Minimal |
| `test_screen_size.py` | `parse_screen_size()` icin 12 test case | Tek fonksiyon |
| `conftest.py` | Stdio encoding ayari | Fixture |

**Toplam: 3 test dosyasi, ~15 test case**

### 6.2 Test Coverage Analizi (Tahmini)

| Modul | Tahmini Coverage | Risk |
|-------|-----------------|------|
| `engine.py` (776 satir) | **%0** | KRITIK |
| `clean.py` (394 satir) | **%0** | KRITIK |
| `normalize.py` (485 satir) | **~%3** (sadece parse_screen_size) | KRITIK |
| `cli.py` (~800 satir) | **%0** | YUKSEK |
| `read.py` (166 satir) | **%0** | YUKSEK |
| `repository.py` (195 satir) | **%0** (self-test var ama pytest'te degil) | ORTA |
| `rules.py` (257 satir) | N/A (konfigürasyon) | DUSUK |
| `scenarios.py` (104 satir) | N/A (veri) | DUSUK |

**Genel tahmini coverage: ~%2-3**

### 6.3 Kritik Eksik Testler

**Hemen yazilmasi gerekenler:**

1. **Skorlama motoru testleri:**
   - `get_cpu_score()`: Bilinen CPU isimleri icin beklenen skorlar
   - `get_gpu_score()`: RTX/GTX/MX/RX/Apple M serileri
   - `calculate_score()`: Farkli kullanim profilleri icin deterministik sonuclar
   - `compute_dev_fit()`: Dev alt profilleri icin dogrulama
   - `filter_by_usage()`: Her kullanim tipi icin filtreleme davranisi
   - `get_recommendations()`: End-to-end oneri pipeline'i

2. **Veri temizleme testleri:**
   - `clean_ram_value()`: "16GB", "8 GB", "8GB + 8GB = 16GB", "DDR4 8GB" vb.
   - `clean_ssd_value()`: "512GB SSD", "1TB NVMe", "256 SSD" vb.
   - `clean_price()`: "34.999 TL", "34999", "34,999", "abc" vb.
   - `extract_brand()`: Bilinen marka isimleri + edge case'ler
   - `clean_data()`: Bozuk veri iceren DataFrame ile entegrasyon testi

3. **Normalizasyon testleri:**
   - `normalize_cpu()`: Intel/AMD/Apple M cesitliligi
   - `normalize_gpu()`: RTX/GTX/MX/RX/Arc/Apple M GPU'lar
   - `parse_ram_gb()`: Baslik metinlerinden RAM cikarimi
   - `parse_ssd_gb()`: Baslik metinlerinden SSD cikarimi

4. **NLP fonksiyon testleri:**
   - `detect_budget()`: "30-50k", "max 40 bin", "35000 TL" vb.
   - `detect_usage_intent()`: Anahtar kelimelerle kullanim tespiti
   - `fuzzy_match_game_titles()`: Oyun ismi eslestirme

---

## 7. ERISILEBILIRLIK (ACCESSIBILITY)

### 7.1 Streamlit UI Erisilebilirligi

Streamlit framework'u temel erisilebilirlik ozelliklerini saglar:
- Semantic HTML ciktisi
- Form elementleri icin label'lar
- Klavye navigasyonu (Streamlit default)

**Eksikler:**
- Ozel ARIA attribute'lari eklenmemis
- Renk kontrasti kontrolu yapilmamis (Streamlit default temasina bagimli)
- Screen reader icin ozel optimizasyon yok
- Sonuc tablosunda erisilebilirlik ozellikleri sinirli
- High contrast mode destegi yok

### 7.2 CLI Erisilebilirligi

- `safe_print()` encoding sorunlarini cozuyor (Windows Turkce locale icin iyi)
- Emoji kullanimi (`safe_print`) screen reader'larda sorun yaratabilir
- Input prompt'lari aciklayici

---

## 8. RESPONSIVE DESIGN & MOBIL UYUMLULUK

### 8.1 Streamlit Layout

```python
# streamlit_app.py:371
left_col, right_col = st.columns([2.4, 1.2], gap="large")
```

- `layout="wide"` kullanimi masaustu icin iyi
- Sidebar kullanimi mobilde Streamlit tarafindan otomatik handle ediliyor
- Sabit kolon oranlari (2.4:1.2) dar ekranlarda sorun yaratabilir

### 8.2 Cross-Browser Uyumluluk

- Streamlit tabanlı oldugu icin modern tarayicilarda calismali
- Ancak test edilmemis

---

## 9. ONCELIKLI GELISTIRME ONERILERI

### 9.1 KRITIK Oncelik

#### K1: Pickle Cache'i Kaldir
- **Oncelik:** KRITIK
- **Etki:** Guvenlik acigini kapatir
- **Uygulama:**
  1. `read.py` icindeki `pickle.load/dump` cagrilarini kaldir
  2. Parquet formati kullan: `df.to_parquet()` / `pd.read_parquet()`
  3. `requirements.txt`'e `pyarrow` ekle

#### K2: Bare except: pass Kaldir
- **Oncelik:** KRITIK
- **Etki:** Gizli hatalari ortaya cikarir, debug kolaylastirir
- **Uygulama:** Tum `except: pass` satirlarini `except Exception as e: logger.warning(...)` ile degistir

#### K3: Test Suite Olustur
- **Oncelik:** KRITIK
- **Etki:** Regression onleme, refactoring guvenligi
- **Uygulama:**
  1. `pytest` + `pytest-cov` ekle
  2. Skorlama motoru icin unit testler yaz
  3. Veri temizleme icin unit testler yaz
  4. CI/CD pipeline'a entegre et

### 9.2 YUKSEK Oncelik

#### Y1: Requirements Pinleme
- **Oncelik:** YUKSEK
- **Etki:** Reproducible builds
- **Uygulama:**
  1. `pip freeze > requirements.lock`
  2. `requirements.txt`'e minimum versiyonlar ekle: `pandas>=2.0,<3.0`
  3. `pyproject.toml`'a `dependencies` alani ekle

#### Y2: `__init__.py` Temizligi
- **Oncelik:** YUKSEK
- **Etki:** API yuzeyini kucultme, import hizlandirma
- **Uygulama:**
  1. Private fonksiyonlari (`_` on-ek) `__all__`'dan cikar
  2. Sadece public API'yi export et
  3. Lazy import kullan

#### Y3: Logging Sistemi Ekle
- **Oncelik:** YUKSEK
- **Etki:** Debug, monitoring, production sorun giderme
- **Uygulama:**
  1. `logging` modulu kullan (`safe_print` yerine)
  2. Log seviyeleri: DEBUG/INFO/WARNING/ERROR
  3. Dosya + konsol handler
  4. Structured logging (JSON)

### 9.3 ORTA Oncelik

#### O1: Scraper'lari Paket Icine Tasi
- **Oncelik:** ORTA
- **Etki:** Kod organizasyonu, import tutarliligi
- **Uygulama:**
  1. `src/laprop/ingestion/sources/` altina tasi
  2. Ortak `BaseScraper` sinifi olustur
  3. Konfigurasyonu `config/` altina tasi

#### O2: cli.py Parcala
- **Oncelik:** ORTA
- **Etki:** Maintainability
- **Uygulama:**
  1. NLP fonksiyonlarini `src/laprop/nlp/` altina tasi
  2. Simulasyon kodunu `src/laprop/simulation/` altina tasi
  3. CLI etkilesimini `src/laprop/app/cli.py`'de birak

#### O3: DRY Refactoring
- **Oncelik:** ORTA
- **Etki:** Kod tekrarini azaltir
- **Uygulama:**
  1. `parse_ssd_gb()` ve `clean_ssd_value()` birlestir
  2. GPU hint/RAM hint mantigi tek fonksiyona cikar
  3. Design profile hesaplama tek yerden yapilsin

### 9.4 DUSUK Oncelik

#### D1: Streamlit UI Iyilestirmeleri
- Grafik/chart ekleme (Plotly/Altair)
- Sayfalama
- Karanlik tema
- Karsilastirma modu

#### D2: API Dokumantasyonu
- Sphinx/MkDocs ile otomatik dokumantasyon
- Type hint tamamlama
- Ornek kullanim dokumleri

---

## 10. REFACTORING ONERILERI

### 10.1 engine.py Yeniden Yapilandirma

**Mevcut:** Tek dosyada 776 satir, 12+ fonksiyon, karisik sorumluluklar.

**Onerilen yapi:**
```
src/laprop/recommend/
+-- engine.py          # get_recommendations (orkestrasyion)
+-- scoring.py         # calculate_score, get_dynamic_weights
+-- dev_scoring.py     # compute_dev_fit, _cpu_suffix, _has_dgpu
+-- hw_scoring.py      # get_cpu_score, get_gpu_score
+-- filtering.py       # filter_by_usage
```

### 10.2 clean.py Yeniden Yapilandirma

**Mevcut:** `clean_data()` 250+ satir, veri temizleme + OS tespiti + raporlama + dogrulama icinicerik.

**Onerilen:**
```
src/laprop/processing/
+-- clean.py           # clean_data (orkestrasyon)
+-- parsers.py         # clean_ram_value, clean_ssd_value, clean_price
+-- brand.py           # extract_brand
+-- os_detect.py       # detect_os
```

### 10.3 Skorlama Sabitlerini Dissal Hale Getirme

`rules.py` icindeki `CPU_SCORES`, `GPU_SCORES`, `RTX_MODEL_SCORES` gibi dictionary'ler JSON/YAML dosyalarina tasinabilir. Bu sayede:
- Kod degisikligi olmadan skor guncellemesi
- A/B test kolayligi
- Konfigürasyon versiyonlama

### 10.4 `__init__.py` Minimal Public API

**Mevcut (228 satir, 90+ export):**
```python
from .processing.normalize import (
    _normalize_title_text,  # PRIVATE!
    _extract_capacity_candidates,  # PRIVATE!
    _score_ssd_candidate,  # PRIVATE!
    # ... 20+ private fonksiyon daha
)
```

**Onerilen (tahminen 30 satir):**
```python
"""laprop public API."""
from .config.settings import BASE_DIR, DATA_FILES
from .config.rules import USAGE_OPTIONS, GAMING_TITLE_SCORES
from .processing.read import load_data
from .processing.clean import clean_data
from .recommend.engine import get_recommendations
from .recommend.scenarios import SCENARIOS

def main():
    from .app.main import main as _main
    return _main()
```

---

## 11. DOKUMANTASYON

### 11.1 README.md

**Mevcut (8 satir):**
```markdown
# Laprop Recommender
Not: Tum guncel ciktilar `data/` altinda tutulur.
## Data & Artifacts Policy
- Uretilen veri ciktilari `data/` altinda tutulur ve git'e eklenmez.
- Test fixture'lari kucuk ornekler olarak `tests/fixtures/` altinda tutulur.
```

**Eksikler:**
- Proje aciklamasi / amaci yok
- Kurulum talimatlari yok
- Kullanim ornekleri yok
- Mimari aciklamasi yok
- Katki kurallari yok
- Lisans bilgisi yok
- Ekran goruntuleri / demo linkleri yok
- Gereksinimler ve onkosusllar yok

### 11.2 API Dokumantasyonu

- Mevcut degil
- Type hint'ler tutarsiz
- Docstring'ler kismi ve standart dissi (Google/NumPy style degil)

### 11.3 Kurulum ve Deployment

- Kurulum dokumani yok
- `streamlit_app.py:500-501`'de tek satirlik yorum var:
  ```python
  # Local: pip install -r requirements.txt then streamlit run streamlit_app.py
  ```
- Docker/Docker Compose yok
- CI/CD pipeline yok

### 11.4 Gelistirici Kilavuzu

- Mevcut degil
- Kod standartlari tanimlanmamis
- Linting/formatting araclari yapilandirilmamis (ruff, black, mypy yok)

---

## 12. OZETIN OZETI

### En Kritik 5 Sorun

| # | Sorun | Ciddiyet | Dosya/Satir |
|---|-------|----------|-------------|
| 1 | **Pickle cache guvenlik acigi** | KRITIK | `read.py:75-76` |
| 2 | **Bare `except: pass` (6+ yer)** | KRITIK | `read.py:91`, `cli.py:103`, `read.py:162` |
| 3 | **Test coverage ~%2-3** | KRITIK | `tests/` (3 dosya) |
| 4 | **Requirements pinlenmemis** | YUKSEK | `requirements.txt` |
| 5 | **`__init__.py` 90+ private fonksiyon export** | YUKSEK | `src/laprop/__init__.py` |

### Hemen Yapilmasi Gereken 3 Iyilestirme

1. **Pickle'i Parquet ile degistir** - 1 dosya degisikligi, guvenlik acigini kapatir
2. **Bare except kaldir** - 6 dosyadaki `except: pass`'lari `except Exception as e:` ile degistir
3. **Requirements pinle** - `pip freeze` + minimum versiyon kilitlenmesi

### Uzun Vadeli Roadmap

| Faz | Icerik | Oncelik |
|-----|--------|---------|
| Faz 1 | Guvenlik fixleri + test altyapisi + requirements | Hemen |
| Faz 2 | engine.py + clean.py refactoring | 1-2 hafta |
| Faz 3 | Scraper'lari paket icine tasima | 2-3 hafta |
| Faz 4 | Logging + monitoring + CI/CD | 3-4 hafta |
| Faz 5 | API dokumantasyonu + README | 4-5 hafta |
| Faz 6 | Streamlit UI iyilestirmeleri | 5-6 hafta |
| Faz 7 | Benchmark entegrasyonu + ML skorlama | 6-8 hafta |

### Genel Puan: 5.5 / 10

| Kategori | Puan (10 uzerinden) |
|----------|---------------------|
| Fonksiyonellik | 7.0 - Calisan, kapsamli skorlama motoru |
| Kod kalitesi | 4.5 - Bare except, magic numbers, DRY ihlalleri |
| Test kapsami | 1.5 - Neredeyse sifir |
| Guvenlik | 3.5 - Pickle, subprocess, bare except |
| Mimari | 5.5 - Iyi katmanlama ama tutarsiz uygulama |
| Dokumantasyon | 2.0 - README 8 satir, API doc yok |
| Performans | 5.0 - iterrows, coklu apply, pickle cache |
| UX/UI | 6.5 - Temiz Streamlit UI, eksik gorsellesstirme |

**Sonuc:** Proje fonksiyonel bir prototip asamasinda. Skorlama motoru ve veri temizleme pipeline'i etkileyici derinlikte; ancak uretim kalitesine ulasmasi icin guvenlik, test, dokumantasyon ve refactoring yatirimi gerekiyor. En acil adim pickle cache'in kaldirilmasi ve test altyapisinin kurulmasidir.

---

*Bu rapor, 2026-02-06 tarihinde projenin mevcut durumunu yansitmaktadir.*
