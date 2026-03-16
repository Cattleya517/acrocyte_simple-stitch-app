import { useState, useRef, useEffect } from 'react'

const MAX_LOG_LINES = 500

function App(): React.JSX.Element {
  const [folderPath, setFolderPath] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const handleSelectFolder = async (): Promise<void> => {
    const selectedDir = await window.api.selectDir()
    setFolderPath(selectedDir)
    setLogs([])
  }

  const handleStitch = (): void => {
    if (!folderPath) {
      alert('Choose a folder to stitch first')
      return
    }
    if (isRunning) return

    setIsRunning(true)
    setLogs(['Initializing...'])
    window.api.removeAshlarListeners()

    window.api.onAshlarLog((line) => {
      setLogs((prev) => {
        const next = [...prev, line]
        return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next
      })
    })

    window.api.onAshlarDone((code) => {
      setIsRunning(false)
      setLogs((prev) => [...prev, code === 0 ? 'Done!' : `Process exited with code ${code}`])
    })

    window.api.runAshlar(folderPath)
  }

  const handleCancel = (): void => {
    window.api.cancelAshlar()
    setIsRunning(false)
    setLogs((prev) => [...prev, 'Cancelled.'])
  }

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'instant' })
  }, [logs])

  return (
    <div className="min-h-screen bg-[#FFEDC7] flex flex-col gap-4 p-4">
      <h1 className="self-center font-serif text-xl">Acrocyte Simple Stitch</h1>

      <button
        className="active:scale-95 active:brightness-90 transition font-serif bg-blue-300 rounded px-4 py-2 w-fit self-center disabled:opacity-50"
        onClick={handleSelectFolder}
        disabled={isRunning}
      >
        Select Folder
      </button>

      <p className="font-serif self-center">{folderPath ?? 'No folder selected'}</p>

      {isRunning ? (
        <button
          className="active:scale-95 active:brightness-90 transition font-serif bg-red-300 rounded px-4 py-2 w-fit self-center"
          onClick={handleCancel}
        >
          Cancel
        </button>
      ) : (
        <button
          className="active:scale-95 active:brightness-90 transition font-serif bg-orange-300 rounded px-4 py-2 w-fit self-center disabled:opacity-50"
          onClick={handleStitch}
          disabled={!folderPath}
        >
          Start Stitching
        </button>
      )}

      <h2 className="font-serif self-start">Progress:</h2>
      <div className="bg-[#F8F3E1] text-black font-mono text-sm p-3 rounded h-48 overflow-y-auto">
        {logs.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  )
}

export default App
