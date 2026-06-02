# hakongke

Home Assistant 控客设备自定义集成。

## 快速安装

### HACS

1. HACS -> 自定义存储库。
2. 仓库地址填写 `https://github.com/HXHuangXiang/hakongke`。
3. 类别选择 `Integration`。
4. 添加后下载 `hakongke`。
5. 完整重启 Home Assistant，不是只重载 YAML 配置。
6. 设置 -> 设备与服务 -> 添加集成 -> 搜索 `hakongke`。

### 手动安装

复制本仓库的 `custom_components/hakongke` 到 Home Assistant 配置目录：

```text
<Home Assistant 配置目录>/custom_components/hakongke
```

常见配置目录：

- Home Assistant OS / Supervised：`/config`
- Container / Docker：启动容器时挂载到 `/config` 的宿主机目录
- Home Assistant Core / venv：启动 Home Assistant 时指定的配置目录

复制后完整重启 Home Assistant，再到“设置 -> 设备与服务”添加 `hakongke`。

## 最小可用路径

安装集成 -> 完整重启 Home Assistant -> 设置 -> 设备与服务 -> 添加集成 -> 搜索 `hakongke` -> 填写设备 IP、名称、型号并选择实体类型。

## 从旧 konke 迁移

旧 `konke` 集成与 `hakongke` 不兼容，不能继续使用 `platform: konke`。建议删除旧配置后通过 UI 重新添加；如继续使用 YAML，需要改为 `platform: hakongke`。

## 日志

可以在 Home Assistant 的“设置 -> 系统 -> 日志”中查看错误信息，也可以查看配置目录下的 `home-assistant.log`。

更多配置、YAML 示例和遥控学习说明请查看 README.md。
