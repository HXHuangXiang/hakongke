# hakongke

hakongke is a Home Assistant custom integration for Konke devices.

本项目计划维护在 HXHuangXiang/hakongke 仓库，项目地址：https://github.com/HXHuangXiang/hakongke 。当前改造基于 5high/konke 仓库，来源地址：https://github.com/5high/konke 。5high/konke 又基于原作者 jedmeng 的 homeassistant-konke 插件改造，原项目地址：https://github.com/jedmeng/homeassistant-konke 。当前版本迁移到 pykongke，并适配较新的 Home Assistant 集成结构。

底层设备通信依赖 pykongke，项目地址：https://github.com/HXHuangXiang/pykongke 。Home Assistant 会根据 `custom_components/hakongke/manifest.json` 中的 `requirements` 自动安装 `pykongke==3.0.0`。

# Supported Devices

| 设备 | model | 支持实体 | 状态 |
| --- | --- | --- | --- |
| Mini K / Mini Pro | `minik` | switch, IR remote | 已适配 |
| Smart Plug K | `k1` 或 `smart plugin` | switch | 未充分测试 |
| K2 Pro | `k2` 或 `k2 pro` | switch, power sensor, IR remote, RF remote | 未充分测试 |
| 多位插排 | `mul` | switch | 未充分测试 |
| 带 USB 多位插排 | `micmul` | switch, USB switch | 未充分测试 |
| Konke Light | `klight` | light | 未充分测试 |
| Konke Bulb | `kbulb` | light | 未充分测试 |
| K2 灯控 | `k2_light` | light | 未充分测试 |
| cnct intelliPLUG | `minik` | switch, IR remote | 未充分测试 |

# Install

## 方式一：通过 HACS 安装

1. 确认 Home Assistant 已安装 HACS。
2. 打开 HACS，进入右上角菜单，选择自定义存储库。
3. 仓库地址填写 `https://github.com/HXHuangXiang/hakongke`。
4. 类别选择 `Integration`。
5. 添加后在 HACS 中搜索并下载 `hakongke`。
6. 完整重启 Home Assistant。这里需要重启 Home Assistant，不是只重载 YAML 配置。
7. 进入“设置 -> 设备与服务 -> 添加集成”，搜索 `hakongke` 并添加设备。

## 方式二：手动安装

1. 下载或克隆本仓库。
2. 将仓库中的 `custom_components/hakongke` 目录复制到 Home Assistant 配置目录下：

   ```text
   <Home Assistant 配置目录>/custom_components/hakongke
   ```

   常见配置目录：

   - Home Assistant OS / Supervised：`/config`
   - Container / Docker：启动容器时挂载到 `/config` 的宿主机目录
   - Home Assistant Core / venv：启动 Home Assistant 时指定的配置目录

3. 确认复制后存在如下文件：

   ```text
   custom_components/hakongke/manifest.json
   custom_components/hakongke/__init__.py
   custom_components/hakongke/config_flow.py
   ```

4. 完整重启 Home Assistant。这里需要重启 Home Assistant，不是只重载 YAML 配置。
5. 进入“设置 -> 设备与服务 -> 添加集成”，搜索 `hakongke` 并添加设备。

依赖说明：

- Home Assistant 集成目录：`custom_components/hakongke`
- Python 设备通信库：`pykongke==3.0.0`
- `pykongke` 会由 Home Assistant 读取 manifest 后自动安装；通常不需要手动执行 `pip install`

最小可用路径：

1. 通过 HACS 或手动方式安装集成。
2. 完整重启 Home Assistant。
3. 打开“设置 -> 设备与服务 -> 添加集成”。
4. 搜索 `hakongke`。
5. 填写设备 IP、名称、型号，并选择要创建的实体类型。
6. 完成后在“设备与服务”或对应实体列表中查看新实体。

# config

推荐在 Home Assistant 的“设置 -> 设备与服务”里添加 hakongke 集成。

## UI 添加

1. 打开“设置 -> 设备与服务”。
2. 点击“添加集成”。
3. 搜索 `hakongke`。
4. 填写设备 IP、名称、型号，并选择要创建的实体类型。

设备 IP 可在路由器后台、DHCP 租约列表或已绑定设备列表中查看。建议在路由器中给设备固定 IP，避免重启路由器后地址变化。

## YAML 配置

推荐使用 UI 添加集成。YAML 示例仅用于从旧配置迁移。

旧 `konke` 集成与 `hakongke` 不兼容，不能继续使用 `platform: konke`。如果原来配置过旧插件，请改成 `platform: hakongke`，或者删除旧 YAML 后通过 UI 重新添加。

开关示例：

```yaml
switch:
  - platform: hakongke
    name: switch_1
    host: 192.168.0.101
    model: minik
  - platform: hakongke
    name: switch_2
    host: 192.168.0.102
    model: minik
```

灯示例：

```yaml
light:
  - platform: hakongke
    name: light_1
    host: 192.168.0.103
    model: klight
```

遥控示例见下方“遥控使用方法”。

CONFIGURATION VARIABLES:

- name
  (string)(Optional)The display name of the device

- host
  (string)(Required)The host/IP address of the device.

- model
  (string)(Required)The device model, such as minik, k2, mul, micmul, klight, kbulb or k2_light.

- type
  (string)(Optional) Remote type for YAML remote platform. Use `ir` or `rf`.

支持的 model 见上方 Supported Devices 表格。
  
遥控使用方法：

控客遥控不支持直接粘贴遥控编码，需要把实体遥控器的按键学习到设备中。hakongke 会在学习成功后自动创建一个按钮实体，后续直接点击按钮即可发送遥控命令。

## UI 添加遥控实体

1. 进入“设置 -> 设备与服务 -> 添加集成”。
2. 搜索并添加 `hakongke`。
3. 填写设备 IP、名称、型号。
4. 如果设备支持红外，勾选 `Create IR remote entity`；如果设备支持射频，勾选 `Create RF remote entity`。
5. 添加完成后，到实体列表中找到“红外遥控”或“射频遥控”实体，学习按键时要选择这个实体。

Mini K / Mini Pro 一般只支持红外遥控；K2 Pro 可创建红外和射频遥控实体。

## 查看遥控实体 ID

在“设置 -> 设备与服务 -> 实体”里找到“红外遥控”或“射频遥控”实体，点开实体详情，再点击右上角齿轮图标进入实体设置页，可以看到“实体标识符”。这个值就是后面动作调用要填的 `entity_id`。

例如客厅红外实体可能是：

```yaml
remote.kong_ke_ting_hong_wai_ir
```

如果同一个家庭里有多个控客设备，学习和发送命令时必须选择对应房间的 `remote.xxx`，否则命令会学习到另一个设备上。

## 学习一个遥控按键

1. 打开 Home Assistant “开发者工具 -> 动作”。旧版 Home Assistant 里这个入口叫“服务”。
2. 学习红外按键时，在动作里搜索并选择 `hakongke.learn_ir_button`；学习射频按键时选择 `hakongke.learn_rf_button`。
3. `entity_id` 选择前面创建的“红外遥控”或“射频遥控”实体。
4. `name` 填按键名称，例如 `电视电源`、`音量+`、`空调制冷`。
5. `timeout` 可不填，默认 10 秒；如果来不及按遥控器，可以填大一点，例如 `20`。
6. 点击“执行动作”后，立刻对着控客设备按下实体遥控器上的目标按键。
7. 学习成功后会自动创建一个按钮实体，后续直接点击该按钮即可发送遥控命令。

动作 YAML 示例：

```yaml
service: hakongke.learn_ir_button
data:
  entity_id: remote.kong_ke_ting_hong_wai_ir
  name: 电视电源
  timeout: 10
```

注意：`timeout` 是数字，不要带 `s`、`秒` 等单位。

## 使用已学习按键

学习成功后，进入“设置 -> 设备与服务 -> 实体”，可以看到刚才按 `name` 创建出的按钮实体。把按钮加入仪表盘后，日常使用时直接点击按钮即可。

## 删除或修改已学习按键

当前版本暂不提供专门的删除/改名界面。如果需要整理已学习按钮，可以删除 hakongke 集成后重新添加并重新学习；高级用户也可以自行编辑 Home Assistant 配置存储中的按键映射。

## 高级用法

推荐使用 UI 添加。以下配置仅用于从旧 YAML 配置迁移：

```yaml
remote:
  - platform: hakongke
    name: k_ir_remote
    model: minik
    host: 192.168.2.162
    type: ir
```

# 升级与卸载

通过 HACS 安装时，在 HACS 中更新后重启 Home Assistant。

手动安装时，替换 `custom_components/hakongke` 目录后重启 Home Assistant。

卸载时先在“设置 -> 设备与服务”中删除 hakongke 集成条目，再删除 `custom_components/hakongke` 目录并重启 Home Assistant。

# 常见问题

## 搜索不到 hakongke 集成

确认目录路径是 `<Home Assistant 配置目录>/custom_components/hakongke`，并且目录中存在 `manifest.json`。复制完成后必须重启 Home Assistant。

## 查看日志

可以在 Home Assistant 的“设置 -> 系统 -> 日志”中查看错误信息，也可以查看配置目录下的 `home-assistant.log`。

## 设备离线或不可用

确认 Home Assistant 与设备在同一局域网内，设备 IP 正确，路由器没有开启客户端隔离。建议给设备设置固定 IP。
