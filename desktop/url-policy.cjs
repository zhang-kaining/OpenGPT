function normalizeLocalHostname(hostname) {
  return hostname === 'localhost' ? '127.0.0.1' : hostname
}

function normalizeOrigin(urlLike) {
  try {
    const url = new URL(urlLike)
    return `${url.protocol}//${normalizeLocalHostname(url.hostname)}${url.port ? `:${url.port}` : ''}`
  } catch (_) {
    return ''
  }
}

function resolveUrl(targetUrl, appUrl) {
  try {
    return new URL(targetUrl, appUrl)
  } catch (_) {
    return null
  }
}

function shouldOpenInExternalBrowser(targetUrl, appUrl) {
  const resolved = resolveUrl(targetUrl, appUrl)
  if (!resolved) return false

  if (resolved.protocol !== 'http:' && resolved.protocol !== 'https:') {
    return false
  }

  return normalizeOrigin(resolved.href) !== normalizeOrigin(appUrl)
}

module.exports = {
  normalizeAppOrigin: normalizeOrigin,
  shouldOpenInExternalBrowser,
}
