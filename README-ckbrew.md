
ckbrew 版本


修改点：

1. `platformio.ini`中，新增`env:gravity-32c3_ckbrew`配置

    - `build-flags`中删除`-D ESPFWK_DISABLE_LED=1`，此为禁用 LED 标识
    - `build-flags`中增加`-D ESP32_C3_DEVKITM_1`
    - `board`，改为`esp32-c3-devkitm-1`，参考 https://github.com/platformio/platform-espressif32/issues/1218 和 https://docs.platformio.org/en/latest/boards/espressif32/esp32-c3-devkitm-1.html

2. `main_gravitymon.hpp`中，新增`ESP32_C3_DEVKITM_1`配置。

    ```
    #elif defined(ESP32_C3_DEVKITM_1)

    // Hardware config for ESP32-c3-mini, iSpindel hardware
    // ------------------------------------------------------
    #define PIN_SDA 4
    #define PIN_SCL 5
    #define PIN_DS A0
    #define PIN_VOLT A3
    #define PIN_CFG1 A5
    #define PIN_CFG2 A4
    #define CFG_FILENAMEBIN "firmware32c3mini_ckbrew.bin"
    ```