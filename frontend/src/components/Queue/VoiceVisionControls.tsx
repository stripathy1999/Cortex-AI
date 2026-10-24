/**
 * Voice + Vision controls for Shadow-OS.
 * - Voice: Web Speech API for speech-to-text
 * - Vision: Webcam capture + finger detection → cursor movement
 */
import React, { useState, useRef, useEffect } from "react"

interface VoiceVisionControlsProps {
  onTranscript: (text: string) => void
  onVisionFinger?: (x: number, y: number) => void
  disabled?: boolean
}

export const VoiceVisionControls: React.FC<VoiceVisionControlsProps> = ({
  onTranscript,
  onVisionFinger,
  disabled = false,
}) => {
  const [isListening, setIsListening] = useState(false)
  const [isVisionOn, setIsVisionOn] = useState(false)
  const [visionError, setVisionError] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const frameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Voice: Web Speech API
  const startListening = () => {
    if (disabled) return
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      console.error("Web Speech API not supported")
      return
    }
    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      const transcript = e.results[0][0].transcript
      onTranscript(transcript)
    }
    recognition.onerror = () => setIsListening(false)
    recognition.onend = () => setIsListening(false)
    recognition.start()
    recognitionRef.current = recognition
    setIsListening(true)
  }

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    setIsListening(false)
  }

  // Vision: Webcam + finger detection
  const startVision = async () => {
    if (disabled) return
    setVisionError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      streamRef.current = stream
      setIsVisionOn(true)
      // Start frame capture loop after video is ready (use setTimeout to wait for render)
      setTimeout(() => {
        if (videoRef.current && streamRef.current) {
          videoRef.current.srcObject = streamRef.current
        }
        frameIntervalRef.current = setInterval(captureAndDetect, 100) // ~10 fps
      }, 100)
    } catch (e: any) {
      setVisionError(e?.message || "Could not access webcam")
    }
  }

  const stopVision = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current)
      frameIntervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setIsVisionOn(false)
    setVisionError(null)
  }

  const captureAndDetect = async () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !streamRef.current || video.readyState !== 4) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    ctx.drawImage(video, 0, 0)
    const dataUrl = canvas.toDataURL("image/jpeg", 0.8)
    const base64 = dataUrl.split(",")[1]
    if (!base64) return

    try {
      const result = await window.electronAPI?.sendVisionFrame(base64)
      if (result?.screen?.x != null && result?.screen?.y != null && onVisionFinger) {
        onVisionFinger(result.screen.x, result.screen.y)
      }
    } catch {
      // Vision service may not be running
    }
  }

  useEffect(() => {
    return () => {
      stopListening()
      stopVision()
    }
  }, [])

  return (
    <div className="flex items-center gap-1">
      {/* Voice button */}
      <button
        onClick={isListening ? stopListening : startListening}
        disabled={disabled}
        className={`p-2 rounded transition-colors ${isListening ? "text-red-400 bg-red-500/20" : "text-slate-400 hover:text-green-400"}`}
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        title={isListening ? "Stop listening" : "Voice input"}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.83V20c0 .55.45 1 1 1s1-.45 1-1v-2.18c3.02-.48 5.42-2.83 5.91-5.83.1-.6-.39-1.14-1-1.14z" />
        </svg>
      </button>

      {/* Vision button */}
      <button
        onClick={isVisionOn ? stopVision : startVision}
        disabled={disabled}
        className={`p-2 rounded transition-colors ${isVisionOn ? "text-amber-400 bg-amber-500/20" : "text-slate-400 hover:text-amber-400"}`}
        style={{ WebkitAppRegion: "no-drag" } as React.CSSProperties}
        title={isVisionOn ? "Stop vision" : "Finger tracking (move cursor)"}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
          <circle cx="12" cy="13" r="4" />
        </svg>
      </button>

      {/* Video preview + hidden canvas for capture */}
      {isVisionOn && (
        <>
          <div className="fixed bottom-12 right-4 w-40 h-30 border border-amber-500/50 rounded overflow-hidden bg-black z-50 shadow-lg">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover"
            />
          </div>
          <canvas ref={canvasRef} width={640} height={480} className="hidden" />
        </>
      )}

      {visionError && (
        <span className="text-xs text-red-400">{visionError}</span>
      )}
    </div>
  )
}
