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
}
'''


def main():
    source = (ROOT / 'src/main_gravitymon.cpp').read_text()
    startup = source.split('  runtimeMillis = millis();\n', 1)[1].split(
        '#if defined(ESP8266)', 1)[0]
    with tempfile.TemporaryDirectory(prefix='led-startup-') as directory:
        cpp, binary = Path(directory) / 'check.cpp', Path(directory) / 'check'
        cpp.write_text('#include <initializer_list>\n' + STUBS +
                       '\nvoid startup() {\n' + startup + '\n}\n' + CHECKS)
        for platform in ['ESP32C3', 'ESP8266', 'ESP32S3']:
            subprocess.run(['c++', '-std=c++14', '-D' + platform, str(cpp),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print('PASS: C3 reset lights immediately, timer wake stays dark; other boards unchanged')


if __name__ == '__main__':
    main()
