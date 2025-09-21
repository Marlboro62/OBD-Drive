# -*- coding: utf-8 -*-
"""Public HTTP endpoint for OBD Drive with merge options."""
from __future__ import annotations
from typing import Any, Dict
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import logging, inspect, math, re, hashlib
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

try:
    from .labels_fr import FR_BY_KEY
except Exception:
    FR_BY_KEY = {}

from .const import (
    DOMAIN, DEFAULT_LANGUAGE, RUNTIME_LANG_MAP,
    SESSION_TTL_SECONDS, MAX_SESSIONS, OBD_CODES,
    OBD_GPS_LAT, OBD_GPS_LON, OBD_GPS_ALTITUDE, OBD_GPS_ACCURACY,
    MERGE_MODE_NONE, MERGE_MODE_NAME, MERGE_MODE_VIN,
)

_LOGGER = logging.getLogger(__name__)

# ---------- Helpers conversion d’unités ----------
def _round(v: float, nd: int = 2) -> float:
    try:
        return round(float(v), nd)
    except Exception:
        return float("nan")

def _apply_unit_preference(values: Dict[str, Any], meta: Dict[str, Dict[str, Any]], unit_pref: str) -> None:
    """Convertit valeurs + unités en place si préférence = impérial."""
    if unit_pref != "imperial":
        return

    for short, m in list(meta.items()):
        unit = (m.get("unit") or "").strip()
        if not unit:
            continue
        v = values.get(short)
        if not isinstance(v, (int, float)):
            continue

        u = unit.lower()

        # 1) Vitesse km/h -> mph
        if u in ("km/h", "kmh"):
            values[short] = _round(v * 0.621371, 2)
            m["unit"] = "mph"

        # 2) Distance km -> mi
        elif u == "km":
            values[short] = _round(v * 0.621371, 3)
            m["unit"] = "mi"

        # 3) Altitude m -> ft (ne pas convertir l'accuracy)
        elif u == "m" and short == OBD_GPS_ALTITUDE:
            values[short] = _round(v * 3.28084, 1)
            m["unit"] = "ft"

        # 4) Températures °C -> °F
        elif u in ("°c", "c", "degc"):
            values[short] = _round((v * 9.0 / 5.0) + 32.0, 1)
            m["unit"] = "°F"

        # 5) Pressions -> psi
        elif u == "kpa":
            values[short] = _round(v * 0.145038, 2)
            m["unit"] = "psi"
        elif u == "bar":
            values[short] = _round(v * 14.5038, 2)
            m["unit"] = "psi"

        # 6) Conso L/100km -> mpg (US)
        elif u in ("l/100km", "lper100km", "l_100km"):
            try:
                fv = float(v)
                if fv > 0:
                    values[short] = _round(235.215 / fv, 2)
                    m["unit"] = "mpg"
            except Exception:
                pass

        # 7) (Optionnel) Couple N·m -> lb·ft
        elif u in ("n·m", "nm"):
            values[short] = _round(v * 0.737562, 2)
            m["unit"] = "lb·ft"

        meta[short] = m
# ---------- Fin helpers unités ----------

_LABELS_FR: dict[str, str] | None = None
def _ensure_labels_fr() -> dict[str, str]:
    global _LABELS_FR
    if _LABELS_FR is not None:
        return _LABELS_FR
    labels: dict[str, str] = {}
    for meta in OBD_CODES.values():
        full_en = (meta.get("fullName") or "").strip().lower()
        short = meta.get("shortName") or ""
        fr = FR_BY_KEY.get(short)
        if full_en and fr:
            labels[full_en] = fr
    _LABELS_FR = labels
    return _LABELS_FR

def get_label(lang: str, full_en: str) -> str:
    if (lang or DEFAULT_LANGUAGE).lower() == "fr":
        labels = _ensure_labels_fr()
        key = (full_en or "").strip().lower()
        return labels.get(key, full_en)
    return full_en

_POOR_NAME_RE = re.compile(r"^\s*vehicle\s*\d+\s*$", re.IGNORECASE)
def _is_poor_name(name: str | None) -> bool:
    if not name:
        return True
    s = name.strip()
    if not s:
        return True
    low = s.lower()
    if low in {"vehicle", "véhicule"}:
        return True
    return bool(_POOR_NAME_RE.match(low))

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _parse_number(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if s == "":
            return None
        s = s.replace(",", ".")
        sl = s.lower()
        if sl in ("inf", "+inf", "-inf", "infinity", "nan"):
            return None
        v = float(s)
        return v if math.isfinite(v) else None
    except Exception:
        return None

def _pick_lang(query_lang: str | None) -> str:
    lang = (query_lang or DEFAULT_LANGUAGE).strip().lower()
    return RUNTIME_LANG_MAP.get(lang, DEFAULT_LANGUAGE)

def _norm_key(k: str) -> str:
    return k.lower().replace(".", "").replace("-", "").replace("_", "").strip()

def _extract_profile_name(q: Dict[str, str]) -> str:
    candidates = (
        "profileName","profile_name","profile",
        "vehicleName","vehicle","carName","car","name",
        "profilename","profile.name"
    )
    wanted = {_norm_key(c) for c in candidates}
    for k, v in q.items():
        if _norm_key(k) in wanted:
            s = str(v).strip()
            if s:
                return s
    return ""

def _parse_name_map_text(text: str) -> dict[str, str]:
    """Supporte multi-lignes ou monoligne (séparateur ';')."""
    mapping: dict[str, str] = {}
    if not text:
        return mapping

    txt = str(text).replace("\r\n", "\n").replace("\r", "\n").replace(";", "\n")
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("->", "=>", ":", "="):
            if sep in line:
                left, right = line.split(sep, 1)
                break
        else:
            parts = line.split()
            if len(parts) >= 2:
                left, right = " ".join(parts[:-1]), parts[-1]
            else:
                continue
        left = left.strip(); right = right.strip()
        if not left or not right:
            continue
        mapping[left.lower()] = right
        mapping[slugify(left)] = right
    return mapping

def _lookup_canonical(name_map: dict[str, str], profile_name: str) -> str:
    if not profile_name:
        return ""
    low = profile_name.strip().lower()
    slug = slugify(profile_name)
    return name_map.get(low) or name_map.get(slug) or ""

class OBDReceiveDataView(HomeAssistantView):
    # Si tu préfères /api/OBD, change ces 2 champs.
    url = "/api/OBD"
    name = "api:OBD"
    requires_auth = True

    coordinator: Any | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        email_filter: str | None = None,
        default_language: str = DEFAULT_LANGUAGE,
        imperial_units: bool = False,
        session_ttl_seconds: int | None = None,
        max_sessions: int | None = None,
    ) -> None:
        self.hass = hass
        self.email = (email_filter or "").strip()
        self.lang = _pick_lang(default_language)
        self.imperial = bool(imperial_units)
        self._sessions: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._ttl_seconds = int(session_ttl_seconds or SESSION_TTL_SECONDS)
        self._max_sessions = int(max_sessions or MAX_SESSIONS)
        self._last_name_by_email: Dict[str, str] = {}
        self._last_name_by_id: Dict[str, str] = {}
        self._entry_routes: dict[str, dict[str, Any]] = {}
        self._email_to_entry: dict[str, str] = {}
        self._merge_prefs_by_entry: dict[str, dict[str, Any]] = {}
        self._canonical_to_entry: dict[str, str] = {}
        self._active: bool = True

    # --- API publiques ---

    def set_session_limits(self, *, ttl_seconds: int | None = None, max_sessions: int | None = None) -> None:
        if ttl_seconds is not None:
            try:
                ttl = int(ttl_seconds)
                if ttl > 0:
                    self._ttl_seconds = ttl
            except Exception as err:
                _LOGGER.debug("set_session_limits: invalid ttl_seconds=%s (%s)", ttl_seconds, err)
        if max_sessions is not None:
            try:
                m = int(max_sessions)
                if m > 0:
                    self._max_sessions = m
            except Exception as err:
                _LOGGER.debug("set_session_limits: invalid max_sessions=%s (%s)", max_sessions, err)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)

    def resolve_entry_route(self, entry_id: str) -> dict[str, Any] | None:
        return self._entry_routes.get(entry_id)

    # -------------------------------------------------------------------------------

    def upsert_route(
        self,
        entry_id: str,
        *,
        email: str | None,
        coordinator: Any,
        imperial: bool,
        lang: str,
        merge_mode: str | None = None,
        merge_name_map: str | None = None,
        # 🆕 garde-fous anti “Vehicle ######”
        reject_poor_name: bool = True,
        require_mapped_name: bool = False,
    ) -> None:
        email_norm = (email or "").strip().lower()
        prev = self._entry_routes.get(entry_id)
        if prev and prev.get("email"):
            self._email_to_entry.pop(prev["email"], None)

        mode = (merge_mode or MERGE_MODE_NONE).strip().lower()
        if mode not in {MERGE_MODE_NONE, MERGE_MODE_NAME, MERGE_MODE_VIN}:
            mode = MERGE_MODE_NONE

        name_map = _parse_name_map_text(merge_name_map or "")
        self._merge_prefs_by_entry[entry_id] = {"mode": mode, "name_map": name_map}

        self._entry_routes[entry_id] = {
            "entry_id": entry_id,
            "coordinator": coordinator,
            "email": email_norm,
            "imperial": bool(imperial),
            "lang": _pick_lang(lang),
            "merge_mode": mode,
            "name_map": name_map,
            # 🆕 stocke les flags
            "reject_poor_name": bool(reject_poor_name),
            "require_mapped_name": bool(require_mapped_name),
        }
        if email_norm:
            self._email_to_entry[email_norm] = entry_id
        self._active = True

    def remove_route(self, entry_id: str) -> None:
        prev = self._entry_routes.pop(entry_id, None)
        if prev and prev.get("email"):
            self._email_to_entry.pop(prev["email"], None)
        self._merge_prefs_by_entry.pop(entry_id, None)
        for k in [k for k, v in self._canonical_to_entry.items() if v == entry_id]:
            self._canonical_to_entry.pop(k, None)
        if not self._entry_routes:
            self._active = False

    def _pick_route(self, email: str | None) -> dict[str, Any] | None:
        key = (email or "").strip().lower()
        if key and key in self._email_to_entry:
            return self._entry_routes.get(self._email_to_entry[key])
        if not key and len(self._entry_routes) == 1:
            return next(iter(self._entry_routes.values()))
        if not self._entry_routes and (self.coordinator or self.email):
            return {
                "entry_id": "legacy",
                "coordinator": self.coordinator,
                "email": (self.email or "").strip().lower(),
                "imperial": self.imperial,
                "lang": self.lang,
                "merge_mode": MERGE_MODE_NONE,
                "name_map": {},
                "reject_poor_name": True,
                "require_mapped_name": False,
            }
        return None

    def _maybe_reroute_by_canonical(self, initial_route: dict[str, Any] | None, profile_name: str) -> dict[str, Any] | None:
        if not self._entry_routes:
            return initial_route
        canonical = ""
        if initial_route:
            eid = None
            for k, v in self._entry_routes.items():
                if v is initial_route:
                    eid = k
                    break
            prefs = self._merge_prefs_by_entry.get(eid or "", {})
            if prefs.get("mode") == MERGE_MODE_NAME:
                canonical = _lookup_canonical(prefs.get("name_map", {}), profile_name)
        if not canonical and profile_name:
            for _, prefs in self._merge_prefs_by_entry.items():
                if prefs.get("mode") != MERGE_MODE_NAME:
                    continue
                c = _lookup_canonical(prefs.get("name_map", {}), profile_name)
                if c:
                    canonical = c
                    break
        if not canonical:
            return initial_route
        owner_entry_id = self._canonical_to_entry.get(canonical)
        if not owner_entry_id:
            owner_entry_id = None
            if initial_route:
                for k, v in self._entry_routes.items():
                    if v is initial_route:
                        owner_entry_id = k
                        break
            if not owner_entry_id and self._entry_routes:
                owner_entry_id = next(iter(self._entry_routes.keys()))
            if owner_entry_id:
                self._canonical_to_entry[canonical] = owner_entry_id
        return self._entry_routes.get(owner_entry_id, initial_route)

    def _cleanup_sessions(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._ttl_seconds)
        while self._sessions:
            _, sess = next(iter(self._sessions.items()))
            last = sess.get("last_seen")
            if last is None or last <= cutoff:
                self._sessions.popitem(last=False)
            else:
                break
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def _upsert_and_touch(self, session: Dict[str, Any]) -> None:
        self._sessions[session["id"]] = session
        self._sessions.move_to_end(session["id"], last=True)

    @staticmethod
    def _extract_app_version(q: Dict[str, str]) -> str:
        for k in ("appVersion", "app_version", "apkVersion", "versionName", "version"):
            v = str(q.get(k, "")).strip()
            if v:
                return v
        for k in ("ver", "v"):
            v = str(q.get(k, "")).strip()
            if v and any(ch in v for ch in ".-"):
                return v
        return ""

    def _parse_fields(
        self,
        q: Dict[str, str],
        lang: str,
        *,
        imperial_override: bool | None = None,
        merge_mode: str = MERGE_MODE_NONE,
        canonical_hint: str = "",
        # 🆕 drapeaux anti “Vehicle ######”
        reject_poor: bool = True,
        require_mapped: bool = False,
    ) -> Dict[str, Any] | None:
        eml = (q.get("eml") or q.get("email") or "").strip()
        session_id = (q.get("session") or "").strip()
        if not session_id:
            return None

        vehicle_id = (q.get("id") or "").strip()
        profile_name_raw = _extract_profile_name(q)
        profile_name_raw = re.sub(r"\s+", " ", (profile_name_raw or "")).strip()
        app_version = self._extract_app_version(q)

        if (q.get("v") or q.get("ver")) and not app_version:
            _LOGGER.debug("Ignoring protocol version v/ver (no app version provided)")

        lat_direct = _parse_number(q.get("lat") or q.get("gpslat"))
        lon_direct = _parse_number(q.get("lon") or q.get("gpslon"))
        if lat_direct is not None and not (-90.0 <= lat_direct <= 90.0):
            lat_direct = None
        if lon_direct is not None and not (-180.0 <= lon_direct <= 180.0):
            lon_direct = None

        values: Dict[str, Any] = {}
        meta: Dict[str, Dict[str, Any]] = {}
        unknown: Dict[str, Any] = {}

        # Décodage des PIDs
        for key, raw in q.items():
            if not key or key[0].lower() != "k":
                continue
            code = key[1:].lower()
            meta_code = OBD_CODES.get(code)
            if not meta_code:
                if len(unknown) < 80:
                    unknown[code] = raw
                continue
            short = meta_code["shortName"]
            unit = meta_code.get("unit") or ""
            full_en = meta_code.get("fullName") or short
            name_fr = get_label(lang, full_en)
            val = _parse_number(raw)
            values[short] = val if val is not None else raw
            meta[short] = {"name": name_fr, "unit": unit, "full_en": full_en, "code": code}

        if lat_direct is not None:
            values[OBD_GPS_LAT] = lat_direct
            meta.setdefault(OBD_GPS_LAT, {"name": get_label(lang, "GPS Latitude"), "unit": "°", "full_en": "GPS Latitude", "code": "ff1006"})
        if lon_direct is not None:
            values[OBD_GPS_LON] = lon_direct
            meta.setdefault(OBD_GPS_LON, {"name": get_label(lang, "GPS Longitude"), "unit": "°", "full_en": "GPS Longitude", "code": "ff1005"})
        alt_direct = _parse_number(q.get("alt") or q.get("altitude") or q.get("gps_height") or q.get("gpsalt"))
        if alt_direct is not None:
            values[OBD_GPS_ALTITUDE] = alt_direct
            meta.setdefault(OBD_GPS_ALTITUDE, {"name": get_label(lang, "GPS Altitude"), "unit": "m", "full_en": "GPS Altitude", "code": "ff1010"})
        acc_direct = _parse_number(q.get("acc") or q.get("accuracy") or q.get("gps_acc") or q.get("gpsaccuracy"))
        if acc_direct is not None and acc_direct >= 0:
            values[OBD_GPS_ACCURACY] = acc_direct
            meta.setdefault(OBD_GPS_ACCURACY, {"name": get_label(lang, "GPS Accuracy"), "unit": "m", "full_en": "GPS Accuracy", "code": "ff1239"})

        # Compat: vitesse GPS directe (legacy gps_spd / speed_gps)
        spd_direct = _parse_number(q.get("speed_gps") or q.get("gps_spd"))
        if spd_direct is not None and spd_direct >= 0:
            values["speed_gps"] = spd_direct
            meta.setdefault(
                "speed_gps",
                {"name": get_label(lang, "Vehicle Speed (GPS)"), "unit": "km/h", "full_en": "Vehicle Speed (GPS)", "code": ""},
            )

        # --- Fusion par nom / VIN ---
        canonical_name = canonical_hint.strip() if canonical_hint else ""
        if merge_mode == MERGE_MODE_VIN:
            vin = str(q.get("vin", "")).strip()
            if vin:
                canonical_name = vin

        # Fallback nom mémorisé si payload pauvre
        profile_name = profile_name_raw
        used_email_fallback = False
        if not profile_name or _is_poor_name(profile_name):
            remembered = (
                (vehicle_id and self._last_name_by_id.get(vehicle_id))
                or (eml and self._last_name_by_email.get(eml))
                or ""
            )
            if remembered and not _is_poor_name(remembered):
                profile_name = remembered
                used_email_fallback = True

        # 🧱 Garde-fous : ignorer les trames "pauvres"
        if reject_poor and (not profile_name or _is_poor_name(profile_name)) and not canonical_name:
            # pas de nom exploitable ET pas de nom canonique -> on ignore
            return None

        # 🧱 En mode name + stricte : refuser si non mappé
        if require_mapped and merge_mode == MERGE_MODE_NAME and not canonical_name:
            return None

        # S'il reste vraiment aucun nom, autoriser un fallback non-persistant
        if not profile_name and not canonical_name:
            profile_name = f"Vehicle {session_id[:6]}"

        # Nom utilisé pour affichage
        display_name = canonical_name or profile_name
        if not display_name or _is_poor_name(display_name):
            display_name = profile_name or f"Vehicle {session_id[:6]}"

        # ID stable (slug + éventuel sel par email)
        effective_name = display_name if not _is_poor_name(display_name) else ""
        salt = ""
        if eml and not canonical_name:
            try:
                salt = hashlib.sha1(eml.encode("utf-8")).hexdigest()[:4]
            except Exception:
                salt = ""

        if canonical_name:
            base = slugify(canonical_name)
            profile_id = base
        else:
            if effective_name:
                base = slugify(effective_name)
                profile_id = (
                    f"{base}_{vehicle_id[:4]}{('_' + salt) if (vehicle_id and salt) else ''}"
                    if vehicle_id else f"{base}{('_' + salt) if salt else ''}"
                )
            elif vehicle_id:
                profile_id = f"{vehicle_id}{('_' + salt) if salt else ''}"
            else:
                profile_id = f"veh_{session_id[:6]}"

        imperial_flag = self.imperial if imperial_override is None else bool(imperial_override)
        unit_preference = "imperial" if imperial_flag else "metric"
        profile = {"Name": display_name, "Id": profile_id, "Email": eml}
        if app_version:
            profile["version"] = app_version

        # Convert seconds->minutes pour certains temps de trajet
        for short, m in list(meta.items()):
            unit = (m.get("unit") or "").strip()
            if short in {"trip_time_since_start", "trip_time_stationary", "trip_time_moving"} and unit == "s":
                v = values.get(short)
                if isinstance(v, (int, float)) and math.isfinite(float(v)):
                    # Preserve raw seconds for debugging
                    try:
                        m["raw_seconds"] = float(v)
                    except Exception:
                        pass                    
                    values[short] = round(float(v) / 60.0, 2)
                    m["unit"] = "min"
                    meta[short] = m

        # Nettoyage des non-finies
        for k, v in list(values.items()):
            try:
                if isinstance(v, (int, float)) and not math.isfinite(float(v)):
                    values[k] = None
            except Exception:
                values[k] = None

        # Conversion d’unités selon préférence
        _apply_unit_preference(values, meta, unit_preference)

        session = {
            "id": session_id,
            "last_seen": _now_utc(),
            "profile": profile,
            "values": values,
            "meta": meta,
            "unknown": unknown,
            "lang": lang,
            "unit_preference": unit_preference,
        }
        if not _is_poor_name(profile_name_raw):
            if eml and not used_email_fallback:
                self._last_name_by_email[eml] = profile_name_raw
            if vehicle_id:
                self._last_name_by_id[vehicle_id] = profile_name_raw
        return session

    async def _async_publish_data(self, session: Dict[str, Any], coordinator: Any | None) -> None:
        if coordinator:
            upd = getattr(coordinator, "update_from_session", None)
            if callable(upd):
                try:
                    if inspect.iscoroutinefunction(upd):
                        await upd(session)  # type: ignore[misc]
                    else:
                        await self.hass.async_add_executor_job(upd, session)  # type: ignore[misc]
                except Exception:
                    _LOGGER.exception("Coordinator.update_from_session failed")
        self.hass.data.setdefault(DOMAIN, {})["last_session"] = session

    async def get(self, request: web.Request) -> web.Response:
        try:
            if not self._active:
                return web.Response(status=404, text="Not Found")
            self._cleanup_sessions()
            q = dict(request.query)
            eml = (q.get("eml") or q.get("email") or "").strip()
            profile_name = _extract_profile_name(q)
            route = self._pick_route(eml)
            route = self._maybe_reroute_by_canonical(route, profile_name)
            if route is None:
                return web.Response(text="IGNORED")
            lang = _pick_lang(str(q.get("lang") or q.get("language") or route["lang"]))
            canonical_hint = _lookup_canonical(route.get("name_map", {}), profile_name) if route.get("merge_mode") == MERGE_MODE_NAME else ""
            session = self._parse_fields(
                q,
                lang,
                imperial_override=route["imperial"],
                merge_mode=route.get("merge_mode", MERGE_MODE_NONE),
                canonical_hint=canonical_hint,
                reject_poor=bool(route.get("reject_poor_name", True)),
                require_mapped=bool(route.get("require_mapped_name", False)),
            )
            if session is None:
                return web.Response(text="IGNORED")
            self._upsert_and_touch(session)
            await self._async_publish_data(session, route.get("coordinator"))
            return web.Response(text="OK!")
        except Exception as err:
            _LOGGER.exception("Error handling OBD Drive GET: %s", err)
            return web.Response(status=500, text="Error")

    async def post(self, request: web.Request) -> web.Response:
        try:
            if not self._active:
                return web.Response(status=404, text="Not Found")
            self._cleanup_sessions()
            data: Dict[str, Any] = {}
            if request.can_read_body:
                # Try JSON first
                try:
                    js = await request.json()
                    if isinstance(js, dict):
                        data.update(js)
                except Exception:
                    pass
                # Then form-data
                try:
                    form = await request.post()
                    for k, v in (form or {}).items():
                        data.setdefault(k, v)
                except Exception:
                    pass
            # Merge with querystring (does not override body keys)
            try:
                for k, v in dict(request.query).items():
                    data.setdefault(k, v)
            except Exception:
                pass
            # Normalize values to simple types (str/int/float) when possible
            normed: Dict[str, Any] = {}
            for k, v in (data or {}).items():
                try:
                    if isinstance(v, (str, int, float)) or v is None:
                        normed[k] = v
                    else:
                        normed[k] = str(v)
                except Exception:
                    normed[k] = None
            data = normed
            eml = (data.get("eml") or data.get("email") or "").strip()
            profile_name = _extract_profile_name(data)
            route = self._pick_route(eml)
            route = self._maybe_reroute_by_canonical(route, profile_name)
            if route is None:
                return web.Response(text="IGNORED")
            lang = _pick_lang(str(data.get("lang") or data.get("language") or route["lang"]))
            canonical_hint = _lookup_canonical(route.get("name_map", {}), profile_name) if route.get("merge_mode") == MERGE_MODE_NAME else ""
            session = self._parse_fields(
                data,
                lang,
                imperial_override=route["imperial"],
                merge_mode=route.get("merge_mode", MERGE_MODE_NONE),
                canonical_hint=canonical_hint,
                reject_poor=bool(route.get("reject_poor_name", True)),
                require_mapped=bool(route.get("require_mapped_name", False)),
            )
            if session is None:
                return web.Response(text="IGNORED")
            self._upsert_and_touch(session)
            await self._async_publish_data(session, route.get("coordinator"))
            return web.Response(text="OK!")
        except Exception as err:
            _LOGGER.exception("Error handling OBD Drive POST: %s", err)
            return web.Response(status=500, text="Error")

    async def head(self, request: web.Request) -> web.Response:
        return web.Response(status=200)
