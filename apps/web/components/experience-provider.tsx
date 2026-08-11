"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getExperiencePreferences, updateExperiencePreferences, type ExperiencePreferences } from "@/lib/api";

const STORAGE_KEY = "jl:experience-preferences:v1";

export const DEFAULT_EXPERIENCE: ExperiencePreferences = {
  ui_language: "en",
  density: "comfortable",
  contrast: "standard",
  font_scale: "default",
  reduce_motion: false,
  show_keyboard_hints: true,
  document_page_window: 8,
  document_text_zoom: 100,
  remember_last_workspace: true,
};

type ExperienceContextValue = {
  preferences: ExperiencePreferences;
  ready: boolean;
  update: (patch: Partial<ExperiencePreferences>) => Promise<void>;
};

const ExperienceContext = createContext<ExperienceContextValue>({
  preferences: DEFAULT_EXPERIENCE,
  ready: false,
  update: async () => undefined,
});

function applyPreferences(value: ExperiencePreferences) {
  const root = document.documentElement;
  root.dataset.uiLanguage = value.ui_language;
  root.dataset.density = value.density;
  root.dataset.contrast = value.contrast;
  root.dataset.fontScale = value.font_scale;
  root.dataset.motion = value.reduce_motion ? "reduced" : "full";
  root.lang = value.ui_language === "hi" ? "hi" : "en";
}

function readLocal(): ExperiencePreferences | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (!value) return null;
    return { ...DEFAULT_EXPERIENCE, ...(JSON.parse(value) as Partial<ExperiencePreferences>) };
  } catch { return null; }
}

export function ExperienceProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(DEFAULT_EXPERIENCE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const local = readLocal();
    if (local) { setPreferences(local); applyPreferences(local); }
    void getExperiencePreferences()
      .then((remote) => {
        const merged = { ...DEFAULT_EXPERIENCE, ...remote };
        setPreferences(merged); applyPreferences(merged);
        try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged)); } catch { /* optional cache */ }
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, []);

  const update = useCallback(async (patch: Partial<ExperiencePreferences>) => {
    const optimistic = { ...preferences, ...patch };
    setPreferences(optimistic); applyPreferences(optimistic);
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(optimistic)); } catch { /* optional cache */ }
    try {
      const saved = await updateExperiencePreferences(patch);
      const merged = { ...DEFAULT_EXPERIENCE, ...saved };
      setPreferences(merged); applyPreferences(merged);
      try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged)); } catch { /* optional cache */ }
    } catch {
      // Authentication can intentionally be disabled during local UI development. Local preference fallback remains usable.
    }
  }, [preferences]);

  const value = useMemo(() => ({ preferences, ready, update }), [preferences, ready, update]);
  return <ExperienceContext.Provider value={value}>{children}</ExperienceContext.Provider>;
}

export function useExperience() { return useContext(ExperienceContext); }
