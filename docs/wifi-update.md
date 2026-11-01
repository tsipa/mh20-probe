# Wi-Fi and firmware updates

At startup, the receiver creates a password-protected Wi-Fi network named **MH-Probe-Service**. The password is generated on the first boot, saved on the receiver and printed to the serial console at 115200 baud. It stays the same after a restart.

Connect to this network and open **http://192.168.4.1/**. The page shows the tuning frequency, RSSI and counters, and provides firmware upload and restart buttons. It works without a router or internet access.

## When the probe is detected

The first confirmed probe signal shuts down the web server and Wi-Fi. Detection uses the decoder's two-frame check; noise or one matching pulse group will not shut the network down.

Wi-Fi stays off even if the probe disappears. Restart the receiver with the probe switched off to use the page again. The output GPIOs remain disabled until the receiver has found the probe and shut Wi-Fi down.

## First installation

Flash this version over USB first. It includes `firmware/probe_rx/partitions.csv`, a layout for **4 MB flash** with two application slots of 1920 KiB each. The build script uses this file automatically. A board flashed with a different layout needs the USB installation before it can accept these OTA images.

Keep the probe switched off while connecting to the service network. Read the Wi-Fi password in the serial console and save it.

## Updating through the browser

1. Build the sketch with `scripts/build.ps1`.
2. Restart the receiver with the probe switched off.
3. Connect to **MH-Probe-Service** and open **http://192.168.4.1/**.
4. Select **build/esp32/probe_rx.ino.bin** and press **Upload firmware**.
5. Keep power connected until the page reports success and the receiver restarts.

Upload the application image only. Bootloader, partition and merged images are not suitable for this page.

Starting an upload puts the receiver into maintenance mode: READY is low and the probe loop is open. Probe processing is paused so an incoming signal cannot shut Wi-Fi down halfway through the upload. A failed or interrupted update leaves probing disabled; retry the upload or restart the receiver to leave maintenance mode. A completed update restarts automatically.

The upload and restart buttons require a token supplied by the receiver's page. Firmware updates are intended for local access through the password-protected service network. Images are checked by the ESP32 updater but are not cryptographically signed.

## Testing

Automated tests cover startup, the probe-detection latch, loss of signal, update lockout, retries and reset. The firmware build was checked with ESP32 Arduino core 3.3.4 and the Adafruit library versions listed in [build instructions](build.md). The documented core 3.3.12 was not available in this environment. Wi-Fi shutdown timing, browser uploads and interrupted updates still need testing on the physical receiver.
