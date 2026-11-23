# 很多问题的小明同学 · ARM 飞牛应用源

给 ARM 版飞牛 fnOS（网心云 OEC / OES 等）用的第三方应用源，同时兼容 **Moo** 与 **FnDepot V2** 两个客户端。

## 添加源

在 Moo 或 FnDepot 应用中心「添加源 / 添加仓库」里填：

```
https://github.com/gulugulupao/FnDepot
```

添加后即可看到下面全部应用，后续发版会随索引自动更新。

## 收录应用

| 应用 | 说明 | 版本 | 项目主页 |
|---|---|---|---|
| 系统盘清理助手 | 系统盘体检 + 逐项清理，给板载 eMMC 腾空间 | 1.6.3 | [fncleankernel](https://github.com/gulugulupao/fncleankernel) |
| 一键超频 | A73 大核四档频率管理，自愈回滚 | 1.2.8 | [onekey-overclock](https://github.com/gulugulupao/onekey-overclock) |
| 综合磁盘检测 | eMMC/NVMe/SATA/USB 硬盘 SMART 健康评估 | 0.1.9 | [fnsmartdisk](https://github.com/gulugulupao/fnsmartdisk) |
| 极测-性能跑分 | CPU/GPU/内存/磁盘/NPU 本机离线跑分 | 1.0.0 | [chipbeat](https://github.com/gulugulupao/chipbeat) |
| ClamSentinel 哨兵杀毒 | 免 Docker 原生轻量杀毒，智能睡眠省内存 | 1.5 | [clamsentinel](https://github.com/gulugulupao/clamsentinel) |

> 未收录 `sd15-one-gpu`：它是 x86 核显 + 16GB 内存的 Docker/镜像分发，不是 fpk 应用，见其仓库 README 手动部署。

## 索引文件

- `fnpack.json` —— FnDepot 外部应用源 V2（`schema_version: "2"`）
- `moo.json` —— Moo 应用源协议（`schema_version: "moo"`）
- `icons/` —— 各应用图标（随源分发，不依赖外部图床）

两个索引的 `apps` 键 = 各 FPK 内 `manifest` 的 `appname`，下载链接指向各项目 GitHub Release，带 sha256 校验。

## 更新机制（全自动，无需手动维护）

本仓库的 GitHub Actions（`.github/workflows/sync-index.yml`）**每 30 分钟自动轮询**各应用仓库的 Release，发现新版本即更新 `moo.json` / `fnpack.json` 并提交。**各应用发完 Release 不用手动改索引**，最多等一个轮询周期。

- 想立即更新：到本仓库 Actions 页手动运行「自动同步应用索引」（workflow_dispatch）。
- 自动同步脚本 `tools/sync_index.py` 直接读 GitHub Release 自带的 sha256 与 size，无需下载安装包；只保留最近 2 版，同版本换包会拒绝（防校验和失配）。

新增应用时才需要手动：改 `tools/sync_index.py` 顶部 `APPS` 映射、放图标到 `icons/`、在两个索引 `apps` 里加节点。详见 `tools/更新索引说明.md`。

校验命令（可选）：

```bash
python3 tools/sync_index.py --check   # 退出0=已最新，退出1=需要更新
```

## 免责声明

本源为社区第三方项目，与飞牛官方无关。第三方应用涉及系统底层权限，使用前请备份数据。所有应用均由 [`很多问题的小明同学`](https://github.com/gulugulupao) 开发维护，MIT 协议（含附加保护条款）。
