# Test_sensor.ps1 — Send simulated OBD sensors to an API

> PowerShell script to **simulate and publish** a large set of OBD‑II sensors + GPS position to an HTTP endpoint (`/api/obd`). Works with **Windows PowerShell 5.1** and **PowerShell 7+**.

---

## ✨ Overview

The script:
- builds a **JSON payload** containing metadata (email, profile, vehicle ID), a **demo GPS position**, and a **very large superset of OBD‑II PIDs** (realistic pseudo‑random values);  
- sends it as `POST` to `http(s)://<BaseUrl>/api/obd` with a **Bearer token**.

Typical console output:
```text
POST http://IP:8123/api/obd
Sensors sent: <n> (190); 189 will be visible because lat & lon are merged
HA response: ok
```

### 🧭 Home Assistant behavior (GPS)
In the integration, we **do not create** two sensors `gpslat` and `gpslon`. Instead, we create **a single `device_tracker`** for the vehicle, which stores **latitude / longitude / accuracy** as **attributes**.

**Net result:**

- **190** measurements sent by the script  
- **– 2** (`lat` & `lon` filtered out as sensors)  
- **+ 1** `device_tracker` (GPS)  
- **= 189 visible entities** (**188 sensors** + **1 device_tracker**)

Where this is handled in code:
- The **coordinator** explicitly **excludes** `gpslat` and `gpslon` when deciding which *sensors* to create (“if key = lat/lon → don’t make a sensor”).  
- The **coordinator** **creates the `device_tracker`** as soon as it sees `lat` and `lon` in the received values for the vehicle (exposed via the `OBDDeviceTracker` class).  

By contrast, **altitude (`gpsalt`)** and **accuracy (`gpsaccuracy`)** remain normal *sensors* and are counted among the **188 sensors**.

> ⚠️ Never commit a real access token to the repo. Replace example values before publishing.

---

## 🧰 Prerequisites

- Windows PowerShell 5.1 **or** PowerShell 7+ (`pwsh`)
- Network access to the target URL (`$BaseUrl`)
- Email (can be dummy), e.g. `odbdrive@gmail.com`
- A valid **access token** (Bearer) for the target API

---

## 🗂️ Installation

```bash
git clone <your-repo>.git
cd <your-repo>
# Script is named Test_sensor.ps1 and lives at the repo root (or adjust paths)
```

---

## ⚙️ Configuration

Open `Test_sensor.ps1` and edit the **Config** section:

- `$BaseUrl`: e.g. `http://IP:8123`
- `$Token`: your token **(do not commit!)**
- `$Email`: source email (metadata)
- `$Profile`: profile name (metadata)
- `$VehId`: vehicle identifier (metadata)
- Demo GPS (`lat`, `lon`, `alt`, `acc`) if needed

### 🔐 Best practices (optional)
- Prefer an **environment variable** over hard‑coding the token:
  ```powershell
  # In your profile or CI/CD
  $Env:HA_TOKEN = "<your-token>"
  ```
  And in the script, replace the `$Token` assignment with:
  ```powershell
  if ($Env:HA_TOKEN) { $Token = $Env:HA_TOKEN }
  ```
- Add proper entries to `.gitignore`/`.gitattributes` if you store secrets locally.

---

## ▶️ Run

From PowerShell:

```powershell
# PowerShell 7+
pwsh ./Test_sensor.ps1

# or Windows PowerShell 5.1
powershell -ExecutionPolicy Bypass -File .\Test_sensor.ps1
```

The script prints the target URL, the **number of sensors** sent (e.g. `190`), then the **API response**.  
On failure, it prints a detailed error message.

---

## 📸 Screenshots

> Images are stored under `assets/screens/`.  
> **Update the file names below** to match your repo if needed.

### Quick preview (grid)

<p align="center">
  <img src="assets/screens/overview.png" alt="Home Assistant overview" width="420" />
  <img src="assets/screens/entities.png" alt="OBD entities list" width="420" />
</p>
<p align="center">
  <img src="assets/screens/device-tracker.png" alt="Device tracker (map)" width="420" />
  <img src="assets/screens/history.png" alt="Sensor history" width="420" />
</p>

### Detailed sections

#### Home Assistant dashboard
![Dashboard](assets/screens/overview.png)

#### Entities list (188 sensors + 1 device_tracker)
![Entities](assets/screens/entities.png)

#### Device tracker (GPS)
![Device tracker](assets/screens/device-tracker.png)

#### Sensor history (e.g., engine RPM)
![History](assets/screens/history.png)

---

## 🔧 Customization

- **PIDs / Sensors:** the script ships with a **superset** of PIDs. You can:
  - remove / add entries;
  - tweak **random ranges** (kPa, °C, V, A, %…);
  - set constant values for deterministic tests.
- **GPS:** adjust `lat`, `lon`, `alt`, `acc` to simulate a specific place.
- **Profile / Vehicle:** change `$Profile` and `$VehId` to distinguish sources.

> Tip: replay the script in a loop (e.g., once per second for 60 s):
> ```powershell
> 1..60 | ForEach-Object { ./Test_sensor.ps1; Start-Sleep -Seconds 1 }
> ```

---

## 🚑 Troubleshooting

| Problem | Likely cause | How to fix |
|---|---|---|
| `401 Unauthorized` | Invalid or missing token | Check `Authorization: Bearer <token>`, mint a new token |
| `404 Not Found` | Wrong endpoint | Confirm `$BaseUrl` and path `/api/obd` |
| `Connection refused / timeout` | No network access | Try `Invoke-WebRequest $BaseUrl`, firewall/proxy |
| `Unsupported protocol` | HTTP/HTTPS mismatch | Adjust the URL (`http` vs `https`) |
| Invalid JSON on server | Unexpected payload | Inspect JSON before POST: `ConvertTo-Json -Depth 7` |

---

## 🔒 Security

- **Never** publish a real token in Git.
- If a token leaks: **revoke** it and **issue** a new one.
- Limit scope and lifetime of secrets whenever possible.

---

## ✅ Pre‑push checklist

- [ ] `$BaseUrl`, `$Email`, `$Profile`, `$VehId` updated
- [ ] **No token** hard‑coded in code/commits
- [ ] Local run OK (POST and expected response)
- [ ] `README.md` and `LICENSE` ready

---

*Happy testing & smooth integration!* 🚗📡
