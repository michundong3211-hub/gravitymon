#!/usr/bin/env python3
"""Check actual startup LED code for external reset and timed wake-up."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
STUBS = r'''
#include <cassert>
enum LedColor { OFF, WHITE, GREEN };
constexpr int ESP_SLEEP_WAKEUP_TIMER = 4;
int wakeCause = 0, calls = 0;
LedColor color = OFF;
int esp_sleep_get_wakeup_cause() { return wakeCause; }
void ledOn(LedColor value) { ++calls; color = value; }
void ledOff() { ledOn(OFF); }
enum class RunMode { measurementMode, configurationMode, wifiSetupMode };
RunMode runMode = RunMode::measurementMode;
struct Config {
  bool ble = false, format = false, wifi = false;
  bool getUseBle() const { return ble; }
  bool isBleActive() const { return format; }
  bool isWifiPushActive() const { return wifi; }
} myConfig;
'''
CHECKS = r'''
int main() {
  for (int cause : {0, ESP_SLEEP_WAKEUP_TIMER}) {
    wakeCause = cause;
    calls = 0;
    color = OFF;
    startup();
#if defined(ESP32C3)
    assert(calls == (cause == ESP_SLEEP_WAKEUP_TIMER ? 0 : 1));
    assert(color == (cause == ESP_SLEEP_WAKEUP_TIMER ? OFF : WHITE));
#else
    assert(calls == 0 && color == OFF);
#endif
  }
  for (bool ble : {false, true}) {
    for (bool format : {false, true}) {
      for (bool wifi : {false, true}) {
        myConfig = {ble, format, wifi};
        measurement();
#if defined(ESP32C3) && defined(ENABLE_BLE)
        assert(color == (ble && format && !wifi ? OFF : GREEN));
#else
        assert(color == GREEN);
#endif
      }
    }
  }
}
'''


def main():
    source = (ROOT / 'src/main_gravitymon.cpp').read_text()
    startup = source.split('  runtimeMillis = millis();\n', 1)[1].split(
        '#if defined(ESP8266)', 1)[0]
    measurement = source.split('// Do this setup for configuration mode', 1)[1].split(
        '    default:\n', 1)[1].split('      break;', 1)[0]
    with tempfile.TemporaryDirectory(prefix='led-startup-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text('#include <initializer_list>\n' + STUBS +
                       '\nvoid startup() {\n' + startup + '\n}\n' +
                       '\nvoid measurement() {\n' + measurement + '\n}\n' + CHECKS)
        for flags in [['ESP32C3', 'ENABLE_BLE'], ['ESP32C3'], ['ESP8266'], ['ESP32S3']]:
            subprocess.run(['c++', '-std=c++14', *['-D' + flag for flag in flags], str(cpp),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print('PASS: C3 reset feedback, dark BLE-only cycles, WIFI indication and other boards')


if __name__ == '__main__':
    main()
