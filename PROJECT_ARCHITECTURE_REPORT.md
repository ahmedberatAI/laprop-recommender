# Proje Mimari Raporu (recommender_2)

**Executive Summary**
- Proje; scraping (Amazon/InceHesap/Vatan/Epey), veri temizleme/normalize ve öneri motoru katmanlarından oluşuyor.
- Gerçek giriş noktaları: `recommender.py` (CLI), `streamlit_app.py` (UI), `simulation.py` (senaryo çalıştırma) ve bağımsız scraper scriptleri.
- `data/` klasörü güncel çıktıların merkezi; `load_data` CSV’leri birleştirip `laptop_cache.pkl` ile önbellekliyor.
- `processing` modülleri RAM/SSD/ekran/CPU/GPU çıkarımı yapıyor ve kalite uyarıları ekliyor.
- Skorlama ve filtreleme çekirdeği `recommend/engine.py` içinde; kurallar/presetler `config/rules.py` ile yönetiliyor.
- Scraper orkestrasyonu `ingestion/orchestrator.py` üzerinden subprocess ile yürütülüyor ve `all_data.csv` güncelleniyor.
- Epey scraper ayrı bir akış; `state.json` ile resume ediyor ve `out/` altına yazıyor.
- `raw/` büyük HTML dump’ları içeriyor; bu raporda tek tek listelenmedi (yalnızca klasör düzeyi belirtildi).

**Folder Tree**
```
recommender_2/
  amazon_scraper.py            # Amazon.com.tr scraper
  amazon_scraper_debug.py      # Amazon bot/captcha debug aracı
  epey_scraper.py              # Epey.com scraper (ayrı akış)
  incehesap_scraper.py         # InceHesap scraper + fix pipeline
  vatan_scraper.py             # VatanBilgisayar scraper
  price_collect.py             # Fiyat toplama ve eşleştirme aracı
  recommender.py               # CLI entrypoint (legacy wrapper)
  streamlit_app.py             # Streamlit UI entrypoint
  simulation.py                # Senaryo/simülasyon entrypoint
  data/                        # Güncel CSV/JSON çıktıları
  out/                         # Epey çıktı klasörü
  logs/                        # Çalışma logları/raporlar
  raw/                         # Büyük HTML dump’ları (tek tek listelenmedi)
  legacy/                      # Eski CSV snapshot’ları
  laprop/                      # Shim paket (src/laprop’a yönlendirir)
  scripts/                     # Yardımcı script’ler
  src/
    laprop/                    # Ana Python paketi
    laprop.egg-info/           # Paket metadata
  tests/
    fixtures/                  # HTML fixture dosyaları
```

**System Map**
Kontrol akışı (dependency graph): `recommender.py` → `src/laprop/app/main.py` → `src/laprop/app/cli.py`. CLI, `processing/read.py` ile veriyi yükler, `processing/clean.py` ile temizler ve `recommend/engine.py` ile öneri üretir. `streamlit_app.py` aynı çekirdek modülleri (`processing` + `recommend`) kullanır. `simulation.py` → `laprop.app.cli.run_simulation` → `recommend.engine.get_recommendations` akışıyla toplu senaryoları çalıştırır. Scraper çalıştırma ise `ingestion/orchestrator.py` üzerinden `amazon_scraper.py`, `incehesap_scraper.py`, `vatan_scraper.py` subprocess’leriyle yapılır ve sonrasında `storage/repository.py` ile `data/all_data.csv` güncellenir. `epey_scraper.py` bağımsızdır; orkestratör tarafından çağrılmaz. `price_collect.py` ayrı bir fiyat toplama/matching hattıdır ve `processing.normalize` yardımcılarını kullanır.

Veri akışı: Web sayfaları → `raw/` ve `cache_html/` (HTML dump/cache) → scraper CSV/JSON çıktıları (`data/*.csv`, `out/*.jsonl`) → `load_data()` ile birleşik DataFrame → `clean_data()` ile normalize/sayısallaştırma → `get_recommendations()` ile skor ve sıralama → CLI/Streamlit sonuçları veya `simulation_outputs.jsonl` çıktı dosyası. Ek olarak `append_to_all_data()` geçmiş scrape sonuçlarını `data/all_data.csv` içine deduplikasyonla ekler; `laptop_cache.pkl` hızlandırma için yazılır.

**File Cards**

**Root**
**File Card: `.gitignore`**
- Path: `.gitignore`
- Purpose: Git tarafından izlenmemesi gereken dosya/klasörleri tanımlar.
- Key functions/classes: (yok)
- Control flow / how it works: Git işlemleri sırasında ignore kuralları uygulanır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `README.md`**
- Path: `README.md`
- Purpose: Projenin kısa açıklamasını ve veri çıktılarının `data/` altında tutulduğunu belirtir.
- Key functions/classes: (yok)
- Control flow / how it works: Dokümantasyon dosyasıdır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `pyproject.toml`**
- Path: `pyproject.toml`
- Purpose: Paketleme/derleme metadata’sını (`laprop`, Python sürümü, build backend) tanımlar.
- Key functions/classes: (yok)
- Control flow / how it works: Paketleme araçları bu ayarları kullanır.
- Dependencies: `setuptools` build backend.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `requirements.txt`**
- Path: `requirements.txt`
- Purpose: Runtime bağımlılıklarını listeler (`streamlit`, `pandas`, `numpy`, `requests`, `beautifulsoup4`, `urllib3`).
- Key functions/classes: (yok)
- Control flow / how it works: `pip install -r requirements.txt` ile kurulur.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `tall -r requirements.txt`**
- Path: `tall -r requirements.txt`
- Purpose: İçeriği bir `git diff` çıktısına benziyor; muhtemelen yanlışlıkla kaydedilmiş terminal çıktısı (belirsiz).
- Key functions/classes: (yok)
- Control flow / how it works: Uygulanabilir bir script değil.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

> diff --git a/streamlit_app.py b/streamlit_app.py
> index 4ec3973..1cca692 100644
> --- a/streamlit_app.py

**File Card: `REFACTOR_REPORT.md`**
- Path: `REFACTOR_REPORT.md`
- Purpose: Monolitik `recommender.py`’den modüler `src/laprop/` yapısına refactor özetini anlatır.
- Key functions/classes: (yok)
- Control flow / how it works: Dokümantasyon dosyasıdır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `STREAMLIT_FOLLOWUPS_REPORT.md`**
- Path: `STREAMLIT_FOLLOWUPS_REPORT.md`
- Purpose: Streamlit UI’ya eklenen kullanım türü follow-up sorularını ve etkilerini açıklar.
- Key functions/classes: (yok)
- Control flow / how it works: Dokümantasyon dosyasıdır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `recommender.py`**
- Path: `recommender.py`
- Purpose: Legacy CLI entrypoint; `laprop.app.main.main()` çağırır ve hata yakalar.
- Key functions/classes: `main`
- Control flow / how it works: Script çalıştırıldığında CLI başlar; `KeyboardInterrupt` ve genel hataları `safe_print` ile yazdırır.
- Dependencies: `laprop.app.main`, `laprop.utils.console.safe_print`.
- Side effects: stdout/stderr yazımı.
- How to test/run: `python recommender.py --help` veya doğrudan `python recommender.py`.

**File Card: `streamlit_app.py`**
- Path: `streamlit_app.py`
- Purpose: Streamlit tabanlı web arayüzü; veri yükler, filtre uygular ve öneri sonuçlarını görselleştirir.
- Key functions/classes: `_load_data_cached`, `_apply_user_filters`, `_price_bounds`.
- Control flow / how it works: UI açıldığında `load_data()` + `clean_data()` ile veri hazırlanır; kullanıcı seçimleri `get_recommendations()` çağrısına dönüşür.
- Dependencies: `streamlit`, `pandas`, `laprop.config.rules`, `laprop.config.settings`, `laprop.processing.clean`, `laprop.processing.read`, `laprop.recommend.engine`, `laprop.app.cli.normalize_and_complete_preferences`.
- Side effects: Dosya okur (CSV); opsiyonel olarak `ALLOW_SCRAPE_UI=1` ile subprocess üzerinden scraper çalıştırır; kullanıcıya CSV download sunar.
- How to test/run: `streamlit run streamlit_app.py`.

**File Card: `simulation.py`**
- Path: `simulation.py`
- Purpose: CLI üzerinden senaryo tabanlı öneri simülasyonu çalıştırır.
- Key functions/classes: `main`, `_parse_args`, `_call_run_simulation`.
- Control flow / how it works: `load_data()` + `clean_data()` sonrasında `run_simulation()` çağırır; çıktı `simulation_outputs.jsonl`.
- Dependencies: `laprop.app.cli.run_simulation`, `laprop.processing.read`, `laprop.processing.clean`, `laprop.recommend.scenarios`.
- Side effects: `simulation_outputs.jsonl` yazar.
- How to test/run: `python simulation.py --n 100 --seed 42`.

**File Card: `price_collect.py`**
- Path: `price_collect.py`
- Purpose: Perakendeci arama sayfalarından fiyat toplayıp katalogla eşleştirir; `offers_raw.jsonl`, `offers_latest.csv`, `products_clean.csv`, `run_report.json` üretir.
- Key functions/classes: `SimpleHttpClient`, `RobotsManager`, `match_offer`, `run_collect`.
- Control flow / how it works: Katalog JSONL okunur → arama URL’leri oluşturulur → HTML parse edilir → teklif/katalog eşleştirme yapılır → çıktılar yazılır.
- Dependencies: `requests`, `beautifulsoup4`, `laprop.processing.normalize`.
- Side effects: Ağ istekleri; `data/` altına CSV/JSON yazma; `logs/run.log` yazma.
- How to test/run: `python price_collect.py --sources amazon,mediamarkt,vatan,incehesap --out data`.

**File Card: `amazon_scraper.py`**
- Path: `amazon_scraper.py`
- Purpose: Amazon.com.tr liste sayfalarından laptop verisi toplar ve CSV üretir.
- Key functions/classes: `AmazonLaptopScraper`, `_price_to_int_tl`, `_normalize_gpu`.
- Control flow / how it works: Sayfa sayfa arama sonuçları taranır → ürün alanları çıkarılır → normalize edilip `data/amazon_laptops.csv` yazılır.
- Dependencies: `requests`, `pandas`, `bs4`.
- Side effects: Ağ istekleri; CSV yazımı.
- How to test/run: `python amazon_scraper.py --max-pages 5 --output data/amazon_laptops.csv`.

**File Card: `amazon_scraper_debug.py`**
- Path: `amazon_scraper_debug.py`
- Purpose: Amazon taramasında bot/captcha teşhisi için debug aracı ve log üretimi.
- Key functions/classes: `run_debug`, `check_bot_or_captcha`.
- Control flow / how it works: Arama sayfalarına denemeler yapar, HTTP cevaplarını ve bot işaretlerini loglar; gerekirse HTML dump alır.
- Dependencies: `requests`, `bs4`.
- Side effects: `amazon_debug.log` yazar; opsiyonel HTML dump dosyaları oluşturur.
- How to test/run: `python amazon_scraper_debug.py --search laptop --start-page 1 --end-page 3`.

**File Card: `epey_scraper.py`**
- Path: `epey_scraper.py`
- Purpose: Epey.com laptop listesini/ürünlerini tarar, JSONL ve CSV çıktı üretir.
- Key functions/classes: `StateManager`, `HtmlCache`, `Fetcher`, `EpeyParser`, `process_product`.
- Control flow / how it works: Liste sayfaları taranır → ürün URL’leri toplanır → ürün sayfaları paralel işlenir → `out/epey_products.jsonl` ve `out/epey_laptops.csv` yazılır.
- Dependencies: `requests`, `bs4`, `threading`, `concurrent.futures`.
- Side effects: Ağ istekleri; `state.json` güncellenir; `cache_html/` ve `out/` dosyaları yazılır.
- How to test/run: `python epey_scraper.py --max-pages 10 --workers 4`.

**File Card: `incehesap_scraper.py`**
- Path: `incehesap_scraper.py`
- Purpose: InceHesap liste/ürün sayfalarını tarar; ayrıca CSV fix/normalize pipeline’ı içerir.
- Key functions/classes: `InceHesapScraper`, `ScrapeConfig`, `fix_incehesap_dataframe`, `scrape_then_fix`.
- Control flow / how it works: Liste URL’leri dolaşılır → ürün sayfaları parse edilir → raw CSV yazılır → fix pipeline ile normalleştirilmiş CSV + rapor üretilir.
- Dependencies: `requests`, `pandas`, `bs4`.
- Side effects: Ağ istekleri; `raw/incehesap_html` ve `data/incehesap_*.csv/json` yazımı.
- How to test/run: `python incehesap_scraper.py scrape --output data/incehesap_laptops.csv`.

**File Card: `vatan_scraper.py`**
- Path: `vatan_scraper.py`
- Purpose: VatanBilgisayar notebook sayfalarını tarar ve CSV/rapor üretir.
- Key functions/classes: `RateLimiter`, `HtmlStore`, `parse_product`, `collect_product_urls`.
- Control flow / how it works: Liste sayfalarından ürün URL’leri çıkarılır → ürün sayfaları paralel parse edilir → `data/vatan_laptops.csv` ve `data/vatan_scrape_report.json` yazılır.
- Dependencies: `requests`, `bs4`, `concurrent.futures`.
- Side effects: Ağ istekleri; `raw/vatan_html` HTML dump’ları; CSV/JSON rapor yazımı.
- How to test/run: `python vatan_scraper.py --max-pages 10 --out data/vatan_laptops.csv`.

**File Card: `sitecustomize.py`**
- Path: `sitecustomize.py`
- Purpose: `src/` dizinini `sys.path`’e ekler ve stdout/stderr encoding’i UTF-8 olarak ayarlar.
- Key functions/classes: `_reconfigure_stream`.
- Control flow / how it works: Python `sitecustomize` yüklerse otomatik çalışır.
- Dependencies: stdlib (`sys`, `os`, `pathlib`).
- Side effects: `sys.path` ve stream encoding’i değiştirir.
- How to test/run: Uygulanamaz; Python başlangıcında otomatik yüklenir.

**File Card: `state.json`**
- Path: `state.json`
- Purpose: `epey_scraper.py` için incremental crawl state dosyası.
- Key functions/classes: (yok)
- Control flow / how it works: `StateManager` tarafından okunur/yazılır.
- Dependencies: Üreten/Tüketen: `epey_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `laptop_cache.pkl`**
- Path: `laptop_cache.pkl`
- Purpose: `load_data()` tarafından oluşturulan birleşik veri önbelleği.
- Key functions/classes: (yok)
- Control flow / how it works: `processing/read.py` cache okur/yazar.
- Dependencies: Üreten/Tüketen: `src/laprop/processing/read.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `simulation_outputs.jsonl`**
- Path: `simulation_outputs.jsonl`
- Purpose: Simülasyon çıktıları (senaryo bazlı öneri sonuçları).
- Key functions/classes: (yok)
- Control flow / how it works: `laprop.app.cli.run_simulation()` yazar.
- Dependencies: Üreten: `simulation.py` veya `laprop.app.cli.run_simulation`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `amazon_debug.log`**
- Path: `amazon_debug.log`
- Purpose: `amazon_scraper_debug.py` çalıştırmalarının log çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: Debug scripti log yazar.
- Dependencies: Üreten: `amazon_scraper_debug.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `incehesap_fix_report.json`**
- Path: `incehesap_fix_report.json`
- Purpose: InceHesap fix pipeline raporu (root kopyası).
- Key functions/classes: (yok)
- Control flow / how it works: `incehesap_scraper.py` fix aşaması üretir.
- Dependencies: Üreten: `incehesap_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `incehesap_laptops_fixed.csv`**
- Path: `incehesap_laptops_fixed.csv`
- Purpose: InceHesap temizlenmiş CSV çıktısı (root kopyası).
- Key functions/classes: (yok)
- Control flow / how it works: `incehesap_scraper.py` fix pipeline üretir.
- Dependencies: Üreten: `incehesap_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `incehesap_warnings.log`**
- Path: `incehesap_warnings.log`
- Purpose: InceHesap parse/normalizasyon uyarı logları.
- Key functions/classes: (yok)
- Control flow / how it works: Scraper veya fix pipeline sırasında yazılmış uyarılar.
- Dependencies: Üreten: `incehesap_scraper.py` (muhtemel).
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**data/**
**File Card: `data/all_data.csv`**
- Path: `data/all_data.csv`
- Purpose: Farklı scraper çıktılarının deduplikasyonla birleştirilmiş arşivi.
- Key functions/classes: (yok)
- Control flow / how it works: `append_to_all_data()` tarafından append edilir.
- Dependencies: Üreten: `src/laprop/storage/repository.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/amazon_laptops.csv`**
- Path: `data/amazon_laptops.csv`
- Purpose: Amazon scraper çıktısı (URL, isim, fiyat, donanım alanları).
- Key functions/classes: (yok)
- Control flow / how it works: `amazon_scraper.py` yazar; `load_data()` okur.
- Dependencies: Üreten: `amazon_scraper.py`; Tüketen: `processing/read.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/incehesap_fix_report.json`**
- Path: `data/incehesap_fix_report.json`
- Purpose: InceHesap fix pipeline raporu (satır düzeltme istatistikleri).
- Key functions/classes: (yok)
- Control flow / how it works: `incehesap_scraper.py` fix aşaması yazar.
- Dependencies: Üreten: `incehesap_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/incehesap_laptops.csv`**
- Path: `data/incehesap_laptops.csv`
- Purpose: InceHesap temizlenmiş CSV çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: `incehesap_scraper.py` fix pipeline üretir; `load_data()` okur.
- Dependencies: Üreten: `incehesap_scraper.py`; Tüketen: `processing/read.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/incehesap_laptops_raw.csv`**
- Path: `data/incehesap_laptops_raw.csv`
- Purpose: InceHesap ham scrape çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: `incehesap_scraper.py` raw aşamada yazar.
- Dependencies: Üreten: `incehesap_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/teknosa_laptops.csv`**
- Path: `data/teknosa_laptops.csv`
- Purpose: Teknosa verisi için beklenen CSV (mevcut scraper yok).
- Key functions/classes: (yok)
- Control flow / how it works: `load_data()` bu dosyayı bekler; yoksa uyarı verir.
- Dependencies: Tüketen: `processing/read.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/vatan_laptops.csv`**
- Path: `data/vatan_laptops.csv`
- Purpose: Vatan scraper çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: `vatan_scraper.py` yazar; `load_data()` okur.
- Dependencies: Üreten: `vatan_scraper.py`; Tüketen: `processing/read.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `data/vatan_scrape_report.json`**
- Path: `data/vatan_scrape_report.json`
- Purpose: Vatan scraper çalışma raporu (tamamlanan sayfalar, eksikler, vb.).
- Key functions/classes: (yok)
- Control flow / how it works: `vatan_scraper.py` yazar.
- Dependencies: Üreten: `vatan_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**out/**

**File Card: `out/epey_products.jsonl`**
- Path: `out/epey_products.jsonl`
- Purpose: Epey ürün JSONL çıktısı (ham kayıtlar).
- Key functions/classes: (yok)
- Control flow / how it works: `epey_scraper.py` yazar.
- Dependencies: Üreten: `epey_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `out/epey_laptops.csv`**
- Path: `out/epey_laptops.csv`
- Purpose: Epey ürünlerinin normalize CSV çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: `epey_scraper.py` JSONL’den CSV üretir.
- Dependencies: Üreten: `epey_scraper.py`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**logs/**

**File Card: `logs/cleaning_report.json`**
- Path: `logs/cleaning_report.json`
- Purpose: Temizleme pipeline adımlarının detaylı raporu.
- Key functions/classes: (yok)
- Control flow / how it works: Harici bir cleaning pipeline tarafından üretilmiş görünüyor.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `logs/cleaning_report_summary.json`**
- Path: `logs/cleaning_report_summary.json`
- Purpose: Temizleme pipeline özet raporu (drop oranları vb.).
- Key functions/classes: (yok)
- Control flow / how it works: Harici bir cleaning pipeline tarafından üretilmiş görünüyor.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `logs/run.log`**
- Path: `logs/run.log`
- Purpose: JSON log formatında scraper/robot bloklama kayıtları.
- Key functions/classes: (yok)
- Control flow / how it works: Epey scraper veya price_collect tarzı bir süreç tarafından yazılmış.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `logs/scrape.log`**
- Path: `logs/scrape.log`
- Purpose: Scrape süreçlerine ait text loglar.
- Key functions/classes: (yok)
- Control flow / how it works: Muhtemelen scraper süreçleri tarafından yazılmış.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**legacy/**

**File Card: `legacy/all_data.csv`**
- Path: `legacy/all_data.csv`
- Purpose: Eski birleşik veri snapshot’ı.
- Key functions/classes: (yok)
- Control flow / how it works: Arşiv amaçlı tutulmuş.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `legacy/amazon_laptops.csv`**
- Path: `legacy/amazon_laptops.csv`
- Purpose: Eski Amazon scraper çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: Arşiv amaçlı tutulmuş.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `legacy/incehesap_laptops.csv`**
- Path: `legacy/incehesap_laptops.csv`
- Purpose: Eski InceHesap scraper çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: Arşiv amaçlı tutulmuş.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `legacy/vatan_laptops.csv`**
- Path: `legacy/vatan_laptops.csv`
- Purpose: Eski Vatan scraper çıktısı.
- Key functions/classes: (yok)
- Control flow / how it works: Arşiv amaçlı tutulmuş.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**laprop/**

**File Card: `laprop/__init__.py`**
- Path: `laprop/__init__.py`
- Purpose: Shim paket; `src/laprop` içeriğini root’tan `import laprop` ile kullanılabilir hale getirir.
- Key functions/classes: (yok)
- Control flow / how it works: `src/laprop/__init__.py` içeriğini exec ederek aynı namespace’e taşır.
- Dependencies: `pkgutil.extend_path`, `pathlib`.
- Side effects: `__path__` genişletilir; `src/laprop/__init__.py` yürütülür.
- How to test/run: `python scripts/smoke_imports.py`.

**scripts/**

**File Card: `scripts/smoke_imports.py`**
- Path: `scripts/smoke_imports.py`
- Purpose: `laprop` importunun çalıştığını doğrulayan basit smoke test.
- Key functions/classes: (yok)
- Control flow / how it works: `import laprop` → `print("OK")`.
- Dependencies: `laprop` paketi.
- Side effects: stdout yazımı.
- How to test/run: `python scripts/smoke_imports.py`.

**src/laprop/**
**File Card: `src/laprop/__init__.py`**
- Path: `src/laprop/__init__.py`
- Purpose: Paketin public API’sini tek noktadan re-export eder.
- Key functions/classes: `main` ve çok sayıda re-export.
- Control flow / how it works: İç modülleri import eder ve `__all__` ile dışa açar.
- Dependencies: `laprop.config`, `laprop.processing`, `laprop.recommend`, `laprop.app`, `laprop.storage`.
- Side effects: Import sırasında alt modüller yüklenir.
- How to test/run: `python -c "import laprop; print('ok')"`.

**File Card: `src/laprop/app/__init__.py`**
- Path: `src/laprop/app/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/app/main.py`**
- Path: `src/laprop/app/main.py`
- Purpose: Paket modu entrypoint; `cli.main()` çağırır.
- Key functions/classes: `main`.
- Control flow / how it works: `laprop.app.cli.main` çağrılır; hatalar `safe_print` ile gösterilir.
- Dependencies: `laprop.app.cli`, `laprop.utils.console`.
- Side effects: stdout/stderr yazımı.
- How to test/run: `python -m laprop.app.main`.

**File Card: `src/laprop/app/cli.py`**
- Path: `src/laprop/app/cli.py`
- Purpose: CLI menü akışı, kullanıcı tercihleri, serbest metin parse ve simülasyon mantığı.
- Key functions/classes: `main`, `get_user_preferences`, `get_user_preferences_free_text`, `run_simulation`, `normalize_and_complete_preferences`.
- Control flow / how it works: Kullanıcıdan tercihleri alır → veriyi yükler/temizler → `get_recommendations()` çağırır → sonuçları yazdırır.
- Dependencies: `numpy`, `pandas`, `laprop.config.rules`, `laprop.processing.read`, `laprop.processing.clean`, `laprop.recommend.engine`, `laprop.ingestion.orchestrator`.
- Side effects: stdout/stderr; `simulation_outputs.jsonl` yazımı; scraper subprocess çağrısı.
- How to test/run: `python recommender.py` veya `python -m laprop.app.main`.

**File Card: `src/laprop/config/__init__.py`**
- Path: `src/laprop/config/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/config/settings.py`**
- Path: `src/laprop/config/settings.py`
- Purpose: Proje kök dizini, data yolları, scraper script yollarını tanımlar.
- Key functions/classes: (yok)
- Control flow / how it works: Statik sabitler sağlar.
- Dependencies: `pathlib`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/config/rules.py`**
- Path: `src/laprop/config/rules.py`
- Purpose: Skor tabloları, kullanım presetleri ve ağırlıklar (CPU/GPU/brand vb.).
- Key functions/classes: (yok; sabitler)
- Control flow / how it works: `engine.py` ve UI/CLI bu sabitleri kullanır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/config/benchmarks.py`**
- Path: `src/laprop/config/benchmarks.py`
- Purpose: Opsiyonel benchmark CSV’lerini okur ve normalize eder.
- Key functions/classes: `_safe_load_bench`.
- Control flow / how it works: `bench_cpu.csv` / `bench_gpu.csv` varsa okunur ve `score_0_10` normalize edilir.
- Dependencies: `pandas`, `laprop.utils.console`, `laprop.config.settings`.
- Side effects: Uyarı mesajı basabilir.
- How to test/run: Uygulanamaz (dosyalar opsiyonel).

**File Card: `src/laprop/ingestion/__init__.py`**
- Path: `src/laprop/ingestion/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/ingestion/orchestrator.py`**
- Path: `src/laprop/ingestion/orchestrator.py`
- Purpose: Scraper scriptlerini çalıştırır ve master dataset’i günceller.
- Key functions/classes: `run_scrapers`.
- Control flow / how it works: Her scraper subprocess ile çalıştırılır → çıktı CSV’leri güncellenir → `append_to_all_data()` çağrılır → cache temizlenir.
- Dependencies: `subprocess`, `laprop.config.settings`, `laprop.storage.repository`.
- Side effects: Scraper subprocess çağrısı; `data/*.csv` ve `data/all_data.csv` güncellemesi; `laptop_cache.pkl` silme.
- How to test/run: `python recommender.py --run-scrapers`.

**File Card: `src/laprop/ingestion/sources/__init__.py`**
- Path: `src/laprop/ingestion/sources/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/ingestion/sources/amazon.py`**
- Path: `src/laprop/ingestion/sources/amazon.py`
- Purpose: Amazon scraper script yolunu sabit olarak taşır.
- Key functions/classes: `SCRIPT_PATH` sabiti.
- Control flow / how it works: Orkestratör veya diğer modüller script yolunu buradan alabilir.
- Dependencies: `laprop.config.settings`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/ingestion/sources/incehesap.py`**
- Path: `src/laprop/ingestion/sources/incehesap.py`
- Purpose: InceHesap scraper script yolunu sabit olarak taşır.
- Key functions/classes: `SCRIPT_PATH` sabiti.
- Control flow / how it works: (yok)
- Dependencies: `laprop.config.settings`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/ingestion/sources/vatan.py`**
- Path: `src/laprop/ingestion/sources/vatan.py`
- Purpose: Vatan scraper script yolunu sabit olarak taşır.
- Key functions/classes: `SCRIPT_PATH` sabiti.
- Control flow / how it works: (yok)
- Dependencies: `laprop.config.settings`.
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/processing/__init__.py`**
- Path: `src/laprop/processing/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/processing/read.py`**
- Path: `src/laprop/processing/read.py`
- Purpose: CSV okuma, kolon standardizasyonu ve `laptop_cache.pkl` cache yönetimi.
- Key functions/classes: `load_data`, `read_csv_robust`, `_standardize_columns`.
- Control flow / how it works: `DATA_FILES` listesi taranır → CSV’ler normalize edilir → birleşik DataFrame oluşturulur → cache yazılır.
- Dependencies: `pandas`, `pickle`, `laprop.config.settings`, `laprop.utils.console`.
- Side effects: `laptop_cache.pkl` yazma; stdout loglar.
- How to test/run: CLI/Streamlit çalıştırıldığında otomatik.

**File Card: `src/laprop/processing/normalize.py`**
- Path: `src/laprop/processing/normalize.py`
- Purpose: Başlıklardan CPU/GPU/RAM/SSD/ekran boyutu çıkarımı ve normalize yardımcıları.
- Key functions/classes: `normalize_cpu`, `normalize_gpu`, `normalize_gpu_model`, `parse_ram_gb`, `parse_ssd_gb`, `parse_screen_size`.
- Control flow / how it works: Regex tabanlı kurallar ile değerler çıkarılır; heuristik skorlar kullanılır.
- Dependencies: `re`, `numpy`, `pandas`.
- Side effects: (yok)
- How to test/run: `pytest tests/test_screen_size.py`.

**File Card: `src/laprop/processing/clean.py`**
- Path: `src/laprop/processing/clean.py`
- Purpose: Veri temizleme; fiyat/RAM/SSD/screen normalize eder ve skor alanları ekler.
- Key functions/classes: `clean_data`, `clean_price`, `clean_ram_value`, `clean_ssd_value`.
- Control flow / how it works: CSV kolonları standardize edilir → kritik alanlar parse edilir → CPU/GPU skorları hesaplanır → kalite uyarıları eklenir.
- Dependencies: `pandas`, `numpy`, `laprop.processing.normalize`, `laprop.processing.validate`, `laprop.recommend.engine`.
- Side effects: stdout loglar.
- How to test/run: CLI/Streamlit çalıştırıldığında otomatik.

**File Card: `src/laprop/processing/validate.py`**
- Path: `src/laprop/processing/validate.py`
- Purpose: Başlık içindeki değerler için basit doğrulama/uyarı üretir.
- Key functions/classes: `validate_record`.
- Control flow / how it works: RAM/ekran boyutu değerlerini tarar ve uyarı listesi döndürür.
- Dependencies: `laprop.processing.normalize`.
- Side effects: (yok)
- How to test/run: `clean_data()` sırasında otomatik.

**File Card: `src/laprop/processing/merge.py`**
- Path: `src/laprop/processing/merge.py`
- Purpose: Placeholder; şu an aktif kullanılmıyor.
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/recommend/__init__.py`**
- Path: `src/laprop/recommend/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/recommend/engine.py`**
- Path: `src/laprop/recommend/engine.py`
- Purpose: Öneri motorunun filtreleme ve skorlama çekirdeği.
- Key functions/classes: `get_recommendations`, `calculate_score`, `filter_by_usage`, `compute_dev_fit`.
- Control flow / how it works: Bütçe filtresi → kullanım profiline göre filtreleme → skor hesaplama → sıralama → Top-N çıktı.
- Dependencies: `pandas`, `numpy`, `laprop.config.rules`, `laprop.processing.normalize`, `laprop.processing.read`.
- Side effects: stdout loglar.
- How to test/run: CLI/Streamlit çalıştırıldığında otomatik.

**File Card: `src/laprop/recommend/explain.py`**
- Path: `src/laprop/recommend/explain.py`
- Purpose: Placeholder; şu an aktif kullanılmıyor.
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/recommend/scenarios.py`**
- Path: `src/laprop/recommend/scenarios.py`
- Purpose: Simülasyon senaryo listesi (SCENARIOS).
- Key functions/classes: `SCENARIOS` listesi.
- Control flow / how it works: `run_simulation()` bu listeden N senaryo çalıştırır.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: `python simulation.py --n 50`.

**File Card: `src/laprop/storage/__init__.py`**
- Path: `src/laprop/storage/__init__.py`
- Purpose: Paket init (boş/placeholder).
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/storage/repository.py`**
- Path: `src/laprop/storage/repository.py`
- Purpose: `all_data.csv` güncelleme ve deduplikasyon yardımcıları.
- Key functions/classes: `append_to_all_data`, `_dedupe_dataframe`.
- Control flow / how it works: Mevcut `all_data.csv` anahtarları okunur → yeni scrape verileri dedupe edilir → append edilir.
- Dependencies: `pandas`, `laprop.config.settings`, `laprop.utils.console`.
- Side effects: `data/all_data.csv` yazımı.
- How to test/run: `python recommender.py --run-scrapers` sonrası otomatik.

**File Card: `src/laprop/utils/__init__.py`**
- Path: `src/laprop/utils/__init__.py`
- Purpose: Boş init dosyası.
- Key functions/classes: (yok)
- Control flow / how it works: (yok)
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop/utils/console.py`**
- Path: `src/laprop/utils/console.py`
- Purpose: Unicode/encoding güvenli yazdırma yardımcıları.
- Key functions/classes: `safe_print`, `safe_str`.
- Control flow / how it works: Encoding uyumsuzluklarında `backslashreplace` ile güvenli çıktı üretir.
- Dependencies: `sys`.
- Side effects: stdout/stderr yazımı.
- How to test/run: CLI çalıştırıldığında otomatik.

**src/laprop.egg-info/**
**File Card: `src/laprop.egg-info/dependency_links.txt`**
- Path: `src/laprop.egg-info/dependency_links.txt`
- Purpose: setuptools tarafından oluşturulan paket metadata dosyası.
- Key functions/classes: (yok)
- Control flow / how it works: Paketleme sırasında güncellenir.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop.egg-info/PKG-INFO`**
- Path: `src/laprop.egg-info/PKG-INFO`
- Purpose: Paket metadata (adı, sürüm, açıklama vb.).
- Key functions/classes: (yok)
- Control flow / how it works: Paketleme sırasında oluşturulur.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop.egg-info/SOURCES.txt`**
- Path: `src/laprop.egg-info/SOURCES.txt`
- Purpose: Paket kaynak dosya listesi.
- Key functions/classes: (yok)
- Control flow / how it works: Paketleme sırasında oluşturulur.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**File Card: `src/laprop.egg-info/top_level.txt`**
- Path: `src/laprop.egg-info/top_level.txt`
- Purpose: Top-level package adını belirtir.
- Key functions/classes: (yok)
- Control flow / how it works: Paketleme sırasında oluşturulur.
- Dependencies: (yok)
- Side effects: (yok)
- How to test/run: Uygulanamaz.

**tests/**

**File Card: `tests/conftest.py`**
- Path: `tests/conftest.py`
- Purpose: Testlerde `src/` ve repo kökünü `sys.path`’e ekler.
- Key functions/classes: (yok)
- Control flow / how it works: Pytest başlangıcında otomatik yüklenir.
- Dependencies: `pathlib`, `sys`.
- Side effects: `sys.path` günceller.
- How to test/run: `pytest` ile otomatik.

**File Card: `tests/test_epey_csv_write.py`**
- Path: `tests/test_epey_csv_write.py`
- Purpose: `epey_scraper.generate_csv_from_jsonl` fonksiyonunun CSV çıktısını doğrular.
- Key functions/classes: `TestEpeyCsvWrite`.
- Control flow / how it works: Geçici JSONL yazar → CSV oluşturur → header/row doğrular.
- Dependencies: `unittest`, `tempfile`, `epey_scraper`.
- Side effects: Geçici dosya oluşturur.
- How to test/run: `pytest tests/test_epey_csv_write.py`.

**File Card: `tests/test_scraper_smoke.py`**
- Path: `tests/test_scraper_smoke.py`
- Purpose: Scraper scriptlerinin `--help` çıktısını smoke test eder; InceHesap fixture parse testini içerir.
- Key functions/classes: `test_scraper_help`, `test_incehesap_parse_list_fixture`.
- Control flow / how it works: Subprocess ile `--help` çalıştırır; fixture HTML parse doğrular.
- Dependencies: `pytest`, `subprocess`, `incehesap_scraper`.
- Side effects: (yok)
- How to test/run: `pytest tests/test_scraper_smoke.py`.

**File Card: `tests/test_screen_size.py`**
- Path: `tests/test_screen_size.py`
- Purpose: `parse_screen_size` fonksiyonunun farklı formatları doğru parse ettiğini test eder.
- Key functions/classes: `TestScreenSizeParsing`.
- Control flow / how it works: Parametrik örneklerle parse sonucu doğrulanır.
- Dependencies: `unittest`, `laprop.processing.normalize`.
- Side effects: (yok)
- How to test/run: `pytest tests/test_screen_size.py`.

**tests/fixtures/**

**File Card: `tests/fixtures/incehesap_list.html`**
- Path: `tests/fixtures/incehesap_list.html`
- Purpose: InceHesap liste sayfası parse testlerinde kullanılan HTML fixture.
- Key functions/classes: (yok)
- Control flow / how it works: `test_incehesap_parse_list_fixture` tarafından okunur.
- Dependencies: Tüketen: `tests/test_scraper_smoke.py`.
- Side effects: (yok)
- How to test/run: `pytest tests/test_scraper_smoke.py`.

**How to Run**
1. Bağımlılıkları kurun: `pip install -r requirements.txt`.
2. Veri toplama (güncelleme) için: `python recommender.py --run-scrapers`.
3. CLI öneri akışı: `python recommender.py` veya `python -m laprop.app.main`.
4. Streamlit arayüzü: `streamlit run streamlit_app.py`.
5. Simülasyon/evaluasyon: `python simulation.py --n 100 --seed 42`.

**Testing**
1. `pip install pytest`.
2. `pytest -q`.

**Gotchas & Maintenance Notes**
- Scraper’lar bot/captcha engellerine takılabilir; Amazon için `amazon_scraper_debug.py` ile teşhis yapın.
- `epey_scraper.py` robots.txt ve 403 blokları nedeniyle sık kesilebilir; `logs/run.log` ve `logs/scrape.log` takip edin.
- `streamlit_app.py` içinde `sys` importu eksik görünüyor; UI’dan scraper çalıştırma kısmı hata verebilir.
- `DATA_FILES` listesinde `teknosa_laptops.csv` var ancak scraper yok; bu dosya yoksa `load_data()` uyarı verebilir.
- `bench_cpu.csv` / `bench_gpu.csv` dosyaları opsiyonel; yoksa `benchmarks.py` uyarı basar.
- RAM/SSD/ekran parse mantığı regex ve heuristiklere dayanıyor; `incehesap_warnings.log` ve parse uyarılarına dikkat edin.
- `raw/` altında çok büyük HTML dump’ları bulunur; repo büyüklüğünü artırır ve raporda tek tek listelenmedi.
- `sitecustomize.py` yüklenmezse `src/` import edilemeyebilir; `python -m laprop.app.main` veya `pip install -e .` ile çalıştırmak daha güvenli.
- `tall -r requirements.txt` dosyası muhtemelen yanlışlıkla kaydedilmiş diff çıktısı; temizlenmesi düşünülebilir.
- `price_collect.py` varsayılan olarak `data/catalog.jsonl` bekler; dosya yoksa önce katalog üretimi gerekir.

**TODO opportunities**
- `teknosa` için gerçek scraper ekleyin veya `DATA_FILES` listesinden çıkarın.
- `streamlit_app.py` için eksik `sys` importunu ekleyip scraper UI akışını stabil hale getirin.
- Scraper log formatlarını standardize edin (`logs/` altına tek format yazım).
- `clean_data` ve parse fonksiyonlarını daha test edilebilir küçük parçalara bölün; ek testler ekleyin.
- `price_collect.py` çıktılarıyla öneri motorunu entegre eden bir pipeline ekleyin.
- `raw/` ve `cache_html/` için retention/temizlik politikası belirleyin.
