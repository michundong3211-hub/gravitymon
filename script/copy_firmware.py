Import("env")
import os
import shutil
from datetime import datetime

# 打包输出: bin/<年.月.日.时分>/<firmware|partitions><芯片>-<版本>-<年.月.日.时分>.bin
CHIP_NAMES = {
    "gravity-8266": "8266",
    "gravity-32c3_mini": "32c3",
    "gravity-32c3_mini_85": "32c3",
    "gravity-32c3_pico": "32c3pico",
    "gravity-32c3_zero": "32c3zero",
    "gravity-32c3_supermini": "32c3supermini",
    "gravity-32s2_mini": "32s2",
    "gravity-32s3_mini": "32s3",
}

def get_build_flag_value(flag_name):
    build_flags = env.ParseFlags(env['BUILD_FLAGS'])
    flags_with_value_list = [build_flag for build_flag in build_flags.get('CPPDEFINES') if type(build_flag) == list]
    defines = {k: v for (k, v) in flags_with_value_list}
    return defines.get(flag_name)

def after_build(source, target, env):
    print("Executing custom step ")
    name = env.get("PIOENV")
    dir = env.GetLaunchDir()

    if name.startswith("gravity-unit"):
        print("Skipping copy of unit test build")
        return

    chip = CHIP_NAMES.get(name)
    if chip is None:
        board = env.BoardConfig().get_brief_data()['id']
        print("Custom board detected: " + board)
        chip = "custom-" + board.lower()

    ver = (get_build_flag_value("CFG_APPVER") or '"dev"').strip('"')
    # 可选变体后缀 (如 13dBm / 8.5dBm), 由 build flag CFG_VARIANT 提供
    variant = get_build_flag_value("CFG_VARIANT")
    variant = "-" + variant.strip('"') if variant else ""
    # 同一次打包(just build-c3)共用一个时间戳目录; 单独 pio build 时取当前时间
    stamp = os.environ.get("PKG_STAMP") or datetime.now().strftime("%Y.%m.%d.%H%M")
    out_dir = os.path.join(dir, "bin", stamp)
    os.makedirs(out_dir, exist_ok=True)

    build_dir = os.path.join(dir, ".pio", "build", name)
    for src_name, prefix in (("firmware.bin", "firmware"), ("partitions.bin", "partitions")):
        src = os.path.join(build_dir, src_name)
        if not os.path.isfile(src):
            print("Skip missing: " + src)
            continue
        # firmware 文件名带变体; partitions 两版相同故不带
        suffix = variant if src_name == "firmware.bin" else ""
        dst = os.path.join(out_dir, prefix + chip + "-" + ver + suffix + "-" + stamp + ".bin")
        print("Copy file : " + src + " -> " + dst)
        shutil.copyfile(src, dst)

print("Adding custom build step (copy firmware): ")
env.AddPostAction("buildprog", after_build)
