# 立维志愿桌面端（Tauri）

立维志愿（lever-gaokao）的桌面客户端壳：引导 DeepSeek 一键配置 → 启动本地 DeepSeek Harness Web UI → 打开应用窗口。

**架构**：本应用是"薄壳"——Tauri 负责配置引导 + 启动 `npx @deepseek-ai/dsh web`（本地 127.0.0.1:3080）+ 打开窗口；AI 志愿功能由 dsh-lever-gaokao 插件提供。零服务器成本，BYOK（用户自配 API Key）。

## 目录结构

```
desktop/
├── index.html             # 启动页：DeepSeek 一键配置引导 + 闲时省钱提示
├── src/main.js            # 前端逻辑（保存配置 → 调 Rust 启动 dsh → 跳转）
├── package.json           # @tauri-apps/cli + vite
└── src-tauri/
    ├── tauri.conf.json    # Tauri 2 配置（产品名"立维志愿"）
    ├── Cargo.toml         # tauri 2 + serde
    ├── build.rs
    ├── capabilities/default.json
    └── src/main.rs        # start_dsh command：后台启动 npx @deepseek-ai/dsh web
```

## 本机构建步骤

前置：Node.js ≥ 20 + Rust 工具链（https://rustup.rs）。

```sh
# 1. 进入桌面端目录
cd dsh-lever-gaokao/desktop

# 2. 安装前端依赖（国内可用 npmmirror）
npm install --registry=https://registry.npmmirror.com

# 3. 开发模式（调试）
npm run tauri dev

# 4. 打包（生成安装包）
npm run tauri build
```

首次运行：Tauri 窗口打开"启动配置"页 → 填 DeepSeek API Key → 点"保存配置并启动" →
Rust 后台启动 `npx @deepseek-ai/dsh web`（首次会自动拉取 dsh）→ 就绪后跳转 Web UI。

## 与 dsh-lever-gaokao 插件的配合

- 插件 6 个工具（立维问诊/查询/校验/成本估算/闲时调度）由 dsh 加载 `cordis.patch.yml` 挂载。
- DeepSeek 配置（base_url/api_key/模型）在 dsh Web UI 的 provider 设置页完成；
  本启动页只做引导与保存，实际调用以 dsh 配置为准。
- 闲时引导：`gaokao_offpeak` 工具输出下一个闲时窗口，配合 `schedule_create` 自动调度重任务。

## 注意

- **本骨架在无 Rust 环境下开发，未在本机编译验证**——按 Tauri 2 标准编写，
  请在本机（Rust 环境）执行 `npm run tauri dev` 验证后调整。
- 图标：`src-tauri/icons/` 需提供 `icon.png`（建议 512x512），用 `npm run tauri icon` 生成全套。
- 若用户已全局安装 dsh，可把 main.rs 的 `npx @deepseek-ai/dsh` 改为 `dsh` 以加快启动。
