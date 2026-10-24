"""HTTP bridge between Agent S and the UI server."""

from __future__ import annotations

import base64
import io
import logging
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import re
import requests
from flask import Flask, Response, jsonify, request
from dotenv import load_dotenv
import socketio

import audio

from video_call_service import (
    is_video_call_request,
    start_video_call,
)

# Global flag to track audio playback state
_audio_playing = False

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.lower() in {"1", "true", "yes", "on"}


def _show_message_notification(title: str, body: str) -> None:
    """Show a native OS notification so the user gets a ping when a message arrives. Non-blocking."""
    if not body and not title:
        return
    text = (body or title or "New message")[:200]
    title_clean = (title or "Cortex")[:50]
    if platform.system() == "Darwin":
        # macOS: display notification (bounces dock, shows in Notification Center)
        script = f'display notification {repr(text)} with title {repr(title_clean)} sound name "Ping"'
        try:
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    elif platform.system() == "Windows":
        # Windows: toast via PowerShell (optional)
        try:
            ps = f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms"); [System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false); $n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; $n.ShowBalloonTip(4000, {repr(title_clean)}, {repr(text)}, [System.Windows.Forms.ToolTipIcon]::Info)'
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


LOG_LEVEL = os.getenv("BACKEND_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = Flask(__name__)

# Socket.IO client for connecting to call.py service
sio = socketio.Client(logger=True, engineio_logger=False)

# Call service configuration
CALL_SERVICE_HOST = os.getenv("CALL_SERVICE_HOST", "localhost")
CALL_SERVICE_PORT = os.getenv("CALL_SERVICE_PORT", "5002")
CALL_SERVICE_URL = f"http://{CALL_SERVICE_HOST}:{CALL_SERVICE_PORT}"

# Audio format configuration (must mirror backend/call.py defaults)
AUDIO_SAMPLE_RATE = int(os.getenv("CALL_AUDIO_SAMPLE_RATE", "48000"))
AUDIO_CHANNELS = int(os.getenv("CALL_AUDIO_CHANNELS", "2"))
AUDIO_SAMPLE_WIDTH = 2  # bytes (int16 PCM)


def _pcm_to_wav_bytes(pcm_data: bytes) -> bytes:
    """Wrap raw PCM int16 audio data into a WAV container."""
    if not pcm_data:
        raise ValueError("PCM data must not be empty when converting to WAV")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(pcm_data)

    return buffer.getvalue()


class CallManager:
    """Manages WebSocket connection and audio output to call.py service."""

    def __init__(self):
        self.connected = False
        self.call_active = False
        self.playback_in_progress = False

    def connect_to_call_service(self):
        """Establish WebSocket connection to call.py service."""
        if not self.connected:
            try:
                logging.info(f"Connecting to call service at {CALL_SERVICE_URL}")
                sio.connect(CALL_SERVICE_URL, namespaces=["/"])
                self.connected = True
                logging.info("Connected to call service successfully")
            except Exception as e:
                logging.error(f"Failed to connect to call service: {e}")
                raise

    def disconnect_from_call_service(self):
        """Disconnect from call.py service."""
        if self.connected:
            try:
                sio.disconnect()
                self.connected = False
                self.call_active = False
                logging.info("Disconnected from call service")
            except Exception as e:
                logging.error(f"Error disconnecting from call service: {e}")

    def start_call(self):
        """Start a FaceTime call session."""
        if not self.connected:
            self.connect_to_call_service()

        if self.connected:
            # Start recording from the virtual audio device
            sio.emit("start_recording")
            self.call_active = True
            logging.info("Call started, recording initiated")
            return True
        return False

    def end_call(self):
        """End the FaceTime call session."""
        if self.connected and self.call_active:
            # Stop recording
            sio.emit("stop_recording")
            self.call_active = False
            logging.info("Call ended, recording stopped")
            # Keep connection alive for potential future calls
            return True
        return False

    def send_audio_to_output(self, audio_bytes: bytes):
        """Send audio to be played through the FaceTime output device."""
        if not self.connected:
            logging.error("Not connected to call service, cannot send audio")
            return False

        if not self.call_active:
            logging.warning("No active call, cannot send audio")
            return False

        try:
            # Encode audio as base64 for transmission
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            sio.emit("audio_input", {"audio": audio_b64})
            self.playback_in_progress = True
            logging.debug(f"Sent {len(audio_bytes)} bytes of audio to FaceTime output")
            return True
        except Exception as e:
            logging.error(f"Failed to send audio: {e}")
            return False


# Initialize call manager
call_manager = CallManager()


# Socket.IO event handlers
@sio.on("connect")
def on_connect():
    logging.info("Connected to call service via WebSocket")
    call_manager.connected = True


@sio.on("disconnect")
def on_disconnect():
    logging.info("Disconnected from call service")
    call_manager.connected = False
    call_manager.call_active = False


# Audio streaming buffer for accumulating chunks
current_utterance_chunks = []
utterance_start_time = None


@sio.on("utterance_start")
def on_utterance_start(data):
    """Handle start of user utterance."""
    global current_utterance_chunks, utterance_start_time
    current_utterance_chunks = []
    utterance_start_time = data.get("timestamp", time.time())
    logging.info("🎤 UTTERANCE START - Beginning audio stream from call.py")


@sio.on("audio_chunk")
def on_audio_chunk(data):
    """Handle incoming audio chunk during utterance."""
    global current_utterance_chunks
    try:
        audio_b64 = data.get("audio")
        if not audio_b64:
            return

        # Decode and store chunk
        audio_bytes = base64.b64decode(audio_b64)
        current_utterance_chunks.append(audio_bytes)
        # Log first few chunks, then every 10th chunk to avoid spam
        if (
            len(current_utterance_chunks) <= 5
            or len(current_utterance_chunks) % 10 == 0
        ):
            logging.info(
                f"📦 Audio chunk #{len(current_utterance_chunks)}: {len(audio_bytes)} bytes"
            )
    except Exception as e:
        logging.error(f"Error processing audio chunk: {e}")


@sio.on("utterance_end")
def on_utterance_end(data):
    """Handle end of user utterance - process complete audio."""
    global current_utterance_chunks, utterance_start_time
    try:
        duration = data.get("duration", 0)
        total_chunks = data.get("total_chunks", len(current_utterance_chunks))

        if not current_utterance_chunks:
            logging.warning("No audio chunks received for utterance")
            return

        # Combine all chunks into single audio buffer (raw PCM)
        pcm_bytes = b"".join(current_utterance_chunks)
        logging.info(
            f"🏁 UTTERANCE END - Received {len(pcm_bytes)} bytes of PCM from {len(current_utterance_chunks)} chunks, {duration:.2f}s duration"
        )

        # Convert to WAV container for downstream services
        wav_bytes = _pcm_to_wav_bytes(pcm_bytes)
        logging.info(f"🎧 Converted PCM to WAV ({len(wav_bytes)} bytes)")

        # Clear buffer
        current_utterance_chunks = []
        utterance_start_time = None

        # Transcribe the complete utterance
        try:
            transcript = audio.transcribe_audio_bytes(wav_bytes)
            logging.info(f"User said: {transcript}")

            if transcript.strip():
                transcript_lower = transcript.strip().lower()
                # Fast path: "share screen" - use vision to find and click the button (Zoom + Meet)
                if "share screen" in transcript_lower or "share my screen" in transcript_lower:
                    try:
                        response = requests.post(
                            f"{AGENT_S_BASE_URL.rstrip('/')}/api/share_screen",
                            json={},
                            timeout=90,
                        )
                        if response and response.status_code == 200:
                            logging.info("Share screen triggered via vision")
                            try:
                                response_audio = audio.synthesize_speech_from_text("Sharing screen now.")
                                call_manager.send_audio_to_output(response_audio)
                            except Exception:
                                pass
                        else:
                            logging.warning("Share screen API failed: %s", response.status_code if response else "no response")
                    except Exception as e:
                        logging.warning("Share screen failed: %s", e)
                else:
                    # Forward transcript to Agent-S for processing
                    prompt_text = transcript.strip()
                    if call_manager.call_active:
                        prompt_text = (
                            "Voice command during video call. IMPORTANT: Only execute actions if this is a "
                            "clear, actionable task. IGNORE and do not execute: filler words (um, uh, like, "
                            "you know), greetings (hi, hello, hey), thinking aloud, casual chat, or unclear "
                            "requests. For non-tasks, respond briefly without performing any actions.\n\n"
                            f"User said: {prompt_text}\n\n"
                            "If it's a task (e.g. 'share screen', 'open Notepad', 'search Google for X'), "
                            "execute it. If it's just talking, acknowledge briefly and do nothing."
                        )
                    agent_payload = {
                        "prompt": prompt_text,
                        "metadata": {
                            "source": "facetime_call",
                            "call_active": call_manager.call_active,
                            "audio_length_bytes": len(wav_bytes),
                            "duration_seconds": duration,
                            "audio_format": "wav",
                        },
                    }

                    # Send to Agent-S and get response
                    try:
                        response = _safe_post(agent_s_client, "/api/chat", agent_payload)

                        if response and response.status_code == 200:
                            result = response.json()
                            response_text = result.get("response", "")

                            if response_text:
                                logging.info(f"Agent-S response: {response_text[:100]}...")

                                # Convert response to speech and send back through call
                                try:
                                    response_audio = audio.synthesize_speech_from_text(
                                        response_text
                                    )
                                    call_manager.send_audio_to_output(response_audio)
                                    logging.info(
                                        f"Sent {len(response_audio)} bytes of synthesized audio to FaceTime"
                                    )
                                except Exception as e:
                                    logging.error(f"Failed to synthesize speech: {e}")
                        else:
                            # Fallback response if Agent-S is unavailable
                            logging.warning("Agent-S unavailable, using fallback response")
                            fallback_text = "I understand. Let me process that for you."

                            try:
                                fallback_audio = audio.synthesize_speech_from_text(
                                    fallback_text
                                )
                                call_manager.send_audio_to_output(fallback_audio)
                            except Exception as e:
                                logging.error(f"Failed to synthesize fallback speech: {e}")

                    except Exception as e:
                        logging.error(f"Error communicating with Agent-S: {e}")

        except audio.FishAudioError as e:
            logging.error(f"Failed to transcribe audio: {e}")
            # Audio might be too short or corrupted, skip processing
        except Exception as e:
            logging.error(f"Unexpected error during transcription: {e}")

    except Exception as e:
        logging.error(f"Error handling utterance end: {e}", exc_info=True)


@sio.on("utterance_cancelled")
def on_utterance_cancelled(data):
    """Handle cancelled utterance (e.g., too short)."""
    global current_utterance_chunks, utterance_start_time
    reason = data.get("reason", "unknown")
    duration = data.get("duration", 0)
    logging.info(
        f"❌ UTTERANCE CANCELLED - Reason: {reason}, Duration: {duration:.2f}s"
    )
    current_utterance_chunks = []
    utterance_start_time = None


@sio.on("playback_interrupted")
def on_playback_interrupted(data):
    """Handle notification that playback was interrupted by user speech."""
    logging.info("Playback interrupted by user speech")


@sio.on("recording_started")
def on_recording_started(data):
    logging.info("Recording started confirmation received")


@sio.on("recording_stopped")
def on_recording_stopped(data):
    logging.info("Recording stopped confirmation received")


@sio.on("error")
def on_error(data):
    logging.error(f"Error from call service: {data}")


@dataclass
class RemoteClient:
    """HTTP helper wrapping requests with shared configuration."""

    base_url: str
    timeout: float

    def _full_url(self, path: str) -> str:
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        return f"{self.base_url.rstrip('/')}{path}"

    def post_json(self, path: str, payload: Dict[str, Any]) -> requests.Response:
        url = self._full_url(path)
        logging.debug("POST %s", url)
        return requests.post(url, timeout=self.timeout, json=payload)

    def get(self, path: str) -> requests.Response:
        url = self._full_url(path)
        logging.debug("GET %s", url)
        return requests.get(url, timeout=self.timeout)


HTTP_TIMEOUT = float(os.getenv("BACKEND_HTTP_TIMEOUT", "60"))
AGENT_HOST = os.environ["AGENT_HOST"]
AGENT_PORT = os.environ["AGENT_PORT"]
UI_HOST = os.environ["UI_HOST"]
UI_PORT = os.environ["UI_PORT"]
# Message bridge: iMessage on Mac, Telegram/Discord on Windows (windows_message_bridge.py)
IMESSAGE_BRIDGE_HOST = os.getenv("IMESSAGE_BRIDGE_HOST", "127.0.0.1")
IMESSAGE_BRIDGE_PORT = os.getenv("IMESSAGE_BRIDGE_PORT", "8100")
SERVER_HOST = os.environ["SERVER_HOST"]
SERVER_PORT = os.environ["SERVER_PORT"]
AGENT_S_BASE_URL = os.getenv(
    "AGENT_S_BASE_URL",
    f"http://{AGENT_HOST}:{AGENT_PORT}",
)
UI_SERVER_BASE_URL = os.getenv(
    "UI_SERVER_BASE_URL",
    f"http://{UI_HOST}:{UI_PORT}",
)
IMESSAGE_BRIDGE_BASE_URL = os.getenv(
    "IMESSAGE_BRIDGE_BASE_URL",
    f"http://{IMESSAGE_BRIDGE_HOST}:{IMESSAGE_BRIDGE_PORT}",
)
# Windows bridge (Discord/Slack/WhatsApp) – default 8101 so it can run alongside iMessage bridge on 8100
WINDOWS_BRIDGE_PORT = int(os.getenv("WINDOWS_BRIDGE_PORT", "8101"))
WINDOWS_BRIDGE_HOST = os.getenv("WINDOWS_BRIDGE_HOST", IMESSAGE_BRIDGE_HOST)
WINDOWS_MESSAGE_BRIDGE_BASE_URL = os.getenv(
    "WINDOWS_MESSAGE_BRIDGE_BASE_URL",
    f"http://{WINDOWS_BRIDGE_HOST}:{WINDOWS_BRIDGE_PORT}",
)
CURSOR_SERVICE_URL = os.getenv(
    "CURSOR_SERVICE_URL",
    "http://127.0.0.1:5004",
)
VISION_SERVICE_URL = os.getenv(
    "VISION_SERVICE_URL",
    "http://127.0.0.1:5003",
)
STAGEHAND_SERVICE_URL = os.getenv(
    "STAGEHAND_SERVICE_URL",
    "http://127.0.0.1:5005",
)
RESEARCH_SERVICE_URL = os.getenv(
    "RESEARCH_SERVICE_URL",
    "http://127.0.0.1:5006",
)

agent_s_client = RemoteClient(base_url=AGENT_S_BASE_URL, timeout=HTTP_TIMEOUT)
# Stagehand can run 5+ min (STAGEHAND_EXECUTE_TIMEOUT); backend must wait longer
STAGEHAND_HTTP_TIMEOUT = float(os.getenv("STAGEHAND_HTTP_TIMEOUT", "420"))
stagehand_client = RemoteClient(base_url=STAGEHAND_SERVICE_URL, timeout=STAGEHAND_HTTP_TIMEOUT)
RESEARCH_HTTP_TIMEOUT = float(os.getenv("RESEARCH_HTTP_TIMEOUT", "90"))
research_client = RemoteClient(base_url=RESEARCH_SERVICE_URL, timeout=RESEARCH_HTTP_TIMEOUT)
ui_client = RemoteClient(base_url=UI_SERVER_BASE_URL, timeout=HTTP_TIMEOUT)
imessage_bridge_client = RemoteClient(
    base_url=IMESSAGE_BRIDGE_BASE_URL, timeout=HTTP_TIMEOUT
)
windows_message_bridge_client = RemoteClient(
    base_url=WINDOWS_MESSAGE_BRIDGE_BASE_URL, timeout=HTTP_TIMEOUT
)


def _message_bridge_client_for_target(target: str):
    """Use Windows bridge for discord:/slack:/whatsapp: targets, else iMessage bridge."""
    if not target:
        return imessage_bridge_client
    t = target.strip().lower()
    if t.startswith("discord:") or t.startswith("slack:") or t.startswith("whatsapp:"):
        return windows_message_bridge_client
    return imessage_bridge_client


class ScreenshotError(RuntimeError):
    pass


_last_requester_phone: Optional[str] = None


def capture_screenshot() -> str:
    """Capture the primary display and return it base64 encoded. Cross-platform."""

    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"agent_s_{uuid4().hex}.png"
    try:
        if platform.system() == "Darwin":
            subprocess.run(["screencapture", "-x", str(temp_path)], check=True)
        else:
            # Windows/Linux: use mss or pyautogui
            try:
                import mss
                with mss.mss() as sct:
                    sct.shot(mon=0, output=str(temp_path))
            except ImportError:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(str(temp_path))

        encoded = base64.b64encode(temp_path.read_bytes()).decode("ascii")
        return encoded
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ScreenshotError("Failed to capture screenshot") from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not delete temporary screenshot %s", temp_path)


def _forward_response(remote_response: Optional[requests.Response]):
    if remote_response is None:
        return jsonify({"status": "forward_failed"}), 502

    content_type = (remote_response.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            body = remote_response.json()
        except ValueError:
            logging.warning(
                "Expected JSON but got invalid payload from %s", remote_response.url
            )
            body = {"raw": remote_response.text}
        return jsonify(body), remote_response.status_code

    return (
        remote_response.text,
        remote_response.status_code,
        {
            "Content-Type": content_type or "text/plain",
        },
    )


def _safe_post(
    client: RemoteClient, path: str, payload: Dict[str, Any]
) -> Optional[requests.Response]:
    try:
        return client.post_json(path, payload)
    except requests.RequestException as exc:
        logging.error("POST %s failed: %s", path, exc, exc_info=True)
        return None


def _safe_get(client: RemoteClient, path: str) -> Optional[requests.Response]:
    try:
        return client.get(path)
    except requests.RequestException as exc:
        logging.error("GET %s failed: %s", path, exc, exc_info=True)
        return None


def _run_browser_task_then_reply(
    reply_target: str,
    message_text: str,
    prompt: str,
) -> None:
    """Run a browser task: try Browserbase/Stagehand first; on failure, fallback to Bright Data (research)."""
    stagehand_response = _safe_post(
        stagehand_client, "/api/execute",
        {"instruction": message_text.strip(), "prompt": prompt},
    )
    if stagehand_response and stagehand_response.status_code == 200:
        result = stagehand_response.json()
        success = result.get("success", False)
        status_msg = result.get("message", "Done")
        live_view = result.get("live_view", "")
        reply_text = f"Browser task: {status_msg}" if success else f"Browser task: {status_msg}"
        if live_view:
            reply_text += f"\n\nWatch / log in: {live_view}"
            if not success and ("auth" in status_msg.lower() or "login" in status_msg.lower()):
                reply_text += "\n(Open the link to log in manually – session stays open ~5 min)"
        if reply_target:
            _safe_post(
                _message_bridge_client_for_target(reply_target), "/api/send_imessage",
                {"target": reply_target, "text": reply_text},
            )
        logging.info("Browser task finished (Stagehand), reply sent to %s", reply_target or "(no target)")
        return
    # Fallback: Bright Data research (scrape content and store)
    urls = _extract_urls_from_text(message_text)
    if urls:
        logging.info("Stagehand failed or unavailable; falling back to Bright Data for %s", urls)
        _run_research_and_store(message_text.strip(), urls, reply_target)
        return
    reply_text = (
        "Browserbase/Stagehand is unavailable. Ensure Stagehand is running: "
        "cd backend && uv run stagehand_service.py. No URLs in message for Bright Data fallback."
    )
    if reply_target:
        _safe_post(
            _message_bridge_client_for_target(reply_target), "/api/send_imessage",
            {"target": reply_target, "text": reply_text},
        )
    logging.info("Browser task failed (no fallback URLs), reply sent to %s", reply_target or "(no target)")


def _synthesize_speech_payload(
    text: str,
    *,
    voice: Optional[str] = None,
    audio_format: Optional[str] = None,
) -> Tuple[bytes, str]:
    """Synthesize speech and return audio bytes with best-effort content type."""
    normalized_voice = (
        voice.strip() if isinstance(voice, str) and voice.strip() else None
    )
    normalized_format = (
        audio_format.strip()
        if isinstance(audio_format, str) and audio_format.strip()
        else None
    )

    audio_bytes = audio.synthesize_speech_from_text(
        str(text),
        voice=normalized_voice,
        audio_format=normalized_format,
    )

    content_type_key = normalized_format.lower() if normalized_format else ""
    content_type = audio.AUDIO_FORMAT_CONTENT_TYPES.get(
        content_type_key, audio.DEFAULT_AUDIO_CONTENT_TYPE
    )
    return audio_bytes, content_type


def _play_audio_bytes(
    audio_bytes: bytes,
    *,
    audio_format: Optional[str] = None,
    output_device: Optional[str] = None,
) -> None:
    """Play synthesized audio through the requested output device if available."""
    global _audio_playing

    if not audio_bytes:
        logging.debug("No audio bytes provided for playback")
        return

    try:
        import sounddevice as sd  # type: ignore
        import soundfile as sf  # type: ignore
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive: runtime environment specific
        logging.error("Audio playback libraries unavailable: %s", exc)
        return

    # Stop any currently playing audio to prevent queueing
    if _audio_playing:
        try:
            sd.stop()
            logging.info("Interrupted previous audio playback for new prompt")
        except Exception as exc:
            logging.debug("Failed to stop previous audio: %s", exc)

    device_name = (
        output_device
        or os.getenv("VOICE_SUMMARY_OUTPUT_DEVICE")
        or os.getenv("CURRENT_ACTION_AUDIO_DEVICE")
        or os.getenv("AUDIO_OUTPUT_DEVICE")
    )

    device_index: Optional[int] = None
    if device_name:
        try:
            devices = sd.query_devices()
        except Exception as exc:  # pragma: no cover - defensive
            logging.error("Unable to query audio devices: %s", exc)
        else:
            lowered = device_name.lower()
            for idx, device in enumerate(devices):
                if device.get("max_output_channels", 0) <= 0:
                    continue
                if lowered in device.get("name", "").lower():
                    device_index = idx
                    break
            if device_index is None:
                logging.warning(
                    "Requested audio output device '%s' not found, using system default",
                    device_name,
                )

    data: Optional[Any] = None
    sample_rate: Optional[int] = None

    try:
        with sf.SoundFile(io.BytesIO(audio_bytes)) as sound_file:
            sample_rate = int(sound_file.samplerate)
            data = sound_file.read(dtype="float32")
    except Exception as exc:
        logging.debug("Primary audio decode failed (%s); attempting fallback", exc)
        if not audio_format or audio_format.lower() != "mp3":
            logging.error("Unable to decode audio for playback: %s", exc)
            return

        try:
            from pydub import AudioSegment
            import numpy as np
        except Exception as inner_exc:  # pragma: no cover - defensive
            logging.error("MP3 playback fallback unavailable: %s", inner_exc)
            return

        segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        sample_rate = int(segment.frame_rate)
        samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
        max_val = float(1 << (segment.sample_width * 8 - 1))
        if max_val:
            samples /= max_val
        if segment.channels > 1:
            data = samples.reshape((-1, segment.channels))
        else:
            data = samples

    if data is None or sample_rate is None:
        logging.error("Decoded audio data unavailable for playback")
        return

    try:
        sd.play(data, sample_rate, device=device_index)
        sd.wait()
    except Exception as exc:  # pragma: no cover - runtime specific
        logging.error("Audio playback failed: %s", exc)


@app.route("/api/completetask", methods=["POST"])
def complete_task():
    payload = request.get_json(silent=True) or {}
    logging.info("[completetask] received from Agent-S: %s", payload)

    reply_target = _last_requester_phone
    if not reply_target:
        logging.warning("No phone number available for task completion notification")
        return jsonify({"error": "phone_number unavailable"}), 400
    reply_target = reply_target.strip()

    try:
        screenshot_b64 = capture_screenshot()
    except ScreenshotError as exc:
        logging.exception("Screenshot capture failed")
        return jsonify({"error": str(exc)}), 500

    action_text = payload.get("action")
    if action_text is not None and not isinstance(action_text, str):
        action_text = str(action_text)

    status = payload.get("status")
    message_parts = []
    if isinstance(status, str) and status.strip():
        message_parts.append(f"Task {status.strip()}")
    if action_text and action_text.strip():
        message_parts.append(action_text.strip())
    message_text = "\n".join(message_parts) if message_parts else "Task update"

    temp_dir = Path(tempfile.gettempdir())
    attachment_path = temp_dir / f"agent_s_task_{uuid4().hex}.png"
    try:
        attachment_path.write_bytes(base64.b64decode(screenshot_b64))
    except (ValueError, OSError) as exc:
        return jsonify({"error": f"Unable to prepare screenshot: {exc}"}), 500

    try:
        forward_payload = {
            "target": reply_target,
            "text": message_text,
            "attachments": [str(attachment_path)],
        }
        bridge = _message_bridge_client_for_target(reply_target)
        response = _safe_post(
            bridge, "/api/send_imessage", forward_payload
        )
        if response is None:
            logging.warning("[completetask] failed to send reply (bridge down?) target=%s", reply_target[:40] if reply_target else "?")
            return jsonify({"status": "failed", "bridge_forwarded": False}), 502
        logging.info("[completetask] reply sent to %s (screenshot + text)", reply_target[:40] if reply_target else "?")
        return _forward_response(response)
    finally:
        try:
            attachment_path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not delete temporary attachment %s", attachment_path)


@app.route("/api/currentaction", methods=["POST"])
def current_action():
    payload = request.get_json(silent=True) or {}
    for _, v in payload.items():
        if isinstance(v, str) and v.strip().lower() == "stopping":
            # Stop the agent
            _proxy_command("/api/stop")
            break

    text = str(payload.get("voice_summary", "") or "").strip()

    # voice = "e58b0d7efca34eb38d5c4985e378abcb"  # fish.audio uses its built-in default voice when reference_id is unset
    voice = "b545c585f631496c914815291da4e893"  # woman voice
    audio_format = "mp3"  # fish.audio TTSRequest default format

    if text:
        try:
            audio_bytes, _ = _synthesize_speech_payload(
                text, voice=voice, audio_format=audio_format
            )
            _play_audio_bytes(audio_bytes, audio_format=audio_format)
        except (audio.FishAudioError, ValueError) as exc:
            logging.error("Failed to synthesize voice notification: %s", exc)
            return

    logging.info("Current action update: %s", payload)

    response = _safe_post(ui_client, "/api/currentaction", payload)
    if response is None:
        return jsonify({"status": "queued", "ui_forwarded": False}), 202

    return _forward_response(response)


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    logging.info("UI chat payload: %s", payload)

    message_text = (payload.get("text") or payload.get("prompt") or "").strip()

    # Video call / FaceTime (same as iMessage path)
    if message_text and is_video_call_request(message_text):
        logging.info("Routing to video call (FaceTime/Zoom/Meet) from UI: %s", message_text[:80])
        result = start_video_call(
            target_platform=None,
            phone_number=os.getenv("FACETIME_DEFAULT_NUMBER") or os.getenv("FACETIME_APPLE_ID") or "",
            source="ui",
        )
        reply_msg = result.get("message", "Video call setup failed.")
        if result.get("success") and result.get("meeting_url"):
            reply_msg = f"{result.get('meeting_url', '')}\n\n{reply_msg}"
        if result.get("success"):
            try:
                call_manager.start_call()
            except Exception as e:
                logging.warning("Could not start call session for voice: %s", e)
        return jsonify({
            "status": "ok",
            "video_call": True,
            "success": result.get("success", False),
            "message": reply_msg,
            "meeting_url": result.get("meeting_url"),
        }), 200

    # Scrape/caption/store → Bright Data (research), save to data/scraped/, return summary
    if message_text and _is_scrape_caption_store_task(message_text):
        urls = _extract_urls_from_text(message_text)
        if urls:
            logging.info("Routing to Bright Data (scrape/caption/store): %s", message_text[:80])
            response = _safe_post(
                research_client, "/api/research",
                {"query": message_text, "urls": urls, "format": "markdown"},
            )
            if response and response.status_code == 200:
                data = response.json()
                out_dir = (Path(__file__).resolve().parent.parent / "data" / "scraped")
                out_dir.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                saved_paths = []
                for i, r in enumerate(data.get("results", [])):
                    if not r.get("success") or not r.get("content"):
                        continue
                    safe_name = re.sub(r"[^\w\-.]", "_", urls[i] if i < len(urls) else str(i))[:80]
                    out_path = (out_dir / f"{ts}_{i}_{safe_name}.txt").resolve()
                    try:
                        out_path.write_text(r.get("content", ""), encoding="utf-8", errors="replace")
                        saved_paths.append(str(out_path))
                    except Exception:
                        pass
                summary = data.get("summary", "")
                msg = f"Bright Data: {summary}"
                if saved_paths:
                    first_content = next((r.get("content", "") for r in data.get("results", []) if r.get("content")), "")
                    if first_content:
                        preview = first_content.replace("\n", " ").strip()[:280] + ("..." if len(first_content.strip()) > 280 else "")
                        msg += f"\n\nPreview: {preview}"
                return jsonify({
                    "status": "ok",
                    "research": True,
                    "message": msg,
                    "success": True,
                    "saved_paths": saved_paths,
                    "stored_local": True,
                    "local_folder": str(out_dir.resolve()),
                }), 200
            return jsonify({
                "status": "error",
                "research": True,
                "message": "Research service unavailable. Start it: cd backend && uv run research_service.py",
                "success": False,
            }), 503
        return jsonify({
            "status": "error",
            "message": "No URLs in message. Add a link or say 'from example.com'.",
            "success": False,
        }), 400

    # Browser → Stagehand first; on failure, fallback to Bright Data
    if message_text and _is_browser_task(message_text):
        logging.info("Routing to Browserbase/Stagehand (browser task): %s", message_text[:80])
        stagehand_response = _safe_post(
            stagehand_client, "/api/execute",
            {"instruction": message_text, "prompt": message_text},
        )
        if stagehand_response and stagehand_response.status_code == 200:
            result = stagehand_response.json()
            status_msg = result.get("message", "Done")
            success = result.get("success", False)
            resp_data = {"status": "ok", "stagehand": True, "message": status_msg, "success": success}
            if result.get("live_view"):
                resp_data["live_view"] = result["live_view"]
            return jsonify(resp_data), 200
        # Fallback: Bright Data if message contains URLs
        urls = _extract_urls_from_text(message_text)
        if urls:
            logging.info("Stagehand failed; falling back to Bright Data")
            response = _safe_post(
                research_client, "/api/research",
                {"query": message_text, "urls": urls, "format": "markdown"},
            )
            if response and response.status_code == 200:
                data = response.json()
                summary = data.get("summary", "")
                return jsonify({
                    "status": "ok",
                    "stagehand": False,
                    "research_fallback": True,
                    "message": f"Bright Data fallback: {summary}",
                    "success": data.get("success", False),
                }), 200
        return jsonify({
            "status": "error",
            "stagehand": False,
            "message": "Browserbase/Stagehand is unavailable. Start it: cd backend && uv run stagehand_service.py",
            "success": False,
        }), 503

    response = _safe_post(agent_s_client, "/api/chat", payload)
    if response is None:
        return jsonify({"status": "queued", "agent_forwarded": False}), 202

    return _forward_response(response)


@app.route("/api/send_imessage", methods=["POST"])
def send_imessage_endpoint() -> Any:
    payload = request.get_json(silent=True) or {}
    target = payload.get("target")
    text = payload.get("text")
    attachments = payload.get("attachments")
    logging.info("Send iMessage request for target=%s", target)

    if not isinstance(target, str) or not target.strip():
        return jsonify({"error": "target is required"}), 400
    if text is not None and not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400
    if attachments is not None and not isinstance(attachments, list):
        return jsonify({"error": "attachments must be a list"}), 400

    file_list: Optional[list[str]] = None
    if attachments:
        file_list = []
        for item in attachments:
            if not isinstance(item, str) or not item.strip():
                return (
                    jsonify({"error": "attachments must contain non-empty paths"}),
                    400,
                )
            file_list.append(str(Path(item.strip().strip("\"'")).expanduser()))

    if text is not None and not text.strip():
        text = None
    if text is None and not file_list:
        return jsonify({"error": "text or attachments must be provided"}), 400

    forward_payload: Dict[str, Any] = {
        "target": target.strip(),
        "text": text,
        "attachments": file_list,
    }
    response = _safe_post(_message_bridge_client_for_target(target.strip()), "/api/send_imessage", forward_payload)
    if response is None:
        return jsonify({"status": "failed", "bridge_forwarded": False}), 502

    return _forward_response(response)


# Sites that need Stagehand (multi-step: login, search, send message, etc.)
# Don't route these to simple Google search
_STAGEHAND_SITES = (
    "linkedin", "facebook", "twitter", "x.com", "instagram", "reddit",
    "slack", "discord", "whatsapp", "messenger", "telegram",
)

# Scrape/caption/store: use Bright Data (research service) to fetch and save web content
_SCRAPE_CAPTION_KEYWORDS = (
    "scrape", "caption", "extract data", "extract content", "get data from",
    "get content from", "save from internet", "store from web", "download content",
    "fetch and save", "fetch and store", "pull data from", "scrape and save",
    "scrape and store", "capture from web", "copy from website",
    "save to file", "save to a file",
)


def _extract_urls_from_text(text: str) -> List[str]:
    """Extract URLs from message. Also turns 'from example.com' into https://example.com."""
    if not text or not isinstance(text, str):
        return []
    urls = []
    # Explicit http(s) URLs
    for m in re.finditer(r"https?://[^\s\]\)\"']+", text, re.I):
        u = m.group(0).rstrip(".,;:)")
        if u not in urls:
            urls.append(u)
    # "from domain.com" or "from www.domain.com"
    from_match = re.search(r"\bfrom\s+(https?://[^\s]+)", text, re.I)
    if from_match and from_match.group(1) not in urls:
        urls.append(from_match.group(1).rstrip(".,;:)"))
    from_domain = re.search(r"\bfrom\s+([a-z0-9][-a-z0-9.]*\.[a-z]{2,}(?:\/[^\s]*)?)", text, re.I)
    if from_domain:
        raw = from_domain.group(1).strip().rstrip(".,;:)")
        if not raw.startswith("http"):
            raw = "https://" + raw
        if raw not in urls:
            urls.append(raw)
    return urls[:10]  # cap at 10 URLs


def _is_scrape_caption_store_task(text: str) -> bool:
    """True if user wants to scrape/caption/extract data from the internet and store it → use Bright Data."""
    if not text or not isinstance(text, str):
        return False
    t = text.lower()
    return any(k in t for k in _SCRAPE_CAPTION_KEYWORDS)


def _run_research_and_store(
    query: str,
    urls: List[str],
    reply_target: str,
) -> None:
    """Call research service (Bright Data), save content to data/scraped/, send reply to reply_target."""
    if not urls:
        reply = "No URLs found in your message. Add a link like https://example.com or say 'from example.com'."
        if reply_target:
            _safe_post(
                _message_bridge_client_for_target(reply_target), "/api/send_imessage",
                {"target": reply_target, "text": reply},
            )
        logging.info("Research skipped (no URLs), reply sent")
        return
    response = _safe_post(
        research_client, "/api/research",
        {"query": query, "urls": urls, "format": "markdown"},
    )
    if not response or response.status_code != 200:
        reply = "Research service unavailable. Start it: cd backend && uv run research_service.py"
        if reply_target:
            _safe_post(
                _message_bridge_client_for_target(reply_target), "/api/send_imessage",
                {"target": reply_target, "text": reply},
            )
        logging.warning("Research service unreachable")
        return
    data = response.json()
    successful = data.get("successful", 0)
    results = data.get("results", [])
    saved_paths: List[str] = []
    out_dir = (Path(__file__).resolve().parent.parent / "data" / "scraped")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    for i, r in enumerate(results):
        if not r.get("success") or not r.get("content"):
            continue
        safe_name = re.sub(r"[^\w\-.]", "_", urls[i] if i < len(urls) else str(i))[:80]
        fname = f"{ts}_{i}_{safe_name}.txt"
        out_path = (out_dir / fname).resolve()
        try:
            out_path.write_text(r.get("content", ""), encoding="utf-8", errors="replace")
            saved_paths.append(str(out_path))
        except Exception as e:
            logging.warning("Could not write scraped file %s: %s", out_path, e)
    summary = data.get("summary", f"Fetched {successful}/{len(urls)} URLs.")
    method_used = results[0].get("method", "research") if results else "research"
    reply = f"Bright Data research: {summary}\nMethod: {method_used}"
    if saved_paths:
        reply += f"\n\nStored on your system (local folder):\n" + "\n".join(saved_paths[:5])
        if len(saved_paths) > 5:
            reply += f"\n... and {len(saved_paths) - 5} more"
        # Add a short preview of what was saved (first result)
        first_content = next((r.get("content", "") for r in results if r.get("content")), "")
        if first_content:
            preview = first_content.replace("\n", " ").strip()[:280]
            if len(first_content.replace("\n", " ").strip()) > 280:
                preview += "..."
            reply += f"\n\nPreview:\n{preview}"
    if reply_target:
        _safe_post(
            _message_bridge_client_for_target(reply_target), "/api/send_imessage",
            {"target": reply_target, "text": reply},
        )
    logging.info("Research done, reply sent to %s", reply_target or "(no target)")


def _try_simple_browser_open(text: str) -> Optional[str]:
    """
    For simple tasks, open URL in default browser (uses existing Chrome/signed-in profile).
    Returns URL if we opened it, None if task needs Stagehand.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip().lower()
    # Site-specific tasks (LinkedIn, Facebook, etc.) need Stagehand - skip simple path
    if any(site in t for site in _STAGEHAND_SITES):
        return None
    url = None
    # "search X on Google" / "google X" / "open chrome and search X"
    import re
    from urllib.parse import quote_plus
    if "search" in t or "google" in t:
        for pat in [
            r"search\s+(?:for\s+)?(.+?)\s+on\s+google",
            r"(?:open\s+chrome\s+and\s+)?search\s+(.+)",
            r"google\s+(.+)",
            r"search\s+(.+)",
        ]:
            m = re.search(pat, t, re.I)
            if m:
                q = m.group(1).strip()
                # Remove trailing "on google" etc
                q = re.sub(r"\s+on\s+google.*$", "", q, flags=re.I)
                if q and len(q) < 200:
                    url = f"https://www.google.com/search?q={quote_plus(q)}"
                break
    if not url and ("youtube music" in t or "music.youtube" in t):
        url = "https://music.youtube.com"
    if not url and ("youtube" in t and "music" not in t):
        url = "https://www.youtube.com"
    if not url and "gmail" in t:
        url = "https://mail.google.com"
    if not url and "google" in t and "search" not in t:
        url = "https://www.google.com"
    if url:
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["cmd", "/c", "start", url], shell=False)
            else:
                import webbrowser
                webbrowser.open(url)
            return url
        except Exception as e:
            logging.warning("Simple browser open failed: %s", e)
    return None


def _is_browser_task(text: str) -> bool:
    """Check if message describes a browser task (Chrome, Google, YouTube, etc.).
    Excludes desktop-only tasks like 'Open Notepad' - those go to Agent-S."""
    if not text or not isinstance(text, str):
        return False
    t = text.lower()
    # Exclude desktop apps - Stagehand handles web only
    if any(desktop in t for desktop in ("notepad", "calculator", "calc", "cmd", "explorer", "file explorer")):
        return False
    # Require browser-specific keywords (not just "open" or "play")
    keywords = [
        "chrome", "browser", "google", "search", "youtube", "music.youtube",
        "youtube music", "go to", "navigate", "website", "web", "browse",
        "spotify", "netflix", "gmail", "facebook", "twitter", "instagram",
        "linkedin", "reddit", "slack", "discord",
    ]
    return any(k in t for k in keywords)


def _enhance_notepad_message(text: str) -> str:
    """When user says 'Open Notepad', add instruction to type a test message."""
    if not text or not isinstance(text, str):
        return text
    t = text.strip().lower()
    # Simple open-notepad only (no 'and type' or 'then type' already)
    if "notepad" in t and "type" not in t and "write" not in t:
        return text.strip() + " and type 'Hello from Shadow-OS' as a test message"
    return text


@app.route("/api/new_imessage", methods=["POST"])
def new_imessage() -> Any:
    payload = request.get_json(silent=True) or {}
    phone = (payload.get("phone_number") or payload.get("source") or "unknown")[:60]
    logging.info("[new_imessage] task received from %s: %s", phone, (payload.get("text") or "")[:80])

    phone_number = payload.get("phone_number")
    global _last_requester_phone
    if isinstance(phone_number, str) and phone_number.strip():
        _last_requester_phone = phone_number.strip()
    else:
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            _last_requester_phone = source.strip()

    message_text = payload.get("text")
    if message_text is None:
        message_text = ""
    elif not isinstance(message_text, str):
        message_text = str(message_text)

    # Enhance simple "Open Notepad" to also type a test message
    message_text = _enhance_notepad_message(message_text)

    if phone_number and isinstance(phone_number, str) and phone_number.strip():
        prompt_body = message_text.strip()
        if prompt_body:
            prompt = f"Message from {phone_number.strip()}:\n{prompt_body}"
        else:
            prompt = f"Message from {phone_number.strip()}."
    else:
        prompt = message_text

    # Notify user so messages appear as a ping (native OS notification)
    notif_title = "New message"
    if phone_number and isinstance(phone_number, str) and phone_number.strip():
        notif_title = f"From {phone_number.strip()}"
    _show_message_notification(notif_title, message_text.strip() or "New iMessage")
    logging.info("[new_imessage] notification sent (title=%s)", notif_title[:40])

    # Route video call requests to video call service
    if is_video_call_request(message_text):
        logging.info("[new_imessage] route=video_call | %s", message_text[:80])
        reply_target = (
            payload.get("source")
            or (f"whatsapp:{phone_number}" if phone_number and "+" in str(phone_number) else phone_number)
            or ""
        )
        if not reply_target and phone_number:
            reply_target = str(phone_number)
        # Contact for FaceTime (phone/email) and WhatsApp
        phone_for_whatsapp = None
        if reply_target and reply_target.startswith("whatsapp:"):
            phone_for_whatsapp = reply_target.replace("whatsapp:", "", 1)
        elif phone_number and isinstance(phone_number, str) and "+" in phone_number:
            phone_for_whatsapp = phone_number.strip()
        # When user says "FaceTime me", force FaceTime. Contact = sender (so they get the call); fall back to .env only if we have no sender.
        force_facetime = "facetime" in message_text.lower() or "face time" in message_text.lower()
        target_platform = "facetime" if force_facetime else None
        contact = (phone_number if isinstance(phone_number, str) and phone_number.strip() else None) or reply_target or phone_for_whatsapp
        if force_facetime:
            # Prefer sender so "FaceTime me" calls the person who asked; use .env only when sender isn't a valid FaceTime contact
            contact = contact or (os.getenv("FACETIME_APPLE_ID") or "").strip() or (os.getenv("FACETIME_DEFAULT_NUMBER") or "").strip().strip('"\'')
            logging.info("FaceTime requested: contact=%s", (contact or "")[:50])
        result = start_video_call(
            target_platform=target_platform,
            phone_number=contact or phone_for_whatsapp,
            source=reply_target,
        )
        reply_text = result.get("message", "Video call setup failed.")
        if result.get("success") and result.get("meeting_url"):
            reply_text = f"Join the call: {result['meeting_url']}\n\n{reply_text}"
        # Start call session so voice commands work during the call (Zoom/Meet audio)
        if result.get("success"):
            try:
                call_manager.start_call()
            except Exception as e:
                logging.warning("Could not start call session for voice: %s", e)
        _safe_post(
            _message_bridge_client_for_target(reply_target or ""),
            "/api/send_imessage",
            {"target": reply_target or "unknown", "text": reply_text},
        )
        logging.info("[new_imessage] video_call reply sent to %s", (reply_target or "unknown")[:40])
        return jsonify(
            {
                "status": "ok",
                "video_call": True,
                "success": result.get("success", False),
                "message": reply_text,
                "meeting_url": result.get("meeting_url"),
            }
        ), 200

    # Scrape/caption/store from internet → Bright Data (research service), save to data/scraped/
    if _is_scrape_caption_store_task(message_text):
        urls = _extract_urls_from_text(message_text)
        reply_target = (phone_number or payload.get("source") or "").strip()
        logging.info("[new_imessage] route=research (Bright Data) | reply_to=%s | urls=%s", reply_target or "?", urls)
        thread = threading.Thread(
            target=_run_research_and_store,
            args=(message_text.strip(), urls, reply_target),
            daemon=True,
        )
        thread.start()
        return jsonify({
            "status": "accepted",
            "research": True,
            "message": "Scraping with Bright Data. You'll get a reply with saved file paths when done.",
        }), 202

    # Browser tasks → Browserbase/Stagehand first; on failure, fallback to Bright Data. Reply when done.
    if _is_browser_task(message_text):
        reply_target = (phone_number or payload.get("source") or "").strip()
        logging.info("[new_imessage] route=browser_task | reply_to=%s | %s", reply_target or "?", message_text[:80])
        thread = threading.Thread(
            target=_run_browser_task_then_reply,
            args=(reply_target, message_text, prompt),
            daemon=True,
        )
        thread.start()
        return jsonify({
            "status": "accepted",
            "stagehand": True,
            "message": "Browser task started. You'll get a reply when it finishes.",
        }), 202

    # Forward to agent_s for LLM processing (reply sent later via /api/completetask)
    if not (prompt or "").strip():
        logging.warning("[new_imessage] empty prompt, skipping agent_s forward")
        return jsonify({"status": "error", "message": "empty prompt"}), 400
    logging.info("[new_imessage] route=agent_s | forwarding to Agent-S /api/chat (prompt len=%s)", len(prompt or ""))
    forward_payload: Dict[str, Any] = {
        "prompt": prompt,
        "metadata": {k: v for k, v in payload.items() if k != "text"},
    }
    response = _safe_post(agent_s_client, "/api/chat", forward_payload)
    if response is None:
        logging.warning("[new_imessage] Agent-S unreachable; returning 202 (no reply sent)")
        return jsonify({"status": "queued", "agent_forwarded": False}), 202
    logging.info("[new_imessage] Agent-S responded; returning to caller")
    return _forward_response(response)


def _proxy_command(path: str):
    response = _safe_get(agent_s_client, path)
    if response is None:
        return jsonify({"status": "failed", "agent_forwarded": False}), 502

    return _forward_response(response)


@app.route("/health", methods=["GET"])
def health():
    """Quick check that the backend is running. Use for scripts and monitoring."""
    return jsonify({"status": "ok", "service": "backend", "port": SERVER_PORT}), 200


@app.route("/api/video_call_options", methods=["GET"])
def video_call_options() -> Any:
    """Return available video call options (Zoom, Meet, WhatsApp) for debugging.
    Query params: phone_number, source - for smart WhatsApp direct-call preference."""
    try:
        phone = request.args.get("phone_number")
        source = request.args.get("source")
        opts = get_video_call_options(phone_number=phone, source=source)
        return jsonify(opts), 200
    except Exception as e:
        logging.exception("video_call_options error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/contact_links", methods=["GET"])
def contact_links() -> Any:
    """
    Return your contact links to message your PC from your phone.
    Add these to your phone's contacts or messaging apps.
    """
    links = []
    # WhatsApp (Twilio number users message)
    wa_num = os.getenv("CONTACT_WHATSAPP_NUMBER", os.getenv("TWILIO_WHATSAPP_NUMBER", ""))
    if wa_num:
        clean = wa_num.replace("whatsapp:", "").strip()
        links.append({
            "platform": "whatsapp",
            "label": "WhatsApp",
            "instruction": f"Message +{clean.replace('+', '')} on WhatsApp to control your PC",
            "value": clean,
        })
    # Discord
    if os.getenv("DISCORD_BOT_TOKEN"):
        invite = os.getenv("CONTACT_DISCORD_INVITE", "")
        links.append({
            "platform": "discord",
            "label": "Discord",
            "instruction": "DM your bot to control your PC" + (f" | Invite: {invite}" if invite else ""),
            "value": invite or "DM your bot",
        })
    # Slack
    if os.getenv("SLACK_BOT_TOKEN"):
        links.append({
            "platform": "slack",
            "label": "Slack",
            "instruction": "Message your bot in Slack to control your PC",
            "value": "Slack DM",
        })
    return jsonify({"contact_links": links, "message": "Message from your phone to control your Windows PC"})


@app.route("/api/stop", methods=["GET"])
def stop():
    logging.info("Received stop command from UI")
    return _proxy_command("/api/stop")


@app.route("/api/pause", methods=["GET"])
def pause():
    logging.info("Received pause command from UI")
    return _proxy_command("/api/pause")


@app.route("/api/resume", methods=["GET"])
def resume():
    logging.info("Received resume command from UI")
    return _proxy_command("/api/resume")


@app.route("/api/shadow_trigger", methods=["POST"])
def shadow_trigger():
    """
    Shadow-OS trigger: accepts voice + optional screenshot, transcribes, forwards to Agent-S.
    Used by Siri/Apple Shortcuts: "Siri, tell Shadow to help me"
    """
    try:
        transcript = ""
        # Accept multipart: voice (audio file), screenshot (optional), prompt (optional text override)
        if request.content_type and "multipart" in (request.content_type or ""):
            voice_file = request.files.get("voice") or request.files.get("audio")
            if voice_file:
                audio_bytes = voice_file.read()
                if audio_bytes:
                    try:
                        transcript = audio.transcribe_audio_bytes(audio_bytes)
                    except audio.FishAudioError as e:
                        logging.warning("Shadow trigger: transcription failed: %s", e)
                        transcript = ""

            prompt_override = request.form.get("prompt", "").strip()
            if prompt_override:
                transcript = prompt_override
        else:
            payload = request.get_json(silent=True) or {}
            prompt_override = (payload.get("prompt") or payload.get("text") or "").strip()
            if prompt_override:
                transcript = prompt_override

        if not transcript.strip():
            return jsonify({"error": "No voice transcript or prompt provided"}), 400

        # Build prompt with optional screenshot context
        prompt = f"Shadow trigger: {transcript}"
        agent_payload = {"prompt": prompt, "metadata": {"source": "shadow_trigger"}}

        response = _safe_post(agent_s_client, "/api/chat", agent_payload)
        if response is None:
            return jsonify({"status": "queued", "agent_forwarded": False}), 202
        return _forward_response(response)
    except Exception as e:
        logging.exception("Shadow trigger error: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/research", methods=["POST"])
def research_proxy():
    """Proxy research requests to the research service (Bright Data / standard fetch)."""
    payload = request.get_json(silent=True) or {}
    response = _safe_post(research_client, "/api/research", payload)
    if response is None:
        return jsonify({
            "success": False,
            "error": "Research service unavailable. Start it: uv run research_service.py (port 5006)",
        }), 503
    return jsonify(response.json()), response.status_code


@app.route("/api/cursor_move", methods=["POST"])
def cursor_move():
    """Proxy cursor move to cursor service (Vision Mirror)."""
    payload = request.get_json(silent=True) or {}
    try:
        r = requests.post(
            f"{CURSOR_SERVICE_URL}/api/cursor_move",
            json=payload,
            timeout=2,
        )
        return jsonify(r.json() if r.text else {}), r.status_code
    except requests.RequestException as e:
        logging.warning("Cursor service unreachable: %s", e)
        return jsonify({"error": "Cursor service not available"}), 503


@app.route("/api/vision/frame", methods=["POST"])
def vision_frame():
    """Proxy vision frame to vision service (hand/finger detection). Accepts JSON {frame: base64}."""
    payload = request.get_json(silent=True) or {}
    try:
        r = requests.post(
            f"{VISION_SERVICE_URL}/api/vision/frame",
            json=payload,
            timeout=5,
        )
        return jsonify(r.json() if r.text else {}), r.status_code
    except requests.RequestException as e:
        logging.warning("Vision service unreachable: %s", e)
        return jsonify({"error": "Vision service not available"}), 503


@app.route("/api/cursor_click", methods=["POST"])
def cursor_click():
    """Proxy cursor click to cursor service (Vision Mirror)."""
    payload = request.get_json(silent=True) or {}
    try:
        r = requests.post(
            f"{CURSOR_SERVICE_URL}/api/cursor_click",
            json=payload,
            timeout=2,
        )
        return jsonify(r.json() if r.text else {}), r.status_code
    except requests.RequestException as e:
        logging.warning("Cursor service unreachable: %s", e)
        return jsonify({"error": "Cursor service not available"}), 503


@app.route("/api/audio/transcribe", methods=["POST"])
def transcribe() -> Response:
    """Transcribe raw audio bytes sent in the request body via fish.audio ASR."""
    audio_bytes = request.get_data(cache=False)
    if not audio_bytes:
        return (
            jsonify({"error": "Request body must contain audio bytes"}),
            HTTPStatus.BAD_REQUEST,
        )

    language = request.args.get("language")

    try:
        transcript = audio.transcribe_audio_bytes(audio_bytes, language=language)
        return jsonify({"text": transcript}), HTTPStatus.OK
    except audio.FishAudioError as exc:
        logging.error("fish.audio error: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_GATEWAY
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST


@app.route("/api/audio/synthesize", methods=["POST"])
def synthesize() -> Response:
    """Synthesize speech for the provided text via fish.audio TTS."""
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")

    if not text:
        return (
            jsonify({"error": "JSON body with 'text' field is required"}),
            HTTPStatus.BAD_REQUEST,
        )

    voice = payload.get("voice")
    audio_format = payload.get("audio_format")

    try:
        audio_bytes, content_type = _synthesize_speech_payload(
            text, voice=voice, audio_format=audio_format
        )
        return Response(io.BytesIO(audio_bytes).getvalue(), mimetype=content_type)
    except audio.FishAudioError as exc:
        logging.error("fish.audio error: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_GATEWAY
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST


@app.route("/api/call_started", methods=["POST"])
def call_started() -> Response:
    """Handle notification from Agent-S that a FaceTime call has been initiated."""
    payload = request.get_json(silent=True) or {}
    logging.info(f"Received call_started notification from Agent-S: {payload}")

    # Extract call metadata if provided
    number = payload.get("number")

    try:

        # Start the call session with the call.py service
        success = call_manager.start_call()

        if success:

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Call session started",
                        "call_active": True,
                        "connected_to_call_service": call_manager.connected,
                    }
                ),
                HTTPStatus.OK,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to start call session",
                        "call_active": False,
                    }
                ),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    except Exception as e:
        logging.error(f"Error starting call session: {e}")
        return (
            jsonify({"status": "error", "message": str(e), "call_active": False}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@app.route("/api/call_ended", methods=["POST"])
def call_ended() -> Response:
    """Handle notification that the FaceTime call has ended."""
    payload = request.get_json(silent=True) or {}
    logging.info(f"Received call_ended notification: {payload}")

    try:
        # End the call session
        success = call_manager.end_call()

        if success:
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Call session ended",
                        "call_active": False,
                    }
                ),
                HTTPStatus.OK,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "info",
                        "message": "No active call to end",
                        "call_active": False,
                    }
                ),
                HTTPStatus.OK,
            )

    except Exception as e:
        logging.error(f"Error ending call session: {e}")
        return (
            jsonify({"status": "error", "message": str(e)}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@app.route("/api/call_status", methods=["GET"])
def call_status() -> Response:
    """Get the current status of the call session."""
    return (
        jsonify(
            {
                "connected_to_service": call_manager.connected,
                "call_active": call_manager.call_active,
                "service_url": CALL_SERVICE_URL,
            }
        ),
        HTTPStatus.OK,
    )


@app.route("/api/send_audio_to_call", methods=["POST"])
def send_audio_to_call() -> Response:
    """Send audio to be played through the call output."""
    # Get raw audio bytes from request body
    audio_bytes = request.get_data(cache=False)

    if not audio_bytes:
        # Try to get from JSON payload with base64 encoding
        payload = request.get_json(silent=True) or {}
        audio_b64 = payload.get("audio")
        if audio_b64:
            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception as e:
                return (
                    jsonify({"error": f"Invalid base64 audio data: {e}"}),
                    HTTPStatus.BAD_REQUEST,
                )
        else:
            return jsonify({"error": "No audio data provided"}), HTTPStatus.BAD_REQUEST

    if not call_manager.call_active:
        return (
            jsonify({"status": "error", "message": "No active call session"}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        call_manager.send_audio_to_output(audio_bytes)
        return (
            jsonify({"status": "success", "bytes_sent": len(audio_bytes)}),
            HTTPStatus.OK,
        )
    except Exception as e:
        logging.error(f"Error sending audio to call: {e}")
        return (
            jsonify({"status": "error", "message": str(e)}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


if __name__ == "__main__":
    debug = _env_bool("BACKEND_DEBUG", default=False)
    app.run(host=SERVER_HOST, port=int(SERVER_PORT), debug=debug, threaded=True)
