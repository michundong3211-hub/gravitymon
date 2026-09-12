#!/usr/bin/env python3
"""Run actual gyro setup/detection code with fake hardware: python3 test/scripts/gyro_recovery.py.

Only the hardware-facing types are stubbed. Compile both platform paths and the
ESP32 RTC path without Arduino or a connected board; temporary files self-clean.
"""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
STUBS = r'''
#include <cassert>
#include <cstdint>
#include <memory>
#define F(x) x
#define CR ""
#define PIN_SDA 0
#define PIN_SCL 1
#define GYRO_RTC_DATA_AVAILABLE 105
struct { template<class... T> void notice(T...) {} template<class... T> void warning(T...) {}
  template<class... T> void error(T...) {} } Log;
struct { void begin(int,int) {} void setClock(int) {} void setTimeOut(int) {} } Wire;
int wireClock = 400000, wireTimeout = 200;
enum GyroType { GYRO_NONE, GYRO_MPU6050, GYRO_ICM42670P };
enum GyroMode { GYRO_UNCONFIGURED, GYRO_RUN, GYRO_CONTINUOUS };
struct { uint8_t Address; uint8_t IsDataAvailable; } myRtcGyroData = {};
#if defined(ESP8266)
constexpr GyroType expected = GYRO_MPU6050;
#else
constexpr GyroType expected = GYRO_ICM42670P;
#endif
struct Config {
  GyroType type = expected;
  int saves = 0;
  GyroType getGyroType() { return type; }
  void setGyroType(GyroType t) { type = t; }
  void saveFile() { ++saves; }
};
int probes = 0, initCalls = 0, failedProbes = 0, failedInits = 0;
struct Driver {
  virtual ~Driver() = default;
  bool setup(GyroMode, bool) { return ++initCalls > failedInits; }
};
template<GyroType type> struct Chip : Driver {
  Chip(uint8_t, Config*) {}
  static bool isDeviceDetected(uint8_t& addr) {
    assert(type == expected);  // Never probe the other platform's chip.
    addr = 0x68;
    return ++probes > failedProbes;
  }
};
using MPU6050Gyro = Chip<GYRO_MPU6050>;
using ICM42670pGyro = Chip<GYRO_ICM42670P>;
struct GyroSensor {
  Config* _gyroConfig;
  std::unique_ptr<Driver> _impl;
  GyroMode _currentMode = GYRO_UNCONFIGURED;
  bool _retried = false;
  explicit GyroSensor(Config* c) : _gyroConfig(c) {}
  GyroType detectGyro();
  void setupImpl(uint8_t&);
  bool setup(GyroMode, bool);
};
void reset(int detectionFailures = 0, int initFailures = 0) {
  probes = initCalls = 0;
  failedProbes = detectionFailures;
  failedInits = initFailures;
  myRtcGyroData = {};
}
'''

CHECKS = r'''
int main() {
  { // Normal startup and an already configured sensor need no recovery.
    reset(); Config c; GyroSensor g(&c);
    assert(g.setup(GYRO_RUN, false));
    assert(g.setup(GYRO_RUN, false));
    assert(initCalls == 1 && probes == 1 && c.saves == 0);
  }
  { // Detection fails once, then recovers during the same setup call.
    reset(1); Config c; GyroSensor g(&c);
    assert(g.setup(GYRO_RUN, false));
    assert(initCalls == 1 && probes == 3 && c.saves == 0);
  }
  { // Detection succeeds but driver initialization fails once.
    reset(0, 1); Config c; GyroSensor g(&c);
    assert(g.setup(GYRO_RUN, false));
    assert(initCalls == 2 && probes == 3);
    assert(g._currentMode == GYRO_RUN);
    // A later failure cannot start another recovery cycle in this boot.
    failedInits = 100;
    assert(!g.setup(GYRO_CONTINUOUS, true));
    assert(initCalls == 3 && probes == 3 && !g._impl);
  }
  { // Persistent initialization failure stays disconnected, including RTC.
    reset(0, 100); Config c; GyroSensor g(&c);
    assert(!g.setup(GYRO_RUN, false));
    assert(initCalls == 2 && probes == 3);
    assert(!g._impl && g._currentMode == GYRO_UNCONFIGURED);
    assert(myRtcGyroData.IsDataAvailable == 0);
    assert(!g.setup(GYRO_RUN, false));
    assert(initCalls == 3 && probes == 4);
  }
  { // Persistent detection failure persists NONE once and stops re-probing.
    reset(100); Config c; GyroSensor g(&c);
    assert(!g.setup(GYRO_RUN, false));
    assert(!g.setup(GYRO_RUN, false));
    assert(probes == 2 && initCalls == 0 && c.saves == 1);
    assert(c.type == GYRO_NONE && !g._impl);
  }
  { // Missing cached type is repaired and persisted after detection.
    reset(); Config c; c.type = GYRO_NONE; GyroSensor g(&c);
    assert(g.setup(GYRO_RUN, false));
    assert(c.type == expected && c.saves == 1);
  }
#if defined(ESP32) && defined(ENABLE_RTCMEM)
  { // Preserve the existing fast path for deep-sleep resume.
    reset(); Config c; GyroSensor g(&c);
    myRtcGyroData = {0x68, GYRO_RTC_DATA_AVAILABLE};
    assert(g.setup(GYRO_RUN, false));
    assert(initCalls == 0 && probes == 0);
    // Forced reconfiguration failure must invalidate the RTC shortcut.
    failedInits = 1;
    assert(g.setup(GYRO_CONTINUOUS, true));
    assert(initCalls == 2 && probes == 2);
    assert(g._currentMode == GYRO_CONTINUOUS);
  }
#endif
}
'''


def main():
    source = (ROOT / 'src/gyro.cpp').read_text()
    # Compile the production methods verbatim, not a Python model of them.
    methods = source[source.index('GyroType GyroSensor::detectGyro()'):
                     source.index('bool GyroSensor::read()')]
    with tempfile.TemporaryDirectory(prefix='gyro-recovery-') as directory:
        cpp = Path(directory) / 'check.cpp'
        binary = Path(directory) / 'check'
        cpp.write_text(STUBS + methods + CHECKS)
        for flags in (['ESP8266'], ['ESP32'], ['ESP32', 'ENABLE_RTCMEM']):
            subprocess.run(['c++', '-std=c++14', *('-D' + f for f in flags),
                            str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            print('PASS:', ', '.join(flags))


if __name__ == '__main__':
    main()
