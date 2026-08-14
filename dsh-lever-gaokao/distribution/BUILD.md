# 立维志愿 · 交付标准与三平台客户端构建方案

> **交付标准（2026-08 更新）**：立维志愿至少交付**可直接安装/运行的桌面客户端**，
> 支持 **Windows / macOS / Linux** 三平台——即直接基于 DeepSeek Harness（dsh）开发、
> 内置立维志愿插件的**专用版 Agent 工具**。用户下载即用，无需自行安装 Node/dsh/插件/配置路径。

## 一、交付形态

```
立维志愿专用版 Agent（三平台安装包）
├── Windows  → 立维志愿-x64.exe / 立维志愿-arm64.exe（可执行或安装器）
├── macOS    → 立维志愿-aarch64 / 立维志愿-x64（app）
└── Linux    → 立维志愿-x86_64 / 立维志愿-aarch64（AppImage/可执行）

单文件可执行，内置：
├── dsh 运行时（DeepSeek Harness，经 pkg SEA 打包，免 Node）
├── 立维志愿 profile（预装 6 工具插件 + 默认数据路径）
├── 官方数据层（DuckDB + official-sources，可选内置基础省）
└── 首次启动向导（DeepSeek Key 配置 + 峰谷闲时提示）
```

**对比**：旧形态（插件 + npx dsh）要求用户装 Node、起 dsh、手配插件路径；新形态
下载即用，契合"让普通甚至贫寒家庭低门槛获得 AI 帮助"的使命。

## 二、技术基础：dsh 的单文件可执行打包

dsh 官方已用 **`@yao-pkg/pkg`（SEA 模式，Node 22+）** 把 dsh 运行时打包成
单文件可执行（参考 `scripts/build-exe-for-python-sdk.ts`，linux/macos 已实现）：

- **原理**：把 Node 应用 + 依赖闭包（node_modules 全树 assets）打进单个可执行，
  用户无需安装 Node。
- **平台**：pkg 本身支持 win/mac/linux × x64/arm64；dsh 官方脚本目前只配了
  linux/macos，立维志愿需**扩展 Windows** 并锁定版本。
- **立维志愿的复用**：把"dsh + 立维志愿 bundle + 数据层"作为打包入口，用同一套
  pkg SEA 技术产出三平台可执行。

## 三、构建架构

```
dsh-lever-gaokao/
├── distribution/                 # 专用版 Agent 工程（本目录即交付单元）
│   ├── package.json              # 聚合包：dsh + dsh-lever-gaokao + profile
│   ├── src/index.ts              # 入口：以立维 profile 启动 dsh web
│   ├── profile/liwei.cordis.yml  # 立维专用 profile（预装插件 + 默认路径）
│   ├── build-release.ts          # pkg 三平台打包脚本（win/mac/linux）
│   ├── data/                     # 捆绑官方数据（DuckDB + official-sources 子集）
│   └── out/                      # 产物：三平台可执行
└── （复用）lever-gaokao 数据层脚本
```

**入口设计**（`src/index.ts`）：启动 dsh，挂载立维 profile（内置
`cordis.patch.yml` 指向随包数据），首次运行弹 DeepSeek 配置向导。

**profile 设计**（`profile/liwei.cordis.yml`）：预置插件行（dsh-lever-gaokao +
6 工具）+ bridge 路径自动探测（随包 data 目录）+ 官方峰谷定价。

## 四、构建步骤（在具备 Node + 网络的构建机执行）

```sh
# 1. 装依赖（dsh + 插件 + 打包工具）
cd dsh-lever-gaokao/distribution
npm install --registry=https://registry.npmmirror.com

# 2. 构建数据层（官方数据 → data/）
#    用 lever-gaokao/scripts 采集目标省数据（或随包内置基础省样例）

# 3. 三平台打包（win/mac/linux）
npm run build:release

# 4. 产物在 out/
#    立维志愿-win-x64.exe / 立维志愿-mac-aarch64 / 立维志愿-linux-x86_64 ...
```

**CI 建议**：GitHub Actions 三平台矩阵构建（ubuntu/macos/windows 各产一平台），
产物挂 Release 页下载。

## 五、本环境限制与交接

- **本环境无 Rust、npm 拉 dsh 依赖树超时**：无法在此实际产出三平台安装包。
- **已交付**：完整构建方案 + 打包脚本骨架（`distribution/`）+ 现有插件/数据/指南。
- **交接动作**：在任一具备 Node ≥ 22 + 网络的构建机执行 `npm run build:release`，
  或在 GitHub Actions 中跑三平台矩阵（见 `distribution/.github/workflows/release.yml` 骨架）。

## 六、发布流程

1. `npm run build:release` → 三平台产物
2. GitHub Release 挂载产物 + SHA256 校验
3. 发布页/下载页：三平台安装说明 + 首次启动向导截图
4. 用户下载 → 双击运行 → 填 DeepSeek Key → 开始问诊
