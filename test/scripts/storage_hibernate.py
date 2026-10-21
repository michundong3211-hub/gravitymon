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
    print('PASS: 30-day boundary, timer resumes, reset, disabled mode and RTC corruption')


if __name__ == '__main__':
    main()
