"""Optional LLM-backed preference parsing with rule-based fallback.

This module is intentionally optional:
- If LLM dependencies are missing
- or required env vars are not set
- or runtime lacks CUDA
it silently falls back to rule-based NLP parsing.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger
from .nlp import parse_free_text_to_preferences

logger = get_logger(__name__)

MISSING_VALUES = (None, "", [])
VALID_USAGE_KEYS = {"gaming", "portability", "productivity", "design", "dev"}
VALID_DEV_MODES = {"web", "ml", "mobile", "gamedev", "general"}
VALID_PRODUCTIVITY_PROFILES = {"office", "data", "light_dev", "multitask"}
VALID_DESIGN_PROFILES = {"graphic", "video", "3d", "cad"}
VALID_DESIGN_GPU_HINTS = {"low", "mid", "high"}

PROMPT_TEMPLATE = (
    "Kullanicinin laptop istegini Laprop tercih formatina (preferences JSON) cevir. "
    "Sadece JSON dondur. Ana alanlar: min_budget, max_budget, usage_key ve amaca gore "
    "opsiyonel alanlar (gaming_titles, dev_mode, design_profiles, "
    "productivity_profile, screen_max...).\n"
    "Kullanici: {text}\n"
    "JSON:"
)


def is_llm_preference_parsing_enabled() -> bool:
    """Return True if env flag explicitly enables LLM preference parsing."""
    flag = os.getenv("LAPROP_ENABLE_LLM_PREFS", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _is_missing(v: Any) -> bool:
    return v in MISSING_VALUES


def _to_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, str):
            s = value.strip().replace(",", ".")
            if not s:
                return None
            return float(s)
        return float(value)
    except Exception:
        return None


def _to_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[;,]", value) if p.strip()]
        return parts
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from free text model output."""
    s = (text or "").strip()
    if not s:
        return None

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, flags=re.S)
    if fence:
        candidate = fence.group(1)
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

    match = re.search(r"\{.*\}", s, flags=re.S)
    if match:
        candidate = match.group(0)
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def sanitize_preferences(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only known Laprop preference keys and normalize value types."""
    if not isinstance(raw, dict):
        return {}

    out: Dict[str, Any] = {}

    usage_key = raw.get("usage_key")
    if isinstance(usage_key, str):
        usage_key = usage_key.strip().lower()
        if usage_key in VALID_USAGE_KEYS:
            out["usage_key"] = usage_key

    for budget_key in ("min_budget", "max_budget", "screen_max", "min_gpu_score_required", "gaming_min_gpu"):
        v = _to_float_or_none(raw.get(budget_key))
        if v is not None:
            out[budget_key] = v

    dev_mode = raw.get("dev_mode")
    if isinstance(dev_mode, str):
        dev_mode = dev_mode.strip().lower()
        if dev_mode in VALID_DEV_MODES:
            out["dev_mode"] = dev_mode

    productivity_profile = raw.get("productivity_profile")
    if isinstance(productivity_profile, str):
        productivity_profile = productivity_profile.strip().lower()
        if productivity_profile in VALID_PRODUCTIVITY_PROFILES:
            out["productivity_profile"] = productivity_profile

    design_profiles = [x.strip().lower() for x in _to_string_list(raw.get("design_profiles"))]
    design_profiles = [x for x in design_profiles if x in VALID_DESIGN_PROFILES]
    if design_profiles:
        out["design_profiles"] = sorted(set(design_profiles))

    design_gpu_hint = raw.get("design_gpu_hint")
    if isinstance(design_gpu_hint, str):
        design_gpu_hint = design_gpu_hint.strip().lower()
        if design_gpu_hint in VALID_DESIGN_GPU_HINTS:
            out["design_gpu_hint"] = design_gpu_hint

    design_min_ram_hint = _to_float_or_none(raw.get("design_min_ram_hint"))
    if design_min_ram_hint is not None:
        out["design_min_ram_hint"] = int(design_min_ram_hint)

    gaming_titles = _to_string_list(raw.get("gaming_titles"))
    if gaming_titles:
        out["gaming_titles"] = gaming_titles

    return out


def merge_preferences(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Merge dicts while preserving primary values and filling missing ones."""
    merged = dict(primary or {})
    for key, val in (fallback or {}).items():
        if _is_missing(merged.get(key)) and not _is_missing(val):
            merged[key] = val
    return merged


class _LazyLlmParser:
    """Lazy-loads model/tokenizer only if actually needed."""

    def __init__(self) -> None:
        self._ready = False
        self._disabled_reason: Optional[str] = None
        self._tokenizer = None
        self._model = None
        self._max_new_tokens = int(os.getenv("LAPROP_LLM_MAX_NEW_TOKENS", "180"))

    def _adapter_dir(self) -> Optional[Path]:
        raw = os.getenv("LAPROP_LLM_ADAPTER_DIR", "").strip()
        if not raw:
            return None
        return Path(raw).expanduser()

    def _model_name_from_meta(self, adapter_dir: Path) -> str:
        env_name = os.getenv("LAPROP_LLM_MODEL_NAME", "").strip()
        if env_name:
            return env_name
        meta_path = adapter_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                model_name = str(meta.get("model_name") or "").strip()
                if model_name:
                    return model_name
            except Exception:
                pass
        return "Qwen/Qwen2.5-1.5B-Instruct"

    def _load(self) -> bool:
        if self._ready:
            return True
        if self._disabled_reason is not None:
            return False

        adapter_dir = self._adapter_dir()
        if adapter_dir is None:
            self._disabled_reason = "LAPROP_LLM_ADAPTER_DIR is not set."
            logger.info("LLM parser disabled: %s", self._disabled_reason)
            return False
        if not adapter_dir.exists():
            self._disabled_reason = f"Adapter path does not exist: {adapter_dir}"
            logger.warning("LLM parser disabled: %s", self._disabled_reason)
            return False

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except Exception as exc:
            self._disabled_reason = f"LLM deps not available ({exc})"
            logger.warning("LLM parser disabled: %s", self._disabled_reason)
            return False

        if not torch.cuda.is_available():
            self._disabled_reason = "CUDA is not available for local LLM inference."
            logger.warning("LLM parser disabled: %s", self._disabled_reason)
            return False

        model_name = self._model_name_from_meta(adapter_dir)
        capability = torch.cuda.get_device_capability(0)
        use_bf16 = capability[0] >= 8
        compute_dtype = torch.bfloat16 if use_bf16 else torch.float16

        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=compute_dtype,
            )

            tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True, trust_remote_code=True)
            if tokenizer.eos_token is None:
                tokenizer.eos_token = "</s>"
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            base_model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
            model = PeftModel.from_pretrained(base_model, str(adapter_dir))
            model.eval()
        except Exception as exc:
            self._disabled_reason = f"Failed to load LLM model/adapter ({exc})"
            logger.exception("LLM parser disabled: %s", self._disabled_reason)
            return False

        self._tokenizer = tokenizer
        self._model = model
        self._ready = True
        logger.info("LLM parser ready. model=%s adapter=%s", model_name, adapter_dir)
        return True

    def parse(self, text: str) -> Dict[str, Any]:
        if not text or not self._load():
            return {}
        try:
            import torch

            prompt = PROMPT_TEMPLATE.format(text=text)
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

            with torch.no_grad():
                out = self._model.generate(
                    **inputs,
                    max_new_tokens=self._max_new_tokens,
                    do_sample=False,
                    eos_token_id=self._tokenizer.eos_token_id,
                    pad_token_id=self._tokenizer.pad_token_id,
                )
            gen = out[0][inputs["input_ids"].shape[1]:]
            pred_text = self._tokenizer.decode(gen, skip_special_tokens=True).strip()
            obj = extract_json_object(pred_text)
            return sanitize_preferences(obj or {})
        except Exception:
            logger.exception("LLM parsing failed; falling back to rules.")
            return {}


_PARSER = _LazyLlmParser()


def try_parse_preferences_with_llm(text: str) -> Dict[str, Any]:
    """Try parsing with LLM. Returns {} on any failure."""
    if not is_llm_preference_parsing_enabled():
        return {}
    return _PARSER.parse(text)


def parse_preferences_hybrid(text: str) -> Dict[str, Any]:
    """Use LLM when enabled, then fill missing fields from rule-based parser."""
    rule_prefs = parse_free_text_to_preferences(text)
    llm_prefs = try_parse_preferences_with_llm(text)
    if not llm_prefs:
        return rule_prefs
    return merge_preferences(primary=llm_prefs, fallback=rule_prefs)
