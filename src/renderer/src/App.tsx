import { useState, useRef, useEffect } from 'react'

function App(): React.JSX.Element {
  const [folderPath, setFolderPath] = useState<string | null>(null)
  const [version, setVersion] = useState<string>('0.1.0')
  const [logs, setLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  const handleSelectFolder = async (): Promise<void> => {
    const seletedDir = await window.api.selectDir()
    console.log(`Dir selected: ${seletedDir}`)
    setFolderPath(seletedDir)

    setLogs([])
    }

  const handleStitch = (): void => {
    if (folderPath) {
      setLogs(['Initializing...'])
      window.api.removeAshlarListeners()
      window.api.onAshlarLog((line) => {
        setLogs((prev) => [...prev, line])
      })
      window.api.runAshlar(folderPath)
      console.log(`Running Ashlar on: ${folderPath}`)
    } else {
      alert('Choose a folder to stitch first')
    }
  }
  useEffect(() => {
    logsEndRef.current?.scrollIntoView()
  }, [logs])
  return (
    <div className="min-h-screen bg-[#FFEDC7] flex flex-col gap-4 p-4">
      <h1 className="self-center font-serif text-xl">Acrocyte Simple Stitch</h1>
      <button
        className="active:scale-95 active:brightness-90 transition font-serif bg-blue-300 rounded px-4 py-2 w-fit self-center"
        onClick={() => handleSelectFolder()}
      >
        Select Folder
      </button>
      <h1 className="font-serif self-center">Directory: {folderPath} </h1>
      <button
        className="active:scale-95 active:brightness-90 transition font-serif bg-orange-300 rounded px-4 py-2 w-fit self-center"
        onClick={() => handleStitch()}
      >
        Start Stitching
      </button>
      <h2 className="font-serif self-left">Progress:</h2>
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
