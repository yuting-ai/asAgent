import { FormEvent, useEffect, useState } from 'react'

type AppInfo = {
  appName: string
  version: string
}

export default function App(): React.JSX.Element {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'ready' | 'unavailable'>(
    'checking'
  )
  const [draft, setDraft] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    void window.desktop.getAppInfo().then(setAppInfo)
  }, [])

  useEffect(() => {
    void window.desktop.getBackendStatus().then((result) => {
      setBackendStatus(result.status)
    })
  }, [])

  function submitDraft(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()

    if (!draft.trim()) {
      return
    }

    setNotice('Backend is not connected; this message was not sent.')
    setDraft('')
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">LOCAL PERSONAL ASSISTANT</p>
          <h1>asAgent</h1>
        </div>

        <button className="new-conversation" type="button">
          + New conversation
        </button>

        <nav aria-label="Conversations">
          <p className="section-label">Conversations</p>
          <button className="conversation active" type="button">
            <span>Welcome to asAgent</span>
            <small>Just now</small>
          </button>
        </nav>

        <p className="version">
          {appInfo ? `${appInfo.appName} ${appInfo.version}` : 'Loading app info…'}
        </p>
      </aside>

      <section className="chat">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Current conversation</p>
            <h2>Welcome to asAgent</h2>
          </div>
          <span className={`connection-status ${backendStatus}`}>
            {backendStatus === 'ready' ? 'Backend ready' : 'Checking backend…'}
          </span>
        </header>

        <div className="messages">
          <article className="message assistant">
            <p className="message-role">asAgent</p>
            <p>
              Welcome. The desktop UI is ready; next we will connect it to the local Agent Backend.
            </p>
          </article>
        </div>

        <form className="composer" onSubmit={submitDraft}>
          <label className="sr-only" htmlFor="message">
            Message
          </label>
          <textarea
            id="message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Type a message…"
            rows={3}
          />
          <div className="composer-footer">
            <span>{notice ?? 'Messages stay in this UI and are not sent yet.'}</span>
            <button disabled={!draft.trim()} type="submit">
              Send
            </button>
          </div>
        </form>
      </section>
    </main>
  )
}
