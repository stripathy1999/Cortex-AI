import React, { useState, useEffect, useRef } from "react"
import { useQuery } from "react-query"
import ScreenshotQueue from "../components/Queue/ScreenshotQueue"
import {
  Toast,
  ToastTitle,
  ToastDescription,
  ToastVariant,
  ToastMessage
} from "../components/ui/toast"
import QueueCommands from "../components/Queue/QueueCommands"

interface QueueProps {
  setView: React.Dispatch<React.SetStateAction<"queue" | "solutions" | "debug">>
}

const Queue: React.FC<QueueProps> = ({ setView }) => {
  const [toastOpen, setToastOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState<ToastMessage>({
    title: "",
    description: "",
    variant: "neutral"
  })

  const contentRef = useRef<HTMLDivElement>(null)

  const [chatInput, setChatInput] = useState("")
  const [originalHistory, setOriginalHistory] = useState<string[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const chatMessagesEndRef = useRef<HTMLDivElement>(null)
  const [agentStatus, setAgentStatus] = useState<string | null>(null)
  const [isAgentRunning, setIsAgentRunning] = useState(false)
  // Display text: show status from agent or fallback when running
  const displayStatus =
    agentStatus ?? (isAgentRunning || chatLoading ? "Agent is thinking…" : null)
  // Phase for UI color: thinking (blue), executing (amber), done (green), ready (neutral)
  const agentPhase =
    !displayStatus && !isAgentRunning && !chatLoading
      ? "ready"
      : /done|finished|stopped|going to stop/i.test(displayStatus ?? "")
        ? "done"
        : /executing|executing —/i.test(displayStatus ?? "")
          ? "executing"
          : "thinking"

  const barRef = useRef<HTMLDivElement>(null)
  const agentTimeoutsRef = useRef<NodeJS.Timeout[]>([])
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  const { data: screenshots = [], refetch } = useQuery<Array<{ path: string; preview: string }>, Error>(
    ["screenshots"],
    async () => {
      try {
        const existing = await window.electronAPI.getScreenshots()
        return existing
      } catch (error) {
        console.error("Error loading screenshots:", error)
        showToast("Error", "Failed to load existing screenshots", "error")
        return []
      }
    },
    {
      staleTime: Infinity,
      cacheTime: Infinity,
      refetchOnWindowFocus: true,
      refetchOnMount: true
    }
  )

  const showToast = (
    title: string,
    description: string,
    variant: ToastVariant
  ) => {
    setToastMessage({ title, description, variant })
    setToastOpen(true)
  }

  const handleDeleteScreenshot = async (index: number) => {
    const screenshotToDelete = screenshots[index]

    try {
      const response = await window.electronAPI.deleteScreenshot(
        screenshotToDelete.path
      )

      if (response.success) {
        refetch()
      } else {
        console.error("Failed to delete screenshot:", response.error)
        showToast("Error", "Failed to delete the screenshot file", "error")
      }
    } catch (error) {
      console.error("Error deleting screenshot:", error)
    }
  }

  const handleTogglePopup = () => { 
    setIsChatOpen(!isChatOpen)
  }

  const handleChatSubmit = async (useShadowTrigger = false) => {
    if (!chatInput.trim()) return

    const userMessage = chatInput
    setChatInput("")

    // Stop any existing agent thread first to prevent "active thread" errors
    try {
      await window.electronAPI.stopAgent()
    } catch (err) {
      console.log('No active agent to stop, continuing...')
    }

    // Clear previous history and start fresh
    setOriginalHistory([])

    // Clear previous timeouts
    agentTimeoutsRef.current.forEach(clearTimeout)
    agentTimeoutsRef.current = []

    // Now start the new agent request
    setChatLoading(true)
    setIsAgentRunning(true)
    setAgentStatus(useShadowTrigger ? "Shadow trigger..." : "Agent is thinking...")

    try {
      const response = useShadowTrigger
        ? await window.electronAPI.sendShadowTrigger(userMessage)
        : await window.electronAPI.sendChatPrompt(userMessage)
      console.log("Message forwarded through server:", response)
    } catch (err) {
      console.error('Error sending chat message:', err)
      setAgentStatus(null)
      setChatLoading(false)
      setIsAgentRunning(false)
      setOriginalHistory((history) => [...history, `Error: ${String(err)}`])
    }
  }

  const handlePauseAgent = async () => {
    if (isAgentRunning) {
      // Stop the agent completely (changed from pause to stop for better reliability)
      try {
        await window.electronAPI.stopAgent()
        setIsAgentRunning(false)
        setAgentStatus(null)
        setChatLoading(false)

        // Clear all pending timeouts
        agentTimeoutsRef.current.forEach(clearTimeout)
        agentTimeoutsRef.current = []

        setOriginalHistory((history) => [...history, "Agent stopped by user."])
      } catch (err) {
        console.error('Error stopping agent:', err)
      }
    }
  }

  const handleStopAgent = async () => {
    // Stop the agent completely - send stop request to Agent S
    try {
      await window.electronAPI.stopAgent()
      setIsAgentRunning(false)
      setAgentStatus(null)
      setChatLoading(false)

      // Clear all pending timeouts
      agentTimeoutsRef.current.forEach(clearTimeout)
      agentTimeoutsRef.current = []

      setOriginalHistory((history) => [...history, "Agent stopped by user."])
    } catch (err) {
      console.error('Error stopping agent:', err)
    }
  }

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (isChatOpen && chatMessagesEndRef.current) {
      chatMessagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [originalHistory, isChatOpen])

  // Listen for current action updates from Flask server
  useEffect(() => {
    const unsubscribe = window.electronAPI.onCurrentActionUpdate((action) => {
      const textSummary =
        (typeof action?.text_summary === "string" && action.text_summary.trim()) ||
        (typeof action?.voice_summary === "string" && action.voice_summary.trim()) ||
        null

      const originalText =
        (typeof action?.original === "string" && action.original.trim()) ||
        null

      setAgentStatus(textSummary)
      setIsAgentRunning(true)

      // Add the original text to history (shown in expanded view)
      const historyEntry = originalText ?? textSummary
      if (historyEntry) {
        setOriginalHistory((history) => [...history, historyEntry])
      }

      // Check if this is a completion message
      const normalized = textSummary?.toLowerCase() ?? ""
      if (
        normalized.includes("completed") ||
        normalized.includes("finished") ||
        normalized.includes("done") ||
        normalized.includes("stopped")
      ) {
        // Reset state after a short delay to show the completion message
        const timeout = setTimeout(() => {
          setIsAgentRunning(false)
          setAgentStatus(null)
          setChatLoading(false)
        }, 2000)
        agentTimeoutsRef.current.push(timeout)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [])


  useEffect(() => {
    const updateDimensions = () => {
      if (contentRef.current) {
        const contentHeight = contentRef.current.scrollHeight
        const contentWidth = contentRef.current.scrollWidth
        window.electronAPI.updateContentDimensions({
          width: contentWidth,
          height: contentHeight
        })
      }
    }

    const resizeObserver = new ResizeObserver(updateDimensions)
    if (contentRef.current) {
      resizeObserver.observe(contentRef.current)
    }
    updateDimensions()

    const cleanupFunctions = [
      window.electronAPI.onScreenshotTaken(() => refetch()),
      window.electronAPI.onResetView(() => refetch()),
      window.electronAPI.onSolutionError((error: string) => {
        showToast(
          "Processing Failed",
          "There was an error processing your screenshots.",
          "error"
        )
        setView("queue")
        console.error("Processing error:", error)
      }),
      window.electronAPI.onProcessingNoScreenshots(() => {
        showToast(
          "No Screenshots",
          "There are no screenshots to process.",
          "neutral"
        )
      })
    ]

    return () => {
      resizeObserver.disconnect()
      cleanupFunctions.forEach((cleanup) => cleanup())
    }
  }, [])

  const handleChatInputChange = (value: string) => {
    setChatInput(value)
  }

  // Track mouse position for close button click-through
  useEffect(() => {
    if (!isChatOpen) return

    let rafId: number | null = null

    const handleMouseMove = (e: MouseEvent) => {
      if (rafId) return

      rafId = requestAnimationFrame(() => {
        if (closeButtonRef.current) {
          const rect = closeButtonRef.current.getBoundingClientRect()
          const isOverButton =
            e.clientX >= rect.left &&
            e.clientX <= rect.right &&
            e.clientY >= rect.top &&
            e.clientY <= rect.bottom

          if (isOverButton) {
            window.electronAPI?.setWindowClickThrough(false)
          }
        }
        rafId = null
      })
    }

    document.addEventListener('mousemove', handleMouseMove)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [isChatOpen])


  const phaseTint =
    agentPhase === "thinking"
      ? "rgba(59, 130, 246, 0.08)"
      : agentPhase === "executing"
        ? "rgba(245, 158, 11, 0.08)"
        : agentPhase === "done"
          ? "rgba(16, 185, 129, 0.08)"
          : "transparent"

  return (
    <div
      ref={barRef}
      style={{
        position: "relative",
        width: "100%",
        pointerEvents: "none",
        backgroundColor: phaseTint,
        borderRadius: "1rem",
        transition: "background-color 0.4s ease",
      }}
      className="select-none min-h-[120px]"
    >
      <div className="bg-transparent w-full" style={{ pointerEvents: "none" }}>
        <div className="px-1 py-4" style={{ pointerEvents: "none" }}>
          <div style={{ pointerEvents: "auto" }}>
            <Toast
              open={toastOpen}
              onOpenChange={setToastOpen}
              variant={toastMessage.variant}
              duration={3000}
            >
              <ToastTitle>{toastMessage.title}</ToastTitle>
              <ToastDescription>{toastMessage.description}</ToastDescription>
            </Toast>
          </div>
          <div style={{ pointerEvents: "auto" }}>
            <QueueCommands
              chatInput={chatInput}
              onChatInputChange={handleChatInputChange}
              onChatSubmit={(useShadow) => handleChatSubmit(useShadow)}
              chatLoading={chatLoading}
              agentStatus={displayStatus}
              agentPhase={agentPhase}
              isAgentRunning={isAgentRunning || chatLoading}
              onPauseAgent={handlePauseAgent}
              isChatOpen={isChatOpen}
              onTogglePopup={handleTogglePopup}
              onVoiceTranscript={(text) => {
                handleChatInputChange(text)
                handleChatSubmit(false)
              }}
              onVisionFinger={(x, y) => window.electronAPI?.sendCursorMove(x, y)}
            />
          </div>

          {/* What the agent is thinking – tap/click anywhere or the button to see full log */}
          {(isAgentRunning || chatLoading) && displayStatus && !isChatOpen && (
            <div
              role="button"
              tabIndex={0}
              onClick={() => setIsChatOpen(true)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setIsChatOpen(true); } }}
              className="mt-3 w-full max-w-2xl mx-auto rounded-xl border-l-4 cursor-pointer transition-all duration-300 shadow-lg px-4 py-3 hover:opacity-95 active:scale-[0.99] select-none"
              style={{
                pointerEvents: "auto",
                borderLeftColor: agentPhase === "thinking" ? "#3b82f6" : agentPhase === "executing" ? "#f59e0b" : agentPhase === "done" ? "#10b981" : "#64748b",
                backgroundColor: agentPhase === "thinking" ? "rgba(59, 130, 246, 0.2)" : agentPhase === "executing" ? "rgba(245, 158, 11, 0.2)" : agentPhase === "done" ? "rgba(16, 185, 129, 0.2)" : "rgba(30, 41, 59, 0.7)",
                borderTopRightRadius: "0.75rem",
                borderBottomRightRadius: "0.75rem",
                zIndex: 10,
              }}
            >
              <p className="text-[10px] uppercase tracking-widest font-semibold mb-1" style={{ color: agentPhase === "thinking" ? "#93c5fd" : agentPhase === "executing" ? "#fcd34d" : agentPhase === "done" ? "#6ee7b7" : "#94a3b8" }}>
                {agentPhase === "thinking" ? "● Thinking" : agentPhase === "executing" ? "● Executing" : agentPhase === "done" ? "● Done" : "Agent"}
              </p>
              <p className="text-sm text-white font-medium truncate" title={displayStatus}>{displayStatus}</p>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setIsChatOpen(true); }}
                className="mt-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/15 hover:bg-white/25 text-slate-200 border border-white/20 transition-colors"
                style={{ pointerEvents: "auto" }}
              >
                See full log
              </button>
            </div>
          )}
          {/* Full log when expanded */}
          {isChatOpen && (
            <div className="mt-4 w-full max-w-2xl mx-auto liquid-glass chat-container p-4 flex flex-col" style={{ pointerEvents: "auto", zIndex: 10 }}>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs text-white/70 font-medium">
                What the agent is thinking
              </h3>
              <button
                ref={closeButtonRef}
                onClick={() => setIsChatOpen(false)}
                className="text-white/50 hover:text-white/90 transition-colors text-xs"
                style={{ pointerEvents: "auto" }}
              >
                ✕
              </button>
            </div>
            {displayStatus && (
              <div
                className={`text-xs mb-2 pb-2 border-b-2 font-medium ${
                  agentPhase === "thinking"
                    ? "text-blue-300 border-blue-500/40"
                    : agentPhase === "executing"
                      ? "text-amber-300 border-amber-500/40"
                      : agentPhase === "done"
                        ? "text-emerald-400 border-emerald-500/40"
                        : "text-slate-300 border-white/10"
                }`}
              >
                <span>Currently: </span>
                <span>{displayStatus}</span>
              </div>
            )}
            <div className="flex-1 overflow-y-auto max-h-64 min-h-[120px] font-mono space-y-1.5" style={{ pointerEvents: "auto" }}>
              {originalHistory.length === 0 ? (
                <div className="text-sm text-white/50 mt-8">
                  Agent steps and thoughts will appear here. Click the bar to open this view.
                  <br />
                  <span className="text-xs text-white/30">Type a command above to start.</span>
                </div>
              ) : (
                originalHistory.map((text, idx) => {
                  const phase =
                    /done|finished|stopped|stop/i.test(text) ? "done" : /executing|executing —/i.test(text) ? "executing" : "thinking"
                  const colorClass =
                    phase === "thinking" ? "text-blue-200/90" : phase === "executing" ? "text-amber-200/90" : "text-emerald-200/90"
                  return (
                    <div
                      key={idx}
                      className={`text-xs leading-relaxed ${colorClass}`}
                      style={{ wordBreak: "break-word", whiteSpace: "pre-wrap" }}
                    >
                      {text}
                    </div>
                  )
                })
              )}
              {chatLoading && (
                <div className="text-blue-300/80 text-xs mb-2 flex items-center gap-2">
                  <span className="animate-pulse">●</span>
                  <span className="animate-pulse animation-delay-200">●</span>
                  <span className="animate-pulse animation-delay-400">●</span>
                  <span>Agent is thinking...</span>
                </div>
              )}
              <div ref={chatMessagesEndRef} />
            </div>
          </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Queue
