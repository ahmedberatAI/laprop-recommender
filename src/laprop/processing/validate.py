from typing import List, Optional

from .normalize import _find_ram_candidates, _find_screen_candidates
def validate_record(
    title: str,
    cpu: Optional[str],
    gpu: Optional[str],
    ram_gb: Optional[float],
    ssd_gb: Optional[float],
    screen_size: Optional[float],
) -> List[str]:
    warnings = []

    for val in _find_ram_candidates(title):
        if val > 128:
            warnings.append("ram_over_128")
            break

    for val in _find_screen_candidates(title):
        if val < 10.0 or val > 20.0:
            warnings.append("screen_size_out_of_range")
            break

    return warnings
