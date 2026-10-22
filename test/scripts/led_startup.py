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
bool everOn = false;
LedColor color = OFF;
int esp_sleep_get_wakeup_cause() { return wakeCause; }
void ledOn(LedColor value) { ++calls; color = value; everOn |= value != OFF; }
void ledOff() { ledOn(OFF); }
enum class RunMode { measurementMode, configurationMode, wifiSetupMode };
RunMode runMode = RunMode::measurementMode;
struct Config {
  bool ble = false, format = false, wifi = false;
  bool direct = false;
  bool targets[5] = {true, false, false, false, false};
  bool getUseBle() const { return ble; }
  bool isBleActive() const { return format; }
  bool isWifiPushActive() const { return wifi; }
  bool isWifiDirect() const { return direct; }
  bool hasTargetHttpPost() const { return targets[0]; }
  bool hasTargetHttpPost2() const { return targets[1]; }
  bool hasTargetHttpGet() const { return targets[2]; }
  bool hasTargetInfluxDb2() const { return targets[3]; }
  bool hasTargetMqtt() const { return targets[4]; }
} myConfig;
using BrewingConfig = Config;
int intervalCounters[5] = {};
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
  myConfig = {true, true, true};
  for (bool &target : myConfig.targets) target = false;
  PushIntervalTracker tracker(&myConfig);
  tracker.load();
  assert(!tracker.hasPendingTargets());
  for (int target = 0; target < 5; ++target) {
    myConfig.targets[target] = true;
    for (int remaining : {2, 1, 0}) {
      intervalCounters[target] = remaining;
      tracker.load();
      assert(tracker.hasPendingTargets() == (remaining == 0));
      wakeCause = ESP_SLEEP_WAKEUP_TIMER;
      everOn = false;
      startup();
      measurement();
#if defined(ESP32C3) && defined(ENABLE_BLE)
      assert(color == (remaining == 0 ? GREEN : OFF));
      assert(everOn == (remaining == 0));
#else
      assert(color == GREEN);
#endif
      // Checking the LED must not advance the upload schedule.
      assert(intervalCounters[target] == remaining);
    }
    myConfig.targets[target] = false;
  }
  myConfig.direct = true;
  measurement();
  assert(color == GREEN); // WiFi Direct sends on every measurement cycle.
}
'''


def main():
    source = (ROOT / 'src/main_gravitymon.cpp').read_text()
    startup = source.split('  runtimeMillis = millis();\n', 1)[1].split(
        '#if defined(ESP8266)', 1)[0]
    measurement = source.split('// Do this setup for configuration mode', 1)[1].split(
        '    default:\n', 1)[1].split('      break;', 1)[0]
    header = (ROOT / 'src/pushtarget.hpp').read_text()
    tracker = 'class PushIntervalTracker {' + header.split(
        'class PushIntervalTracker {', 1)[1].split('\n};', 1)[0] + '\n};\n'
    tracker += '''void PushIntervalTracker::load() {
      for (int i = 0; i < 5; ++i) _counters[i] = intervalCounters[i];
    }\n'''
    with tempfile.TemporaryDirectory(prefix='led-startup-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text('#include <initializer_list>\n' + STUBS + tracker +
                       '\nvoid startup() {\n' + startup + '\n}\n' +
                       '\nvoid measurement() {\n' + measurement + '\n}\n' + CHECKS)
        for flags in [['ESP32C3', 'ENABLE_BLE'], ['ESP32C3'], ['ESP8266'], ['ESP32S3']]:
            subprocess.run(['c++', '-std=c++14', *['-D' + flag for flag in flags], str(cpp),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print('PASS: C3 reset feedback, dark BLE-only and skipped HTTP cycles, five targets, WiFi Direct and other boards')


if __name__ == '__main__':
    main()
