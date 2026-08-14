; 立维志愿 Windows 安装器（NSIS）
; 用法：makensis installer.nsi（在 CI 中于 dsh-lever-gaokao/distribution/installer 目录执行）
; 产物：立维志愿-Setup-x64.exe（安装 pkg 单文件可执行 + 桌面/开始菜单快捷方式）

!include "MUI2.nsh"
!include "x64.nsh"

!define APP_NAME "立维志愿"
!define APP_EXE "立维志愿-win-x64.exe"
!define VERSION "0.1.0"
!define INSTALL_DIR "$PROGRAMFILES64\${APP_NAME}"

Name "${APP_NAME}"
OutFile "..\out\立维志愿-Setup-x64.exe"
InstallDir "${INSTALL_DIR}"
RequestExecutionLevel admin
Unicode True
BrandingText "立维志愿 · lever-gaokao"

; 页面
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 语言
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "安装立维志愿"
  SetOutPath "${INSTALL_DIR}"
  ; pkg 单文件可执行 + 首次启动向导
  File "..\out\${APP_EXE}"
  File "..\guide.html"
  ; 数据层目录（随包数据，由 profile 引用）
  SetOutPath "${INSTALL_DIR}\data"
  File /nonfatal "..\data\gaokao.duckdb"

  ; 桌面快捷方式
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_EXE}" "" "${INSTALL_DIR}\${APP_EXE}" 0
  ; 开始菜单
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "${INSTALL_DIR}\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\卸载 ${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"

  ; 卸载信息
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "Publisher" "lever-gaokao"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\卸载 ${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\guide.html"
  Delete "$INSTDIR\data\gaokao.duckdb"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
