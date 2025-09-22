# full.ps1 — seed massif de PIDs vers /api/OBD (compatible Windows PowerShell 5 / PowerShell 7)

# === Config ===
$BaseUrl = "http://10.10.0.100:8123"
$Token   = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI5Y2QwMTY3NGJmYjE0MTY4OWU1Njg2NGU2MzkyNzY2YiIsImlhdCI6MTc1ODQxMDYyMSwiZXhwIjoyMDczNzcwNjIxfQ.EjAzDw6lR4XSMHyGlu5eTm7gBKigVn-IAZBXJ2sc2Ag"
$Email   = "odbdrive@gmail.com"
$Profile = "PS1 Full"
$VehId   = "veh_full_demo"

$Endpoint = "$BaseUrl/api/obd"
$Headers  = @{ "Authorization" = "Bearer $Token" }

# === Position GPS de démo ===
$lat = 48.8566; $lon = 2.3522; $alt = 35; $acc = 8

# === Gros superset de PIDs ===
# (⚠️ pas $pid, réservé !)
$PidCodes = @(
  '04','05','06','07','08','09','0a','0b','0c','0d','0e','0f','10','11',
  '14','15','16','17','18','19','1a','1b','1f','21','22','23',
  '24','25','26','27','28','29','2a','2b','2c','2d','2f','31','32','33',
  '34','35','36','37','38','39','3a','3b','3c','3d','3e','3f',
  '42','43','44','45','46','47','49','4a','4b','52','5a','5b','5c','5e',
  '61','62','63','66','70','73','77','78','79','7a','7b','7c','83','87',
  '9a','a6','b2','b4',
  # Extensions Torque / GPS
  'ff1001','ff1005','ff1006','ff1010',
  'ff1201','ff1202','ff1203','ff1204','ff1205','ff1206','ff1207','ff1208','ff120c',
  'ff1214','ff1215','ff1216','ff1217','ff1218','ff1219','ff121a','ff121b',
  'ff1220','ff1221','ff1222','ff1223','ff1225','ff1226',
  'ff122d','ff122e','ff122f','ff1230',
  'ff1237','ff1238','ff1239','ff123a','ff123b',
  'ff1240','ff1241','ff1242','ff1243','ff1244','ff1245','ff1246','ff1247',
  'ff1249','ff124d','ff124f',
  'ff1257','ff1258','ff125a','ff125c','ff125d','ff125e','ff125f','ff1260','ff1261',
  'ff1263','ff1264','ff1265','ff1266','ff1267','ff1268','ff1269','ff126a','ff126b','ff126d','ff126e',
  'ff1270','ff1271','ff1272','ff1273','ff1275','ff1276','ff1277','ff1278','ff1280',
  'ff1282','ff1283','ff1284','ff1286','ff1287','ff1288','ff128a',
  'ff1296','ff1297','ff1298','ff129a','ff129b','ff129c','ff129d','ff129e',
  'ff12a1','ff12a4','ff12a5','ff12a6','ff12ab',
  'ff12b0','ff12b1','ff12b2','ff12b3','ff12b4','ff12b5','ff12b6',
  'ff5201','ff5202','ff5203'
)

# === Générateur de valeurs plausibles ===
function Get-PidValue([string]$c) {
  switch ($c.ToLower()) {
    '0c' { 850 }        # RPM
    '0d' { 0 }          # Speed OBD
    '05' { 90 }         # Coolant °C
    '0f' { 28 }         # IAT °C
    '10' { 9.8 }        # MAF g/s
    '11' { 18 }         # Throttle %
    '33' { 101 }        # Baro kPa
    '42' { 13.9 }       # ECU voltage V
    'ff1001' { 0 }      # GPS speed km/h
    'ff1005' { $lon }   # GPS lon °
    'ff1006' { $lat }   # GPS lat °
    'ff1010' { $alt }   # GPS alt m
    'ff1239' { $acc }   # GPS accuracy m
    'ff1238' { 12.2 }   # OBD adapter voltage V
    '77' { 35 }         # CACT °C
    '5c' { 90 }         # Oil temp °C
    '70' { 120 }        # Boost cmd A kPa
    '73' { 110 }        # Exhaust press B1 kPa
    '7a' { 0.8 }        # DPF ΔP B1 kPa
    '7b' { 0.9 }        # DPF ΔP B2 kPa
    '7c' { 280 }        # DPF inlet temp °C
    '83' { 150 }        # NOx pre SCR ppm
    '9a' { 350 }        # HV battery V
    'a6' { 123456 }     # Odometer km
    'b4' { 85 }         # ATF temp °C (m2)
    default {
      if ($c -match '^(1f|31|ff12(6[6-8]|[de]))$') { [math]::Round((Get-Random -Min 0 -Max 600),2) }          # secondes
      elseif ($c -match '^(3c|3d|3e|3f|77|78|79|7c|b4|ff12(8[2-8]|b[0-3]))$') { [math]::Round((Get-Random -Min 20 -Max 900),1) } # °C
      elseif ($c -match '^(0a|0b|22|23|32|33|66|70|73|87|ff12(a[15-6]|ab)|ff12b[0-3])$') { [math]::Round((Get-Random -Min 10 -Max 300),1) } # kPa
      elseif ($c -match '^(24|25|26|27|28|29|2a|2b|42|9a|ff121[4-9]|ff121a|ff121b)$') { [math]::Round((Get-Random -Min 0.0 -Max 14.9),2) }  # V
      elseif ($c -match '^(34|35|36|37|38|39|3a|3b)$') { [math]::Round((Get-Random -Min -5 -Max 5),2) }                              # mA
      elseif ($c -match '^(61|62|63)$') { [math]::Round((Get-Random -Min 0 -Max 100),1) }                                           # %
      else { [math]::Round((Get-Random -Min 0 -Max 100),2) }
    }
  }
}

# === Corps JSON ===
$session = (Get-Date).ToString("yyyyMMddHHmmss")
$body = @{
  session     = $session
  email       = $Email
  profileName = $Profile
  id          = $VehId
  # GPS directs (activent le tracker sans PID)
  lat      = $lat
  lon      = $lon
  alt      = $alt
  accuracy = $acc
}

foreach ($code in $PidCodes) {
  $body["k$code"] = Get-PidValue $code
}

# Aperçu & envoi
$kcount = ($body.Keys | Where-Object { $_ -like 'k*' }).Count
Write-Host "POST $Endpoint"
Write-Host "Capteurs envoyés: $kcount"

try {
  $json = $body | ConvertTo-Json -Depth 7 -Compress
  $resp = Invoke-RestMethod -Uri $Endpoint -Method POST -Headers $Headers -ContentType 'application/json; charset=utf-8' -Body $json -ErrorAction Stop
  Write-Host "Réponse HA: $resp" -ForegroundColor Green
} catch {
  Write-Host "Erreur POST: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
}
