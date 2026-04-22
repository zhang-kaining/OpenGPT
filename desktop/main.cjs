/**
 * 开发机试用：拉起 embedding 网关 + 主 API（含静态前端），再用 Electron 打开本地页面。
 * 需在仓库根目录：frontend 已 build、backend 已有 .venv 与 .env。
 */
const { app, BrowserWindow, dialog, nativeImage, ipcMain, nativeTheme, session, shell } = require('electron')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const net = require('net')
const { shouldOpenInExternalBrowser } = require('./url-policy.cjs')

// 与 start.sh、Vite 代理默认一致；可用环境变量 OpenGPT_API_PORT / MYGPT_API_PORT 覆盖
const DEFAULT_API_PORT = '18789'

// 系统代理若未排除 localhost，fetch(127.0.0.1) 会失败 → 误判超时
if (!/\b127\.0\.0\.1\b/.test(process.env.NO_PROXY || '')) {
  process.env.NO_PROXY = ['127.0.0.1', 'localhost', '::1', process.env.NO_PROXY].filter(Boolean).join(',')
}

/** @type {import('child_process').ChildProcess[]} */
const children = []
const devRootDir = path.resolve(__dirname, '..')
const ORPHAN_API_PORTS = new Set([18789, 18000, 18001, 18002, 18010, 18080, 19000])
const ORPHAN_GATEWAY_PORTS = new Set([8101, 18101, 18102, 18103, 19101])
const ORPHAN_UVICORN_MARKERS = ['uvicorn app.main:app', 'uvicorn embedding_gateway.main:app']

/** @type {import('electron').BrowserWindow | null} */
let mainWin = null
let isQuitting = false
let isShuttingDownChildren = false

function setupMainWindowClose(win) {
  win.on('close', (e) => {
    if (process.platform === 'darwin' && !isQuitting) {
      e.preventDefault()
      win.hide()
    }
  })
}

function runtimeRootDir() {
  return app.isPackaged ? process.resourcesPath : devRootDir
}

function parseOrphanPort(command) {
  const match = String(command || '').match(/--port\s+(\d+)/)
  return match ? Number(match[1]) : null
}

function shouldCleanupOrphanProcess(command) {
  const cmd = String(command || '')
  if (!ORPHAN_UVICORN_MARKERS.some((marker) => cmd.includes(marker))) return false
  const port = parseOrphanPort(cmd)
  if (!port) return false
  return ORPHAN_API_PORTS.has(port) || ORPHAN_GATEWAY_PORTS.has(port)
}

function cleanupStaleBackendProcesses() {
  if (process.platform === 'win32') return
  let stdout = ''
  try {
    const res = spawnSync('ps', ['-axo', 'pid=,ppid=,command='], { encoding: 'utf8' })
    if (res.status !== 0) {
      console.warn('OpenGPT: ps failed while checking stale backend processes')
      return
    }
    stdout = res.stdout || ''
  } catch (e) {
    console.warn('OpenGPT: unable to inspect stale backend processes:', e)
    return
  }

  const stalePids = []
  for (const rawLine of stdout.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const match = line.match(/^(\d+)\s+(\d+)\s+(.*)$/)
    if (!match) continue
    const pid = Number(match[1])
    const ppid = Number(match[2])
    const command = match[3]
    if (!pid || pid === process.pid || ppid !== 1) continue
    if (shouldCleanupOrphanProcess(command)) {
      stalePids.push(pid)
    }
  }

  for (const pid of stalePids) {
    try {
      process.kill(pid, 'SIGTERM')
      console.warn(`OpenGPT: cleaned stale backend pid=${pid}`)
    } catch (e) {
      console.warn(`OpenGPT: failed to clean stale backend pid=${pid}:`, e)
    }
  }
}

function themeFilePath() {
  return path.join(app.getPath('userData'), 'theme-mode.txt')
}

function readSavedTheme() {
  try {
    const mode = fs.readFileSync(themeFilePath(), 'utf-8').trim()
    if (mode === 'light' || mode === 'dark' || mode === 'system') return mode
  } catch (_) {}
  return 'dark'
}

function resolveThemeBg() {
  const mode = readSavedTheme()
  const isDark = mode === 'dark' || (mode === 'system' && nativeTheme.shouldUseDarkColors)
  return isDark ? '#212121' : '#ffffff'
}

/** Dock / 窗口图标：开发用 build/app-icon-1024.png，安装包用 Resources/icon.icns */
function appIconPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'icon.icns')
  }
  return path.join(__dirname, 'build', 'app-icon-1024.png')
}

function userDataRootDir() {
  return app.getPath('userData')
}

function runtimeDataRoot() {
  return path.join(userDataRootDir(), 'data')
}

function venvPython(backendRoot) {
  if (process.platform === 'win32') {
    return path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
  }
  return path.join(backendRoot, '.venv', 'bin', 'python')
}

function runtimeVenvRoot(dataRoot) {
  return path.join(dataRoot, 'runtime-venv')
}

function runtimeVenvPython(dataRoot) {
  const root = runtimeVenvRoot(dataRoot)
  if (process.platform === 'win32') {
    return path.join(root, 'Scripts', 'python.exe')
  }
  return path.join(root, 'bin', 'python')
}

function createLineWriter(filePath) {
  const stream = fs.createWriteStream(filePath, { flags: 'a' })
  return (line) => {
    stream.write(`${line}\n`)
  }
}

function runCommand(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, {
      cwd: opts.cwd,
      env: { ...process.env, ...(opts.env || {}) },
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const write = opts.writeLine || (() => {})
    p.stdout.on('data', (buf) => write(String(buf).trimEnd()))
    p.stderr.on('data', (buf) => write(String(buf).trimEnd()))
    p.on('error', reject)
    p.on('close', (code) => {
      if (code === 0) return resolve()
      reject(new Error(`${cmd} ${args.join(' ')} exited with code ${code}`))
    })
  })
}

async function findSystemPython() {
  const candidates = process.platform === 'win32'
    ? ['python', 'py']
    : await collectPythonCandidates()
  const uniqueCandidates = [...new Set(candidates)]
  const available = []
  let fallback = null
  for (const cmd of uniqueCandidates) {
    try {
      const version = await getPythonVersion(cmd)
      if (!fallback) {
        fallback = { cmd, version }
      }
      available.push({ cmd, version })
    } catch (_) {
      /* try next */
    }
  }
  const supported = available
    .filter((item) => isPythonVersionSupported(item.version))
    .sort((a, b) => comparePythonVersions(b.version, a.version))
  if (supported.length) {
    return supported[0].cmd
  }
  return fallback ? fallback.cmd : null
}

async function collectPythonCandidates() {
  const home = process.env.HOME || ''
  const candidates = [
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.10/bin/python3',
    home ? path.join(home, '.pyenv', 'shims', 'python3') : '',
    home ? path.join(home, '.pyenv', 'shims', 'python') : '',
    home ? path.join(home, '.local', 'bin', 'python3') : '',
    home ? path.join(home, '.local', 'bin', 'python') : '',
    'python3',
    'python',
  ].filter(Boolean)
  const shellCandidates = await discoverPythonFromShell()
  return [...candidates, ...shellCandidates]
}

async function discoverPythonFromShell() {
  if (process.platform === 'win32') return []
  const shells = ['/bin/zsh', '/bin/bash']
  for (const shellPath of shells) {
    if (!fs.existsSync(shellPath)) continue
    try {
      const output = await new Promise((resolve, reject) => {
        const p = spawn(
          shellPath,
          ['-lc', 'command -v python3 2>/dev/null; command -v python 2>/dev/null'],
          { stdio: ['ignore', 'pipe', 'pipe'] },
        )
        let stdout = ''
        let stderr = ''
        p.stdout.on('data', (buf) => {
          stdout += String(buf)
        })
        p.stderr.on('data', (buf) => {
          stderr += String(buf)
        })
        p.on('error', reject)
        p.on('close', (code) => {
          if (code !== 0 && !stdout.trim()) {
            reject(new Error(stderr.trim() || `${shellPath} exited with code ${code}`))
            return
          }
          resolve(stdout)
        })
      })
      const lines = String(output)
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
      if (lines.length) return lines
    } catch (_) {
      /* try next shell */
    }
  }
  return []
}

async function getPythonVersion(cmd) {
  return await new Promise((resolve, reject) => {
    const p = spawn(cmd, ['-c', 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'], {
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let stdout = ''
    let stderr = ''
    p.stdout.on('data', (buf) => {
      stdout += String(buf)
    })
    p.stderr.on('data', (buf) => {
      stderr += String(buf)
    })
    p.on('error', reject)
    p.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `${cmd} exited with code ${code}`))
        return
      }
      resolve((stdout || '').trim())
    })
  })
}

function isPythonVersionSupported(versionText) {
  const match = String(versionText || '').match(/^(\d+)\.(\d+)/)
  if (!match) return false
  const major = Number(match[1])
  const minor = Number(match[2])
  return major > 3 || (major === 3 && minor >= 10)
}

function comparePythonVersions(a, b) {
  const parse = (text) => {
    const match = String(text || '').match(/^(\d+)\.(\d+)/)
    if (!match) return [0, 0]
    return [Number(match[1]), Number(match[2])]
  }
  const [aMajor, aMinor] = parse(a)
  const [bMajor, bMinor] = parse(b)
  if (aMajor !== bMajor) return aMajor - bMajor
  return aMinor - bMinor
}

function removeRuntimeVenv(dataRoot, writeLine) {
  const venvRoot = runtimeVenvRoot(dataRoot)
  try {
    fs.rmSync(venvRoot, { recursive: true, force: true })
    if (writeLine) writeLine(`removed broken runtime venv: ${venvRoot}`)
  } catch (e) {
    if (writeLine) writeLine(`failed to remove broken runtime venv: ${String(e && e.message ? e.message : e)}`)
    throw e
  }
}

async function isRuntimeVenvUsable(dataRoot, writeLine) {
  const py = runtimeVenvPython(dataRoot)
  if (!fs.existsSync(py)) return false
  try {
    await runCommand(
      py,
      ['-c', 'import uvicorn, fastapi, langchain_mcp_adapters'],
      { writeLine },
    )
    return true
  } catch (e) {
    if (writeLine) {
      writeLine(`runtime venv validation failed: ${String(e && e.message ? e.message : e)}`)
    }
    return false
  }
}

function buildLoadingHtml(opts = {}) {
  const bg = resolveThemeBg()
  const isDark = bg !== '#ffffff'
  const fg = isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.7)'
  const fgMuted = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.35)'
  const dotColor = isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.4)'
  const logoCircleBg = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'
  const logoCircleBorder = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'
  const extra = opts.firstTimeDeps
    ? `<p class="hint extra">首次启动正在创建 Python 运行环境并安装依赖，可能需要数分钟，请保持网络畅通。</p>`
    : ''
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>OpenGPT</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,sans-serif;
background:${bg};color:${fg};display:flex;flex-direction:column;align-items:center;
justify-content:center;min-height:100vh;overflow:hidden}
.container{display:flex;flex-direction:column;align-items:center;gap:28px;
animation:fadeIn 0.6s ease-out both}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.logo-ring{width:64px;height:64px;border-radius:50%;
background:${logoCircleBg};border:1px solid ${logoCircleBorder};
display:flex;align-items:center;justify-content:center;position:relative}
.logo-ring svg{width:28px;height:28px;opacity:0.7}
.spinner{position:absolute;inset:-3px;border-radius:50%;
border:2px solid transparent;border-top-color:${dotColor};
animation:spin 1.2s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.text-group{display:flex;flex-direction:column;align-items:center;gap:8px}
.title{font-size:15px;font-weight:500;letter-spacing:0.3px}
.dots{display:inline-flex;gap:3px;margin-left:2px;vertical-align:middle}
.dots span{width:3px;height:3px;border-radius:50%;background:${dotColor};
animation:blink 1.4s ease-in-out infinite}
.dots span:nth-child(2){animation-delay:0.2s}
.dots span:nth-child(3){animation-delay:0.4s}
@keyframes blink{0%,80%,100%{opacity:0.2}40%{opacity:1}}
.hint{font-size:12px;line-height:1.5;color:${fgMuted};text-align:center;max-width:400px}
.hint.extra{margin-top:4px;color:${fg};opacity:0.75}
</style></head><body>
<div class="container">
  <div class="logo-ring">
    <div class="spinner"></div>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
    </svg>
  </div>
  <div class="text-group">
    <div class="title">正在启动服务<span class="dots"><span></span><span></span><span></span></span></div>
    <p class="hint">首次启动可能需要稍等片刻</p>
    ${extra}
  </div>
</div>
</body></html>`
}

function createShellWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    show: false,
    backgroundColor: resolveThemeBg(),
    icon: appIconPath(),
    titleBarStyle: 'hidden',
    trafficLightPosition: { x: 14, y: 12 },
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })

  const openExternalIfNeeded = ({ url }) => {
    if (!shouldOpenInExternalBrowser(url, win.webContents.getURL())) {
      return { action: 'allow' }
    }

    shell.openExternal(url).catch((err) => {
      console.warn('OpenGPT: failed to open external link:', err)
    })
    return { action: 'deny' }
  }

  win.webContents.setWindowOpenHandler(openExternalIfNeeded)
  win.webContents.on('will-navigate', (event, url) => {
    if (!shouldOpenInExternalBrowser(url, win.webContents.getURL())) return
    event.preventDefault()
    shell.openExternal(url).catch((err) => {
      console.warn('OpenGPT: failed to open external navigation:', err)
    })
  })

  return win
}

async function createLoadingWindow(firstTimeDeps) {
  const win = createShellWindow()
  await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(buildLoadingHtml({ firstTimeDeps })))
  if (!win.isDestroyed()) win.show()
  return win
}

function buildLoadRetryHtml(message = '正在连接本地服务，请稍候…') {
  const bg = resolveThemeBg()
  const isDark = bg !== '#ffffff'
  const fg = isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.72)'
  const muted = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.42)'
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>OpenGPT</title>
<style>
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,sans-serif;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{max-width:420px;padding:24px;text-align:center}
.title{font-size:15px;font-weight:600;margin-bottom:10px}
.hint{font-size:12px;line-height:1.6;color:${muted}}
</style></head><body><div class="box"><div class="title">OpenGPT</div><div class="hint">${message}</div></div></body></html>`
}

async function loadWindowUrlWithRetry(win, url, opts = {}) {
  const retries = Math.max(1, Number(opts.retries || 1))
  const delayMs = Math.max(200, Number(opts.delayMs || 800))
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    if (win.isDestroyed()) return false
    try {
      await win.loadURL(url)
      if (!win.isVisible()) win.show()
      return true
    } catch (e) {
      if (isQuitting || isShuttingDownChildren || win.isDestroyed()) return false
      if (attempt >= retries) throw e
      try {
        await win.loadURL(
          'data:text/html;charset=utf-8,' +
            encodeURIComponent(buildLoadRetryHtml(`连接本地服务失败，正在重试（${attempt + 1}/${retries}）…`)),
        )
      } catch (_) {
        /* ignore fallback page failure */
      }
      await new Promise((r) => setTimeout(r, delayMs))
    }
  }
  return false
}

async function ensureRuntimeVenv(backendRoot, dataRoot, setupLogPath) {
  const py = runtimeVenvPython(dataRoot)
  const write = createLineWriter(setupLogPath)
  write(`--- ${new Date().toISOString()} setup runtime venv ---`)

  if (await isRuntimeVenvUsable(dataRoot, write)) {
    write('reuse existing runtime venv')
    return py
  }
  if (fs.existsSync(runtimeVenvRoot(dataRoot))) {
    removeRuntimeVenv(dataRoot, write)
  }

  const sysPy = await findSystemPython()
  if (!sysPy) {
    throw new Error('未找到系统 Python3，无法自动创建运行环境')
  }
  const sysPyVersion = await getPythonVersion(sysPy)
  write(`detected system python: ${sysPy} (${sysPyVersion})`)
  if (!isPythonVersionSupported(sysPyVersion)) {
    throw new Error(
      `首次启动需要 Python 3.10 或更高版本；当前检测到 ${sysPyVersion}，无法安装必需依赖 langchain-mcp-adapters。请先升级 Python 后重新启动 OpenGPT。`,
    )
  }
  const req = path.join(backendRoot, 'requirements.txt')
  const venvRoot = runtimeVenvRoot(dataRoot)
  try {
    await runCommand(sysPy, ['-m', 'venv', venvRoot], { writeLine: write })
    await runCommand(runtimeVenvPython(dataRoot), ['-m', 'pip', 'install', '-r', req], { writeLine: write })
    if (!(await isRuntimeVenvUsable(dataRoot, write))) {
      throw new Error('运行环境创建后校验失败：缺少 uvicorn、fastapi 或 langchain_mcp_adapters')
    }
    return runtimeVenvPython(dataRoot)
  } catch (e) {
    if (fs.existsSync(runtimeVenvRoot(dataRoot))) {
      removeRuntimeVenv(dataRoot, write)
    }
    throw e
  }
}

function spawnManaged(cmd, args, opts) {
  const useErrLog = opts.stderrLog
  const p = spawn(cmd, args, {
    cwd: opts.cwd,
    env: { ...process.env, ...opts.env },
    stdio: useErrLog ? ['ignore', 'ignore', 'pipe'] : 'ignore',
  })
  if (useErrLog && p.stderr) {
    const w = fs.createWriteStream(opts.stderrLog, { flags: 'a' })
    w.write(`\n--- ${new Date().toISOString()} pid=${p.pid} ---\n`)
    p.stderr.pipe(w)
  }
  children.push(p)
  return p
}

function killAllChildren() {
  for (const p of children) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(p.pid), '/f', '/t'], { stdio: 'ignore' })
      } else {
        p.kill('SIGTERM')
      }
    } catch (_) {
      /* ignore */
    }
  }
  children.length = 0
}

async function fetchWithTimeout(url, timeoutMs) {
  try {
    return await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
  } catch (_) {
    return null
  }
}

async function waitHealth(url, timeoutMs = 120000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const res = await fetchWithTimeout(url, 2000)
    if (res && res.ok) return
    await new Promise((r) => setTimeout(r, 400))
  }
  throw new Error(`health check timeout: ${url}`)
}

function tcpPortOpen(port, host = '127.0.0.1', timeoutMs = 1500) {
  return new Promise((resolve) => {
    const socket = net.connect({ port: Number(port), host }, () => {
      socket.end()
      resolve(true)
    })
    const fail = () => {
      socket.destroy()
      resolve(false)
    }
    socket.on('error', fail)
    socket.setTimeout(timeoutMs, fail)
  })
}

async function pickFreePort(candidates) {
  for (const p of candidates) {
    if (!(await tcpPortOpen(p))) return String(p)
  }
  throw new Error(`no free port in candidates: ${candidates.join(',')}`)
}

async function waitForApiHealth(apiPort, timeoutMs = 120000) {
  const url = `http://127.0.0.1:${apiPort}/api/health`
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const res = await fetchWithTimeout(url, 2000)
    if (res && res.ok) return true
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

/** 指定端口上是否为桌面版所需的静态首页（npm run build 产物） */
async function isBundledSpaOnPort(apiPort) {
  const res = await fetchWithTimeout(`http://127.0.0.1:${apiPort}/`, 3000)
  if (!res) return false
  const text = await res.text()
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  if (res.status === 404 && (text.includes('"Not Found"') || text.includes("'Not Found'"))) {
    return false
  }
  const looksLikeHtml =
    ct.includes('text/html') || /^\s*</.test(text) || text.includes('<!doctype')
  return !!(res.ok && looksLikeHtml && !text.trimStart().startsWith('{'))
}

/** start.sh：API 与 OpenGPT_API_PORT 一致、界面在 Vite 5173 */
async function isViteDevFrontend() {
  const res = await fetchWithTimeout('http://127.0.0.1:5173/', 2500)
  if (!res || !res.ok) return false
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  return ct.includes('text/html')
}

/**
 * 若本机已有可用服务则直接复用，避免与 start.sh 抢默认 API 口 / 8101。
 * 端口未监听 → 立即自启；已监听但 health 未就绪 → 最长等待（start.sh + MCP 加载较慢）。
 * @returns {'spawn'|'open'|'conflict'|'bad-port'} & { url?: string }
 */
async function resolveExistingStack(apiPort) {
  const listening = await tcpPortOpen(apiPort)
  if (!listening) return { action: 'spawn' }

  const healthOk = await waitForApiHealth(apiPort, 120000)
  if (!healthOk) return { action: 'bad-port' }

  if (await isBundledSpaOnPort(apiPort)) {
    return { action: 'open', url: `http://127.0.0.1:${apiPort}/` }
  }
  const viteDeadline = Date.now() + 45000
  while (Date.now() < viteDeadline) {
    if (await isViteDevFrontend()) {
      return { action: 'open', url: 'http://127.0.0.1:5173/' }
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  return { action: 'conflict' }
}

/** 避免端口已被「无 OpenGPT_STATIC_DIR」的旧后端占用：/api/health 正常但 / 会返回 {"detail":"Not Found"} */
async function verifySpaRoot(apiPort, timeoutMs = 30000) {
  const url = `http://127.0.0.1:${apiPort}/`
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, {
        redirect: 'follow',
        signal: AbortSignal.timeout(3000),
      })
      const ct = (res.headers.get('content-type') || '').toLowerCase()
      const text = await res.text()
      if (res.status === 404 && (text.includes('"Not Found"') || text.includes("'Not Found'"))) {
        throw new Error('SPA_ROOT_CHECK_FAILED')
      }
      const looksLikeHtml =
        ct.includes('text/html') || /^\s*</.test(text) || text.includes('<!doctype')
      if (res.ok && looksLikeHtml && !text.trimStart().startsWith('{')) return
    } catch (e) {
      if (e && e.message === 'SPA_ROOT_CHECK_FAILED') throw e
      /* 子进程刚起，再等 */
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('SPA_ROOT_CHECK_FAILED')
}

async function bootstrap() {
  cleanupStaleBackendProcesses()
  const root = runtimeRootDir()
  const userDataRoot = userDataRootDir()
  const dataRoot = runtimeDataRoot()
  fs.mkdirSync(dataRoot, { recursive: true })
  const logDir = app.isPackaged ? path.join(userDataRoot, 'logs') : path.join(root, 'logs')
  fs.mkdirSync(logDir, { recursive: true })
  const spawnGwLog = path.join(logDir, 'electron-spawn-gateway.log')
  const spawnApiLog = path.join(logDir, 'electron-spawn-api.log')
  const setupLog = path.join(logDir, 'electron-setup.log')
  const backendRoot = path.join(root, 'backend')
  const dist = path.join(root, 'frontend', 'dist')
  let py = venvPython(backendRoot)
  /** @type {import('electron').BrowserWindow | null} */
  let win = null

  if (app.isPackaged) {
    const hasRuntimePython = fs.existsSync(runtimeVenvPython(dataRoot))
    if (!hasRuntimePython) {
      win = await createLoadingWindow(true)
    }
    try {
      py = await ensureRuntimeVenv(backendRoot, dataRoot, setupLog)
    } catch (e) {
      if (win && !win.isDestroyed()) win.close()
      await dialog.showErrorBox(
        'OpenGPT',
        `首次启动需初始化 Python 依赖，失败：${String(e && e.message ? e.message : e)}\n` +
          `请查看日志：${setupLog}`,
      )
      app.quit()
      return
    }
  } else if (!fs.existsSync(py)) {
    await dialog.showErrorBox(
      'OpenGPT',
      '未找到 backend/.venv。\n请在 backend 目录执行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt',
    )
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(backendRoot, '.env'))) {
    if (win && !win.isDestroyed()) win.close()
    await dialog.showErrorBox('OpenGPT', '未找到 backend/.env，请从 .env.example 复制并填写。')
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(dist, 'index.html'))) {
    if (win && !win.isDestroyed()) win.close()
    await dialog.showErrorBox(
      'OpenGPT',
      '未找到 frontend/dist。\n请在 frontend 目录执行：npm install && npm run build',
    )
    app.quit()
    return
  }

  let gwPort = process.env.EMBEDDING_GATEWAY_PORT || '8101'
  let apiPort = process.env.OpenGPT_API_PORT || process.env.MYGPT_API_PORT || DEFAULT_API_PORT

  /**
   * 必须先有窗口再 resolveExistingStack：若默认 API 端口已被占用，waitForApiHealth 最长等 120s、
   * 等 Vite 再等 45s，否则 Dock 只有图标、用户以为卡死。
   */
  if (!win || win.isDestroyed()) {
    win = await createLoadingWindow(false)
  } else {
    await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(buildLoadingHtml({ firstTimeDeps: false })))
  }

  // 打包版必须使用当前安装包自带的后端与前端资源，避免误复用旧进程导致“重装后仍是旧界面”。
  if (!app.isPackaged) {
    const existing = await resolveExistingStack(apiPort)
    if (existing.action === 'open') {
      await loadWindowUrlWithRetry(win, existing.url, { retries: 6, delayMs: 700 })
      mainWin = win
      setupMainWindowClose(win)
      return
    }
    if (existing.action === 'bad-port') {
      // 常见于默认端口被其它进程占用，自动改用备用端口继续启动
      apiPort = await pickFreePort([18000, 18001, 18002, 18010, 18080, 19000])
    }
    if (existing.action === 'conflict') {
      // 已有 API-only 服务但无 Vite 时，自动起一套桌面专用后端到备用端口
      apiPort = await pickFreePort([18000, 18001, 18002, 18010, 18080, 19000])
    }
  } else if (await tcpPortOpen(apiPort)) {
    // 打包版端口冲突时仅换端口，不复用已有服务。
    apiPort = await pickFreePort([18000, 18001, 18002, 18010, 18080, 19000])
  }

  if (await tcpPortOpen(gwPort)) {
    gwPort = await pickFreePort([18101, 18102, 18103, 19101])
  }

  spawnManaged(py, ['-m', 'uvicorn', 'embedding_gateway.main:app', '--host', '127.0.0.1', '--port', gwPort], {
    cwd: backendRoot,
    env: {
      EMBEDDING_GATEWAY_PORT: gwPort,
      PYTHONDONTWRITEBYTECODE: '1',
    },
    stderrLog: spawnGwLog,
  })

  await new Promise((r) => setTimeout(r, 1200))

  spawnManaged(py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', apiPort], {
    cwd: backendRoot,
    env: {
      OpenGPT_API_PORT: apiPort,
      OpenGPT_STATIC_DIR: dist,
      EMBEDDING_GATEWAY_PORT: gwPort,
      EMBEDDING_BASE_URL: `http://127.0.0.1:${gwPort}/v1`,
      DB_PATH: path.join(dataRoot, 'chat.db'),
      SETTINGS_DB_PATH: path.join(dataRoot, 'settings.db'),
      MCP_CONFIG_PATH: path.join(dataRoot, 'mcp.json'),
      FILE_MEMORY_DIR: path.join(dataRoot, 'file_memories'),
      MEM0_DIR: path.join(dataRoot, 'mem0'),
      MEMORY_LEGACY_PATH: path.join(dataRoot, 'qdrant'),
      PYTHONDONTWRITEBYTECODE: '1',
    },
    stderrLog: spawnApiLog,
  })

  try {
    await waitHealth(`http://127.0.0.1:${apiPort}/api/health`)
    await verifySpaRoot(apiPort)
  } catch (e) {
    const msg =
      e && e.message === 'SPA_ROOT_CHECK_FAILED'
        ? `首页不是前端页面（常见原因：${apiPort} 端口已被占用）。\n` +
          '请先停止其它后端，例如：在项目根目录执行 bash start.sh stop\n' +
          `或改用其它端口：export OpenGPT_API_PORT=18001 后再 npm start\n` +
          '并确认已执行：cd frontend && npm run build'
        : `主服务启动超时。\n请查看项目下 logs/electron-spawn-api.log 与 logs/electron-spawn-gateway.log；\n` +
          '并检查 backend/.env、依赖是否完整，或在 backend 目录手动运行 uvicorn 查看报错。'
    await dialog.showErrorBox('OpenGPT', msg)
    killAllChildren()
    app.quit()
    return
  }

  await session.defaultSession.clearCache()
  await loadWindowUrlWithRetry(win, `http://127.0.0.1:${apiPort}/`, { retries: 20, delayMs: 800 })
  mainWin = win
  setupMainWindowClose(win)
}

app.whenReady().then(() => {
  ipcMain.on('save-theme-mode', (_, mode) => {
    if (mode === 'light' || mode === 'dark' || mode === 'system') {
      try { fs.writeFileSync(themeFilePath(), mode) } catch (_) {}
    }
  })
  try {
    const iconPath = appIconPath()
    if (fs.existsSync(iconPath)) {
      const icon = nativeImage.createFromPath(iconPath)
      if (!icon.isEmpty() && process.platform === 'darwin' && app.dock) {
        app.dock.setIcon(icon)
      }
    }
  } catch (_) {
    /* ignore icon loading errors */
  }
  bootstrap().catch(async (e) => {
    console.error(e)
    await dialog.showErrorBox('OpenGPT', String(e && e.message ? e.message : e))
    killAllChildren()
    app.quit()
  })
})

app.on('window-all-closed', () => {
  // macOS：关窗不等于退出，保留本机后端进程，再次点开 Dock 可秒开；真正退出用 Cmd+Q（会走 before-quit）
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  isQuitting = true
})

app.on('will-quit', () => {
  isShuttingDownChildren = true
  killAllChildren()
})

app.on('activate', () => {
  if (mainWin && !mainWin.isDestroyed()) {
    mainWin.show()
  } else if (BrowserWindow.getAllWindows().length === 0) {
    bootstrap().catch(() => app.quit())
  }
})
