# -*- coding: utf-8 -*-
"""Coordinator for OBD Drive."""
from __future__ import annotations
from typing import Any, Optional, Callable, Iterable, Tuple, List
import logging, math
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify
from .const import DOMAIN, ENTITY_GPS, OBD_GPS_LAT, OBD_GPS_LON
_LOGGER: logging.Logger = logging.getLogger(__name__)
_NONFINITE_STR = {"inf","+inf","-inf","infinity","nan"}
def _is_non_finite(v: Any) -> bool:
    try:
        if isinstance(v,(int,float)): return not math.isfinite(float(v))
        if isinstance(v,str): return v.strip().lower() in _NONFINITE_STR
    except Exception: return True
    return False

class OBDCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]] | None]):
    _sensor_adder: Optional[Callable[[str, str, dict[str, Any]], None]] = None
    async_add_device_tracker: Optional[Callable[[List[Any], bool], None]] = None
    def __init__(self, hass: HomeAssistant, view: Any, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.hass = hass; self.entry = entry; self.view = view; view.coordinator = self
        self.tracked: set[str] = set(); self.cars: dict[str, dict[str, Any]] = {}; self.data: dict[str, dict[str, Any]] = {}
        self._pending_trackers: set[str] = set()

    async def _async_update_data(self) -> dict[str, dict[str, Any]] | None: return self.data

    def set_sensor_adder(self, adder: Callable[[str, str, dict[str, Any]], None]) -> None:
        self._sensor_adder = adder
        for car_id, session in list(self.cars.items()):
            meta_map = session.get("meta") or {}
            for short, meta in meta_map.items():
                if not self._is_creatable_sensor(short, meta): continue
                tracked_key = f"{car_id}:{short}"
                if tracked_key in self.tracked: continue
                try: adder(car_id, short, meta); self.tracked.add(tracked_key)
                except Exception: _LOGGER.exception("sensor adder callback failed for %s/%s (backfill)", car_id, short)

    def iter_current_sensors(self) -> Iterable[Tuple[str, str, dict[str, Any]]]:
        for car_id, session in self.cars.items():
            meta_map = session.get("meta") or {}
            for short, meta in meta_map.items():
                if not self._is_creatable_sensor(short, meta): continue
                yield (car_id, short, meta)

    @staticmethod
    def _is_textual_sensor(name: str) -> bool:
        if not name: return False
        n = name.strip().lower()
        return n.endswith(("status","state","mode")) or "état" in n or "statut" in n

    def _is_creatable_sensor(self, short: str, meta: dict[str, Any]) -> bool:
        if short in (OBD_GPS_LAT, OBD_GPS_LON): return False
        name = (meta.get("name") or short).strip(); unit = (meta.get("unit") or "").strip()
        if unit == "" and not self._is_textual_sensor(name): return False
        if name == short: return False
        return True

    def get_value(self, car_id: str, key: str) -> Any:
        data = self.cars.get(car_id); 
        if not data: return None
        val = (data.get("values") or {}).get(key)
        return None if _is_non_finite(val) else val

    def get_meta(self, car_id: str) -> dict[str, Any]:
        data = self.cars.get(car_id)
        if not data: return {}
        return data.get("meta", {})  # type: ignore[return-value]

    def _ensure_device_registry(self, car_id: str, profile: dict[str, Any]) -> str:
        dev_reg = dr.async_get(self.hass); raw_name = (profile or {}).get("Name") or ""; sw_ver = (profile or {}).get("version")
        existing = dev_reg.async_get_device(identifiers={(DOMAIN, car_id)})
        def _is_poor(n: str) -> bool:
            if not n: return True
            s = n.strip()
            if not s:
                return True
            if s == car_id: return True
            if s.lower() in {"vehicle","véhicule"}: return True
            return False
        if _is_poor(raw_name):
            effective_name = existing.name if (existing and existing.name) else f"Vehicle {car_id[:6]}"
        else: effective_name = raw_name
        device = dev_reg.async_get_or_create(config_entry_id=self.entry.entry_id, identifiers={(DOMAIN,car_id)},
                                             manufacturer="OBD Drive", model=effective_name, name=effective_name, sw_version=sw_ver)
        updates: dict[str, Any] = {}
        if device.name != effective_name: updates["name"] = effective_name
        if device.model != effective_name: updates["model"] = effective_name
        if sw_ver and getattr(device, "sw_version", None) != sw_ver: updates["sw_version"] = sw_ver
        if updates: dev_reg.async_update_device(device.id, **updates)
        return effective_name

    def set_device_tracker_adder(self, adder: Callable[[List[Any], bool], None]) -> None:
        self.async_add_device_tracker = adder; self._try_create_all_trackers()

    def _try_create_all_trackers(self) -> None:
        if not callable(self.async_add_device_tracker): return
        new_entities: list[Any] = []
        from .device_tracker import OBDDeviceTracker
        for car_id, session in list(self.cars.items()):
            values = session.get("values") or {}
            if OBD_GPS_LAT in values and OBD_GPS_LON in values:
                tracked_key = f"{car_id}:{ENTITY_GPS}"
                if tracked_key in self.tracked: continue
                profile = session.get("profile") or {}; effective_name = self._ensure_device_registry(car_id, profile)
                device = DeviceInfo(identifiers={(DOMAIN,car_id)}, manufacturer="OBD Drive", model=effective_name, name=effective_name, sw_version=profile.get("version"))
                new_entities.append(OBDDeviceTracker(self, self.entry, device, car_id)); self.tracked.add(tracked_key)
        if new_entities:
            try: self.async_add_device_tracker(new_entities, True)  # type: ignore[misc]
            except Exception: _LOGGER.exception("Error while adding backfilled device_trackers")

    async def update_from_session(self, session_data: dict[str, Any]) -> None:
        try:
            profile = session_data.get("profile") or {}; car_name = profile.get("Name") or "Vehicle"
            car_id = profile.get("Id") or slugify(car_name)
            vals = session_data.get("values") or {}
            for k, v in list(vals.items()):
                if _is_non_finite(v): vals[k] = None
            self.cars[car_id] = session_data; self.data[car_id] = session_data
            effective_name = self._ensure_device_registry(car_id, profile)
            values = session_data.get("values") or {}
            if (OBD_GPS_LAT in values and OBD_GPS_LON in values):
                tracked_key = f"{car_id}:{ENTITY_GPS}"
                if tracked_key not in self.tracked:
                    if callable(self.async_add_device_tracker):
                        from .device_tracker import OBDDeviceTracker
                        device = DeviceInfo(identifiers={(DOMAIN,car_id)}, manufacturer="OBD Drive", model=effective_name, name=effective_name, sw_version=profile.get("version"))
                        try:
                            self.async_add_device_tracker(
                                [OBDDeviceTracker(self, self.entry, device, car_id)],
                                True  # type: ignore[misc]
                            )
                            self.tracked.add(tracked_key)
                        except Exception as err:
                            _LOGGER.exception(
                                "Failed to add device_tracker for car_id=%s: %s",
                                car_id, err
                            )
                            # Retenter plus tard si l’adder devient dispo
                            self._pending_trackers.add(car_id)
                    else: self._pending_trackers.add(car_id)
            meta_map = session_data.get("meta") or {}
            if self._sensor_adder:
                for short, meta in meta_map.items():
                    if not self._is_creatable_sensor(short, meta): continue
                    tracked_key = f"{car_id}:{short}"
                    if tracked_key in self.tracked: continue
                    try:
                        self._sensor_adder(car_id, short, meta)
                        self.tracked.add(tracked_key)
                    except Exception as err:
                        _LOGGER.exception(
                            "Sensor adder failed for car_id=%s short=%s", car_id, short
                        )
            if self._pending_trackers and callable(self.async_add_device_tracker):
                self._try_create_all_trackers(); self._pending_trackers.clear()
            self.async_set_updated_data(self.data)
        except Exception: _LOGGER.exception("update_from_session failed")

    def forget_vehicle(self, vehicle_key: str) -> None:
        self.cars.pop(vehicle_key, None); self.data.pop(vehicle_key, None)
        to_remove = {k for k in self.tracked if k.startswith(f"{vehicle_key}:")}
        if to_remove: self.tracked.difference_update(to_remove)
