import React, { useState, useEffect } from "react"
import { VoiceVisionControls } from "./VoiceVisionControls"

interface ContactLink {
  platform: string
  label: string
  instruction: string
  value: string
}

export type AgentPhase = "ready" | "thinking" | "executing" | "done"

interface QueueCommandsProps {
  chatInput: string
  onChatInputChange: (value: string) => void
  onChatSubmit: (useShadowTrigger?: boolean) => void
  chatLoading: boolean
  agentStatus: string | null
  agentPhase?: AgentPhase
  isAgentRunning: boolean
  onPauseAgent: () => void
  isChatOpen: boolean
  onTogglePopup: () => void
  onVoiceTranscript?: (text: string) => void
  onVisionFinger?: (x: number, y: number) => void
}

const phaseBarClasses: Record<AgentPhase, string> = {
  ready: "border-slate-500/70 bg-slate-800/50",
  thinking: "border-blue-400 shadow-[0_0_16px_rgba(59,130,246,0.4)] bg-blue-900/50",
  executing: "border-amber-400 shadow-[0_0_16px_rgba(245,158,11,0.4)] bg-amber-900/50",
  done: "border-emerald-400 shadow-[0_0_16px_rgba(16,185,129,0.35)] bg-emerald-900/50",
}

const phaseDotClasses: Record<AgentPhase, string> = {
  ready: "text-slate-400",
  thinking: "text-blue-400 animate-pulse",
  executing: "text-amber-400 animate-pulse",
  done: "text-emerald-400",
}

const QueueCommands: React.FC<QueueCommandsProps> = ({
  chatInput,
  onChatInputChange,
  onChatSubmit,
  chatLoading,
  agentStatus,
  agentPhase = "ready",
  isAgentRunning,
  onPauseAgent,
  onTogglePopup,
  onVoiceTranscript,
  onVisionFinger,
}) => {
  const [isInputActive, setIsInputActive] = useState(false)
  const [isGlowing, setIsGlowing] = useState(false)
  const [showPersistentGlow, setShowPersistentGlow] = useState(false)
  const [showContact, setShowContact] = useState(false)
  const [contactLinks, setContactLinks] = useState<ContactLink[]>([])
  const formRef = React.useRef<HTMLFormElement>(null)

  useEffect(() => {
    if (showContact && contactLinks.length === 0) {
      window.electronAPI?.getContactLinks?.().then((r: any) => {
        setContactLinks(r?.contact_links || [])
      })
    }
  }, [showContact])

  const handleSubmit = (e: React.FormEvent, useShadowTrigger = false) => {
    e.preventDefault()
    if (chatInput.trim() && !chatLoading) {
      setIsGlowing(true)
      setTimeout(() => {
        setIsGlowing(false)
        setShowPersistentGlow(true)
      }, 1500)

      onChatSubmit(useShadowTrigger)
      setIsInputActive(false)
    }
  }

  const handleBarClick = () => {
    if (isAgentRunning) {
      // If agent is running, toggle the popup
      onTogglePopup()
    } else {
      // If agent is not running, activate input
      if (!isInputActive) {
        setIsInputActive(true)
      }
    }
  }

  // Trigger glow animation when agent starts running (for iMessage)
  // and remove persistent glow when agent stops
  React.useEffect(() => {
    if (isAgentRunning) {
      // Agent just started - trigger the animation
      setIsGlowing(true)
      const timeout = setTimeout(() => {
        setIsGlowing(false)
        setShowPersistentGlow(true)
      }, 1500)
      return () => clearTimeout(timeout)
    } else {
      // Agent stopped - remove persistent glow
      setShowPersistentGlow(false)
    }
  }, [isAgentRunning])

  // Track mouse position to enable/disable click-through
  React.useEffect(() => {
    let rafId: number | null = null

    const handleMouseMove = (e: MouseEvent) => {
      if (rafId) return // Debounce using requestAnimationFrame

      rafId = requestAnimationFrame(() => {
        if (formRef.current) {
          const rect = formRef.current.getBoundingClientRect()
          const isOverBar =
            e.clientX >= rect.left &&
            e.clientX <= rect.right &&
            e.clientY >= rect.top &&
            e.clientY <= rect.bottom

          window.electronAPI?.setWindowClickThrough(!isOverBar)
        }
        rafId = null
      })
    }

    document.addEventListener('mousemove', handleMouseMove)

    // Enable click-through initially
    window.electronAPI?.setWindowClickThrough(true)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  return (
    <div className="w-full max-w-2xl mx-auto py-1">
      {/* Contact link - message your PC from phone */}
      <div className="flex justify-center mb-1">
        <button
          type="button"
          onClick={() => setShowContact(!showContact)}
          className="text-slate-500 hover:text-slate-400 text-[10px] transition-colors"
          style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
          title="Contact links to message your PC"
        >
          {showContact ? "▼ Hide contact" : "📱 Message your PC from phone"}
        </button>
      </div>
      {showContact && (
        <div className="mb-2 p-2 rounded bg-slate-800/50 text-xs text-slate-300" style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}>
          <p className="text-slate-400 mb-2">Add these to your phone to control your PC:</p>
          {contactLinks.length === 0 ? (
            <p className="text-slate-500">Loading...</p>
          ) : (
            <ul className="space-y-1">
              {contactLinks.map((link) => (
                <li key={link.platform}>
                  <span className="font-medium text-slate-300">{link.label}:</span> {link.instruction}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <form
        ref={formRef}
        onSubmit={(e) => handleSubmit(e, false)}
        className={`text-xs text-slate-300 liquid-glass-bar draggable-area flex items-center border transition-colors duration-300 ${phaseBarClasses[agentPhase]} ${isGlowing ? 'glowing' : ''} ${showPersistentGlow ? 'glowing-persistent' : ''}`}
      >
        {/* Main Content Area - Clickable, Not Draggable */}
        {isInputActive && !isAgentRunning ? (
          <div className="flex-1 px-4 py-2 text-center" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => onChatInputChange(e.target.value)}
              placeholder="Ask your AI agent..."
              disabled={chatLoading}
              autoFocus
              onBlur={() => !chatInput && setIsInputActive(false)}
              className="w-full px-0 py-0 bg-transparent text-slate-300 placeholder-slate-400 text-xs text-center focus:outline-none focus:ring-0 border-0 transition-all duration-200 disabled:opacity-50"
            />
          </div>
        ) : (
          <div
            onClick={handleBarClick}
            className="flex-1 px-4 py-2 bg-transparent text-slate-300 text-xs cursor-pointer hover:bg-slate-700/30 transition-all duration-200 flex items-center justify-center gap-2"
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          >
            {agentStatus ? (
              <>
                <span className={phaseDotClasses[agentPhase]} title={agentPhase}>●</span>
                <span className={agentPhase === "thinking" ? "text-blue-200" : agentPhase === "executing" ? "text-amber-200" : agentPhase === "done" ? "text-emerald-200" : "text-slate-300"}>
                  {agentStatus}
                </span>
              </>
            ) : (
              <span className="text-slate-400">Agent is ready</span>
            )}
          </div>
        )}

        {/* Voice + Vision controls */}
        {onVoiceTranscript && onVisionFinger && (
          <VoiceVisionControls
            onTranscript={onVoiceTranscript}
            onVisionFinger={onVisionFinger}
            disabled={chatLoading || isAgentRunning}
          />
        )}

        {/* Shadow trigger button - when input is active */}
        {isInputActive && !isAgentRunning && chatInput.trim() && (
          <button
            onClick={(e) => {
              e.preventDefault()
              handleSubmit(e as unknown as React.FormEvent, true)
            }}
            className="px-2 py-2 text-amber-400/80 hover:text-amber-300 transition-colors flex items-center"
            style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
            title="Shadow trigger (Siri-style)"
            type="button"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2z" />
              <path d="M12 6v6l4 2" />
            </svg>
          </button>
        )}

        {/* Stop Button - Only show when agent is running */}
        {isAgentRunning && (
          <button
            onClick={onPauseAgent}
            className="px-2 py-2 text-slate-400 hover:text-red-400 transition-colors flex items-center"
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
            title="Stop Agent"
            type="button"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="3" y="3" width="8" height="8" rx="1"/>
            </svg>
          </button>
        )}

        {/* Drag Handle - Draggable */}
        <div
          className="px-3 py-2 text-slate-500 hover:text-slate-400 transition-colors cursor-move flex items-center"
          title="Drag to move"
        >
          <svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor">
            <circle cx="3" cy="4" r="1.5"/>
            <circle cx="9" cy="4" r="1.5"/>
            <circle cx="3" cy="8" r="1.5"/>
            <circle cx="9" cy="8" r="1.5"/>
            <circle cx="3" cy="12" r="1.5"/>
            <circle cx="9" cy="12" r="1.5"/>
          </svg>
        </div>
      </form>
    </div>
  )
}

export default QueueCommands
