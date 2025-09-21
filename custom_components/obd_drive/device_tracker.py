# -*- coding: utf-8 -*-
"""Device tracker for OBD Drive — unique_id stable, nom/icône dynamiques, restauration + recréation depuis l'Entity Registry."""
from __future__ import annotations

from typing import Any
import logging
import math

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType as TrackerSourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    ENTITY_GPS,
    OBD_GPS_LAT,
    OBD_GPS_LON,
    OBD_GPS_ACCURACY,
)
from .coordinator import OBDCoordinator
from .entity import OBDEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Register adder + recréer les trackers depuis l'Entity Registry."""
    store = hass.data.get(DOMAIN, {}) or {}
    data = store.get(entry.entry_id) or {}
    coordinator: OBDCoordinator | None = data.get("coordinator")  # type: ignore[assignment]

    if coordinator is None:
        view = store.get("view")
        try:
            resolve = getattr(view, "resolve_entry_route", None)
            route = resolve(entry.entry_id) if callable(resolve) else getattr(view, "_entry_routes", {}).get(entry.entry_id)
            if route and route.get("coordinator"):
                coordinator = route.get("coordinator")
                store.setdefault(entry.entry_id, {})["coordinator"] = coordinator
        except Exception as err:
            _LOGGER.debug("device_tracker: failed to resolve coordinator via view for %s: %s", entry.entry_id, err)

    if not coordinator:
        _LOGGER.warning("No coordinator found for %s (device_tracker)", entry.entry_id)
        return

    try:
        coordinator.set_device_tracker_adder(async_add_entities)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to register device_tracker adder")

    # ✅ Recréer immédiatement les trackers connus
    try:
        registry = er.async_get(hass)
        for ent in list(registry.entities.values()):
            if ent.config_entry_id != entry.entry_id:
                continue
            if ent.platform != DOMAIN or ent.domain != "device_tracker":
                continue
            uid = ent.unique_id or ""
            pref = f"{DOMAIN}-"
            if not uid.startswith(pref) or "-" not in uid[len(pref):]:
                continue
            rest = uid[len(pref):]
            car_id, key = rest.rsplit("-", 1)
            if key != ENTITY_GPS:
                continue
            device = DeviceInfo(identifiers={(DOMAIN, car_id)})
            async_add_entities([OBDDeviceTracker(coordinator, entry, device, car_id)], True)
    except Exception as err:
        _LOGGER.debug("device_tracker: registry restore failed: %s", err)


class OBDDeviceTracker(OBDEntity, TrackerEntity, RestoreEntity):
    """GPS tracker lié à un véhicule."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OBDCoordinator, entry: ConfigEntry, device: DeviceInfo, car_id: str) -> None:
        super().__init__(coordinator, entry, ENTITY_GPS, device, vehicle_id=car_id)
        veh = self.coordinator_vehicle() or {}
        display = (veh.get("profile") or {}).get("Name") or getattr(device, "name", None) or "Véhicule"
        self._attr_name = display
        self._rest_lat: float | None = None
        self._rest_lon: float | None = None
        self._rest_acc: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            last = await self.async_get_last_state()
            if last:
                attrs = last.attributes or {}
                self._rest_lat = attrs.get("latitude")
                self._rest_lon = attrs.get("longitude")
                self._rest_acc = attrs.get("gps_accuracy") or attrs.get("accuracy")
        except Exception:
            pass

    @property
    def name(self) -> str | None:
        veh = self.coordinator_vehicle() or {}
        return (veh.get("profile") or {}).get("Name") or self._attr_name

    @property
    def source_type(self) -> TrackerSourceType:
        return TrackerSourceType.GPS

    @property
    def latitude(self) -> float | None:
        v = self.get_coordinator_value(OBD_GPS_LAT)
        if isinstance(v, (int, float)):
            return float(v)
        return self._rest_lat

    @property
    def longitude(self) -> float | None:
        v = self.get_coordinator_value(OBD_GPS_LON)
        if isinstance(v, (int, float)):
            return float(v)
        return self._rest_lon

    @property
    def gps_accuracy(self) -> float | None:
        v = self.get_coordinator_value(OBD_GPS_ACCURACY)
        try:
            return float(v) if v is not None else (float(self._rest_acc) if self._rest_acc is not None else None)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        # Disponible uniquement si latitude ET longitude sont présentes et finies
        lat = self.latitude
        lon = self.longitude
        try:
            return (
                lat is not None and lon is not None
                and math.isfinite(float(lat)) and math.isfinite(float(lon))
            )
        except Exception:
            return False

    # Icône dynamique
    @property
    def icon(self) -> str | None:
        try:
            spd = self.get_coordinator_value("speed_gps")
            if not isinstance(spd, (int, float)):
                spd = self.get_coordinator_value("speed_obd")
            veh = self.coordinator_vehicle() or {}
            meta_by_key: dict[str, Any] = veh.get("meta") or {}
            unit = (meta_by_key.get("speed_gps", {}).get("unit") or "").strip().lower()
            threshold = 1.0 if unit == "mph" else 2.0
            if isinstance(spd, (int, float)) and spd > threshold:
                return "mdi:car-arrow-right"
        except Exception:
            pass
        return "mdi:car"
