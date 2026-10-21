#!/usr/bin/env python3
"""Exercise production ICM power-down and empty-FIFO recovery with fake I2C."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
STUBS = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <vector>
using std::min;
#define F(x) x
#define CR ""
struct { template<class... T> void notice(T...) {} template<class... T> void verbose(T...) {}
  template<class... T> void error(T...) {} } Log;
enum GyroMode { GYRO_UNCONFIGURED, GYRO_RUN, GYRO_CONTINUOUS, GYRO_SLEEP };
struct RawGyroData { int16_t ax, ay, az, gx, gy, gz, temp; };
struct RawGyroDataL { int32_t ax, ay, az, gx, gy, gz, temp; };
struct GyroResultData { bool valid; float angle, temp; };
struct Config { int getGyroReadCount() { return 1; } } config;
uint32_t clockMs = 100;
uint32_t millis() { return clockMs; }
void delay(uint32_t ms) { clockMs += ms; }
int power = 15, fifoCount = 0, snapshots = 0, fifoReads = 0;
int16_t rawTemp = 0;
bool writeFails = false, readFails = false, readMismatch = false;
bool moving = false, setupFails = false, restoreFails = false;
bool neverReady = false, sampleFails = false, fifoCountFails = false;
std::vector<GyroMode> setups;
struct I2Cdev {
  static bool writeByte(uint8_t, uint8_t reg, uint8_t value) {
    assert(reg == 0x1F && value == 0);
    if (writeFails) return false;
    power = value;
    return true;
  }
  static int readByte(uint8_t, uint8_t reg, uint8_t* data) {
    if (reg == 0x1F) {
      if (readFails) return 0;
      *data = readMismatch ? 15 : power;
    } else {
      assert(reg == 0x39);
      *data = neverReady ? 0 : 1;
    }
    return 1;
  }
  static int readBytes(uint8_t, uint8_t reg, uint8_t count, uint8_t* data) {
    std::fill(data, data + count, 0);
    if (reg == 0x3D) {
      if (fifoCountFails) return 0;
      data[1] = fifoCount;
    } else {
      assert(reg == 0x09 && count == 14);
      if (sampleFails) return 0;
      ++snapshots;
      data[0] = static_cast<uint16_t>(rawTemp) >> 8;
      data[1] = rawTemp & 0xFF;
      data[2] = 0x40;
    }
    return count;
  }
};
class ICM42670pGyro {
  uint8_t _addr = 0x68, _buffer[16] = {};
  uint32_t _configStart = 0;
  Config* _gyroConfig = &config;
  bool setup(GyroMode mode, bool force) {
    assert(force || mode == GYRO_RUN);
    setups.push_back(mode);
    return mode == GYRO_CONTINUOUS ? !setupFails : !restoreFails;
  }
  uint8_t ReadFIFOPackets(const uint16_t &count, RawGyroDataL &data) {
    ++fifoReads;
    data.ax = 16384;
    return count;
  }
  bool isSensorMoving(int16_t, int16_t, int16_t) { return moving; }
  float calculateAngle(float ax, float, float) { return ax; }
 public:
  GyroMode enterSleep(GyroMode mode, bool storage);
  GyroResultData readSensor(GyroMode mode);
};
void reset() {
  power = 15;
  fifoCount = snapshots = fifoReads = 0;
  rawTemp = 0;
  writeFails = readFails = readMismatch = moving = setupFails = restoreFails = false;
  neverReady = sampleFails = fifoCountFails = false;
  setups.clear();
}
'''
CHECKS = r'''
int main() {
  ICM42670pGyro gyro;
  reset();
  assert(gyro.enterSleep(GYRO_RUN, false) == GYRO_RUN);
  assert(power == 15 && setups.empty()); // Measurement sleep keeps sampling.
  assert(gyro.enterSleep(GYRO_CONTINUOUS, false) == GYRO_RUN);
  assert(setups == std::vector<GyroMode>{GYRO_RUN});
  for (auto mode : {GYRO_RUN, GYRO_CONTINUOUS}) {
    reset();
    assert(gyro.enterSleep(mode, true) == GYRO_SLEEP && power == 0);
    assert(setups.empty());
  }
  reset(); writeFails = true;
  assert(gyro.enterSleep(GYRO_RUN, true) == GYRO_UNCONFIGURED);
  reset(); readFails = true;
  assert(gyro.enterSleep(GYRO_RUN, true) == GYRO_UNCONFIGURED);
  reset(); readMismatch = true;
  assert(gyro.enterSleep(GYRO_RUN, true) == GYRO_UNCONFIGURED);
  reset(); // A fresh sample is available immediately after storage, even without FIFO history.
  auto result = gyro.readSensor(GYRO_RUN);
  assert(result.valid && result.angle == 1 && snapshots == 1 && fifoReads == 0);
  assert((setups == std::vector<GyroMode>{GYRO_CONTINUOUS, GYRO_RUN}));
  // Register temperatures use the ICM scale, including negative raw values.
  for (int16_t value : {-1280, 0, 1280}) {
    reset(); rawTemp = value;
    auto sample = gyro.readSensor(GYRO_RUN);
    assert(sample.valid && fabs(sample.temp - (value / 128.0f + 25)) < 0.001f);
  }
  reset(); fifoCount = 1; // Normal measurement consumes FIFO without reconfiguration.
  assert(gyro.readSensor(GYRO_RUN).valid);
  assert(fifoReads == 1 && snapshots == 0 && setups.empty());
  reset(); setupFails = true;
  assert(!gyro.readSensor(GYRO_RUN).valid && snapshots == 0);
  reset(); restoreFails = true;
  assert(!gyro.readSensor(GYRO_RUN).valid && snapshots == 1);
  reset(); fifoCountFails = true;
  assert(!gyro.readSensor(GYRO_RUN).valid && setups.empty());
  reset(); sampleFails = true;
  assert(!gyro.readSensor(GYRO_RUN).valid);
  reset(); neverReady = true;
  auto started = millis();
  assert(!gyro.readSensor(GYRO_RUN).valid);
  assert(millis() - started >= 1000 && millis() - started < 1200);
  assert((setups == std::vector<GyroMode>{GYRO_CONTINUOUS, GYRO_RUN}));
  reset(); moving = true;
  assert(!gyro.readSensor(GYRO_RUN).valid);
  assert((setups == std::vector<GyroMode>{GYRO_CONTINUOUS, GYRO_RUN}));
}
'''


def main():
    source = (ROOT / 'src/ICM42670P_gyro.cpp').read_text()
    macros = source[source.index('#define INT16_FROM_BUFFER'):
                    source.index('bool ICM42670pGyro::isDeviceDetected')]
    sleep = source[source.index('GyroMode ICM42670pGyro::enterSleep('):
                   source.index('uint8_t ICM42670pGyro::ReadFIFOPackets')]
    read = source[source.index('GyroResultData ICM42670pGyro::readSensor('):
                  source.index('bool ICM42670pGyro::calibrateSensor()')]
    with tempfile.TemporaryDirectory(prefix='storage-sleep-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text(STUBS + macros + sleep + read + CHECKS)
        subprocess.run(['c++', '-std=c++14', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('PASS: ICM storage power-down, errors, fresh sample and measurement FIFO')


if __name__ == '__main__':
    main()
