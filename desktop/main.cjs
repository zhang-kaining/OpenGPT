/**
 * 开发机试用：拉起 embedding 网关 + 主 API（含静态前端），再用 Electron 打开本地页面。
 * 需在仓库根目录：frontend 已 build、backend 已有 .venv 与 .env。
 */
const { app, BrowserWindow, dialog } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')

/** @type {import('child_process').ChildProcess[]} */
const children = []

function venvPython(backendRoot) {
  if (process.platform === 'win32') {
    return path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
  }
  return path.join(backendRoot, '.venv', 'bin', 'python')
}

function spawnManaged(cmd, args, opts) {
  const p = spawn(cmd, args, {
    cwd: opts.cwd,
    env: { ...process.env, ...opts.env },
    stdio: 'ignore',
  })
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

async function waitHealth(url, timeoutMs = 90000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2000) })
      if (res.ok) return
    } catch (_) {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 400))
  }
  throw new Error(`health check timeout: ${url}`)
}

/** 避免 8000 已被「无 MYGPT_STATIC_DIR」的旧后端占用：/api/health 正常但 / 会返回 {"detail":"Not Found"} */
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
    } catch (_) {
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
      'MyGPT',
      '未找到 backend/.venv。\n请在 backend 目录执行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt',
    )
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(backendRoot, '.env'))) {
    await dialog.showErrorBox('MyGPT', '未找到 backend/.env，请从 .env.example 复制并填写。')
    app.quit()
    return
  }
  if (!fs.existsSync(path.join(dist, 'index.html'))) {
    await dialog.showErrorBox(
      'MyGPT',
      '未找到 frontend/dist。\n请在 frontend 目录执行：npm install && npm run build',
    )
    app.quit()
    return
  }

  const gwPort = process.env.EMBEDDING_GATEWAY_PORT || '8101'
  const apiPort = process.env.MYGPT_API_PORT || '8000'

  spawnManaged(py, ['-m', 'uvicorn', 'embedding_gateway.main:app', '--host', '127.0.0.1', '--port', gwPort], {
    cwd: backendRoot,
    env: { EMBEDDING_GATEWAY_PORT: gwPort },
  })

  await new Promise((r) => setTimeout(r, 1200))

  spawnManaged(py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', apiPort], {
    cwd: backendRoot,
    env: {
      MYGPT_STATIC_DIR: dist,
    },
  })

  try {
    await waitHealth(`http://127.0.0.1:${apiPort}/api/health`)
    await verifySpaRoot(apiPort)
  } catch (e) {
    const msg =
      e && e.message === 'SPA_ROOT_CHECK_FAILED'
        ? `首页不是前端页面（常见原因：${apiPort} 端口已被占用）。\n` +
          '请先停止其它后端，例如：在项目根目录执行 bash start.sh stop\n' +
          '或改用其它端口：export MYGPT_API_PORT=8001 后再 npm start\n' +
          '并确认已执行：cd frontend && npm run build'
        : '主服务启动超时。\n请检查 backend/.env、依赖是否完整，或在终端手动运行 uvicorn 查看报错。'
    await dialog.showErrorBox('MyGPT', msg)
    killAllChildren()
    app.quit()
    return
  }

  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })
  await win.loadURL(`http://127.0.0.1:${apiPort}/`)
}

app.whenReady().then(() => {
  bootstrap().catch(async (e) => {
    console.error(e)
    await dialog.showErrorBox('MyGPT', String(e && e.message ? e.message : e))
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
