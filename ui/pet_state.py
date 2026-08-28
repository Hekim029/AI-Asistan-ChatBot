"""Masaüstü karakterinin durum adları ve sprite karesi eşlemesi."""

VALID_PET_STATES = frozenset({
    "idle",
    "busy",
    "success",
    "alert",
    "listening",
    "speaking",
    "sleeping",
})


def normalize_pet_state(state: object) -> str:
    candidate = str(state or "").strip().casefold()
    return candidate if candidate in VALID_PET_STATES else "idle"


def pet_sprite_frame(state: object, *, blinking: bool = False) -> int:
    """Dört karelik şeritte kullanılacak güvenli kare indeksini döndürür."""
    normalized = normalize_pet_state(state)
    if normalized == "busy":
        return 2
    if normalized == "alert":
        return 3
    if normalized == "sleeping" or (blinking and normalized in {"idle", "success"}):
        return 1
    return 0


def resting_state(has_active_work: bool) -> str:
    """Geçici başarı/uyarı efekti bittikten sonra dönülecek durumu seçer."""
    return "busy" if bool(has_active_work) else "idle"
