// Native Electron regression test. Pass a bundled browser_view.ts as argv[2].
// This fixture separates a keyboard-driven editor's staging DOM from its model;
// it does not substitute for a real Google Sheets acceptance test.
/* eslint-disable @typescript-eslint/explicit-function-return-type -- Plain JavaScript Electron smoke test. */
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { app, BrowserWindow } from 'electron'
const { default: browserInput } = await import(pathToFileURL(process.argv[2]).href)
const { dispatchBrowserEditorInput } = browserInput
const profile = mkdtempSync(join(tmpdir(), 'asagent-editor-input-'))
app.setPath('userData', profile)
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function main() {
  await app.whenReady()
  const window = new BrowserWindow({ width: 500, height: 300, webPreferences: { sandbox: true } })
  await window.loadURL(
    'data:text/html,' +
      encodeURIComponent(`
    <div id="cells"></div><div id="editor" contenteditable="true"></div>
    <script>
      const editor = document.querySelector('#editor');
      window.model = ['', '']; window.cell = 0; window.editing = false;
      window.select = index => {
        cell = index; editing = false; editor.textContent = model[cell]; editor.focus();
        const range = document.createRange(); range.selectNodeContents(editor);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      };
      const commit = () => {
        if (editing) model[cell] = editor.textContent;
        document.querySelector('#cells').textContent = JSON.stringify(model);
        select((cell + 1) % 2);
      };
      editor.addEventListener('keypress', event => {
        if (event.key === 'Enter') { event.preventDefault(); commit(); }
        else if (event.isTrusted) editing = true;
      });
      editor.addEventListener('keydown', event => {
        if (event.key === 'Tab') { event.preventDefault(); commit(); }
      });
      select(0);
    </script>`)
  )
  window.focus()
  window.webContents.focus()
  await delay(150)
  const wc = window.webContents
  // Reproduce the old false positive: text appears in DOM, never in the model.
  await wc.insertText('旧输入')
  wc.sendInputEvent({ type: 'keyDown', keyCode: 'Enter' })
  wc.sendInputEvent({ type: 'keyUp', keyCode: 'Enter' })
  await delay(80)
  assert.equal(await wc.executeJavaScript('editor.textContent'), '旧输入')
  assert.deepEqual(await wc.executeJavaScript('model'), ['', ''])
  await wc.executeJavaScript('select(0)')
  const url = 'https://docs.google.com/spreadsheets/d/fixture/edit'
  await dispatchBrowserEditorInput(wc, { url, kind: 'text', value: '订单日期' })
  await dispatchBrowserEditorInput(wc, { url, kind: 'key', value: 'Tab' })
  await dispatchBrowserEditorInput(wc, { url, kind: 'text', value: '产品😀' })
  await dispatchBrowserEditorInput(wc, { url, kind: 'key', value: 'Enter' })
  await delay(100)
  assert.deepEqual(await wc.executeJavaScript('model'), ['订单日期', '产品😀'])
  // Re-select both cells and verify that their model values survive navigation.
  for (const [index, text] of ['订单日期', '产品😀'].entries()) {
    await wc.executeJavaScript(`select(${index})`)
    assert.equal(await wc.executeJavaScript('editor.textContent'), text)
  }
  console.log('PASS: native input commits two separate cells and survives reselection')
  window.destroy()
}
main()
  .then(() => app.quit())
  .catch((error) => {
    console.error(error)
    app.exit(1)
  })
app.on('quit', () => rmSync(profile, { recursive: true, force: true }))
