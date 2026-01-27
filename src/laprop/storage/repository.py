from datetime import datetime

import pandas as pd

from ..config.settings import DATA_FILES, ALL_DATA_FILE
def append_to_all_data():
    """Yeni scraping verilerini all_data.csv'ye ekler (tarih damgası ile)"""
    print("\n📝 all_data.csv güncelleniyor...")

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_data_list = []

    # Mevcut CSV dosyalarını oku
    for file_path in DATA_FILES:
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
                df['scraped_at'] = current_time  # Tarih damgası ekle
                df['source'] = file_path.stem.replace('_laptops', '')  # Kaynak bilgisi
                new_data_list.append(df)
                print(f"  ✅ {file_path.name}: {len(df)} kayıt eklendi")
            except Exception as e:
                print(f"  ⚠️ {file_path.name} okunamadı: {e}")

    if not new_data_list:
        print("  ℹ️ Eklenecek yeni veri yok")
        return

    # Yeni verileri birleştir
    new_data = pd.concat(new_data_list, ignore_index=True)

    # all_data.csv varsa, mevcut verilerle birleştir
    if ALL_DATA_FILE.exists():
        try:
            existing_data = pd.read_csv(ALL_DATA_FILE, encoding='utf-8')
            combined_data = pd.concat([existing_data, new_data], ignore_index=True)
            print(f"  📊 Mevcut {len(existing_data)} kayda {len(new_data)} yeni kayıt eklendi")
        except Exception as e:
            print(f"  ⚠️ Mevcut all_data.csv okunamadı, yeni dosya oluşturuluyor: {e}")
            combined_data = new_data
    else:
        combined_data = new_data
        print(f"  🆕 Yeni all_data.csv oluşturuluyor ({len(new_data)} kayıt)")

    # Kaydet
    try:
        combined_data.to_csv(ALL_DATA_FILE, index=False, encoding='utf-8-sig')
        print(f"  ✅ all_data.csv kaydedildi: toplam {len(combined_data)} kayıt")
    except Exception as e:
        print(f"  ❌ all_data.csv kaydedilemedi: {e}")
