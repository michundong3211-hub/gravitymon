#!/usr/bin/env python3
"""Check retained storage time and configuration bounds without a device."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CHECKS = r'''
#include <cassert>
#include "storage_sleep.hpp"
struct Config {
  int _storageHibernateDays = 30;
  bool _saveNeeded = false;
  SETTER
};
int main() {
  Config config;
  assert(config._storageHibernateDays == 30);
  config.setStorageHibernateDays(-1);
  assert(config._storageHibernateDays == 30 && !config._saveNeeded);
  config.setStorageHibernateDays(366);
  assert(config._storageHibernateDays == 30 && !config._saveNeeded);
  config.setStorageHibernateDays(0);
  assert(config._storageHibernateDays == 0 && config._saveNeeded);
  config.setStorageHibernateDays(365);
  assert(config._storageHibernateDays == 365);

  StorageSleepState state;
  state.resume(false);
  assert(!state.shouldHibernate(30));
  for (int hour = 1; hour <= 720; ++hour) {
    state.pendingSeconds = 3600;
    // Simulate reboot with only RTC memory surviving.
    StorageSleepState rebooted = state;
    rebooted.resume(true);
    state = rebooted;
    assert(state.elapsedSeconds == static_cast<uint32_t>(hour * 3600));
    assert(state.shouldHibernate(30) == (hour == 720));
    assert(!state.shouldHibernate(0));
  }
  state.resume(true); // Do not count the same interval twice.
  assert(state.elapsedSeconds == 30UL * 86400);
  state.resume(false); // Magnetic/manual reset clears the countdown.
  assert(state.elapsedSeconds == 0);
  state.pendingSeconds = 3600;
  state.resume(true);
  assert(state.elapsedSeconds == 3600);
  state = {}; // Leaving storage clears the state before measurement sleep.
  state.resume(true);
  assert(state.elapsedSeconds == 0);
  state.pendingSeconds = 0xFFFFFFFF; // Reject corrupt RTC state.
  state.resume(true);
  assert(state.elapsedSeconds == 0 && state.pendingSeconds == 0);
  state.elapsedSeconds = 366UL * 86400;
  state.resume(true);
  assert(state.elapsedSeconds == 0);
}
'''


ENTRY_STUBS = r'''
#include <cassert>
#include <cstdint>
#include "storage_sleep.hpp"
#define F(x) x
#define CR ""
#define PIN_CHARGING 3
#define INPUT_PULLDOWN 1
#define ESP_GPIO_WAKEUP_GPIO_HIGH 2
#define ESP_EXT1_WAKEUP_ANY_HIGH 3
#define ESP_SLEEP_WAKEUP_ALL 4
struct { template<class... T> void notice(T...) {} } Log;
struct { int getStorageHibernateDays() { return 1; }
  bool isPinChargingMode() { return true; } } myConfig;
struct { void enterSleep(bool storage) { assert(storage); } } myGyro;
struct { void stopDoubleReset() {} } myWifi;
struct { void end() {} } LittleFS;
enum class RunMode { storageMode };
RunMode runMode = RunMode::storageMode;
StorageSleepState storageSleepState;
void saveStorageSleepState() {}
void delay(int) {}
void ledOff() {}
void pinMode(int, int) {}
bool gpioWake = false;
void esp_deep_sleep_enable_gpio_wakeup(uint64_t pin, int level) {
  assert(pin == (1ULL << PIN_CHARGING) && level == ESP_GPIO_WAKEUP_GPIO_HIGH);
  gpioWake = true;
}
void esp_sleep_enable_ext1_wakeup(uint64_t pin, int level) {
  assert(pin == (1ULL << PIN_CHARGING) && level == ESP_EXT1_WAKEUP_ANY_HIGH);
  gpioWake = true;
}
void esp_sleep_disable_wakeup_source(int) { gpioWake = false; }
struct Sleep { uint64_t interval; };
void esp_deep_sleep_start() { throw Sleep{0}; }
struct { void deepSleep(uint64_t interval) { throw Sleep{interval}; } } ESP;
'''
ENTRY_CHECKS = r'''
int main() {
  storageSleepState.resume(false);
  for (int hour = 0; hour <= 24; ++hour) {
    try { enterStorage(); assert(false); }
    catch (Sleep sleep) {
      if (hour < 24) {
        assert(sleep.interval == 3600000000ULL);
#if defined(ESP32C3) || defined(ESP32S2) || defined(ESP32S3)
        assert(gpioWake);
#endif
        storageSleepState.resume(true);
      } else {
        assert(sleep.interval == 0 && !gpioWake);
      }
    }
  }
}
'''


def check_storage_entry():
    source = (ROOT / 'src/main_gravitymon.cpp').read_text()
    entry = source[source.index('  // If we are in storage mode, just go back to sleep'):
                   source.index('void runGpioHardwareTests() {')]
    with tempfile.TemporaryDirectory(prefix='storage-entry-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text(ENTRY_STUBS + '\nvoid enterStorage() {\n' + entry + ENTRY_CHECKS)
        for platform in ['ESP8266', 'ESP32C3', 'ESP32S2', 'ESP32S3', 'ESP32']:
            subprocess.run(['c++', '-std=c++14', '-D' + platform, '-I', str(ROOT / 'src'),
                            str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print('PASS: storage entry retains hourly timer with charging enabled and hibernates after 24 wakes')


def main():
    config = (ROOT / 'src/config_gravitymon.hpp').read_text()
    setter = config[config.index('  void setStorageHibernateDays('):
                    config.index('  bool isStorageSleep()')]
    with tempfile.TemporaryDirectory(prefix='storage-hibernate-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text(CHECKS.replace('SETTER', setter))
        subprocess.run(['c++', '-std=c++14', '-I', str(ROOT / 'src'),
                        str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    check_storage_entry()
    print('PASS: 30-day boundary, timer resumes, reset, disabled mode and RTC corruption')


if __name__ == '__main__':
    main()
