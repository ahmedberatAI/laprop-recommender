DEV_PRESETS = {
    # 1) Web/Backend
    'web': {
        'min_ram': 16, 'min_ssd': 512,
        'screen_max': 15.6,     # taşınabilirlik ama 14–15.6 rahat
        'prefer_os': {'windows': 1.0, 'macos': 1.0, 'linux': 1.05},
        'need_dgpu': False, 'need_cuda': False,
        'cpu_bias': {'hx': +1.0, 'h': +0.5, 'u': -0.2, 'p': +0.2},  # çok çekirdek bonusu
        'gpu_bias': {'igpu_ok': +0.3, 'dgpu_penalty': -0.2},       # gereksiz dGPU azıcık eksi
        'port_bias': {'<=14': +0.3, '<=15.6': +0.2, '>16': -0.4}
    },

    # 2) Veri/ML (CUDA odaklı; Mac/Arc için framework seçiminde farklı yol gerekir)
    'ml': {
        'min_ram': 32, 'min_ssd': 1024,
        'screen_max': 16.0,     # 15–16 inç makul
        'prefer_os': {'windows': 1.04, 'macos': 1.00, 'linux': 1.03},
        'need_dgpu': True, 'need_cuda': True,                      # NVIDIA şart (heuristic)
        'cpu_bias': {'hx': +0.8, 'h': +0.5, 'u': -0.6, 'p': -0.2},
        # mevcut kural dili korunuyor
        'gpu_bias': {'rtx>=4060': +1.2, 'rtx>=4050': +0.8, 'rtx<4050': +0.3, 'igpu': -2.0},
        'port_bias': {'<=14': -0.2, '<=15.6': +0.2, '>16': -0.1}
    },

    # 3) Mobil (Android/iOS)
    'mobile': {
        'min_ram': 16, 'min_ssd': 512,
        'screen_max': 14.5,
        'prefer_os': {'macos': 1.06, 'windows': 1.0, 'linux': 0.98},  # Xcode avantajı
        'need_dgpu': False, 'need_cuda': False,
        'cpu_bias': {'u': +0.6, 'p': +0.3, 'h': -0.2, 'hx': -0.5},
        'gpu_bias': {'igpu_ok': +0.5, 'heavy_dgpu': -0.6},
        'port_bias': {'<=13.6': +0.8, '<=14.5': +0.5, '15-16': -0.2}
    },

    # 4) Oyun Motoru / 3D (Unreal/Unity)
    'gamedev': {
        'min_ram': 32, 'min_ssd': 1024,
        'screen_max': 16.0,
        'prefer_os': {'windows': 1.04, 'macos': 0.97, 'linux': 1.0},
        'need_dgpu': True, 'need_cuda': True,
        'cpu_bias': {'hx': +1.0, 'h': +0.6, 'u': -0.8, 'p': -0.3},
        'gpu_bias': {'rtx>=4070': +1.2, 'rtx>=4060': +0.9, 'rtx>=4050': +0.5, 'igpu': -2.5},
        'port_bias': {'<=14': -0.2, '<=15.6': +0.2, '>16': +0.1}  # 15–16 daha iyi
    },

    # 5) Genel CS Öğrencisi
    'general': {
        'min_ram': 16, 'min_ssd': 512,
        'screen_max': 15.6,
        'prefer_os': {'windows': 1.02, 'macos': 1.02, 'linux': 1.02},
        'need_dgpu': False, 'need_cuda': False,
        'cpu_bias': {'h': +0.3, 'p': +0.2, 'u': 0.0, 'hx': -0.1},
        'gpu_bias': {'igpu_ok': +0.3, 'mid_dgpu': +0.1},
        'port_bias': {'<=14': +0.3, '<=15.6': +0.2, '>16': -0.2}
    }
}

GAMING_TITLE_SCORES = {
    "Starfield": 7.5,                         # RX 6800 XT / RTX 2080 bandı
    "Call of Duty: Black Ops 6": 7.0,         # RTX 3060 / RX 6600 XT bandı
    "Forza Horizon 5": 5.2,                   # GTX 1070 / RX 590 bandı
    "Baldur's Gate 3": 6.5,                   # RTX 2060 Super / RX 5700 XT bandı
    "Helldivers 2": 6.5,                      # RTX 2060 / RX 6600 XT bandı
    "Cyberpunk 2077 (2.0)": 6.6,              # RTX 2060 Super / RX 5700 XT bandı
    "Assassin's Creed Mirage": 5.8,           # GTX 1660 Ti / RX 5600 XT bandı
    "Forza Motorsport (2023)": 7.5,           # RTX 2080 Ti / RX 6800 XT / Arc A770 bandı
    "Lies of P": 5.5,                         # GTX 1660 bandı
    "Apex/Fortnite (yüksek ayar)": 5.0        # entry-mid (espor + yüksek ayar)
}

CPU_SCORES = {
    # Intel 14. nesil (genel tier)
    'i9-14': 9.5, 'i7-14': 8.5, 'i5-14': 7.0, 'i3-14': 5.0,

    # Intel 13. nesil
    'i9-13': 9.0, 'i7-13': 8.0, 'i5-13': 6.5, 'i3-13': 4.5,

    # Intel 12. nesil
    'i9-12': 8.5, 'i7-12': 7.5, 'i5-12': 6.0, 'i3-12': 4.0,

    # Intel Core Ultra (Meteor Lake / yeni isimlendirme)
    'ultra 9': 9.0, 'ultra 7': 8.0, 'ultra 5': 7.0,

    # AMD Ryzen (kaba tier: 7xxx/8xxx)
    'ryzen 9 7': 9.2, 'ryzen 7 7': 8.2, 'ryzen 5 7': 6.8,
    'ryzen 9 8': 9.5, 'ryzen 7 8': 8.5, 'ryzen 5 8': 7.0,

    # Apple Silicon (Pro/Max katmanları eklendi)
    'm1': 7.8, 'm1 pro': 8.3, 'm1 max': 8.5,
    'm2': 8.2, 'm2 pro': 8.8, 'm2 max': 9.0,
    'm3': 8.6, 'm3 pro': 8.7, 'm3 max': 9.4,
    'm4': 9.1, 'm4 pro': 9.6, 'm4 max': 9.8,
}

GPU_SCORES = {
    # NVIDIA GeForce RTX 50 (Laptop)
    'rtx 5090': 10.0,
    'rtx 5080': 9.7,
    'rtx 5070': 8.8,
    'rtx 5060': 8.4,
    'rtx 5050': 7.8,

    # NVIDIA GeForce RTX 40 (Laptop)
    'rtx 4090': 9.8,
    'rtx 4080': 9.3,
    'rtx 4070': 8.8,
    'rtx 4060': 8.0,
    'rtx 4050': 7.2,

    # NVIDIA GeForce RTX 30 (Laptop) - kaba tier (TGP çok oynatır)
    'rtx 3080': 8.5, 'rtx 3070': 7.8, 'rtx 3060': 7.0, 'rtx 3050': 6.0,

    # NVIDIA GeForce RTX 20 (Laptop) — oyun gereksinimleri için faydalı
    'rtx 2080': 8.0, 'rtx 2070': 7.2, 'rtx 2060': 6.7,

    # NVIDIA GTX/MX
    'gtx 16': 5.0,
    'gtx 1660': 5.5, 'gtx 1650': 5.0, 'gtx 1060': 4.5,
    'mx5': 4.0, 'mx4': 3.5, 'mx3': 3.0,

    # NVIDIA Workstation (Ada / Laptop)
    'rtx 5000 ada': 9.1,
    'rtx 4000 ada': 8.9,
    'rtx 3500 ada': 8.4,
    'rtx 2000 ada': 7.3,

    # NVIDIA Workstation (Ampere A-serisi) - kaba tier
    'rtx a5000': 8.0,
    'rtx a4000': 7.4,

    # AMD Radeon (Laptop)
    'rx 7900m': 9.4, 'rx 7800m': 8.8, 'rx 7700s': 8.0,
    'rx 7600m xt': 7.2, 'rx 7600m': 7.0,
    'rx 6800m': 7.6, 'rx 6700m': 7.0, 'rx 6600m': 6.6,
    'rx 7': 7.5, 'rx 6': 6.5, 'radeon': 5.0,

    # Intel Arc (Laptop)
    'arc a770m': 7.1, 'arc a730m': 6.4, 'arc a550m': 5.6, 'arc a370m': 4.8,
    'arc': 5.5,

    # Integrated
    'radeon 890m': 4.4, 'radeon 880m': 4.2, 'radeon 780m': 4.0,
    'iris xe': 3.5, 'iris plus': 3.0, 'uhd': 2.0, 'integrated': 2.0,

    # Apple (Metal/CUDA yok; genel GPU gücü kaba)
    'm4 gpu': 6.5, 'm4 pro gpu': 7.0, 'm4 max gpu': 7.5,
    'm3 gpu': 6.0, 'm3 pro gpu': 6.6, 'm3 max gpu': 7.2,
    'm2 gpu': 5.5, 'm2 pro gpu': 6.1, 'm2 max gpu': 6.7,
    'm1 gpu': 5.0, 'm1 pro gpu': 5.6, 'm1 max gpu': 6.2,
}

BRAND_PARAM_SCORES = {
    "apple": {"gaming": 65, "portability": 95, "productivity": 90, "design": 98, "dev": 92},
    "lenovo": {"gaming": 85, "portability": 82, "productivity": 95, "design": 85, "dev": 93},
    "asus": {"gaming": 92, "portability": 75, "productivity": 85, "design": 88, "dev": 85},
    "dell": {"gaming": 80, "portability": 83, "productivity": 92, "design": 87, "dev": 90},
    "hp": {"gaming": 78, "portability": 82, "productivity": 88, "design": 90, "dev": 84},
    "huawei": {"gaming": 60, "portability": 90, "productivity": 82, "design": 92, "dev": 80},
    "samsung": {"gaming": 65, "portability": 92, "productivity": 80, "design": 91, "dev": 78},
    "msi": {"gaming": 95, "portability": 60, "productivity": 75, "design": 78, "dev": 80},
    "acer": {"gaming": 80, "portability": 78, "productivity": 78, "design": 75, "dev": 78},
    "microsoft": {"gaming": 55, "portability": 88, "productivity": 86, "design": 90, "dev": 85},
    "monster": {"gaming": 90, "portability": 55, "productivity": 70, "design": 70, "dev": 75},
    "casper": {"gaming": 75, "portability": 70, "productivity": 72, "design": 70, "dev": 73},
}

BRAND_SCORES = {
    "apple": 9.5,
    "lenovo": 9.0,
    "dell": 8.8,
    "asus": 8.5,
    "hp": 8.3,
    "microsoft": 8.5,
    "huawei": 8.0,
    "samsung": 8.0,
    "msi": 8.0,
    "acer": 7.5,
    "monster": 7.0,
    "casper": 6.8,
    "other": 5.0
}

USAGE_OPTIONS = {
    1: ("gaming", "🎮 Oyun"),
    2: ("portability", "💼 Taşınabilirlik"),
    3: ("productivity", "📈 Üretkenlik"),
    4: ("design", "🎨 Tasarım"),
    5: ("dev", "👨‍💻 Yazılım Geliştirme")
}

BASE_WEIGHTS = {
    'price': 25,
    'performance': 20,
    'ram': 15,
    'storage': 10,
    'brand': 10,
    'brand_purpose': 10,
    'battery': 5,
    'portability': 5
}

RTX_MODEL_SCORES = {
    # RTX 50 (Laptop)
    '5090': 10.0, '5080': 9.7, '5070': 8.8, '5060': 8.4, '5050': 7.8,

    # RTX 40 (Laptop)
    '4090': 9.8, '4080': 9.3, '4070': 8.8, '4060': 8.0, '4050': 7.2,

    # RTX 30 (Laptop)
    '3090': 8.9, '3080': 8.5, '3070': 7.8, '3060': 7.0, '3050': 6.0,

    # RTX 20 (Laptop)
    '2080': 8.0, '2070': 7.2, '2060': 6.7,

    # Workstation Ada / A-serisi (kaba)
    '5000': 9.1, '4000': 8.9, '3500': 8.4, '2000': 7.3,
}

GTX_MODEL_SCORES = {
    '1070': 5.3,
    '1660': 5.5, '1650': 5.0,
    '1060': 4.5, '1050': 4.2,
    '970': 4.2, '960': 3.8,
}

MX_MODEL_SCORES = {
    '570': 4.2, '550': 4.0, '450': 3.6, '350': 3.2, '330': 3.0
}

RX_MODEL_SCORES = {
    # Mobil suffix’li
    '7900m': 9.4, '7800m': 8.8, '7700s': 8.0,
    '7600mxt': 7.2, '7600m': 7.0,
    '6800m': 7.6, '6700m': 7.0, '6600m': 6.6,

    # Suffix’siz yakalayıcı (bazı siteler “RX 7800” diye yazıyor)
    '7900': 9.4, '7800': 8.8, '7700': 8.0, '7600': 7.2,
    '6800': 7.6, '6700': 7.0, '6600': 6.6
}

IMPORTANCE_MULT = {
    1: 0.5,   # Önemsiz
    2: 0.75,  # Az önemli
    3: 1.0,   # Normal
    4: 1.5,   # Önemli
    5: 2.0    # Çok önemli
}

MIN_REQUIREMENTS = {
    'gaming': {'gpu_score': 6.0, 'ram_gb': 16, 'cpu_score': 6.5},
    'portability': {'screen_size_max': 14.5, 'weight_preference': 'light'},
    'productivity': {'ram_gb': 16, 'cpu_score': 6.0},
    'design': {'ram_gb': 16, 'screen_quality': 'high', 'gpu_score': 5.0},
    'dev': {'ram_gb': 16, 'cpu_score': 7.0, 'ssd_gb': 512}
}
