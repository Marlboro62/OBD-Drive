![OBD Drive](https://github.com/Marlboro62/OBD-Drive/blob/main/assets/logo.png)

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/nothing_one)

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4%EF%B8%8F_GitHub_Sponsors-ff69b4?logo=githubsponsors)](https://github.com/sponsors/Marlboro62)

# OBD‑Drive — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5)](https://www.home-assistant.io/)
[![Status](https://img.shields.io/badge/Status-Stable-success)](#)
[![Language](https://img.shields.io/badge/Language-FR%20%2F%20EN-informational)](#)

Monitor your vehicle’s **OBD‑II data in real time** inside **Home Assistant** using the Android app **Torque** (ELM327). The **OBD‑Drive** integration dynamically exposes sensors (PIDs), creates a GPS *device_tracker*, and auto‑handles metric units.

> ⚠️ **Driving**: do not use your phone while driving. This integration is provided **as‑is** with **no warranty**. You are responsible for your safety and your data.

---

## ✨ Features

- Receive live uploads from **Torque** via `GET` or `POST` to `/api/obd`
- **Automatic** sensor (PID) creation with localized names/units (EN/FR)
- GPS tracking: `device_tracker` (latitude, longitude, altitude, accuracy, speed)
- **Multi‑vehicle / multi‑profile** (via `profileName` and/or `eml`)
- Smart unit conversion (e.g., L/100 ↔ KPL/MPG — avoids duplicates)
- No YAML required (Home Assistant UI)
- HACS compatible (Custom Repository)

---

## 📦 Requirements

- **Home Assistant** (recent version) — *Tested on 2025.9.4*
- **Android smartphone** with **Torque**  
  <a href="https://play.google.com/store/apps/details?id=org.prowl.torque" target="_blank" rel="noopener noreferrer">
    <img alt="Get it on Google Play"
         src="https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png"
         height="40">
  </a>
- **OBD‑II Bluetooth dongle** (e.g., **ELM327**)  
  <a href="https://amzn.to/3KezyCM" target="_blank" rel="noopener noreferrer">
    <img alt="View on Amazon"
         src="https://img.shields.io/badge/View%20on-Amazon-FF9900?logo=amazon&logoColor=white">
  </a>
- Network access from the phone to Home Assistant (LAN, VPN, or public HTTPS)

---

## 🧭 Table of Contents

- [Installation](#installation)
  - [Via HACS (recommended)](#via-hacs)
  - [Manual installation](#manual-installation)
- [Home Assistant configuration](#home-assistant-configuration)
- [Settings in Torque (Android)](#settings-in-torque-android)
  - [Supported parameters](#supported-parameters)
  - [URL examples](#url-examples)
- [Created entities](#created-entities)
- [Dashboard (Lovelace example)](#lovelace-dashboard-example)
- [Security & exposure](#security-exposure)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

<a id="installation"></a>

## Installation 🚀

<a id="via-hacs"></a>

### Via HACS (recommended)

[![Open repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Marlboro62&repository=OBD-Drive&category=integration)

1. Open **HACS → Integrations → ⋮ (menu) → Custom repositories**  
2. Add repo: `https://github.com/Marlboro62/OBD-Drive` as type **Integration**  
3. Search for **OBD‑Drive** and install the integration  
4. **Restart Home Assistant** if prompted

> ℹ️ If you don’t see the integration, refresh HACS (**⋮ → Reload**) and **restart Home Assistant**.

[![Start configuration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=obd_drive)

<a id="manual-installation"></a>

### Manual installation

1. Download the latest release and **copy** the folder `custom_components/obd_drive/`  
   into your HA config: `<config>/custom_components/obd_drive/`  
2. **Restart Home Assistant**

> On Home Assistant OS / Container, `<config>` is your config directory (where `configuration.yaml` lives).

---

<a id="home-assistant-configuration"></a>

## ⚙️ Home Assistant configuration

From the UI: **Settings → Devices & services → Add integration → OBD‑Drive**

Common fields:

- **Email (eml)**: logical identifier to route uploads (required if you have multiple phones)
- **Language**: `en` or `fr` for automatic labels
- **Memory / session (optional)**: session TTL, LRU size, cleanup

> 💡 You can create **multiple integration entries** (one phone/vehicle per entry) or share a single entry and pass `eml`/`profileName` from Torque.

No YAML is required. Everything is configured in the UI.

---

<a id="settings-in-torque-android"></a>

## 📱 Settings in Torque (Android)

In **Torque**: **Settings → Data logging & upload → Web server URL (webhook)**

- **URL**: `https://your-domain-or-ip/api/obd`
- **Method**: `GET` or `POST`
- **Recommended parameters**:

| Parameter | Req. | Description |
|---|:--:|---|
| `session=<session>` | ✅ | Session ID (generated by the integration or set by you) |
| `eml=<email>` | ✅* | Multi‑phone / multi‑entry routing (*required when using multiple entries*) |
| `profileName=<profile>` | ✅* | Separates vehicles/profiles (*strongly recommended*) |
| `id=<vehicleId>` | ⭕ | Vehicle identifier on the integration side |
| `lang=en` / `fr` | ⭕ | Force language on the integration side |
| `lat=<lat>&lon=<lon>&alt=<altitude>&acc=<gpsacc>` | ⭕ | **GPS fallback** when your PIDs don’t include GPS |
| *(do not send `imperial`)* | — | The integration ingests **metric**; HA converts if needed |

<a id="supported-parameters"></a>

### Supported parameters

- `session`, `eml`, `profileName`, `id`, `lang`, `lat`, `lon`, `alt`, `acc`.

<a id="url-examples"></a>

### URL examples

**Minimal (single phone / single entry):**
```
https://ha.example.org/api/obd?session=<session>&profileName=<profile>
```

**Multiple phones (route by email):**
```
https://ha.example.org/api/obd?eml=alex@example.com&session=<session>&profileName=<profile>&id=<vehicleId>
```

**With forced language and GPS fallback:**
```
https://ha.example.org/api/obd?eml=car@family.com&lang=en&session=<session>&profileName=<profile>&lat=<lat>&lon=<lon>&alt=<altitude>&acc=<gpsacc>
```

> Tip: start simple (GET, a few essential PIDs), verify in HA, then add more as needed.

---

<a id="created-entities"></a>

## 🧩 Created entities

- **Sensors (`sensor.*`)** — Standard PIDs: engine RPM, OBD/GPS speed, coolant temperature, intake air temperature, MAP, battery voltage, calculated load, average/instant fuel consumption, etc.  
  Units are set automatically with EN/FR labels.
- **Device tracker (`device_tracker.*`)** — GPS position (lat/lon/alt), accuracy, GPS speed.  
  One *device_tracker* per vehicle/profile.

> Entities are created **dynamically** once the first samples arrive. If a sensor is missing, make sure the corresponding PID is enabled in Torque.

---

<a id="lovelace-dashboard-example"></a>

## 📊 Dashboard (Lovelace example)

Paste this YAML into a dashboard (replace `car_1` with your *entity_id* / device name):

```yaml
title: OBD‑Drive
type: vertical-stack
cards:
  - type: glance
    title: Engine
    entities:
      - entity: sensor.car_1_engine_rpm
        name: RPM
      - entity: sensor.car_1_coolant_temp
        name: Coolant temp
      - entity: sensor.car_1_intake_temp
        name: Intake temp
      - entity: sensor.car_1_battery_voltage
        name: Battery

  - type: gauge
    name: OBD speed
    entity: sensor.car_1_speed_obd
    min: 0
    max: 220

  - type: gauge
    name: GPS speed
    entity: sensor.car_1_speed_gps
    min: 0
    max: 220

  - type: statistics-graph
    entities:
      - sensor.car_1_fuel_consumption_instant
    days_to_show: 1
    stat_types:
      - mean
      - min
      - max
    hide_legend: false

  - type: map
    entities:
      - device_tracker.car_1
    aspect_ratio: 16x9
```

---

<a id="security-exposure"></a>

## 🔐 Security & exposure

- By default, `/api/obd` **honors Home Assistant authentication**. However, the **Torque** app **does not send** `Authorization` headers.  
- **Do not** put a token in the URL. Prefer:  
  - **VPN** (WireGuard, Tailscale) or **LAN‑only** access  
  - Reverse proxy (Nginx, Traefik) with **server‑side auth injection** (advanced)  
- If you expose HTTPS publicly, restrict by IP / GeoIP / rate‑limit, and watch the logs.

> When in doubt, use a VPN: simple, effective, and avoids token leaks.

---

<a id="troubleshooting"></a>

## 🛠️ Troubleshooting

| Issue | Hints |
|---|---|
| No entities created | Check the URL in Torque, make sure PIDs are enabled, and that the phone can reach `https://.../api/obd` (test in a browser). |
| `401/403 Unauthorized` | The endpoint is protected. Use VPN/LAN, or a reverse proxy that handles HA auth server‑side. |
| `404` | Wrong path (must be `/api/obd`) or the integration didn’t load (restart HA). |
| Inconsistent values | Avoid duplicated derived PIDs (e.g., L/100 *and* MPG). Clean up and restart. |
| No GPS | Enable GPS PIDs in Torque or add the **fallback** `lat/lon/alt/acc` in the URL. |
| Slow / battery drain | Don’t tick **all** PIDs. Keep only essentials for smooth refresh. |

**Where to see logs?**  
*Settings → System → Logs* (filter by `obd_drive`). Enable *debug* level if needed.

---

<a id="faq"></a>

## ❓ FAQ

**Can I have multiple vehicles?**  
Yes. Use `profileName=<profile>` and/or `eml=...` to separate devices. Create one entry per vehicle if you prefer.

**GET or POST?**  
Both are supported. `POST` is slightly cleaner for larger payloads.

**Are units metric?**  
Yes. The integration ingests metric. Do not force `imperial` in Torque.

**Do I need to open a port to the Internet?**  
No if you use a **VPN**. If you expose publicly, lock it down **heavily** (HTTPS, IP filtering, rate‑limit).

---

<a id="roadmap"></a>

## 🗺️ Roadmap

- Better detection of custom PIDs
- Aggregation options (trips / refuels)
- Additional translations
- Broader tests & QA

> Open an *Issue* or *Discussion* to propose ideas.

---

<a id="contributing"></a>

## 🤝 Contributing

Contributions are welcome! Submit a **PR** with a clear description or open an **Issue** to discuss a bug/feature. Please follow code style and add tests when possible.

---

<a id="license"></a>

## 📄 License

This project is distributed under a license **to be specified by the repository owner** (MIT recommended).  
Create a `LICENSE` file at the root if not already present.

---

<a id="credits"></a>

## 🙏 Credits

- **Home Assistant** community

---

## 🧾 Changelog

- **2025.9.0** — Initial public release: Torque uploads, auto PIDs, GPS device_tracker, UI config, HACS.
