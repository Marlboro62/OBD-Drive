# Test_sensor.ps1 — Send simulated OBD sensors to an API

> PowerShell script to **simulate and publish** a large set of OBD‑II sensors + GPS position to an HTTP endpoint (`/api/obd`). Works with **Windows PowerShell 5.1** and **PowerShell 7+**.

---

## ✨ Overview

The script:
- builds a **JSON payload** with metadata (email, profile, vehicle ID), a **demo GPS position**, and a **very large superset of OBD‑II PIDs** (realistic pseudo‑random values);
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

Where this is handled in the code:
- The **coordinator** explicitly **excludes** `gpslat` and `gpslon` when deciding which *sensors* to create (“if key = lat/lon → don’t create a sensor”).  
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

The script prints the target URL, the **number of sensors** sent (e.g., `190`), then the **API response**.  
On failure, it prints a detailed error message.

---

## 📸 Step‑by‑step (screenshots)

> Chronological order of the screens to configure the **OBD Drive** integration and send sensors with `Test_sensor.ps1`.
> (Images hosted in `assets/screens/` on the repo.)

1. **Open the configuration form**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/1.png?raw=1" alt="OBD Drive — empty form" width="720" /></p>

2. **Enter email + options**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/2.png?raw=1" alt="OBD Drive — filled form" width="720" /></p>

3. **Creation confirmed**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/3.png?raw=1" alt="OBD Drive — configuration created" width="1200" /></p>

4. **Prepare to run the PowerShell script**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/4.png?raw=1" alt="PowerShell window ready" width="1200" /></p>

5. **Run the script — POST & OK response (189 visible entities)**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/5.png?raw=1" alt="Script run — HA OK response" width="1400" /></p>

6. **Device view: PS1 Full (panels & categories)**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/6.png?raw=1" alt="PS1 Full device — overview" width="1200" /></p>

7. **Sensors list — page 1**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/7.png?raw=1" alt="Sensors list — page 1" width="1200" /></p>

8. **Sensors list — page 2**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/8.png?raw=1" alt="Sensors list — page 2" width="1200" /></p>

9. **Sensors list — page 3**  
   <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/9.png?raw=1" alt="Sensors list — page 3" width="1200" /></p>

10. **Sensors list — page 4 (bottom + Diagnostic card)**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/10.png?raw=1" alt="Sensors list — page 4 (bottom + Diagnostic card)" width="1400" /></p>

11. **Sensors list — page 5**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/11.png?raw=1" alt="Sensors list — page 5" width="1200" /></p>

12. **Sensors list — page 6**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/12.png?raw=1" alt="Sensors list — page 6" width="1200" /></p>

13. **Sensors list — page 7**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/13.png?raw=1" alt="Sensors list — page 7" width="1200" /></p>

14. **Sensors list — page 8**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/14.png?raw=1" alt="Sensors list — page 8" width="1200" /></p>

15. **Sensors list — page 9 (end)**  
    <p align="center"><img src="https://github.com/Marlboro62/OBD-Drive/blob/main/assets/screens/15.png?raw=1" alt="Sensors list — page 9 (end)" width="1400" /></p>

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
