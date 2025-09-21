# -*- coding: utf-8 -*-
"""The OBD Drive integration with Home Assistant (merge options, no HA services)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er, device_registry as dr

from .coordinator import OBDCoordinator
from .api import OBDReceiveDataView
from .const import (
    DOMAIN,
    PLATFORMS,
    NAME,
    CONF_EMAIL,
    CONF_IMPERIAL,
    CONF_LANGUAGE,
    CONF_SESSION_TTL,
    CONF_MAX_SESSIONS,
    DEFAULT_LANGUAGE,
    SESSION_TTL_SECONDS,
    MAX_SESSIONS,
    CONF_MERGE_MODE,
    CONF_MERGE_NAME_MAP,
    DEFAULT_MERGE_MODE,
    DEFAULT_MERGE_NAME_MAP,
    # Garde-fous côté serveur (déclarés dans const.py)
    CONF_REJECT_POOR_NAME,
    CONF_REQUIRE_MAPPED_NAME,
    DEFAULT_REJECT_POOR_NAME,
    DEFAULT_REQUIRE_MAPPED_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def _async_forget_vehicle_core(
    hass: HomeAssistant, *, car_id: str, entry_id: str | None
) -> int:
    """Supprime toutes les entités + l'appareil d'un véhicule et retourne le nb d'entités supprimées."""
    entreg = er.async_get(hass)
    devreg = dr.async_get(hass)

    # Si l'entry_id n'est pas fourni, tenter de le déduire via le device
    if not entry_id:
        try:
            dev = devreg.async_get_device(identifiers={(DOMAIN, car_id)})
            if dev and dev.config_entries:
                entry_id = next(iter(dev.config_entries), None)
        except Exception:
            entry_id = None

    # 1) Supprimer toutes les entités OBD pour ce car_id
    prefix = f"{DOMAIN}-{car_id}-"
    to_remove: list[str] = []
    for ent in list(entreg.entities.values()):
        if ent.platform != DOMAIN:
            continue
        if entry_id and ent.config_entry_id != entry_id:
            continue
        if ent.unique_id and ent.unique_id.startswith(prefix):
            to_remove.append(ent.entity_id)

    for entity_id in to_remove:
        try:
            entreg.async_remove(entity_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("forget_vehicle: failed removing entity %s", entity_id)

    # 2) Supprimer le device lui-même
    try:
        dev = devreg.async_get_device(identifiers={(DOMAIN, car_id)})
        if dev:
            devreg.async_remove_device(dev.id)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("forget_vehicle: failed removing device for %s", car_id)

    _LOGGER.info("Vehicle %s forgotten (entities removed=%d)", car_id, len(to_remove))
    return len(to_remove)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Initialisation au niveau intégration (aucun service HA enregistré)."""
    hass.data.setdefault(DOMAIN, {})
    # ⚠️ Ne PAS enregistrer de service ici (pour éviter tout services.yaml)
    return True


def _get_or_register_view(
    hass: HomeAssistant, *, session_ttl: int, max_sessions: int
) -> OBDReceiveDataView:
    """Create (or update) the public HTTP view for OBD uploads."""
    store = hass.data.setdefault(DOMAIN, {})
    view: OBDReceiveDataView | None = store.get("view")
    if view is None:
        view = OBDReceiveDataView(
            hass,
            default_language=DEFAULT_LANGUAGE,
            imperial_units=False,
            session_ttl_seconds=session_ttl,
            max_sessions=max_sessions,
        )
        try:
            hass.http.register_view(view)
        except Exception as err:  # noqa: BLE001
            raise ConfigEntryNotReady from err
        store["view"] = view
    else:
        # ✅ API publique (pas d'écriture d'attributs privés)
        setter = getattr(view, "set_session_limits", None)
        if callable(setter):
            setter(ttl_seconds=session_ttl, max_sessions=max_sessions)
    return view


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    session_ttl = int(entry.options.get(CONF_SESSION_TTL, SESSION_TTL_SECONDS))
    max_sessions = int(entry.options.get(CONF_MAX_SESSIONS, MAX_SESSIONS))
    view = _get_or_register_view(hass, session_ttl=session_ttl, max_sessions=max_sessions)

    email = str(entry.data.get(CONF_EMAIL, "")).strip().lower()
    imperial = bool(entry.options.get(CONF_IMPERIAL, entry.data.get(CONF_IMPERIAL, False)))
    lang_rt = entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE))
    merge_mode = entry.options.get(CONF_MERGE_MODE, DEFAULT_MERGE_MODE)
    merge_name_map = entry.options.get(CONF_MERGE_NAME_MAP, DEFAULT_MERGE_NAME_MAP)

    # Lecture des garde-fous
    reject_poor = bool(entry.options.get(CONF_REJECT_POOR_NAME, DEFAULT_REJECT_POOR_NAME))
    require_mapped = bool(entry.options.get(CONF_REQUIRE_MAPPED_NAME, DEFAULT_REQUIRE_MAPPED_NAME))

    coordinator = OBDCoordinator(hass, view, entry)
    # Store coordinator early
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    # Transmettre les préférences à la vue
    view.upsert_route(
        entry.entry_id,
        email=email or None,
        coordinator=coordinator,
        imperial=bool(imperial),
        lang=lang_rt,
        merge_mode=merge_mode,
        merge_name_map=merge_name_map,
        reject_poor_name=reject_poor,
        require_mapped_name=require_mapped,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _reload_entry(hass: HomeAssistant, changed_entry: ConfigEntry) -> None:
        await hass.config_entries.async_reload(changed_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_reload_entry))
    _LOGGER.debug("OBD Drive entry ready (%s)", email)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    store = hass.data.get(DOMAIN, {})
    view: OBDReceiveDataView | None = store.get("view")
    if view:
        try:
            view.remove_route(entry.entry_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Error removing API route for entry_id=%s: %s", entry.entry_id, err)
    store.pop(entry.entry_id, None)
    return ok


# --------- Suppression d’un appareil depuis l’UI (page Appareil) ---------
async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Permet de supprimer un véhicule directement depuis l'UI des appareils."""
    # Vérifie que l'appareil appartient bien à cette config_entry
    if entry.entry_id not in device.config_entries:
        return False

    # Trouve le car_id via les identifiers (DOMAIN, car_id)
    car_id: str | None = None
    for domain, ident in device.identifiers:
        if domain == DOMAIN:
            car_id = ident
            break

    if not car_id:
        return False

    await _async_forget_vehicle_core(hass, car_id=car_id, entry_id=entry.entry_id)
    return True
