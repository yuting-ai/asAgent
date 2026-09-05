/* eslint-disable @typescript-eslint/explicit-function-return-type -- Native JavaScript regression fixture. */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { app, BrowserWindow, WebContentsView, session } from 'electron'
const { default: module } = await import(pathToFileURL(process.argv[2]).href)
const profile = mkdtempSync(join(tmpdir(), 'asagent-read-page-'))
app.setPath('userData', profile)
let browser
let window
const server = createServer((request, response) => {
  response.setHeader('Content-Type', 'text/html; charset=utf-8')
  const port = server.address().port
  if (request.url === '/child') {
    response.end(
      '<body>Visible cross-origin frame<table><tr><td>Revenue 123</td></tr></table><script>/* HIDDEN_CHILD_SCRIPT */</script></body>'
    )
  } else if (request.url === '/hidden') {
    response.end(
      '<body>HIDDEN_FRAME_ACCOUNT<script>/* HIDDEN_FRAME_SCRIPT */</script><iframe src="/child"></iframe></body>'
    )
  } else {
    response.end(`<body><p>Visible introduction</p><code>window.example = 42</code>
      <script style="display:block">/* HIDDEN_SCRIPT_CONFIG */</script>
      <style style="display:block">/* HIDDEN_STYLE */</style>
      <noscript>HIDDEN_NOSCRIPT</noscript><template>HIDDEN_TEMPLATE</template>
      <div hidden>HIDDEN_ATTRIBUTE</div><div style="display:none">HIDDEN_DISPLAY</div>
      <div style="opacity:0"><table><tr><td>HIDDEN_TABLE</td></tr></table></div>
      <div style="display:contents">Visible contents</div>
      <table><tr><td><b>Visible cell</b><script>/* HIDDEN_CELL_SCRIPT */</script></td></tr></table>
      <iframe src="http://localhost:${port}/child"></iframe>
      <iframe style="display:none" src="http://localhost:${port}/hidden"></iframe>
      <div hidden><iframe src="/hidden"></iframe></div>
      <iframe style="width:0;height:0;border:0" src="/hidden"></iframe>
    </body>`)
  }
})
async function main() {
  try {
    await new Promise((resolve) => server.listen(0, resolve))
    await app.whenReady()
    window = new BrowserWindow({ width: 900, height: 700, webPreferences: { sandbox: true } })
    browser = new module.VisibleBrowser({
      session: session.fromPartition('page-read-test'),
      createView: (options) => new WebContentsView(options)
    })
    browser.show(window, { x: 0, y: 0, width: 900, height: 700 }, 'fixture')
    await browser.navigate('fixture', `http://127.0.0.1:${server.address().port}/`)
    const page = await browser.readCurrentPage('fixture')
    for (const text of [
      'Visible introduction',
      'window.example = 42',
      'Visible cell',
      'Visible contents',
      'Visible cross-origin frame',
      'Revenue 123'
    ])
      assert.ok(page.text.includes(text), `Missing ${text}`)
    assert.ok(!page.text.includes('HIDDEN_'), 'Non-visible content leaked')
    assert.equal(
      page.text.split('Visible cross-origin frame').length - 1,
      1,
      'Hidden subtree was included'
    )
    console.log(
      'PASS: real DOM filtering preserves visible cross-origin frames and tables; excludes scripts and hidden subtrees'
    )
  } catch (error) {
    console.error(error)
    process.exitCode = 1
  } finally {
    browser?.dispose()
    window?.destroy()
    server.close()
    app.quit()
  }
}
void main()
app.on('quit', () => rmSync(profile, { recursive: true, force: true }))
