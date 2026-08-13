"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "@/lib/api";

// Ordered by preference: the first the browser can encode wins.
const CANDIDATE_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

function pickMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return CANDIDATE_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

/**
 * Hold-to-dictate for the question box.
 *
 * The recording is sent to the remote model for transcription, so the control
 * is disabled unless remote AI is permitted for the request — the same gate
 * every other remote call passes through. The audio is not stored: the server
 * returns text and discards the upload.
 */
export function DictateButton({
  allowRemote,
  disabled,
  onTranscript,
}: {
  allowRemote: boolean;
  disabled?: boolean;
  onTranscript: (text: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [supported, setSupported] = useState(true);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    setSupported(Boolean(pickMimeType()) && Boolean(navigator.mediaDevices?.getUserMedia));
  }, []);

  const stopTracks = useCallback(() => {
    recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
  }, []);

  useEffect(() => () => stopTracks(), [stopTracks]);

  async function start() {
    setError("");
    const mimeType = pickMimeType();
    if (!mimeType) { setSupported(false); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        stopTracks();
        if (blob.size === 0) { setError("Nothing was recorded."); return; }
        setWorking(true);
        try {
          const result = await transcribeAudio(blob, mimeType);
          onTranscript(result.text);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Could not transcribe that recording");
        } finally { setWorking(false); }
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      // The browser refuses without a user gesture or a granted permission.
      setError("Microphone access was refused.");
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  if (!supported) return null;

  const blocked = !allowRemote;
  const label = working ? "Transcribing…" : recording ? "Stop" : "Dictate";

  return (
    <div className="dictate">
      <button
        type="button"
        className={recording ? "danger-button dictate-button" : "ghost-button dictate-button"}
        onClick={recording ? stop : start}
        disabled={disabled || working || blocked}
        title={
          blocked
            ? "Dictation sends audio to the remote model. Enable “Allow remote model” to use it."
            : "Record a question instead of typing it"
        }
        aria-label={label}
      >
        <span aria-hidden="true">{recording ? "■" : "🎙"}</span> {label}
      </button>
      {recording ? <span className="dictate-hint">Listening — press stop when finished.</span> : null}
      {blocked ? <span className="dictate-hint">Enable remote AI to dictate.</span> : null}
      {error ? <span className="dictate-error">{error}</span> : null}
    </div>
  );
}
