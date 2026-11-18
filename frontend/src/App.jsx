import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE_URL = 'http://localhost:8000'
const suggestedQuestions = ['When is the release?', 'What did we decide?', 'Summarize my notes']

function formatUserError(message) {
  if (!message) return 'Something went wrong. Please try again.'

  const lower = message.toLowerCase()
  if (lower.includes('403') || lower.includes('forbidden') || lower.includes('could not read content from url')) {
    return 'This page blocked automated access. Please paste the content manually or try a different URL.'
  }

  if (lower.includes('url is required')) {
    return 'Please enter a valid URL.'
  }

  return message
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(formatUserError(data.error || 'Request failed'))
  }

  return data
}

function normalizeText(value) {
  return (value || '').replace(/\s+/g, ' ').trim()
}

function buildTitleFromContent(content, fallback = 'Untitled note') {
  const text = normalizeText(content)
  if (!text) return fallback

  const firstLine = text.split(/\r?\n/)[0] || text
  const sentences = firstLine.split(/(?<=[.!?])\s+/)
  const firstSentence = sentences[0] || firstLine
  const words = firstSentence.split(' ')

  let titleWords = []
  let titleLength = 0

  for (const word of words) {
    const nextLength = titleLength + word.length + (titleWords.length ? 1 : 0)
    if (nextLength > 60) break
    titleWords.push(word)
    titleLength = nextLength
  }

  const title = titleWords.join(' ') || firstSentence
  return title || fallback
}

function buildPreviewFromContent(content) {
  const text = normalizeText(content)
  if (!text) return 'No content yet.'

  const firstLine = text.split(/\r?\n/)[0] || text
  const sentences = firstLine.split(/(?<=[.!?])\s+/)
  return sentences[0] || firstLine
}

function formatSidebarDate(value) {
  if (!value) return 'Today'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Today'

  const now = new Date()
  const diffDays = Math.round((now.setHours(0, 0, 0, 0) - date.setHours(0, 0, 0, 0)) / 86400000)

  if (diffDays === 0) {
    return `Today, ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
  }

  if (diffDays === 1) {
    return 'Yesterday'
  }

  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function isShortDisplayAnswer(answer) {
  const text = normalizeText(answer)
  if (!text) return false
  if (text.length > 120) return false
  return !text.includes('\n') && !text.includes('\r')
}

function SourceIcon({ type }) {
  const isNote = type === 'note'

  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className="source-svg" focusable="false">
      {isNote ? (
        <path d="M5 2.75A1.75 1.75 0 0 1 6.75 1h3.5A2.25 2.25 0 0 1 12.5 3.25v9.5A2.25 2.25 0 0 1 10.25 15h-3.5A1.75 1.75 0 0 1 5 13.25V2.75Zm1.75-.5a.75.75 0 0 0-.75.75v10.5c0 .41.34.75.75.75h3.5c.41 0 .75-.34.75-.75v-9.5h-2.25A1.75 1.75 0 0 1 6.5 3.25V2.25h.25Zm2 3.5h2v1h-2v-1Zm-2 2.5h4v1h-4v-1Zm0 2.5h3v1h-3v-1Z" />
      ) : (
        <path d="M3.5 2.25A1.75 1.75 0 0 1 5.25 0h4.5A1.75 1.75 0 0 1 11.5 1.75V12.5A1.5 1.5 0 0 1 10 14h-5a1.5 1.5 0 0 1-1.5-1.5v-10Zm1.75-.5a.75.75 0 0 0-.75.75v10.5c0 .28.22.5.5.5h5.5a.5.5 0 0 0 .5-.5V1.75a.75.75 0 0 0-.75-.75h-4.5Zm1.5 2.75h2.5v1h-2.5v-1Zm0 2.5h4.5v1h-4.5v-1Zm0 2.5h3.5v1h-3.5v-1Z" />
      )}
    </svg>
  )
}

function App() {
  const [items, setItems] = useState([])
  const [mode, setMode] = useState('note')
  const [noteInput, setNoteInput] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [question, setQuestion] = useState('')
  const [conversation, setConversation] = useState([
    {
      role: 'assistant',
      answer: 'Hi! I can help you search your saved notes and URLs. Ask me anything about your knowledge base.',
      sources: [],
    },
  ])
  const [loading, setLoading] = useState({ items: false, ingest: false, query: false })
  const [error, setError] = useState('')
  const threadRef = useRef(null)

  const loadItems = async () => {
    setLoading((prev) => ({ ...prev, items: true }))
    try {
      const data = await apiRequest('/api/items/')
      setItems(data)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading((prev) => ({ ...prev, items: false }))
    }
  }

  useEffect(() => {
    loadItems()
  }, [])

  useEffect(() => {
    const threadEl = threadRef.current
    if (!threadEl) return
    threadEl.scrollTo({ top: threadEl.scrollHeight, behavior: 'smooth' })
  }, [conversation, loading.query])

  const handleAddNote = async (event) => {
    event.preventDefault()
    if (!noteInput.trim()) {
      setError('Please add some note content first.')
      return
    }

    setLoading((prev) => ({ ...prev, ingest: true }))
    try {
      await apiRequest('/api/ingest/', {
        method: 'POST',
        body: JSON.stringify({
          source_type: 'note',
          content: noteInput,
        }),
      })
      setNoteInput('')
      await loadItems()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading((prev) => ({ ...prev, ingest: false }))
    }
  }

  const handleAddUrl = async (event) => {
    event.preventDefault()
    if (!urlInput.trim()) {
      setError('Please enter a URL.')
      return
    }

    setLoading((prev) => ({ ...prev, ingest: true }))
    try {
      await apiRequest('/api/ingest/', {
        method: 'POST',
        body: JSON.stringify({
          source_type: 'url',
          url: urlInput,
        }),
      })
      setUrlInput('')
      await loadItems()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading((prev) => ({ ...prev, ingest: false }))
    }
  }

  const runQuestion = async (prompt) => {
    const nextQuestion = (prompt || question).trim()
    if (!nextQuestion) {
      setError('Please ask a question about the saved content.')
      return
    }

    const history = conversation
      .filter((turn) => (turn.text || turn.answer) && turn.role)
      .map((turn) => ({
        role: turn.role,
        content: turn.text || turn.answer || '',
      }))
      .filter((turn) => turn.content)

    setQuestion('')
    setLoading((prev) => ({ ...prev, query: true }))
    try {
      const result = await apiRequest('/api/query/', {
        method: 'POST',
        body: JSON.stringify({
          question: nextQuestion,
          messages: history,
          provider: 'openai',
        }),
      })

      const assistantReply = {
        answer: result.answer || 'No answer found.',
        sources: result.sources || [],
      }

      setConversation((prev) => [...prev, { role: 'user', text: nextQuestion }, { role: 'assistant', ...assistantReply }])
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading((prev) => ({ ...prev, query: false }))
    }
  }

  const handleAskQuestion = async (event) => {
    event.preventDefault()
    if (!question.trim()) return
    await runQuestion(question)
  }

  const handleComposerKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!question.trim()) return
      runQuestion(question)
    }
  }

  const handleCopyAnswer = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch (error) {
      setError('Copy failed. Please copy the answer manually.')
    }
  }

  const handleSourceClick = (source) => {
    if (!source || !source.id) return
    const target = document.querySelector(`[data-item-id="${source.id}"]`)
    if (!target) return

    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    target.classList.add('is-highlighted')
    window.setTimeout(() => target.classList.remove('is-highlighted'), 1500)
  }

  const sendDisabled = !question.trim() || loading.query
  const showSuggestions = conversation.length <= 1

  return (
    <div className="knowledge-app">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">◌</div>
          <div className="brand-title">Knowledge Inbox</div>
        </div>
        <div className="workspace-label">Private workspace</div>

        <div className="mode-toggle" aria-label="Entry type selector">
          <button
            type="button"
            className={mode === 'note' ? 'mode-button active' : 'mode-button'}
            onClick={() => setMode('note')}
          >
            Note
          </button>
          <button
            type="button"
            className={mode === 'url' ? 'mode-button active' : 'mode-button'}
            onClick={() => setMode('url')}
          >
            Link
          </button>
        </div>

        {mode === 'note' ? (
          <form onSubmit={handleAddNote} className="sidebar-form">
            <textarea
              value={noteInput}
              onChange={(event) => setNoteInput(event.target.value)}
              placeholder="Write a note, meeting summary or reference"
            />
            <button type="submit" disabled={loading.ingest} className="primary-button">
              {loading.ingest ? 'Saving...' : 'Save note'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleAddUrl} className="sidebar-form">
            <input
              type="url"
              value={urlInput}
              onChange={(event) => setUrlInput(event.target.value)}
              placeholder="Paste a URL"
            />
            <button type="submit" disabled={loading.ingest} className="primary-button">
              {loading.ingest ? 'Fetching...' : 'Save link'}
            </button>
          </form>
        )}

        <div className="library-header">
          <span>Library</span>
          <button type="button" className="mini-button" onClick={loadItems} aria-label="Refresh items">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M12 3a9 9 0 0 1 6.86 2.93l1.14 1.07H16.5a1 1 0 1 1 0 2h4.5a1 1 0 0 1 1 1v-4.5a1 1 0 1 1-2 0V5.58l-1.3-1.22A11 11 0 0 0 12 1a1 1 0 1 1 0 2Zm-8.86 7.07L1 9.14V13.5a1 1 0 1 1-2 0v-4.5a1 1 0 0 1 1-1h4.5a1 1 0 1 1 0 2H3.28l1.3 1.22A11 11 0 0 0 12 23a1 1 0 1 1 0-2A9 9 0 0 1 3.14 10.07Z" fill="currentColor" />
            </svg>
          </button>
        </div>

        <div className="saved-list">
          {loading.items ? (
            <div className="list-empty">Loading…</div>
          ) : items.length === 0 ? (
            <div className="list-empty">No saved items yet</div>
          ) : (
            items.map((item) => {
              const itemTitle = item.title || buildTitleFromContent(item.content, 'Untitled note')
              const preview = buildPreviewFromContent(item.content)

              return (
                <button
                  key={item.id}
                  type="button"
                  className="saved-item"
                  data-item-id={item.id}
                  onClick={() => handleSourceClick({ id: item.id })}
                >
                  <div className="saved-meta">
                    <span>{item.source_type === 'note' ? 'Note' : 'Link'}</span>
                    <time>{formatSidebarDate(item.created_at)}</time>
                  </div>
                  <div className="saved-title">{itemTitle}</div>
                  <div className="saved-preview">{preview}</div>
                </button>
              )
            })
          )}
        </div>
      </aside>

      <main className="workspace">
        <div className="thread-panel" ref={threadRef}>
          <div className="workspace-inner">
            <h1>Ask anything you have saved.</h1>
            <p>
              Answers come from your notes and links, with the source shown next to each one.
            </p>

            <div className="chat-stack">
              {conversation.map((message, index) => {
                if (message.role === 'user') {
                  return (
                    <div key={`user-${index}`} className="user-message">
                      <div className="user-bubble">{message.text}</div>
                    </div>
                  )
                }

                const source = message.sources && message.sources[0]
                const answerTextClass = isShortDisplayAnswer(message.answer) ? 'answer-text display' : 'answer-text body'

                return (
                  <div key={`assistant-${index}`} className="answer-shell">
                    <div className="answer-header-row">
                      <div className="answer-label">Answer</div>
                      <button type="button" className="copy-button" onClick={() => handleCopyAnswer(message.answer)}>
                        Copy
                      </button>
                    </div>

                    <div className={answerTextClass}>{message.answer}</div>

                    {source ? (
                      <>
                        <div className="source-label">Source</div>
                        <button type="button" className="source-box" onClick={() => handleSourceClick(source)}>
                          <div className="source-icon">
                            <SourceIcon type={source.source_type || 'note'} />
                          </div>
                          <div className="source-copy">
                            <div className="source-title">{source.title || 'Saved item'}</div>
                            <div className="source-snippet">{source.snippet || source.content || 'Saved item details'}</div>
                            <div className="source-meta">
                              {source.source_type === 'note' ? 'Note' : 'Link'} · {formatSidebarDate(source.created_at || new Date().toISOString())}
                            </div>
                          </div>
                        </button>
                      </>
                    ) : null}
                  </div>
                )
              })}

              {loading.query ? <div className="thread-loading">Searching your notes…</div> : null}
            </div>
          </div>
        </div>

        <div className="composer-wrap">
          {showSuggestions ? (
            <div className="composer-options">
              {suggestedQuestions.map((prompt) => (
                <button key={prompt} type="button" className="secondary-chip" onClick={() => runQuestion(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          ) : null}

          <form className="composer" onSubmit={handleAskQuestion}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask a question about your saved content"
              rows={1}
            />
            <button type="submit" className="send-button" aria-label="Send question" disabled={sendDisabled}>
              ↑
            </button>
          </form>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}
      </main>
    </div>
  )
}

export default App
