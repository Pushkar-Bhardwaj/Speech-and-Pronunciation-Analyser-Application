from __future__ import annotations

from speechbrain.inference.ASR import EncoderDecoderASR

from config import PRETRAINED_MODEL_DIR, PRETRAINED_MODEL_ID

_cached_model = None


def get_asr_model():
    """Return a cached SpeechBrain ASR model instance."""
    global _cached_model

    if _cached_model is not None:
        return _cached_model

    model_source = str(PRETRAINED_MODEL_DIR) if PRETRAINED_MODEL_DIR.exists() else PRETRAINED_MODEL_ID

    _cached_model = EncoderDecoderASR.from_hparams(
        source=model_source,
        savedir=str(PRETRAINED_MODEL_DIR),
        run_opts={"device": "cpu"},
    )

    return _cached_model
