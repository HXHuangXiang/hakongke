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
控客的遥控器是不支持直接输入遥控编码的，只能通过学习添加遥控器。

- 添加遥控：
进入 service 界面，选择 hakongke.ir_learn 或 hakongke.rf_learn。
```yaml
{
  "entity_id": 【设备的entity_id】,
  "slot": 【命令id，取值范围1000-999999】,
  "timeout": 【超时时长，默认10s】
}
```
注意 slot 参数是 int 格式，周围不能带引号，timeout 参数不带单位，否则命令会不生效。
学习开始、成功或失败会在 Home Assistant 持久通知中显示，也会写入 Home Assistant 日志。

- 使用遥控：
调用remote.send_command这个service，data:
```yaml
{
  "entity_id": 【设备的entity_id】,
  "command": 【遥控类型ir或rf】_【命令id，取值范围1000-999999】,
  "num_repeats": 【发送次数，默认1】,
  "delay_secs": 【两次发射间的延时，默认0.4s】
}
```
使用示例：

configuration.yaml中添加：
```yaml
remote:
  - platform: hakongke
    name: k_ir_remote
    model: minik
    host: 192.168.2.162
    type: ir
```
学习遥控：
```yaml
service: hakongke.ir_learn
data:
  entity_id: remote.k_ir_remote
  slot: 1001
  timeout: 10
```
使用遥控：
```yaml
service: remote.send_command
data:
  entity_id: remote.k_ir_remote
  command: ir_1001
  num_repeats: 1
  delay_secs: 0.4
```

命令格式：

- 红外命令：`ir_<slot>`，例如 `ir_1001`
- 射频命令：`rf_<slot>`，例如 `rf_1001`

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
