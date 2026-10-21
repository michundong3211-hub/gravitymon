#ifndef SRC_STORAGE_SLEEP_HPP_
#define SRC_STORAGE_SLEEP_HPP_

#include <stdint.h>

// Retained across timed deep sleep, but reset when the device is manually reset.
struct StorageSleepState {
  uint32_t magic = 0;
  uint32_t elapsedSeconds = 0;
  uint32_t pendingSeconds = 0;

  void resume(bool timerWake) {
    if (!timerWake || magic != 0x53544F52 || pendingSeconds > 3600 ||
        elapsedSeconds > 365UL * 86400) {
      *this = {};
    } else {
      elapsedSeconds += pendingSeconds;
      pendingSeconds = 0;
    }
    magic = 0x53544F52;
  }

  bool shouldHibernate(int days) const {
    return days > 0 && elapsedSeconds >= static_cast<uint32_t>(days) * 86400;
  }
};

#endif  // SRC_STORAGE_SLEEP_HPP_
