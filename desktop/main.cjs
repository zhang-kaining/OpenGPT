/**
 * 开发机试用：拉起 embedding 网关 + 主 API（含静态前端），再用 Electron 打开本地页面。
 * 需在仓库根目录：frontend 已 build、backend 已有 .venv 与 .env。
 */
const { app, BrowserWindow, dialog } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const net = require('net')

// 系统代理若未排除 localhost，fetch(127.0.0.1) 会失败 → 误判超时
if (!/\b127\.0\.0\.1\b/.test(process.env.NO_PROXY || '')) {
  process.env.NO_PROXY = ['127.0.0.1', 'localhost', '::1', process.env.NO_PROXY].filter(Boolean).join(',')
}

/** @type {import('child_process').ChildProcess[]} */
const children = []

function venvPython(backendRoot) {
  if (process.platform === 'win32') {
    return path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
  }
  return path.join(backendRoot, '.venv', 'bin', 'python')
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

/** 8000 上是否为桌面版所需的静态首页（npm run build 产物） */
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

/** start.sh：API 在 8000、界面在 Vite 5173 */
async function isViteDevFrontend() {
  const res = await fetchWithTimeout('http://127.0.0.1:5173/', 2500)
  if (!res || !res.ok) return false
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  return ct.includes('text/html')
}

/**
 * 若本机已有可用服务则直接复用，避免与 start.sh 抢 8000/8101。
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

/** 避免 8000 已被「无 OpenGPT_STATIC_DIR」的旧后端占用：/api/health 正常但 / 会返回 {"detail":"Not Found"} */
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
  const root = path.resolve(__dirname, '..')
  const backendRoot = path.join(root, 'backend')
  const dist = path.join(root, 'frontend', 'dist')
  const py = venvPython(backendRoot)

  if (!fs.existsSync(py)) {
    await dialog.showErrorBox(
      'OpenGPT',
      '未找到 backend/.venv。\n请在 backend 目录执行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt',
    )
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(backendRoot, '.env'))) {
    await dialog.showErrorBox('OpenGPT', '未找到 backend/.env，请从 .env.example 复制并填写。')
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(dist, 'index.html'))) {
    await dialog.showErrorBox(
      'OpenGPT',
      '未找到 frontend/dist。\n请在 frontend 目录执行：npm install && npm run build',
    )
    app.quit()
    return
  }

  const loadingHtml =
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>OpenGPT</title></head>' +
    '<body style="margin:0;font:15px system-ui,-apple-system,sans-serif;background:#1e1e1e;color:#e0e0e0;' +
    'display:flex;align-items:center;justify-content:center;min-height:100vh">' +
    '<p>正在检测或启动本机服务，请稍候…</p></body></html>'
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })
  await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(loadingHtml))

  let gwPort = process.env.EMBEDDING_GATEWAY_PORT || '8101'
  let apiPort = process.env.OpenGPT_API_PORT || process.env.MYGPT_API_PORT || '8000'

  const logDir = path.join(root, 'logs')
  fs.mkdirSync(logDir, { recursive: true })
  const spawnGwLog = path.join(logDir, 'electron-spawn-gateway.log')
  const spawnApiLog = path.join(logDir, 'electron-spawn-api.log')

  const existing = await resolveExistingStack(apiPort)
  if (existing.action === 'open') {
    await win.loadURL(existing.url)
    return
  }
  if (existing.action === 'bad-port') {
    // 常见于 8000 被其它进程占用（如 IDE 扩展），自动改用备用端口继续启动
    apiPort = await pickFreePort([18000, 18001, 18002, 18010, 18080, 19000])
  }
  if (existing.action === 'conflict') {
    // 已有 API-only 服务但无 Vite 时，自动起一套桌面专用后端到备用端口
    apiPort = await pickFreePort([18000, 18001, 18002, 18010, 18080, 19000])
  }

  if (await tcpPortOpen(gwPort)) {
    gwPort = await pickFreePort([18101, 18102, 18103, 19101])
  }

  spawnManaged(py, ['-m', 'uvicorn', 'embedding_gateway.main:app', '--host', '127.0.0.1', '--port', gwPort], {
    cwd: backendRoot,
    env: { EMBEDDING_GATEWAY_PORT: gwPort },
    stderrLog: spawnGwLog,
  })

  await new Promise((r) => setTimeout(r, 1200))

  spawnManaged(py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', apiPort], {
    cwd: backendRoot,
    env: {
      OpenGPT_STATIC_DIR: dist,
      EMBEDDING_GATEWAY_PORT: gwPort,
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
          '或改用其它端口：export OpenGPT_API_PORT=8001 后再 npm start\n' +
          '并确认已执行：cd frontend && npm run build'
        : `主服务启动超时。\n请查看项目下 logs/electron-spawn-api.log 与 logs/electron-spawn-gateway.log；\n` +
          '并检查 backend/.env、依赖是否完整，或在 backend 目录手动运行 uvicorn 查看报错。'
    await dialog.showErrorBox('OpenGPT', msg)
    killAllChildren()
    app.quit()
    return
  }

  await win.loadURL(`http://127.0.0.1:${apiPort}/`)
}

app.whenReady().then(() => {
  bootstrap().catch(async (e) => {
    console.error(e)
    await dialog.showErrorBox('OpenGPT', String(e && e.message ? e.message : e))
    killAllChildren()
    app.quit()
  })
})

app.on('window-all-closed', () => {
  killAllChildren()
  app.quit()
})

app.on('before-quit', () => {
  killAllChildren()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    bootstrap().catch(() => app.quit())
  }
})
