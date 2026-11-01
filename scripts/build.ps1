param(
    [string]$ArduinoCli = 'arduino-cli',
    [string]$Port = '',
    [switch]$Install
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$sketch = Join-Path $repoRoot 'firmware\probe_rx'
$buildDir = Join-Path $repoRoot 'build\esp32'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
if ($Install) {
    & $ArduinoCli core update-index --additional-urls 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
    if ($LASTEXITCODE) { throw 'Core index update failed' }
    & $ArduinoCli core install 'esp32:esp32@3.3.12' --additional-urls 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
    if ($LASTEXITCODE) { throw 'ESP32 core installation failed' }
    & $ArduinoCli lib install --no-deps 'Adafruit GFX Library@1.13.0' 'Adafruit ST7735 and ST7789 Library@1.12.0' 'Adafruit BusIO@1.17.4'
    if ($LASTEXITCODE) { throw 'Library installation failed' }
}
& $ArduinoCli compile --fqbn 'esp32:esp32:esp32' --build-path $buildDir $sketch
if ($LASTEXITCODE) { throw 'Build failed' }
if ($Port) {
    & $ArduinoCli upload --fqbn 'esp32:esp32:esp32' --port $Port --input-dir $buildDir $sketch
    if ($LASTEXITCODE) { throw 'Upload failed' }
}
Write-Host "Done: $buildDir"
