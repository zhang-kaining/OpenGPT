const test = require('node:test')
const assert = require('node:assert/strict')

const {
  shouldOpenInExternalBrowser,
  normalizeAppOrigin,
} = require('./url-policy.cjs')

test('normalizes localhost app origin', () => {
  assert.equal(normalizeAppOrigin('http://127.0.0.1:18789/'), 'http://127.0.0.1:18789')
})

test('keeps same-origin app links inside desktop app', () => {
  const appUrl = 'http://127.0.0.1:18789/'

  assert.equal(shouldOpenInExternalBrowser('/settings', appUrl), false)
  assert.equal(shouldOpenInExternalBrowser('http://127.0.0.1:18789/help', appUrl), false)
  assert.equal(shouldOpenInExternalBrowser('http://localhost:18789/help', appUrl), false)
})

test('opens external http links in default browser', () => {
  const appUrl = 'http://127.0.0.1:18789/'

  assert.equal(shouldOpenInExternalBrowser('https://example.com/docs', appUrl), true)
  assert.equal(shouldOpenInExternalBrowser('http://127.0.0.1:3000/devtools', appUrl), true)
})

test('does not treat invalid urls as external browser targets', () => {
  const appUrl = 'http://127.0.0.1:18789/'

  assert.equal(shouldOpenInExternalBrowser('not a url', appUrl), false)
})
