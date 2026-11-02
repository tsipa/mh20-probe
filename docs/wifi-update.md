# Wi-Fi and firmware updates

By default, the receiver starts a password-protected Wi-Fi network named **MH-Probe-Service**. It can also join a 2.4 GHz router, or run both modes together. The password is generated on the first boot, saved on the receiver and printed to the serial console at 115200 baud. It stays the same after a restart.

Connect to this network and open **http://192.168.4.1/**. Log in as **admin** with the service password printed in the serial console. The page shows tuning frequency, RSSI and counters, and provides network settings, firmware upload and restart buttons. It works without a router or internet access.

## Connecting to a router

Open **Wi-Fi settings**, choose a mode and enter the router SSID and password:

| Mode | Behavior |
|---|---|
| Access point (`ap`) | Creates MH-Probe-Service |
| Connect to router (`sta`) | Joins the saved network; starts a recovery access point if disconnected for 15 seconds |
| Router + access point (`apsta`) | Joins the router and keeps MH-Probe-Service available |

Press **Save settings**, then **Restart receiver**. Settings are stored on the ESP32 and survive power loss. Saving settings disables probing until restart, so flash writes cannot interrupt a probing move.

In client mode, use the IP address assigned by the router. It is printed in the serial console and can also be found in the router's device list. **OTA works through this address**, using the same page and service login. Router, access-point and web login passwords are separate. The web login initially uses the generated access-point password. Change it with `wifi web-password <value>` over UART, then restart. This does not change the access-point password, which must meet WPA2 length requirements.

A blank password field keeps the saved password. To change it, tick **Replace saved password** and enter the new value. To use an open network, tick the same box and leave the field blank. SSIDs are limited to 32 bytes; passwords can be empty, 8–63 bytes, or a 64-digit hex key. The saved router password is never sent back to the browser.

The display shows **WiFi AP**, **WiFi CLIENT CONNECTED**, **WiFi CLIENT NOT CONNECTED**, or **WiFi OFF**. In combined or recovery mode it shows **AP+CLIENT** and the client connection state. No IP address is shown on the display.

## UART setup and recovery

Use the USB serial port at **115200 baud**, with LF or CRLF line endings. Commands do not echo the router password. For example:

```text
wifi mode sta
wifi ssid Workshop Network
wifi password replace-with-your-password
wifi save
wifi reboot
```

Everything after `wifi ssid ` or `wifi password ` is the value, including spaces; do not add quotes. Changes are staged until `wifi save` and take effect after restart.

| Command | Action |
|---|---|
| `wifi help` | List commands |
| `wifi status` | Show staged mode, SSID and whether a password is set |
| `wifi mode ap`, `wifi mode sta`, `wifi mode apsta` | Set the startup mode |
| `wifi ssid <name>` | Set the router SSID |
| `wifi password <value>` | Set the router password |
| `wifi password` | Clear the router password for an open network |
| `wifi save` | Validate and save settings; disable probing until restart |
| `wifi reset` | Save access-point defaults; disable probing until restart |
| `wifi access` | Print the web login and access-point password locally over UART |
| `wifi web-password <value>` | Save a separate web login password (1–64 bytes); restart to apply |
| `wifi reboot` | Restart and apply saved settings |

UART remains available after probe detection. It can save new settings but cannot turn Wi-Fi back on without a restart. If the router credentials are wrong, wait for the recovery access point or use `wifi reset` followed by `wifi reboot`. Resetting network settings keeps the existing service password.

## When the probe is detected

The first confirmed probe signal shuts down the web server, access point and client connection. Automatic reconnection and recovery are disabled too. Detection uses the decoder's two-frame check; noise or one matching pulse group will not shut the network down.

Wi-Fi stays off even if the probe disappears. Restart the receiver with the probe switched off to use the page again. The output GPIOs remain disabled until the receiver has found the probe and shut Wi-Fi down.

## First installation

Flash this version over USB first. It includes `firmware/probe_rx/partitions.csv`, a layout for **4 MB flash** with two application slots of 1920 KiB each. The build script uses this file automatically. A board flashed with a different layout needs the USB installation before it can accept these OTA images.

Keep the probe switched off while connecting to the service network. Read the Wi-Fi password in the serial console and save it.

## Updating through the browser

1. Build the sketch with `scripts/build.ps1`.
2. Restart the receiver with the probe switched off.
3. Open the receiver's IP address on your router, or connect to **MH-Probe-Service** and open **http://192.168.4.1/**. Log in as **admin** with the service password.
4. Select **build/esp32/probe_rx.ino.bin** and press **Upload firmware**.
5. Keep power connected until the page reports success and the receiver restarts.

Upload the application image only. Bootloader, partition and merged images are not suitable for this page.

Starting an upload puts the receiver into maintenance mode: READY is low and the probe loop is open. Probe processing is paused so an incoming signal cannot shut Wi-Fi down halfway through the upload. A failed or interrupted update leaves probing disabled; retry the upload or restart the receiver to leave maintenance mode. A completed update restarts automatically.

The page requires the service login in every network mode. Settings, uploads and restart also require a token supplied by the page. Use a trusted local network; the web server uses HTTP. Images are checked by the ESP32 updater but are not cryptographically signed.

## Testing

Automated host tests cover startup, the probe-detection latch, recovery timeout, loss of signal, update lockout, UART commands, credential validation and display labels. Router connection, fallback access point, Wi-Fi shutdown timing, browser settings and uploads still need testing on the receiver. See [testing status](validation.md).
