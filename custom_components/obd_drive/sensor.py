# -*- coding: utf-8 -*-
"""Sensors for OBD Drive — unités dynamiques + restauration + recréation depuis l'Entity Registry + icônes MDI étendues."""
from __future__ import annotations

from typing import Any
import logging
import math
import re  # ✅ nécessaire pour ICON_KEYWORDS (regex)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, OBD_CODES
from .coordinator import OBDCoordinator
from .entity import OBDEntity

_LOGGER = logging.getLogger(__name__)

# --- Fallback d’unités par clé courte (avant 1ʳᵉ trame) --------------------
# Construit un mapping { shortName(lower) -> unit } à partir d'OBD_CODES.
DEFAULT_UNIT_BY_KEY: dict[str, str] = {
    (d.get("shortName") or "").strip().lower(): (d.get("unit") or "").strip()
    for d in OBD_CODES.values()
    if (d.get("shortName") or "").strip()
}

# --- Icônes MDI par clé courte (prioritaire) -------------------------------
ICON_BY_KEY: dict[str, str] = {
    # Vitesse / RPM
    "engine_rpm": "mdi:gauge",
    "rpm": "mdi:gauge",
    "speed_obd": "mdi:speedometer",
    "gps_spd": "mdi:speedometer",
    "speed_gps": "mdi:speedometer",

    # Températures
    "coolant_temp": "mdi:thermometer-water",
    "engine_coolant_temperature": "mdi:thermometer-water",
    "intake_air_temp": "mdi:thermometer",
    "ambient_air_temp": "mdi:thermometer",
    "engine_oil_temperature": "mdi:oil",
    "charge_air_cooler_temp": "mdi:thermometer",
    "cat_temp_b1s1": "mdi:thermometer",
    "cat_temp_b2s1": "mdi:thermometer",
    "cat_temp_b1s2": "mdi:thermometer",
    "cat_temp_b2s2": "mdi:thermometer",
    "egt_b1_s1": "mdi:thermometer",
    "egt_b2_s1": "mdi:thermometer",
    "egt_b1_s2": "mdi:thermometer",
    "egt_b1_s3": "mdi:thermometer",
    "egt_b1_s4": "mdi:thermometer",
    "egt_b2_s2": "mdi:thermometer",
    "egt_b2_s3": "mdi:thermometer",
    "egt_b2_s4": "mdi:thermometer",
    "transmission_temp_method_2": "mdi:thermometer",

    # Électricité / tension / puissance
    "voltage_control_module": "mdi:car-battery",
    "control_module_voltage": "mdi:car-battery",
    "voltage_obd_adapter": "mdi:car-battery",
    "hybrid_ev_batt_voltage": "mdi:car-battery",
    "hybrid_ev_batt_current": "mdi:current-dc",
    "hybrid_ev_batt_power": "mdi:flash",

    # Pressions / boost / baro / carburant
    "fuel_pressure": "mdi:gauge",
    "fuel_rail_pressure": "mdi:gauge",
    "fuel_rail_pressure_rel": "mdi:gauge",
    "intake_manifold_pressure": "mdi:gauge",
    "intake_manifold_abs_pressure_a": "mdi:gauge",
    "intake_manifold_abs_pressure_b": "mdi:gauge",
    "boost_pressure_commanded_a": "mdi:gauge",
    "boost_pressure_commanded_b": "mdi:gauge",
    "boost_pressure_sensor_a": "mdi:gauge",
    "boost_pressure_sensor_b": "mdi:gauge",
    "barometric_pressure_vehicle": "mdi:gauge",
    "dpf_b1_delta_pressure": "mdi:gauge",
    "dpf_b2_delta_pressure": "mdi:gauge",
    "dpf_b1_inlet_pressure": "mdi:gauge",
    "dpf_b1_outlet_pressure": "mdi:gauge",
    "dpf_b2_inlet_pressure": "mdi:gauge",
    "dpf_b2_outlet_pressure": "mdi:gauge",
    "exhaust_pressure_b1": "mdi:gauge",
    "exhaust_pressure_b2": "mdi:gauge",

    # Air / mélange / O2 / AFR
    "mass_air_flow_rate": "mdi:air-filter",
    "maf_sensor_a": "mdi:air-filter",
    "maf_sensor_b": "mdi:air-filter",
    "o2_o2l1_wide_voltage": "mdi:lambda",
    "o2_o2l2_wide_voltage": "mdi:lambda",
    "o2_o2l3_wide_voltage": "mdi:lambda",
    "o2_o2l4_wide_voltage": "mdi:lambda",
    "o2_o2l5_wide_voltage": "mdi:lambda",
    "o2_o2l6_wide_voltage": "mdi:lambda",
    "o2_o2l7_wide_voltage": "mdi:lambda",
    "o2_o2l8_wide_voltage": "mdi:lambda",
    "o2_o2l1_wide_current": "mdi:lambda",
    "o2_o2l2_wide_current": "mdi:lambda",
    "o2_o2l3_wide_current": "mdi:lambda",
    "o2_o2l4_wide_current": "mdi:lambda",
    "o2_o2l5_wide_current": "mdi:lambda",
    "o2_o2l6_wide_current": "mdi:lambda",
    "o2_o2l7_wide_current": "mdi:lambda",
    "o2_o2l8_wide_current": "mdi:lambda",
    "commanded_equivalence_ratio": "mdi:lambda",
    "air_fuel_ratio_measured": "mdi:lambda",
    "air_fuel_ratio_commanded": "mdi:lambda",

    # Trim / position / couple / avance
    "fuel_trim_b1_short": "mdi:tune",
    "fuel_trim_b1_long": "mdi:tune",
    "fuel_trim_b2_short": "mdi:tune",
    "fuel_trim_b2_long": "mdi:tune",
    "fuel_trim_o2l_1": "mdi:tune",
    "fuel_trim_o2l_2": "mdi:tune",
    "fuel_trim_o2l_3": "mdi:tune",
    "fuel_trim_o2l_4": "mdi:tune",
    "fuel_trim_o2l_5": "mdi:tune",
    "fuel_trim_o2l_6": "mdi:tune",
    "fuel_trim_o2l_7": "mdi:tune",
    "fuel_trim_o2l_8": "mdi:tune",
    "relative_throttle_position": "mdi:valve",
    "absolute_throttle_position_b": "mdi:valve",
    "throttle_position_manifold": "mdi:valve",
    "accelerator_pedal_pos_d": "mdi:car-cruise-control",
    "accelerator_pedal_pos_e": "mdi:car-cruise-control",
    "accelerator_pedal_pos_f": "mdi:car-cruise-control",
    "engine_load": "mdi:gauge",
    "engine_load_absolute": "mdi:gauge",
    "timing_advance": "mdi:engine",
    "driver_demand_engine_torque_pct": "mdi:engine",
    "actual_engine_torque_pct": "mdi:engine",
    "engine_reference_torque": "mdi:engine",
    "torque": "mdi:engine",
    "horsepower_wheels": "mdi:engine",

    # Carburant / conso / niveau / coût
    "fuel_level_ecu": "mdi:gas-station",
    "fuel_rate_ecu": "mdi:gas-station",
    "l_per_100_instant": "mdi:gas-station",
    "l_per_100_trip_avg": "mdi:gas-station",
    "mpg_instant": "mdi:gas-station",
    "mpg_trip_avg": "mdi:gas-station",
    "kpl_instant": "mdi:gas-station",
    "kpl_trip_avg": "mdi:gas-station",
    "l_per_100_long_term_avg": "mdi:gas-station",
    "mpg_long_term_avg": "mdi:gas-station",
    "kpl_long_term_avg": "mdi:gas-station",
    "fuel_flow_rate_min": "mdi:gas-station",
    "fuel_flow_rate_hr": "mdi:gas-station",
    "fuel_used_trip": "mdi:gas-station",
    "ethanol_fuel_pct": "mdi:gas-station",
    "distance_to_empty_est": "mdi:gas-station",
    "fuel_remaining_calc": "mdi:gas-station",
    "cost_per_km_instant": "mdi:cash-multiple",
    "cost_per_km_trip": "mdi:cash-multiple",

    # GPS & télémétrie
    "TORQUE_GPS_LAT": "mdi:map-marker",
    "TORQUE_GPS_LON": "mdi:map-marker",
    "TORQUE_GPS_ALTITUDE": "mdi:altimeter",
    "TORQUE_GPS_ACCURACY": "mdi:crosshairs-gps",
    "gpslat": "mdi:map-marker",
    "gpslon": "mdi:map-marker",
    "gpsalt": "mdi:altimeter",
    "gpsaccuracy": "mdi:crosshairs-gps",
    "gps_satellites": "mdi:satellite-variant",
    "gps_bearing": "mdi:compass",

    # Distances / temps de trajet / divers
    "trip_distance": "mdi:map-marker-distance",
    "trip_distance_stored": "mdi:map-marker-distance",
    "dist_since_codes_cleared": "mdi:map-marker-distance",
    "dist_mil_on": "mdi:map-marker-distance",
    "odometer_ecu": "mdi:map-marker-distance",
    "avg_trip_speed_moving": "mdi:speedometer",
    "avg_trip_speed_overall": "mdi:speedometer",
    "run_time_since_start": "mdi:timer-outline",
    "trip_time_since_start": "mdi:timer-outline",
    "trip_time_stationary": "mdi:timer-outline",
    "trip_time_moving": "mdi:timer-outline",
    "time_0_60mph": "mdi:timer-outline",
    "time_0_100kph": "mdi:timer-outline",
    "time_quarter_mile": "mdi:timer-outline",
    "time_eighth_mile": "mdi:timer-outline",
    "time_60_120mph": "mdi:timer-outline",
    "time_60_80mph": "mdi:timer-outline",
    "time_40_60mph": "mdi:timer-outline",
    "time_100_0kph": "mdi:timer-outline",
    "time_60_0mph": "mdi:timer-outline",
    "time_0_30mph": "mdi:timer-outline",
    "time_0_100mph": "mdi:timer-outline",
    "time_0_200kph": "mdi:timer-outline",
    "time_80_120kph": "mdi:timer-outline",
    "time_100_200kph": "mdi:timer-outline",
    "spd_diff_gps_obd": "mdi:swap-horizontal",

    # Qualité air / émissions / NOx / CO2
    "nox_pre_scr": "mdi:molecule",
    "nox_post_scr": "mdi:molecule",
    "co2_gkm_instant": "mdi:molecule-co2",
    "co2_gkm_avg": "mdi:molecule-co2",

    # DPF températures
    "dpf_b1_inlet_temp": "mdi:thermometer",
    "dpf_b1_outlet_temp": "mdi:thermometer",
    "dpf_b2_inlet_temp": "mdi:thermometer",
    "dpf_b2_outlet_temp": "mdi:thermometer",

    # Hybride
    "hybrid_ev_batt_charge": "mdi:battery",
    "hybrid_ev_batt_soh": "mdi:battery-heart-variant",

    # Accélérations (accéléromètre)
    "accel_x": "mdi:axis-arrow",
    "accel_y": "mdi:axis-arrow",
    "accel_z": "mdi:axis-arrow",
    "accel_total": "mdi:axis-arrow",
}

# --- Icônes par mots-clés (FR/EN) dans le nom complet ----------------------
ICON_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    # RPM / vitesse
    (re.compile(r"\brpm\b|revolutions", re.I), "mdi:gauge"),
    (re.compile(r"\bspeed\b|vitesse", re.I), "mdi:speedometer"),

    # Températures
    (re.compile(r"coolant.*temp|temp.*coolant|liquide.*refroid", re.I), "mdi:thermometer-water"),
    (re.compile(r"intake.*temp|air.*admission.*temp|air.*temp|IAT", re.I), "mdi:thermometer"),
    (re.compile(r"\boil\b.*temp|temp.*huile", re.I), "mdi:oil"),
    (re.compile(r"cat.*temp|catalyst.*temp|exhaust gas temp|EGT", re.I), "mdi:thermometer"),
    (re.compile(r"ambient.*temp|temp.*ambiante", re.I), "mdi:thermometer"),
    (re.compile(r"transmission.*temp", re.I), "mdi:thermometer"),

    # Électricité
    (re.compile(r"voltage|tension|battery|batterie|control module voltage", re.I), "mdi:car-battery"),
    (re.compile(r"\bcurrent\b|courant", re.I), "mdi:current-dc"),
    (re.compile(r"\bpower\b|puissance", re.I), "mdi:flash"),

    # Pressions / boost / baro / DPF
    (re.compile(r"\bmap\b|manifold.*absolute.*pressure|boost|suraliment", re.I), "mdi:gauge"),
    (re.compile(r"barometric|baro|barométrique", re.I), "mdi:gauge"),
    (re.compile(r"fuel.*pressure|pression.*carburant|rail", re.I), "mdi:gauge"),
    (re.compile(r"exhaust.*pressure|pression.*échappement|dpf.*pressure|pression.*dpf", re.I), "mdi:gauge"),

    # Mélange / O2 / AFR / lambda
    (re.compile(r"\bmaf\b|mass.*air.*flow|débit.*air", re.I), "mdi:air-filter"),
    (re.compile(r"oxygen|sonde.*o2|lambda|equivalence ratio|air fuel ratio", re.I), "mdi:lambda"),

    # Trim / réglages / couple / papillon
    (re.compile(r"short.*trim|long.*trim|fuel.*trim|correction.*carburant", re.I), "mdi:tune"),
    (re.compile(r"throttle|papillon|accelerat", re.I), "mdi:valve"),
    (re.compile(r"engine.*load|charge.*moteur", re.I), "mdi:gauge"),
    (re.compile(r"timing.*advance|avance.*allum|ignition|allumage", re.I), "mdi:engine"),
    (re.compile(r"torque|horsepower|kW", re.I), "mdi:engine"),

    # Carburant / conso / coût
    (re.compile(r"fuel.*level|niveau.*carburant", re.I), "mdi:gas-station"),
    (re.compile(r"fuel.*rate|consumption|conso|mpg|kpl|l/100", re.I), "mdi:gas-station"),
    (re.compile(r"distance to empty|autonomie", re.I), "mdi:gas-station"),
    (re.compile(r"cost.*km|coût", re.I), "mdi:cash-multiple"),

    # Distances / temps
    (re.compile(r"\btrip\b|temps.*trajet|duration|time|quarter mile|eighth mile", re.I), "mdi:timer-outline"),
    (re.compile(r"distance|odometer|odomètre|range", re.I), "mdi:map-marker-distance"),

    # GPS
    (re.compile(r"\bgps\b|latitude|longitude|accuracy|altitude|satellites|bearing", re.I), "mdi:map-marker"),

    # NOx / CO2 / pollution
    (re.compile(r"\bnox\b", re.I), "mdi:molecule"),
    (re.compile(r"\bco2\b", re.I), "mdi:molecule-co2"),

    # Hybride
    (re.compile(r"hybrid|ev|battery", re.I), "mdi:battery"),
    (re.compile(r"\bsoh\b|state of health", re.I), "mdi:battery-heart-variant"),

    # Accéléromètre
    (re.compile(r"accel", re.I), "mdi:axis-arrow"),
]

# --- Icônes par unité (fallback final) -------------------------------------
ICON_BY_UNIT: dict[str, str] = {
    "km/h": "mdi:speedometer",
    "kmh": "mdi:speedometer",
    "mph": "mdi:speedometer",
    "rpm": "mdi:gauge",
    "°c": "mdi:thermometer",
    "°f": "mdi:thermometer",
    "c": "mdi:thermometer",
    "f": "mdi:thermometer",
    "v": "mdi:car-battery",
    "a": "mdi:current-dc",
    "w": "mdi:flash",
    "kw": "mdi:flash",
    "kpa": "mdi:gauge",
    "bar": "mdi:gauge",
    "psi": "mdi:gauge",
    "g/s": "mdi:air-filter",
    "l/100km": "mdi:gas-station",
    "mpg": "mdi:gas-station",
    "kpl": "mdi:gas-station",
    "l/m": "mdi:gas-station",
    "l/hr": "mdi:gas-station",
    "cc/min": "mdi:gas-station",
    "s": "mdi:timer-outline",
    "min": "mdi:timer-outline",
    "h": "mdi:timer-outline",
    "ppm": "mdi:molecule",
    "g/km": "mdi:molecule-co2",
    "km": "mdi:map-marker-distance",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Register callback + recréer les anciens capteurs depuis l'Entity Registry."""
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
            _LOGGER.debug("sensor: failed to resolve coordinator via view for %s: %s", entry.entry_id, err)

    if coordinator is None:
        _LOGGER.warning("No coordinator found for %s (sensor)", entry.entry_id)
        return

    def _adder(car_id: str, short: str, meta: dict[str, Any]) -> None:
        device = DeviceInfo(identifiers={(DOMAIN, car_id)})
        ent = OBDSensor(coordinator, entry, device, car_id, short, meta)
        async_add_entities([ent], True)

    coordinator.set_sensor_adder(_adder)

    # ✅ Recréer immédiatement les entités déjà connues (avant la 1ʳᵉ trame)
    try:
        registry = er.async_get(hass)
        for ent in list(registry.entities.values()):
            if ent.config_entry_id != entry.entry_id:
                continue
            if ent.platform != DOMAIN or ent.domain != "sensor":
                continue
            uid = ent.unique_id or ""
            pref = f"{DOMAIN}-"
            if not uid.startswith(pref) or "-" not in uid[len(pref):]:
                continue
            rest = uid[len(pref):]
            car_id, short = rest.rsplit("-", 1)  # car_id peut contenir des '-'
            device = DeviceInfo(identifiers={(DOMAIN, car_id)})
            meta = {"name": ent.original_name or short}
            async_add_entities([OBDSensor(coordinator, entry, device, car_id, short, meta)], True)
    except Exception as err:
        _LOGGER.debug("sensor: registry restore failed: %s", err)


class OBDSensor(OBDEntity, SensorEntity, RestoreEntity):
    """Capteur OBD (unique_id stable)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OBDCoordinator,
        entry: ConfigEntry,
        device: DeviceInfo,
        car_id: str,
        short: str,
        meta: dict[str, Any] | None,
    ) -> None:
        super().__init__(coordinator, entry, short, device, vehicle_id=car_id)
        self._meta = meta or {}
        self._attr_name = (self._meta.get("name") or short).strip()
        self._restored_value: Any = None

    # ------- Restauration après reboot -------
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            last = await self.async_get_last_state()
            if last and last.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self._restored_value = self._coerce_number(last.state)
        except Exception as err:
            _LOGGER.debug("sensor(%s): restore failed: %s", self.unique_id, err)

    @staticmethod
    def _coerce_number(v: Any) -> Any:
        try:
            s = str(v).strip().replace(",", ".")
            f = float(s)
            return f if math.isfinite(f) else v
        except Exception:
            return v

    @property
    def available(self) -> bool:
        # Disponible si on a une valeur courante OU restaurée
        has_now = self.get_coordinator_value(self._sensor_key) is not None
        return bool(has_now or self._restored_value is not None)

    @property
    def native_value(self) -> Any:
        cur = self.get_coordinator_value(self._sensor_key)
        return cur if cur is not None else self._restored_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unité : d'abord la session (si déjà reçue), sinon la valeur par défaut
        issue du catalogue OBD_CODES pour ne pas perdre l'unité au reboot.
        """
        veh = self.coordinator_vehicle() or {}
        meta_by_key = veh.get("meta") or {}
        unit = (meta_by_key.get(self._sensor_key, {}).get("unit") or "").strip()
        if unit:
            return unit
        # Fallback avant la 1ʳᵉ trame
        key = (self._sensor_key or "").lower()
        return (DEFAULT_UNIT_BY_KEY.get(key) or None)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose raw_seconds for trip time sensors when available."""
        try:
            veh = self.coordinator_vehicle() or {}
            meta_by_key = veh.get("meta") or {}
            m = meta_by_key.get(self._sensor_key) or {}
            if isinstance(m, dict) and "raw_seconds" in m:
                return {"raw_seconds": m.get("raw_seconds")}
        except Exception:
            pass
        return None

    # ------- Icône dynamique (clé → nom → unité) -------
    @property
    def icon(self) -> str | None:
        key = (self._sensor_key or "").lower()

        # 1) mapping direct par clé courte
        icon = ICON_BY_KEY.get(key)
        if icon:
            return icon

        # 2) mots-clés sur le nom (FR/EN)
        try:
            veh = self.coordinator_vehicle() or {}
            meta_by_key: dict[str, Any] = veh.get("meta") or {}
            m = meta_by_key.get(key) or {}
            nm = (m.get("name") or m.get("full_en") or self._attr_name or key) or ""
            nm = str(nm)
            for rx, mdi in ICON_KEYWORDS:
                if rx.search(nm):
                    return mdi
        except Exception:
            pass

        # 3) fallback par unité
        unit = (self.native_unit_of_measurement or "").strip().lower()
        if unit in ICON_BY_UNIT:
            return ICON_BY_UNIT[unit]

        # 4) fallback très générique
        if key.startswith(("trip_", "time_")):
            return "mdi:timer-outline"
        if "temp" in key:
            return "mdi:thermometer"
        if "voltage" in key or "volt" in key or key.endswith("_v"):
            return "mdi:car-battery"
        if "pressure" in key or key.endswith("_kpa") or key.endswith("_bar") or key.endswith("_psi"):
            return "mdi:gauge"

        return None
