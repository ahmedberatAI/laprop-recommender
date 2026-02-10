# Laprop Recommender

Not: Tüm güncel çıktılar `data/` altında tutulur.

## Data & Artifacts Policy
- Üretilen veri çıktıları `data/` altında tutulur ve git'e eklenmez.
- Test fixture'ları küçük örnekler olarak `tests/fixtures/` altında tutulur ve repoda kalır.

## LLM Preference Parsing (Optional)
- Serbest metin modu artık hibrit çalışır: `LLM + rule-based fallback`.
- Varsayılan davranış değişmez; LLM kapalıdır.
- LLM açmak için:
  - `LAPROP_ENABLE_LLM_PREFS=1`
  - `LAPROP_LLM_ADAPTER_DIR=/path/to/adapter` (Colab çıktındaki `adapter` klasörü)
  - Opsiyonel: `LAPROP_LLM_MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct`
- LLM hatası/dependency eksikliği/CUDA yokluğu durumunda sistem otomatik rule-based parse'a döner.
