# -*- coding: utf-8 -*-
"""Config flow for OBD Drive (selectors for options UI)."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from homeassistant.helpers.selector import selector

from .const import (
    NAME, DOMAIN,
    CONF_EMAIL, CONF_IMPERIAL, CONF_LANGUAGE,
    CONF_SESSION_TTL, CONF_MAX_SESSIONS,
    DEFAULT_LANGUAGE, SUPPORTED_LANGS,
    SESSION_TTL_SECONDS, MAX_SESSIONS,
    CONF_MERGE_MODE, CONF_MERGE_NAME_MAP,
    MERGE_MODE_NONE, MERGE_MODE_NAME, MERGE_MODE_VIN,
    DEFAULT_MERGE_MODE, DEFAULT_MERGE_NAME_MAP,
    CONF_REJECT_POOR_NAME, CONF_REQUIRE_MAPPED_NAME,
    DEFAULT_REJECT_POOR_NAME, DEFAULT_REQUIRE_MAPPED_NAME,
)

# -------------------- Libellés localisés --------------------
LANG_LABELS = {
    "fr": "Français",
    "en": "English",
}

MERGE_MODE_LABELS = {
    "fr": {
        MERGE_MODE_NONE: "Aucune (désactivé)",
        MERGE_MODE_NAME: "Par nom (recommandé)",
        MERGE_MODE_VIN:  "Par VIN (identifiant véhicule)",
    },
    "en": {
        MERGE_MODE_NONE: "None (disabled)",
        MERGE_MODE_NAME: "By name (recommended)",
        MERGE_MODE_VIN:  "By VIN (vehicle identifier)",
    },
}
# ------------------------------------------------------------


def _codes_from_supported_langs(supported) -> list[str]:
    if isinstance(supported, dict):
        return list(supported.keys())
    if isinstance(supported, (list, tuple, set)):
        return list(supported)
    return [str(supported)]


class OBDFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OBD Drive."""
    VERSION = 2

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}
        lang_codes = _codes_from_supported_langs(SUPPORTED_LANGS)

        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL, "")).strip().lower()
            imperial = bool(user_input.get(CONF_IMPERIAL, False))
            language = user_input.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

            if not email:
                errors[CONF_EMAIL] = "email_required"
            if language not in lang_codes:
                language = DEFAULT_LANGUAGE

            if not errors:
                for entry in self._async_current_entries():
                    if str(entry.data.get(CONF_EMAIL, "")).strip().lower() == email:
                        return self.async_abort(reason="already_configured")

                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_EMAIL: email,
                    CONF_IMPERIAL: imperial,
                    CONF_LANGUAGE: language,
                }
                return self.async_create_entry(title=f"{NAME} ({email})", data=data)

        lang_option_labels = {code: LANG_LABELS.get(code, code) for code in _codes_from_supported_langs(SUPPORTED_LANGS)}

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Optional(CONF_IMPERIAL, default=False): bool,
            vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(lang_option_labels),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_import(self, user_input: dict):
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return OBDOptionsFlowHandler(config_entry)


class OBDOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler (selectors + libellés + garde-fous)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        lang_codes = _codes_from_supported_langs(SUPPORTED_LANGS)

        # Langue UI (pour libellés de merge_mode)
        opts = self._config_entry.options
        data = self._config_entry.data
        cur = lambda k, d: opts.get(k, data.get(k, d))

        ui_lang = str(cur(CONF_LANGUAGE, DEFAULT_LANGUAGE))
        if ui_lang not in MERGE_MODE_LABELS:
            ui_lang = "en"

        lang_option_labels = {code: LANG_LABELS.get(code, code) for code in lang_codes}
        merge_mode_labels = MERGE_MODE_LABELS.get(ui_lang, MERGE_MODE_LABELS["en"])

        if user_input is not None:
            # sanitize booleans & ints
            user_input[CONF_IMPERIAL] = bool(user_input.get(CONF_IMPERIAL, False))
            user_input[CONF_SESSION_TTL] = int(user_input.get(CONF_SESSION_TTL, SESSION_TTL_SECONDS))
            user_input[CONF_MAX_SESSIONS] = int(user_input.get(CONF_MAX_SESSIONS, MAX_SESSIONS))

            # language clamp
            user_input[CONF_LANGUAGE] = user_input.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
            if user_input[CONF_LANGUAGE] not in lang_codes:
                user_input[CONF_LANGUAGE] = DEFAULT_LANGUAGE

            # merge mode clamp (support libellé renvoyé)
            selected = user_input.get(CONF_MERGE_MODE, DEFAULT_MERGE_MODE)
            if selected in merge_mode_labels.values():
                inv = {v: k for k, v in merge_mode_labels.items()}
                selected = inv.get(selected, DEFAULT_MERGE_MODE)
            selected = str(selected).lower()
            if selected not in (MERGE_MODE_NONE, MERGE_MODE_NAME, MERGE_MODE_VIN):
                selected = DEFAULT_MERGE_MODE
            user_input[CONF_MERGE_MODE] = selected

            # mapping + garde-fous
            user_input[CONF_MERGE_NAME_MAP] = str(user_input.get(CONF_MERGE_NAME_MAP, DEFAULT_MERGE_NAME_MAP))
            user_input[CONF_REJECT_POOR_NAME] = bool(user_input.get(CONF_REJECT_POOR_NAME, DEFAULT_REJECT_POOR_NAME))
            user_input[CONF_REQUIRE_MAPPED_NAME] = bool(user_input.get(CONF_REQUIRE_MAPPED_NAME, DEFAULT_REQUIRE_MAPPED_NAME))

            return self.async_create_entry(title="", data=user_input)

        # --- Defaults “safe” pour éviter 400 si anciennes valeurs stockées ---
        def_mode = str(cur(CONF_MERGE_MODE, DEFAULT_MERGE_MODE)).lower()
        if def_mode in merge_mode_labels.values():
            inv = {v: k for k, v in merge_mode_labels.items()}
            def_mode = inv.get(def_mode, DEFAULT_MERGE_MODE)
        if def_mode not in (MERGE_MODE_NONE, MERGE_MODE_NAME, MERGE_MODE_VIN):
            def_mode = DEFAULT_MERGE_MODE

        _lang_default = str(cur(CONF_LANGUAGE, DEFAULT_LANGUAGE))
        if _lang_default not in lang_option_labels:
            _lang_default = DEFAULT_LANGUAGE
        # --------------------------------------------------------------------

        schema = vol.Schema({
            vol.Optional(CONF_IMPERIAL, default=bool(cur(CONF_IMPERIAL, False))): bool,
            vol.Optional(CONF_LANGUAGE, default=_lang_default): vol.In(lang_option_labels),
            vol.Optional(CONF_SESSION_TTL, default=int(cur(CONF_SESSION_TTL, SESSION_TTL_SECONDS))): int,
            vol.Optional(CONF_MAX_SESSIONS, default=int(cur(CONF_MAX_SESSIONS, MAX_SESSIONS))): int,

            # select avec labels → stocke valeurs none/name/vin
            vol.Optional(CONF_MERGE_MODE, default=def_mode): selector({
                "select": {
                    "options": [
                        {"label": merge_mode_labels.get(MERGE_MODE_NONE, MERGE_MODE_NONE), "value": MERGE_MODE_NONE},
                        {"label": merge_mode_labels.get(MERGE_MODE_NAME, MERGE_MODE_NAME), "value": MERGE_MODE_NAME},
                        {"label": merge_mode_labels.get(MERGE_MODE_VIN,  MERGE_MODE_VIN),  "value": MERGE_MODE_VIN},
                    ],
                    "mode": "dropdown"
                }
            }),

            # textarea (multiligne) — pas de 'rows' (non supporté)
            vol.Optional(CONF_MERGE_NAME_MAP, default=str(cur(CONF_MERGE_NAME_MAP, DEFAULT_MERGE_NAME_MAP))): selector({
                "text": {"multiline": True}
            }),

            # garde-fous
            vol.Optional(CONF_REJECT_POOR_NAME,  default=bool(cur(CONF_REJECT_POOR_NAME,  DEFAULT_REJECT_POOR_NAME))): bool,
            vol.Optional(CONF_REQUIRE_MAPPED_NAME, default=bool(cur(CONF_REQUIRE_MAPPED_NAME, DEFAULT_REQUIRE_MAPPED_NAME))): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
