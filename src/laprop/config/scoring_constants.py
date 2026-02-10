"""
Scoring engine sabit değerleri.

engine.py'deki magic number'lar buraya çıkarılmıştır.
Tek bir yerden ayarlanabilir, test edilebilir hale gelmiştir.
"""

# ── CPU suffix ayarlamaları ──────────────────────────────────────────
CPU_SUFFIX_HX_BONUS = 0.5       # HX suffix → skor artışı
CPU_SUFFIX_U_PENALTY = 1.0      # U suffix → skor düşüşü
CPU_SUFFIX_P_PENALTY = 0.3      # P suffix → skor düşüşü

# ── CPU fallback skorları ────────────────────────────────────────────
CPU_FALLBACK_I9 = 9.0
CPU_FALLBACK_I7 = 7.5
CPU_FALLBACK_I5 = 6.0
CPU_FALLBACK_I3 = 4.0
CPU_DEFAULT_SCORE = 5.0

# ── GPU skorlama sabitleri ───────────────────────────────────────────
GPU_DEFAULT_SCORE = 2.0
GPU_IGPU_HIGH_SCORE = 3.5       # 780M, 680M
GPU_IGPU_MID_SCORE = 3.0        # 760M, 660M
GPU_IGPU_LOW_SCORE = 2.5        # diğer iGPU'lar
GPU_ARC_HIGH_SCORE = 7.5        # A770, A750
GPU_ARC_MID_SCORE = 6.5         # A570, A550
GPU_ARC_LOW_SCORE = 5.5         # A370, A350
GPU_ARC_DEFAULT_SCORE = 3.0
GPU_RTX_50_FALLBACK = 8.3       # RTX 50xx bilinmeyen model
GPU_RTX_40_FALLBACK = 8.0       # RTX 40xx bilinmeyen model
GPU_RTX_30_FALLBACK = 7.0       # RTX 30xx bilinmeyen model
GPU_RTX_DEFAULT_FALLBACK = 6.5  # RTX diğer
GPU_GTX_DEFAULT_SCORE = 4.5
GPU_MX_DEFAULT_SCORE = 3.5
GPU_RX_DEFAULT_SCORE = 5.5
GPU_DISCRETE_UNKNOWN_SCORE = 4.0
GPU_APPLE_M4_SCORE = 8.5
GPU_APPLE_M3_SCORE = 8.0
GPU_APPLE_M2_SCORE = 7.5
GPU_APPLE_M1_SCORE = 7.0

# RX prefix fallback skorları
GPU_RX_FALLBACK = {
    '79': 8.6, '78': 8.2, '77': 7.7,
    '76': 7.1, '67': 6.9, '66': 6.5,
}

# ── calculate_score sabitleri ────────────────────────────────────────
PRICE_BASE_FACTOR = 0.95        # fiyat skor çarpanı
PRICE_MID_BONUS_MAX = 4         # bütçe ortasına yakınlık bonusu
PRICE_OUT_OF_RANGE_BASE = 50    # bütçe dışı baz skor

# CPU/GPU ağırlık karışımları (usage_key bazlı)
PERF_MIX = {
    'default':      (0.7, 0.3),
    'gaming':       (0.3, 0.7),
    'design':       (0.5, 0.5),
    'portability':  (0.8, 0.2),
    'multitask':    (0.85, 0.15),   # productivity → multitask
    'dev_web':      (1.0, 0.0),
}

# RAM tier skorları (gb_min → skor)
RAM_SCORE_TIERS = [
    (64, 100),
    (32, 90),
    (24, 80),
    (16, 70),
    (12, 55),
    (8,  40),
    (0,  20),
]

# SSD tier skorları (gb_min → skor)
SSD_SCORE_TIERS = [
    (2048, 100),
    (1024, 85),
    (512,  70),
    (256,  50),
    (0,    30),
]

# Pil skoru sabitleri
BATTERY_BASE_SCORE = 50
BATTERY_ADJUSTMENTS = {
    'apple_m':   30,
    'intel_u':   20,
    'intel_p':   10,
    'intel_hx': -20,
    'intel_h':  -10,
    'ryzen_u':   20,
    'ryzen_hs':   5,
    'ryzen_h':  -15,
    'ultra':     15,
}
BATTERY_GPU_LOW_BONUS = 15      # gpu_score < 3
BATTERY_GPU_HIGH_PENALTY = 20   # gpu_score > 7
BATTERY_GPU_MID_PENALTY = 10    # gpu_score > 5

# Taşınabilirlik skoru sabitleri
PORTABILITY_BASE_SCORE = 50
PORTABILITY_SCREEN_TIERS = [
    (13,  40),    # <= 13"  → +40
    (14,  30),    # <= 14"  → +30
    (15,  10),    # <= 15"  → +10
]
PORTABILITY_LARGE_PENALTY = 30  # >= 17" → -30
PORTABILITY_DEFAULT_PENALTY = 10  # 15-17" arası → -10
PORTABILITY_GPU_LOW_BONUS = 10    # gpu_score < 3
PORTABILITY_GPU_HIGH_PENALTY = 15 # gpu_score > 7

# OS çarpanları
OS_MULTIPLIERS = {
    'design_dev': {
        'macos': 1.05,
        'windows': 1.03,
        'linux': 1.02,
        'freedos': 0.95,
    },
    'productivity': {
        'windows': 1.02,
        'macos': 1.02,
        'freedos': 0.97,
    },
}

# Dev profil karışım oranları (base_score, dev_fit)
DEV_FIT_BLEND = {
    'web':     (0.5, 0.5),
    'mobile':  (0.55, 0.45),
    'general': (0.65, 0.35),
    'default': (0.7, 0.3),
}

# Dev GPU bonus/penalty
DEV_GPU_NO_DGPU_BONUS = 1.0
DEV_GPU_HEAVY_PENALTY = 4.0
DEV_GPU_LIGHT_PENALTY = 1.5

# ── compute_dev_fit sabitleri ────────────────────────────────────────
DEV_FIT_RAM_POINTS = 20
DEV_FIT_SSD_POINTS = 15
DEV_FIT_CPU_MULTIPLIER = 4
DEV_FIT_GPU_BASE_POINTS = 20
DEV_FIT_GPU_MAX_POINTS = 25
DEV_FIT_SCREEN_POINTS = 10
DEV_FIT_SCREEN_TOTAL_PARTS = 20
DEV_FIT_SIZE_OK = 1.0
DEV_FIT_SIZE_PENALTY = 0.7
DEV_FIT_APPLE_BONUS = 3.0

# Dev web ayarları
DEV_WEB_CPU_U_BONUS = 3.0
DEV_WEB_CPU_P_BONUS = 2.0
DEV_WEB_CPU_HX_PENALTY = 2.0
DEV_WEB_DGPU_PENALTY = 6.0
DEV_WEB_DGPU_RTX_EXTRA_PENALTY = 4.0
DEV_WEB_SMALL_SCREEN_BONUS = 2.0
DEV_WEB_LARGE_SCREEN_PENALTY = 3.0
DEV_WEB_DGPU_LARGE_SCREEN_PENALTY = 2.0
DEV_WEB_FREEDOS_PENALTY = 6.0

# Dev ML/Gamedev GPU bonus
DEV_ML_GPU_BONUS = {4060: 5, 4050: 3, 'dgpu': 1}
DEV_GAMEDEV_GPU_BONUS = {4070: 6, 4060: 4, 4050: 2}
DEV_WEB_GENERAL_DGPU_PENALTY = 1.5
DEV_MOBILE_DGPU_PENALTY = 2.5

# ── filter_by_usage sabitleri ────────────────────────────────────────
FILTER_MIN_RESULTS = 5
FILTER_GAMING_RELAXED_GPU = 5.0
FILTER_PORTABILITY_MAX_SCREEN = 14.5
FILTER_PORTABILITY_RELAXED_SCREEN = 15.6
FILTER_PORTABILITY_GPU_THRESHOLDS = (50, 5.0, 30, 6.0)  # (count, gpu, count, gpu)
FILTER_DESIGN_MIN_RAM = 16
FILTER_DESIGN_MIN_GPU = 4.0
FILTER_DESIGN_MIN_SCREEN = 14.0
FILTER_DESIGN_GPU_HINT_MAP = {'high': 6.5, 'mid': 4.5, 'low': 2.5}
FILTER_DEV_MIN_RAM = 16
FILTER_DEV_MIN_CPU = 6.0
FILTER_DEV_MIN_SSD = 256
FILTER_RELAXED_MIN_RAM = 12

# ── get_recommendations sabitleri ────────────────────────────────────
BUDGET_CLOSE_FACTOR = 0.1       # %10 bütçe toleransı
BUDGET_MIN_PRICE = 5000         # minimum fiyat eşiği (clean.py'de de kullanılır)
HEAVY_DGPU_MIN_RTX_TIER = 4060 # _is_heavy_dgpu_for_dev eşiği
