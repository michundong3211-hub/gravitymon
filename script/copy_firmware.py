Import("env")
import os
import shutil

# 打包输出: bin/ 固定目录 + 固定文件名 (flash.py / version.json / OTA 依赖该路径)
# 8.5dBm 变体的 firmware 文件名追加 -<变体> 后缀; partitions 两变体内容相同, 共用固定名
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

    # 可选变体后缀 (如 8.5dBm), 由 build flag CFG_VARIANT 提供
    variant = get_build_flag_value("CFG_VARIANT")
    variant = "-" + variant.strip('"') if variant else ""

    out_dir = os.path.join(dir, "bin")
    os.makedirs(out_dir, exist_ok=True)

    build_dir = os.path.join(dir, ".pio", "build", name)
    for src_name, prefix in (("firmware.bin", "firmware"), ("partitions.bin", "partitions")):
        src = os.path.join(build_dir, src_name)
        if not os.path.isfile(src):
            print("Skip missing: " + src)
            continue
        # firmware 文件名带变体; partitions 两版相同故不带
        suffix = variant if src_name == "firmware.bin" else ""
        dst = os.path.join(out_dir, prefix + chip + suffix + ".bin")
        print("Copy file : " + src + " -> " + dst)
        shutil.copyfile(src, dst)

print("Adding custom build step (copy firmware): ")
env.AddPostAction("buildprog", after_build)
