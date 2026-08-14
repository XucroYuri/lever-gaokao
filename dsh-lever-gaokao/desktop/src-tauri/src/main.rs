//! 立维志愿桌面端 Rust 入口。
//!
//! 职责：
//! 1. 提供 `start_dsh` command：后台启动 DeepSeek Harness Web UI（npx @deepseek-ai/dsh web）
//! 2. 前端（启动页）完成 DeepSeek 一键配置后，调用本 command 并跳转到 dsh Web UI
//!
//! 说明：dsh 通过 `npx @deepseek-ai/dsh web` 运行在本地（默认 127.0.0.1:3080），
//! 零服务器成本；本应用只负责"引导配置 + 启动 + 打开窗口"。

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Stdio};

/// 启动 dsh Web UI（后台进程，窗口隐藏）。
/// 返回 "started"；失败返回错误信息（如未安装 Node/npx）。
#[tauri::command]
fn start_dsh() -> Result<String, String> {
    let mut cmd = Command::new("npx");
    cmd.args(["@deepseek-ai/dsh", "web"]);

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW：不弹出黑色控制台窗口
        cmd.creation_flags(0x0800_0000);
    }

    cmd.stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| {
            format!(
                "启动 DeepSeek Harness 失败：{}。请确认已安装 Node.js（>=20）并可运行 npx。",
                e
            )
        })?;

    Ok("started".into())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_dsh])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
