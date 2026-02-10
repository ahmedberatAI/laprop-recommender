# PROJE ANALİZ RAPORU – Laptop Öneri Sistemi (Laprop)

---

## 1. Proje Genel Bakışı

### 1.1 Amaç
Bu proje, Türkiye pazarındaki e-ticaret sitelerinden laptop verilerini toplayarak kullanıcıya kişiselleştirilmiş laptop önerisi sunan bir **öneri sistemi** (recommendation system) geliştirmektedir. Sistem üç temel Türk e-ticaret sitesinden (Amazon.com.tr, VatanBilgisayar.com, InceHesap.com) veri kazıyarak (web scraping), bu verileri temizleyip normalleştirdikten sonra kullanıcının bütçe, kullanım amacı ve donanım tercihlerine göre en uygun laptopları skorlayıp sıralama yapar.

### 1.2 Kullanılan Teknolojiler

| Teknoloji | Kullanım Alanı |
|-----------|---------------|
| **Python 3.9+** | Ana programlama dili |
| **pandas** | Veri işleme (data processing), CSV okuma/yazma, DataFrame işlemleri |
| **NumPy** | Sayısal hesaplamalar, NaN kontrolü |
| **requests** | HTTP istekleri (web scraping) |
| **BeautifulSoup4** | HTML ayrıştırma (parsing) |
| **lxml** | Hızlı HTML/XML ayrıştırıcı (parser) |
| **urllib3** | Alt seviye HTTP istemcisi |
| **Streamlit** | Web tabanlı kullanıcı arayüzü (UI) |
| **argparse** | Komut satırı arayüzü (CLI) |
| **subprocess** | Scraper orkestrasyon (orchestration) |
| **pickle** | Veri önbelleği (cache) |
| **re** (regex) | Metin ayrıştırma, CPU/GPU/RAM/SSD çıkarma |
| **difflib** | Bulanık metin eşleştirme (fuzzy matching) |
| **ThreadPoolExecutor** | Çok iş parçacıklı (multi-threaded) kazıma |
| **json** | JSON veri çıktısı |
| **setuptools** | Paket yapılandırma (build system) |

### 1.3 Mimari (Architecture)

Proje **katmanlı mimari** (layered architecture) kullanmaktadır:

```
┌─────────────────────────────────────────────────┐
│              Sunum Katmanı (Presentation)         │
│  ┌─────────────────┐  ┌───────────────────────┐  │
│  │  CLI (cli.py)   │  │ Streamlit (streamlit   │  │
│  │  argparse menü  │  │    _app.py)            │  │
│  └─────────────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────┤
│             Öneri Katmanı (Recommendation)        │
│  ┌────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │ engine.py  │ │ scenarios.py │ │ explain.py │  │
│  └────────────┘ └──────────────┘ └────────────┘  │
├─────────────────────────────────────────────────┤
│             İşleme Katmanı (Processing)           │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐    │
│  │ read.py  │ │ clean.py │ │ normalize.py  │    │
│  ├──────────┤ ├──────────┤ ├───────────────┤    │
│  │validate.py│ │ merge.py │ │ repository.py │    │
│  └──────────┘ └──────────┘ └───────────────┘    │
├─────────────────────────────────────────────────┤
│          Veri Toplama Katmanı (Ingestion)          │
│  ┌──────────────┐ ┌────────────┐ ┌────────────┐  │
│  │amazon_scraper│ │vatan_scraper│ │incehesap   │  │
│  │   .py        │ │   .py       │ │ _scraper.py│  │
│  └──────────────┘ └────────────┘ └────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │       orchestrator.py (subprocess yönetim)   │  │
│  └─────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│            Yapılandırma (Configuration)            │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ settings.py  │ │ rules.py │ │benchmarks.py │  │
│  └──────────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────────┘
```

Paket yapısı `src/laprop/` altında organize edilmiştir:

```
src/laprop/
├── app/          → Uygulama giriş noktaları (CLI, main)
├── config/       → Yapılandırma ve kural tanımları
├── ingestion/    → Veri toplama orkestratörü ve kaynak tanımları
├── processing/   → Veri okuma, temizleme, normalleştirme, doğrulama
├── recommend/    → Öneri motoru, senaryolar, açıklama
├── storage/      → Veri deposu (repository)
└── utils/        → Yardımcı fonksiyonlar (konsol çıktısı)
```

---

## 2. Dosya Bazında Detaylı Analiz

### 2.1 Kök Dizin Dosyaları

#### `pyproject.toml` (10 satır)
- **Amaç:** Paket yapılandırma dosyası (build configuration).
- **İçerik:** `laprop` paketi için setuptools tabanlı build tanımı. Python >= 3.9 gerektirir.
- **İlişkiler:** `pip install -e .` ile geliştirme modunda kurulum sağlar.

#### `requirements.txt` (6 satır)
- **Amaç:** Bağımlılık listesi (dependency list).
- **Bağımlılıklar:** streamlit, pandas, numpy, requests, beautifulsoup4, urllib3.

#### `amazon_scraper.py` (~860 satır)
- **Amaç:** Amazon.com.tr'den laptop verisi kazıma.
- **Sınıf:** `AmazonLaptopScraper`
  - `__init__()`: Oturum (session) başlatma, başlık (header) profilleri
  - `_rotate_headers()`: 3 farklı tarayıcı profili arasında dönüşümlü başlık değiştirme
  - `fetch_page(url)`: HTTP isteği, yeniden deneme (retry) mantığı, bot algılama kontrolü
  - `check_captcha_or_bot_detection(soup)`: CAPTCHA/robot doğrulama tespiti
  - `extract_laptop_info(title)`: Ürün başlığından CPU, GPU, RAM, SSD ayrıştırma
  - `search_laptops(pages)`: Çok sayfalı arama (multi-page search)
  - `run()`: Ana çalıştırma akışı
- **Yardımcı fonksiyonlar:** `_price_to_int_tl`, `_ram_to_gb`, `_ssd_to_gb`, `_screen_to_float`, `_normalize_os`, `_brand_from_name`, `_normalize_gpu`, `_normalize_cpu`
- **Özellikler:** Anti-bot önlemleri (User-Agent rotasyonu, oturum yönetimi), Türkçe fiyat formatı desteği (nokta/virgül), `FAST_SCRAPE` çevre değişkeni ile hızlı mod.

#### `vatan_scraper.py` (~1088 satır)
- **Amaç:** VatanBilgisayar.com'dan laptop verisi kazıma.
- **Sınıflar:**
  - `RateLimiter`: Thread-safe hız sınırlayıcı (rate limiter)
  - `HtmlStore`: HTML sayfalarını diske kaydetme/okuma
  - `LaptopRow` (dataclass): Yapılandırılmış laptop verisi
  - `Stats`: İstatistik takibi (sayaçlar)
- **Fonksiyonlar:** `normalize_cpu`, `normalize_gpu`, `extract_discrete_gpu`, `extract_integrated_gpu`, `parse_screen_size`, `normalize_os`, `parse_product_page`, `scrape_list_pages`, `scrape_product_pages`
- **Özellikler:** `ThreadPoolExecutor` ile eşzamanlı (concurrent) ürün sayfası çekme, JSON-LD yapılandırılmış veri (structured data) ayrıştırma, HTML tablo ayrıştırma, JSON rapor üretimi.

#### `incehesap_scraper.py` (~1163 satır)
- **Amaç:** InceHesap.com'dan laptop verisi kazıma.
- **Sınıflar:**
  - `ScrapeConfig` (dataclass): Kazıma yapılandırması
  - `InceHesapScraper`: Ana kazıyıcı sınıf
- **Fonksiyonlar:** `extract_ssd_capacity`, `extract_ram_gb`, `extract_cpu_from_text`, `extract_gpu_from_text`, `fix_incehesap_dataframe`, `run_fix_pipeline`
- **Özellikler:** Regex tabanlı çıkarma (extraction), güvenilirlik skoru (confidence scoring), alt komutlar (subcommands: scrape, fix, scrape-only), ham CSV + düzeltilmiş CSV + JSON düzeltme raporu üretimi.

#### `streamlit_app.py` (502 satır)
- **Amaç:** Web tabanlı kullanıcı arayüzü.
- **İçerik:** Streamlit ile interaktif laptop öneri arayüzü.
- **Fonksiyonlar:**
  - `_load_data_cached()`: Önbellekli veri yükleme (`@st.cache_data`)
  - `_filter_sources()`: Kaynak bazlı filtreleme (Amazon/Vatan/InceHesap)
  - `_apply_user_filters()`: Kullanıcı filtrelerini uygulama (RAM, SSD, ekran, GPU)
  - `_is_integrated_gpu()`: Entegre GPU tespiti
  - `_price_bounds()`: Fiyat aralığı hesaplama
  - `_source_summary()`: Kaynak bazlı veri dağılımı
- **UI Bileşenleri:** Yan panel (sidebar) kontrolleri, bütçe kaydırıcısı (slider), kullanım amacı seçimi, donanım filtreleri, sonuç tablosu, detay paneli, CSV indirme düğmesi, kazıyıcı log gösterimi.
- **İlişkiler:** `laprop.recommend.engine.get_recommendations()`, `laprop.app.cli.normalize_and_complete_preferences()`, `laprop.processing.clean.clean_data()`, `laprop.processing.read.load_data()` kullanır.

#### `recommender.py`
- **Amaç:** Kök seviye öneri betiği (eski/basitleştirilmiş).
- **İlişki:** `laprop.app.main` ile birlikte çalışır.

#### `simulation.py`
- **Amaç:** Simülasyon modülü.
- **İlişki:** `cli.py` içindeki `run_simulation()` fonksiyonu tarafından kullanılır.

#### `price_collect.py`
- **Amaç:** Fiyat toplama yardımcı betiği.

#### `sitecustomize.py`
- **Amaç:** Python site özelleştirmesi (UTF-8 kodlama ayarı).

### 2.2 Yapılandırma Modülü (`src/laprop/config/`)

#### `settings.py` (19 satır)
- **Amaç:** Merkezi yol yapılandırması (path configuration).
- **Değişkenler:**
  - `BASE_DIR`: Proje kök dizini (3 üst klasör)
  - `DATA_DIR`: `data/` klasörü
  - `SCRAPERS`: Kazıyıcı betik yolları sözlüğü (dict)
  - `DATA_FILES`: 3 CSV dosya yolu listesi (amazon, vatan, incehesap)
  - `CACHE_FILE`: `laptop_cache.pkl` yolu
  - `ALL_DATA_FILE`: `data/all_data.csv` yolu
- **İlişkiler:** Tüm modüller tarafından import edilir.

#### `rules.py` (257 satır)
- **Amaç:** İş kuralları ve skor tabloları (business rules & scoring tables).
- **Sabitler:**
  - `DEV_PRESETS` (dict): 5 yazılım geliştirme profili (web, ml, mobile, gamedev, general) — RAM, SSD, ekran, OS tercihi, GPU/CPU bias değerleri
  - `GAMING_TITLE_SCORES` (dict): 10 oyun başlığı ve GPU gereksinim eşikleri
  - `CPU_SCORES` (dict): Intel (12-14. nesil, Ultra), AMD Ryzen (7xxx/8xxx), Apple M1-M4 CPU skorları (0-10)
  - `GPU_SCORES` (dict): NVIDIA RTX 20-50, GTX, MX, AMD RX, Intel Arc, iGPU, Apple GPU skorları (0-10)
  - `BRAND_PARAM_SCORES` (dict): 12 marka x 5 kullanım amacı puan matrisi
  - `BRAND_SCORES` (dict): Marka güvenilirlik puanları
  - `USAGE_OPTIONS` (dict): 5 kullanım amacı (gaming, portability, productivity, design, dev)
  - `BASE_WEIGHTS` (dict): 8 kriter temel ağırlıkları (toplam 100)
  - `RTX_MODEL_SCORES`, `GTX_MODEL_SCORES`, `MX_MODEL_SCORES`, `RX_MODEL_SCORES`: GPU model bazlı detaylı skor tabloları
  - `IMPORTANCE_MULT` (dict): 1-5 önem çarpanları
  - `MIN_REQUIREMENTS` (dict): Kullanım amacına göre asgari gereksinimler
- **İlişkiler:** `engine.py`, `cli.py`, `streamlit_app.py` tarafından yoğun şekilde kullanılır.

#### `benchmarks.py`
- **Amaç:** CPU/GPU benchmark verisi (rules.py ile örtüşen yapı).

### 2.3 İşleme Modülü (`src/laprop/processing/`)

#### `read.py` (166 satır)
- **Amaç:** CSV dosyalarını güvenli şekilde okuma ve birleştirme.
- **Fonksiyonlar:**
  - `read_csv_robust(path)`: Birden fazla encoding deneyen (utf-8-sig, utf-8, cp1254, latin1) dayanıklı CSV okuyucu, otomatik ayırıcı (delimiter) algılama
  - `load_data(use_cache)`: Pickle önbellek kontrolü, 3 CSV'yi birleştirme (`pd.concat`), Vatan URL istatistikleri
  - `_standardize_columns(df)`: BOM karakteri temizleme, kolon adlarını küçük harfe çevirme
  - `_sanitize_column_name(name)`: Kolon adı temizleme
  - `_get_domain_counts(url_series)`: URL bazlı kaynak sayımı (Amazon/Vatan/InceHesap)
  - `_count_filled_urls(url_series)`: Dolu URL sayısı
- **İlişkiler:** `clean.py`, `cli.py`, `streamlit_app.py` tarafından kullanılır.

#### `clean.py` (394 satır)
- **Amaç:** Ham verileri temizleme ve dönüştürme (data cleaning & transformation).
- **Ana fonksiyon: `clean_data(df)`** — Tüm temizleme hattını (pipeline) çalıştırır:
  1. Kolon standardizasyonu (`_standardize_columns`)
  2. Fiyat temizleme (`clean_price`)
  3. Vatan kategori/placeholder satırları filtreleme
  4. Marka çıkarma (`extract_brand`)
  5. CPU/GPU normalleştirme (`normalize_cpu`, `normalize_gpu`)
  6. RAM/SSD/Ekran boyutu ayrıştırma (başlıktan + kolondan)
  7. RAM-SSD değer takası (swap) düzeltmeleri
  8. Geçersiz SSD değerleri temizleme
  9. Doğrulama uyarıları (`validate_record`)
  10. CPU/GPU skorlama (`get_cpu_score`, `get_gpu_score`)
  11. GPU model normalleştirme (`normalize_gpu_model`)
  12. OS tespiti (`detect_os`)
  13. Kritik kolon filtreleme (fiyat > 5000 TL)
  14. Veri kalite raporu çıktısı
- **Yardımcı fonksiyonlar:**
  - `clean_price(price_str)`: Fiyat metnini tam sayıya çevirme (1000-500000 TL aralığı)
  - `clean_ram_value(ram_str)`: RAM metnini GB'ye çevirme (parantez içi, "8GB + 8GB = 16GB" gibi)
  - `clean_ssd_value(storage_str)`: SSD kapasitesini çıkarma (regex tabanlı, GB/TB dönüşümü)
  - `extract_brand(name)`: 12 marka ve 40+ anahtar kelime ile marka tespiti
- **İlişkiler:** `normalize.py`, `validate.py`, `engine.py` fonksiyonlarını kullanır.

#### `normalize.py` (485 satır)
- **Amaç:** Metin normalleştirme ve değer çıkarma (text normalization & extraction).
- **Ana fonksiyonlar:**
  - `normalize_gpu_model(gpu_text)`: Ham GPU metnini standart etiketlere dönüştürme (9 kategori: RTX, GTX, MX, RX, Arc, Apple M, Intel iGPU, AMD iGPU, fallback)
  - `normalize_cpu(title, brand)`: Ürün başlığından CPU bilgisi çıkarma (Intel Core i3-i9, Ultra, AMD Ryzen, Apple M1-M4)
  - `normalize_gpu(title, brand)`: Ürün başlığından GPU bilgisi çıkarma
  - `parse_ram_gb(title)`: Başlıktan RAM kapasitesi çıkarma (regex: "16GB RAM", "DDR5 16GB")
  - `parse_ssd_gb(title)`: Başlıktan SSD kapasitesi çıkarma (skor tabanlı aday seçimi)
  - `parse_screen_size(value)`: Ekran boyutu ayrıştırma (inç, inch, ", Türkçe inç destekli)
  - `sanitize_ram(product)`: >64GB RAM değerleri için güvenlik filtresi
- **Sabitler:** `SSD_COMMON_GB`, `SSD_TINY_GB`, `SSD_FORM_FACTOR_GB`, `SSD_MIN_GB`, `SSD_MAX_GB`, `RAM_STORAGE_SWAP_GB`, `SSD_ANCHORS`, `RAM_HINTS`, `GPU_HINTS`, `HDD_HINTS`
- **Yardımcı fonksiyonlar:** `_normalize_title_text`, `_normalize_capacity_gb`, `_extract_capacity_candidates`, `_extract_no_unit_ssd_candidates`, `_score_ssd_candidate`, `_coerce_int`, `_is_valid_ssd_value`, `_find_larger_ssd_in_title`, `_find_ram_candidates`, `_find_screen_candidates`
- **Önemli tasarım kararı:** SSD çıkarma, **pencere tabanlı skor sistemi** (window-based scoring) kullanır — adayın çevresindeki 40 karakterlik bağlamda SSD/RAM/GPU ipuçlarına bakarak doğru değeri seçer.

#### `validate.py` (25 satır)
- **Amaç:** Kayıt doğrulama (record validation).
- **Fonksiyon:** `validate_record(title, cpu, gpu, ram_gb, ssd_gb, screen_size)` — Uyarı listesi döndürür (ram_over_128, screen_size_out_of_range).

#### `merge.py`
- **Amaç:** Çoklu kaynak verisini birleştirme (henüz aktif olarak kullanılmıyor; read.py içinde concat ile yapılıyor).

### 2.4 Öneri Modülü (`src/laprop/recommend/`)

#### `engine.py` (776 satır)
- **Amaç:** **Temel öneri motoru** — skorlama, filtreleme ve sıralama.
- **Ana fonksiyonlar:**
  - **`get_recommendations(df, preferences, top_n=5)`**: Ana öneri fonksiyonu:
    1. Bütçe filtresi
    2. Ekran üst sınırı (opsiyonel)
    3. Kullanım amacına göre filtreleme (`filter_by_usage`)
    4. Gaming GPU eşiği fail-safe
    5. Duplikasyon temizleme (URL + isim+fiyat bazlı)
    6. RAM sanitizasyonu (>64GB)
    7. Her ürünü skorlama (`calculate_score`)
    8. Skor + fiyat bazlı sıralama
    9. Top-N seçimi (marka çeşitliliği korumalı)
    10. Metadata ekleme (kullanım etiketi, ortalama skor, fiyat aralığı)

  - **`calculate_score(row, preferences)`**: 8 kriterli puanlama:
    1. **Fiyat skoru** (price): Bütçe aralığına göre, ortaya yakınlık bonusu
    2. **Performans skoru** (performance): CPU + GPU ağırlıklı karışım (kullanım amacına göre %30-70 ile %70-30 arası)
    3. **RAM skoru** (ram): Kademeli puanlama (8GB=40, 16GB=70, 32GB=90, 64GB=100)
    4. **Depolama skoru** (storage): Kademeli puanlama (256GB=50, 512GB=70, 1TB=85, 2TB=100)
    5. **Marka güven skoru** (brand): `BRAND_SCORES` tablosundan
    6. **Marka-amaç uyum skoru** (brand_purpose): `BRAND_PARAM_SCORES` matrisinden
    7. **Pil skoru** (battery): CPU tipi + GPU gücüne göre tahmin
    8. **Taşınabilirlik skoru** (portability): Ekran boyutu + GPU ağırlığına göre
    - OS çarpanı ile final skoru düzeltme
    - Dev profili için `compute_dev_fit()` ile harmanlama (%30-50)

  - **`compute_dev_fit(row, dev_mode)`**: Yazılım geliştirme uyumluluk skoru (0-100):
    - RAM yeterliliği (20 puan)
    - SSD yeterliliği (15 puan)
    - CPU yapısı/suffix (4 puan ± bias)
    - GPU gerekliliği (25 puan)
    - Ekran/taşınabilirlik (20 puan)
    - OS uyumu (çarpan)
    - Web geliştirme özel kuralları (GPU irrelevant, FreeDOS ceza)

  - **`filter_by_usage(df, usage_key, preferences)`**: Kullanım amacına göre ön filtreleme:
    - Gaming: GPU eşiği, min RAM 8GB, MacBook hariç
    - Portability: Ekran ≤14.5", ağır GPU filtresi
    - Productivity: RAM ≥8, CPU skoru ≥5
    - Design: RAM ≥16, GPU ≥4, ekran ≥14", GPU/RAM ipuçları
    - Dev: RAM ≥16, CPU ≥6, SSD ≥256, dev_mode bazlı preset filtreleri, Web dev için gaming laptop engelleyici (RTX 4050+ hariç, HX CPU hariç, 16"+ dGPU hariç, FreeDOS+dGPU hariç)
    - Adaptif gevşetme: <5 sonuç kalırsa kriterleri hafifletme

  - **`get_dynamic_weights(usage_key)`**: Kullanım amacına göre ağırlık tabloları (toplam 100'e normalize):
    - Gaming: performance=40, price=15, battery=3
    - Portability: portability=25, battery=20, performance=10
    - Productivity: performance=25, ram=20
    - Design: performance=22, ram=18, storage=15
    - Dev: performance=28, ram=22, storage=15

  - **`get_cpu_score(cpu_text)`**: CPU metin eşleştirme → 0-10 skor (HX/H/U/P suffix ayarlaması)
  - **`get_gpu_score(gpu_text)`**: GPU metin eşleştirme → 0-10 skor (iGPU, Arc, RTX, GTX, MX, RX, Apple M)

- **Yardımcı fonksiyonlar:** `_cpu_suffix`, `_has_dgpu`, `_is_nvidia_cuda`, `_rtx_tier`, `_is_heavy_dgpu_for_dev`, `_safe_num`, `_series_with_default`

#### `scenarios.py` (105 satır)
- **Amaç:** 100 önceden tanımlanmış (predefined) test senaryosu.
- **İçerik:** `SCENARIOS` listesi — Her senaryo bir ID, etiket ve tercih sözlüğü içerir.
- **Senaryo dağılımı:**
  - S001-S020: Gaming senaryoları (farklı oyun başlıkları, 35K-180K bütçe)
  - S021-S040: Portability senaryoları (18K-90K bütçe, ekran sınırları)
  - S041-S060: Productivity senaryoları (office, data, multitask, light_dev profilleri)
  - S061-S080: Design senaryoları (graphic, video, 3d, cad profilleri)
  - S081-S100: Dev senaryoları (web, ml, mobile, gamedev, general)
- **İlişkiler:** `cli.py` içindeki `run_simulation()` tarafından kullanılır.

#### `explain.py` (2 satır)
- **Amaç:** Açıklama yardımcıları (henüz implementasyonu boş, yapı için ayrılmış).

### 2.5 Uygulama Modülü (`src/laprop/app/`)

#### `main.py` (19 satır)
- **Amaç:** Uygulama giriş noktası (entry point).
- **İçerik:** `cli.main()` fonksiyonunu çağırır, `KeyboardInterrupt` ve genel hata yakalama.

#### `cli.py` (1228 satır)
- **Amaç:** Komut satırı arayüzü ve kullanıcı etkileşimi.
- **Ana fonksiyon: `main()`**:
  - argparse ile komut satırı argümanları (--run-scrapers, --debug, --nl/--free-text)
  - 9 seçenekli ana menü döngüsü:
    1. Klasik soru-cevap öneri
    2. Serbest metin (akıllı) öneri
    3. Veri durumu inceleme
    4. Scraper verileri detaylı analiz
    5. CSV export
    6. Veri güncelleme (scraper çalıştır)
    7. Debug modu aç/kapa
    8. Simülasyon (100 senaryo)
    9. Çıkış
- **Tercih toplama fonksiyonları:**
  - `get_user_preferences()`: Klasik adım adım tercih toplama
  - `get_user_preferences_free_text()`: Serbest metin ile akıllı tercih toplama
  - `_prompt_gaming_titles()`: Oyun seçimi (10 oyun listesi)
  - `_prompt_design_details()`: Tasarım profili seçimi (grafik/video/3D/CAD)
  - `_prompt_productivity_details()`: Üretkenlik profili seçimi (office/data/light_dev/multitask)
- **Doğal dil işleme (NLP-like) fonksiyonları:**
  - `parse_free_text_to_preferences(text)`: Serbest metinden tercih çıkarma
  - `detect_budget(text)`: Regex ile bütçe aralığı tespiti ("30-45k", "max 50 bin", "40k civarı")
  - `detect_usage_intent(text)`: Anahtar kelime tabanlı kullanım amacı tespiti (5 kategori x 10-20 anahtar kelime)
  - `detect_dev_mode(text)`: Dev alt profil tespiti
  - `fuzzy_match_game_titles(text, titles)`: Bulanık oyun adı eşleştirme (difflib + token eşleştirme)
  - `parse_design_profile_from_text(text)`: Tasarım profili anahtar kelime tespiti
- **Diğer fonksiyonlar:**
  - `normalize_and_complete_preferences(p)`: Tercih normalizasyonu
  - `ask_missing_preferences(p)`: Eksik tercihler için interaktif sorular
  - `display_recommendations(recommendations, preferences)`: Öneri sonuçlarını biçimlendirilmiş çıktı
  - `inspect_data(df)`: Veri istatistikleri (marka, fiyat, RAM, GPU dağılımları)
  - `inspect_scrapers_separately()`: Her scraper verisini ayrı analiz
  - `save_data(df, filename)`: CSV export
  - `run_simulation(n, seed, out_path, df, top_n)`: 100 senaryoluk simülasyon, JSONL çıktı

### 2.6 Veri Toplama Modülü (`src/laprop/ingestion/`)

#### `orchestrator.py` (98 satır)
- **Amaç:** 3 kazıyıcıyı sıralı çalıştırma (sequential orchestration).
- **Fonksiyon: `run_scrapers()`**:
  - Her kazıyıcıyı `subprocess.run()` ile bağımsız süreç (process) olarak çalıştırır
  - 600 saniye zaman aşımı (timeout)
  - `FAST_SCRAPE=1` ve `PYTHONIOENCODING=utf-8` çevre değişkenleri
  - Her kazıyıcıya uygun komut satırı argümanları
  - Dosya değişiklik zamanı (mtime) takibi
  - Çalıştırma sonrası `append_to_all_data()` ve önbellek temizleme
- **İlişkiler:** `settings.py` (SCRAPERS, DATA_FILES, CACHE_FILE), `repository.py` (append_to_all_data).

#### `sources/amazon.py`, `sources/incehesap.py`, `sources/vatan.py`
- **Amaç:** Minimal sarmalayıcı (wrapper) modüller — kazıyıcı betik yollarını tanımlar.

### 2.7 Depolama Modülü (`src/laprop/storage/`)

#### `repository.py` (195 satır)
- **Amaç:** Verileri `all_data.csv`'ye ekleme (append) ve tekrar engelleme (deduplication).
- **Ana fonksiyon: `append_to_all_data()`**:
  - 3 CSV dosyasını okur
  - `scraped_at` (zaman damgası) ve `source` (kaynak) kolonları ekler
  - Mevcut `all_data.csv` ile karşılaştırarak tekrar eden satırları filtreler
  - Yalnızca yeni satırları append modunda ekler
- **Tekrar engelleme sistemi:**
  - `_build_row_key(source, url, row)`: URL varsa URL bazlı, yoksa tüm alan bazlı (fallback) benzersiz anahtar üretir
  - `_iter_existing_keys(path)`: Mevcut anahtarları chunk bazlı okur (50000 satır/chunk)
  - `_dedupe_dataframe(df, existing_keys)`: Yeni veriyi mevcut anahtarlarla karşılaştırır
  - `_self_test_dedupe()`: Minimal kendi kendine test (self-test)
- **İlişkiler:** `orchestrator.py` tarafından çağrılır.

### 2.8 Yardımcı Modüller

#### `utils/console.py`
- **Amaç:** Güvenli konsol çıktısı.
- **Fonksiyon:** `safe_print(*args)`: Unicode karakter hatalarını yakalayan print sarmalayıcısı.

### 2.9 Test Dosyaları

#### `tests/conftest.py`
- **Amaç:** Pytest yapılandırması — `src/` ve proje kök dizinini `sys.path`'e ekler.

#### `tests/test_screen_size.py`
- **Amaç:** `parse_screen_size()` fonksiyonu için 11 birim testi (unit test).
- **Test senaryoları:** Sayısal değerler, "14.0 inch", Türkçe "15.6 inç", tırnak işareti "15.6\"" vb.

#### `tests/test_scraper_smoke.py`
- **Amaç:** Duman testleri (smoke tests).
- **İçerik:** Her 3 kazıyıcının `--help` komutunu test eder, InceHesap HTML fixture ayrıştırma testi.

#### `scripts/smoke_imports.py`
- **Amaç:** Import doğrulama betiği — tüm modüllerin düzgün import edildiğini kontrol eder.

---

## 3. Veri Akışı Analizi (Data Flow Analysis)

### 3.1 Genel Veri Akışı

```
E-ticaret Siteleri          Kazıma (Scraping)           Ham Veri
 ┌──────────────┐      ┌────────────────────┐      ┌──────────────┐
 │Amazon.com.tr │──→──│ amazon_scraper.py   │──→──│amazon_laptops│
 │              │      │                    │      │    .csv      │
 └──────────────┘      └────────────────────┘      └──────────────┘
 ┌──────────────┐      ┌────────────────────┐      ┌──────────────┐
 │ VatanBilgi.  │──→──│ vatan_scraper.py    │──→──│vatan_laptops │
 │   sayar.com  │      │                    │      │    .csv      │
 └──────────────┘      └────────────────────┘      └──────────────┘
 ┌──────────────┐      ┌────────────────────┐      ┌──────────────┐
 │InceHesap.com │──→──│incehesap_scraper.py │──→──│incehesap     │
 │              │      │                    │      │ _laptops.csv │
 └──────────────┘      └────────────────────┘      └──────────────┘
                                                         │
                              Birleştirme & Temizleme     │
                       ┌────────────────────────────┐    │
                       │  read.py → load_data()      │←───┘
                       │  (3 CSV birleştir, cache)    │
                       └──────────┬─────────────────┘
                                  │
                       ┌──────────▼─────────────────┐
                       │  clean.py → clean_data()    │
                       │  - Fiyat temizleme          │
                       │  - Marka çıkarma            │
                       │  - CPU/GPU normalleştirme   │
                       │  - RAM/SSD/Ekran ayrıştırma │
                       │  - OS tespiti               │
                       │  - Skorlama                 │
                       └──────────┬─────────────────┘
                                  │
                       Temizlenmiş DataFrame
                                  │
                       ┌──────────▼─────────────────┐
                       │  engine.py → get_recs()     │
                       │  1. Bütçe filtresi          │
                       │  2. Kullanım filtresi       │
                       │  3. Çok kriterli skorlama   │
                       │  4. Top-N seçimi            │
                       └──────────┬─────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
             ┌──────▼──────┐ ┌───▼────┐ ┌──────▼──────┐
             │  CLI çıktı  │ │Streamlit│ │ Simülasyon  │
             │  (terminal) │ │ (web)  │ │  (JSONL)   │
             └─────────────┘ └────────┘ └─────────────┘
```

### 3.2 Kullanıcı Verisi Toplama

**CLI modu (2 yol):**

1. **Klasik soru-cevap** (`get_user_preferences`):
   - Adım 1: Minimum/Maksimum bütçe (TL)
   - Adım 2: Kullanım amacı seçimi (1-5)
   - Adım 3 (koşullu): Alt profil seçimi
     - Gaming → Oyun listesinden seçim → GPU eşiği hesaplama
     - Dev → Web/ML/Mobile/GameDev/Genel seçimi
     - Design → Grafik/Video/3D/CAD seçimi → GPU/RAM ipucu
     - Productivity → Office/Data/Light Dev/Multitask seçimi

2. **Serbest metin** (`get_user_preferences_free_text`):
   - Tek cümle girişi: "35-55k, oyun + okul, 15.6, RTX 4060 olsun"
   - `detect_budget()` → Bütçe aralığı çıkarma
   - `detect_usage_intent()` → Kullanım amacı tahmin
   - `fuzzy_match_game_titles()` → Oyun adı eşleştirme
   - `parse_design_profile_from_text()` → Tasarım profili tespiti
   - `detect_dev_mode()` → Dev alt profil tespiti
   - Eksik bilgiler için follow-up soruları

**Streamlit modu:**
- Yan panel widget'ları ile etkileşim
- Bütçe slider, kullanım selectbox
- Koşullu follow-up soruları (gaming → oyun seçimi, dev → profil seçimi vb.)
- Donanım filtreleri (min RAM, min SSD, ekran aralığı, GPU tipi)

### 3.3 Öneri Algoritması Detayı

**Adım 1 — Ön Filtreleme:**
```
Ham veri (N satır)
   ↓ Bütçe filtresi (min_budget ≤ price ≤ max_budget)
   ↓ Ekran üst sınırı (opsiyonel)
   ↓ Kullanım filtresi (filter_by_usage):
   │   Gaming: GPU ≥ eşik, RAM ≥ 8, MacBook hariç
   │   Portability: Ekran ≤ 14.5", ağır GPU kısıtla
   │   Productivity: RAM ≥ 8, CPU ≥ 5
   │   Design: RAM ≥ 16, GPU ≥ 4, ekran ≥ 14"
   │   Dev: RAM ≥ 16, CPU ≥ 6, SSD ≥ 256 + preset filtreleri
   ↓ Duplikasyon temizleme
   ↓ RAM sanitizasyonu
Filtrelenmiş veri (M satır, M << N)
```

**Adım 2 — Skorlama (100 puan üzerinden):**
```
Her ürün için:
  fiyat_skoru × ağırlık_fiyat            (ör: 25%)
+ performans_skoru × ağırlık_performans  (ör: 20%)
+ ram_skoru × ağırlık_ram                (ör: 15%)
+ depolama_skoru × ağırlık_depolama      (ör: 10%)
+ marka_skoru × ağırlık_marka            (ör: 10%)
+ marka_amaç_skoru × ağırlık_amaç       (ör: 10%)
+ pil_skoru × ağırlık_pil               (ör: 5%)
+ taşınabilirlik_skoru × ağırlık_taş    (ör: 5%)
─────────────────────────────────────────
= temel_skor × os_çarpanı
+ dev_gpu_bonusu (dev modu için)
─────────────────────────────────────────
= final_skor (dev ise: %50-70 temel + %30-50 dev_fit)
```

**Adım 3 — Seçim ve Sıralama:**
```
Skor (yüksekten düşüğe) + Fiyat (düşükten yükseğe)
   ↓ Marka çeşitliliği koruması (ilk 3'te farklı markalar)
   ↓ Top-N seçimi
Sonuç listesi
```

### 3.4 Backend-Frontend İletişimi

```
                 Streamlit (Frontend)
                       │
                       │ Python fonksiyon çağrısı
                       │ (aynı süreç içinde)
                       ▼
              ┌──────────────────┐
              │  Ortak Kütüphane │
              │  (laprop paketi) │
              ├──────────────────┤
              │ load_data()      │ ← CSV dosyaları
              │ clean_data()     │
              │ get_recs()       │ → DataFrame
              └──────────────────┘
                       │
                       │ DataFrame → st.dataframe()
                       ▼
              Streamlit Tablosu + Detay Paneli
```

- **İletişim modeli:** Doğrudan Python fonksiyon çağrısı (no REST API, no RPC)
- **Veri formatı:** pandas DataFrame
- **Önbellek:** `@st.cache_data` dekoratörü + pickle dosyası
- **Durum yönetimi (state management):** `st.session_state` sözlüğü

---

## 4. Özellikler ve İşlevsellik

### 4.1 Filtreleme Sistemi

| Filtre | Açıklama | Uygulama Noktası |
|--------|----------|------------------|
| Bütçe aralığı | Min-Max TL | `get_recommendations()` |
| Kullanım amacı | 5 preset | `filter_by_usage()` |
| Min RAM | GB cinsinden | `filter_by_usage()` + Streamlit sidebar |
| Min SSD | GB cinsinden | `filter_by_usage()` (dev preset) |
| Ekran boyutu | Min-Max inç | Streamlit sidebar slider |
| GPU tipi | Any/Integrated/Dedicated | Streamlit `_apply_user_filters()` |
| GPU eşiği | Oyun bazlı min GPU skor | Gaming filtresi |
| Marka | MacBook hariç (gaming) | `filter_by_usage()` |
| OS | FreeDOS+dGPU hariç (web dev) | Dev web filtresi |
| Kaynak | Amazon/Vatan/InceHesap | Streamlit kaynak seçimi |

### 4.2 Öneri Sistemi

- **Kural tabanlı** (rule-based) öneri sistemi
- 8 kriterli ağırlıklı puanlama (weighted scoring)
- Kullanım amacına göre dinamik ağırlıklar
- Yazılım geliştirme için 5 alt profilli özel puanlama (compute_dev_fit)
- Oyun için GPU gereksinim tablosu (10 oyun başlığı)
- Tasarım için GPU/RAM ipucu sistemi (graphic/video/3d/cad)
- Adaptif filtreleme (çok az sonuçta gevşetme)
- Marka çeşitliliği koruma mekanizması

### 4.3 Kriter Ağırlıklandırma

**Temel ağırlıklar (BASE_WEIGHTS):**
- price: 25, performance: 20, ram: 15, storage: 10
- brand: 10, brand_purpose: 10, battery: 5, portability: 5

**Kullanım amacına göre özelleştirme:**
- Gaming: Performans ağırlığı 40'a çıkar, pil/taşınabilirlik düşer
- Portability: Taşınabilirlik 25 + pil 20, performans 10'a düşer
- Dev: Performans 28, RAM 22, depolama 15

### 4.4 Kullanıcı Arayüzleri

**CLI Arayüzü:**
- 9 menülü interaktif terminal uygulaması
- 2 tercih toplama modu (klasik + serbest metin)
- Debug modu (skor detayları)
- Veri inceleme ve export
- 100 senaryoluk simülasyon çalıştırma

**Streamlit Web Arayüzü:**
- Responsive 2 sütunlu düzen (layout)
- Yan panel: Veri yükleme, filtreler, kullanıma özel sorular, ayarlar
- Sol sütun: Öneri tablosu, arama, CSV export
- Sağ sütun: Seçili ürün detayı, skor dağılımı, debug bilgisi
- Kaynak seçimi (Amazon/Vatan/InceHesap)
- Follow-up soruları (gaming → oyun seçimi, dev → profil seçimi)

---

## 5. Yapılandırma ve Bağımlılıklar

### 5.1 Proje Yapılandırması

**`pyproject.toml`:**
- Paket adı: `laprop`
- Versiyon: `0.0.0`
- Build sistemi: setuptools >= 65.0
- Minimum Python: 3.9

**`requirements.txt`:**
- streamlit, pandas, numpy, requests, beautifulsoup4, urllib3

### 5.2 Dosya Yolu Yapılandırması (`settings.py`)

```
BASE_DIR/
├── data/
│   ├── amazon_laptops.csv
│   ├── vatan_laptops.csv
│   ├── incehesap_laptops.csv
│   └── all_data.csv
├── laptop_cache.pkl
├── amazon_scraper.py
├── vatan_scraper.py
└── incehesap_scraper.py
```

### 5.3 Çevre Değişkenleri (Environment Variables)

| Değişken | Değer | Açıklama |
|----------|-------|----------|
| `FAST_SCRAPE` | `1` | Hızlı kazıma modu (daha az sayfa) |
| `PYTHONIOENCODING` | `utf-8` | Python çıktı kodlaması |
| `ALLOW_SCRAPE_UI` | `1` | Streamlit'te scraper düğmesini etkinleştir |

### 5.4 Veri Önbellek Stratejisi

1. **Pickle cache** (`laptop_cache.pkl`): Temizlenmemiş ham verilerin birleştirilmiş hali
   - `data_files` metadata ile dosya listesi kontrolü
   - Scraper çalıştırılınca otomatik silinir
2. **Streamlit cache** (`@st.cache_data`): Temizlenmiş verilerin bellekte tutulması
3. **HTML store** (Vatan scraper): HTML sayfalarını `raw/` klasörüne kaydetme (incremental scraping)

---

## 6. İyileştirme Önerileri

### 6.1 Kod Kalitesi (Code Quality)

1. **Tip açıklamaları (Type Annotations):** `engine.py` ve `clean.py` fonksiyonlarının büyük çoğunluğunda tip açıklamaları eksik. `preferences` sözlüğü (dict) birçok opsiyonel anahtara sahip — `TypedDict` veya `dataclass` ile modellenmeli.

2. **Tekrar eden kod (Code Duplication):**
   - GPU/CPU normalleştirme mantığı 3 scraper dosyasında ve `normalize.py`'da ayrı ayrı tekrarlanıyor. Ortak bir normalizasyon kütüphanesi oluşturulmalı.
   - `_safe_num()` fonksiyonu `engine.py`'de tanımlanırken benzer `_safe_float()` fonksiyonu `cli.py`'de var.

3. **Dosya boyutları:** `cli.py` (1228 satır) ve `engine.py` (776 satır) çok büyük. Sorumluluklar ayrıştırılmalı:
   - `cli.py`'deki NLP fonksiyonları (detect_budget, detect_usage_intent, fuzzy_match vb.) ayrı bir `text_parser.py` modülüne taşınmalı.
   - `cli.py`'deki simülasyon fonksiyonu `simulation.py`'ye taşınmalı.
   - `cli.py`'deki `inspect_data()` ve `inspect_scrapers_separately()` fonksiyonları ayrı bir `analysis.py` modülüne taşınmalı.

4. **Sihirli sayılar (Magic Numbers):** Skorlama fonksiyonlarında çok sayıda hard-coded değer var (ör: 40 karakter pencere, 0.95 çarpan, 4 puan bonus). Bunlar sabit olarak tanımlanmalı.

5. **Hata yönetimi (Error Handling):** Bare `except:` kullanımı birçok yerde var (ör: `read.py:91`, `cli.py:103`). Spesifik exception türleri yakalanmalı.

6. **Global değişken:** `cli.py:1133`'te `global preferences` kullanımı kötü bir pratik. Bir yapılandırma (config) nesnesi tercih edilmeli.

### 6.2 Performans (Performance)

1. **Satır bazlı iteration:** `clean.py:239-274`'te satır bazlı `for idx in df.index` döngüsü var (RAM-SSD swap düzeltmesi). Bu, büyük veri setlerinde yavaş çalışır. Vektörel (vectorized) pandas işlemleri tercih edilmeli.

2. **Skorlama döngüsü:** `engine.py:736-740`'ta `for _, row in filtered.iterrows()` ile skorlama yapılıyor. `df.apply()` veya vektörel hesaplama ile hızlandırılabilir.

3. **Scraper paralelleştirme:** `orchestrator.py` kazıyıcıları sıralı (sequential) çalıştırıyor. 3 bağımsız kaynak olduğundan `concurrent.futures.ProcessPoolExecutor` ile paralel çalıştırılabilir.

4. **Pickle cache güvenliği:** Pickle dosyası güvenlik riski taşır (arbitrary code execution). JSON veya Parquet format tercih edilmeli.

### 6.3 Güvenlik (Security)

1. **Anti-bot risk:** Kazıyıcılar User-Agent rotation ve session yönetimi kullanıyor, ancak:
   - Rate limiting Amazon ve InceHesap scraper'larında yeterli değil
   - IP rotasyonu veya proxy desteği yok
   - robots.txt kontrolü yapılmıyor

2. **Girdi doğrulama (Input Validation):** CLI'da kullanıcı girişleri için temel doğrulama var, ancak:
   - `detect_budget()` regex'i aşırı geniş eşleşme yapabilir
   - Fiyat aralığı kontrolü sınırlı (1000-500000)

3. **Pickle dosya güvenliği:** `laptop_cache.pkl` dosyası zararlı veri içerebilir. Güvenilmeyen ortamlarda çalıştırılması riskli.

4. **subprocess çalıştırma:** `orchestrator.py` ve `streamlit_app.py`'de `subprocess.run()` kullanımı, betik yolları `settings.py`'den geldiği için kontrollü, ancak çevre değişkeni enjeksiyonu riski minimal düzeyde mevcut.

### 6.4 Kullanıcı Deneyimi (User Experience)

1. **Serbest metin modu iyileştirmesi:**
   - Mevcut NLP basit anahtar kelime eşleştirme ile sınırlı. Daha gelişmiş intent detection için sentence embedding veya basit bir ML modeli eklenebilir.
   - Çoklu amaç desteği yok (ör: "hem oyun hem okul için").

2. **Sonuç açıklama:** `explain.py` modülü boş. Her öneri için "Bu laptop neden seçildi?" açıklaması eklenebilir — skor dağılımını doğal dilde anlatarak.

3. **Karşılaştırma (Comparison):** Kullanıcının 2-3 laptopı yan yana karşılaştırma özelliği yok.

4. **Fiyat geçmişi (Price History):** `all_data.csv`'de `scraped_at` zaman damgası mevcut. Fiyat değişim grafiği eklenebilir.

5. **Streamlit iyileştirmeleri:**
   - Ürün resimleri gösterilmiyor
   - Doğrudan satış sayfasına link var ancak yeni sekmede açılmıyor
   - Mobil uyum (responsive) için ek düzen çalışması gerekli

6. **Eksik veri uyarısı:** Bazı ürünlerde RAM, SSD veya ekran boyutu bilgisi eksik kalabiliyor. Kullanıcıya bu ürünlerin "tahmini" değerlerle skorlandığı belirtilmeli.

### 6.5 Ek İyileştirme Önerileri

1. **Veritabanı entegrasyonu:** CSV/Pickle yerine SQLite veya PostgreSQL kullanımı — özellikle `all_data.csv` büyüdükçe performans sorunları yaşanacaktır.

2. **Test kapsamı (Test Coverage):** Şu anda yalnızca `parse_screen_size` ve scraper smoke testleri mevcut. `clean_data`, `calculate_score`, `filter_by_usage`, `detect_budget` gibi kritik fonksiyonlar için birim testleri eklenmeli.

3. **Logging:** `safe_print()` yerine Python `logging` modülü kullanılmalı — log seviyeleri (DEBUG, INFO, WARN, ERROR) ve dosyaya yazma desteği.

4. **API katmanı:** Streamlit doğrudan modül fonksiyonlarını çağırıyor. REST API (FastAPI) eklenerek frontend-backend ayrımı yapılabilir.

5. **Yapılandırma yönetimi:** Skor tabloları, ağırlıklar ve eşikler kod içinde hard-coded. YAML/TOML yapılandırma dosyasına taşınarak kod değiştirmeden ayarlanabilir hale getirilebilir.

6. **CI/CD:** Otomatik test çalıştırma, lint kontrolü (flake8/ruff), ve kod formatlama (black) için pipeline eklenmeli.

---

## Özet İstatistikler

| Metrik | Değer |
|--------|-------|
| Toplam Python dosyası | ~25 |
| Toplam satır (tahmini) | ~7500+ |
| Kazıyıcı sayısı | 3 (Amazon, Vatan, InceHesap) |
| Kullanım amacı | 5 (Gaming, Portability, Productivity, Design, Dev) |
| Dev alt profili | 5 (Web, ML, Mobile, GameDev, General) |
| Test senaryosu | 100 (scenarios.py) |
| Marka tanımlı | 12 |
| Oyun başlığı | 10 |
| CPU/GPU skor girişi | ~60+ |
| Puanlama kriteri | 8 |
| Arayüz | 2 (CLI + Streamlit) |
| Birim testi | 11 (screen_size) + 3 (smoke) |

---

*Bu rapor, proje kodunun kapsamlı incelenmesi sonucu otomatik olarak oluşturulmuştur.*
*Rapor tarihi: 2026-02-06*
