"use client";

import { useEffect, useRef, useState } from "react";
import { SettingsIcon, XIcon } from "@/components/icons";
import { useExperience } from "@/components/experience-provider";

export function ExperienceSettings() {
  const { preferences, update } = useExperience();
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("jl:open-preferences", handler);
    return () => window.removeEventListener("jl:open-preferences", handler);
  }, []);
  useEffect(() => { if (open) window.setTimeout(() => closeRef.current?.focus(), 20); }, [open]);
  if (!open) return null;

  return <div className="drawer-overlay" role="presentation" onMouseDown={(e) => { if (e.currentTarget === e.target) setOpen(false); }}>
    <aside className="settings-drawer" role="dialog" aria-modal="true" aria-labelledby="display-settings-title">
      <div className="drawer-header">
        <div><div className="eyebrow">Personal</div><h2 id="display-settings-title">Display & accessibility</h2></div>
        <button ref={closeRef} className="icon-button" type="button" aria-label="Close display settings" onClick={() => setOpen(false)}><XIcon /></button>
      </div>
      <div className="drawer-body">
        <fieldset className="setting-group"><legend>Interface language</legend>
          <div className="segmented" role="group" aria-label="Interface language">
            {([['en','English'],['hi','हिन्दी'],['bilingual','Both']] as const).map(([value,label]) => <button key={value} type="button" aria-pressed={preferences.ui_language===value} className={preferences.ui_language===value?'selected':''} onClick={() => void update({ui_language:value})}>{label}</button>)}
          </div>
        </fieldset>
        <fieldset className="setting-group"><legend>Text size</legend>
          <div className="segmented" role="group" aria-label="Text size">
            {([['small','Small'],['default','Default'],['large','Large'],['extra_large','XL']] as const).map(([value,label]) => <button key={value} type="button" aria-pressed={preferences.font_scale===value} className={preferences.font_scale===value?'selected':''} onClick={() => void update({font_scale:value})}>{label}</button>)}
          </div>
        </fieldset>
        <fieldset className="setting-group"><legend>Layout density</legend>
          <div className="segmented"><button type="button" className={preferences.density==='comfortable'?'selected':''} aria-pressed={preferences.density==='comfortable'} onClick={() => void update({density:'comfortable'})}>Comfortable</button><button type="button" className={preferences.density==='compact'?'selected':''} aria-pressed={preferences.density==='compact'} onClick={() => void update({density:'compact'})}>Compact</button></div>
        </fieldset>
        <label className="toggle-row"><span><strong>High contrast</strong><small>Stronger borders and text contrast.</small></span><input type="checkbox" checked={preferences.contrast==='high'} onChange={(e)=>void update({contrast:e.target.checked?'high':'standard'})}/></label>
        <label className="toggle-row"><span><strong>Reduce motion</strong><small>Disables non-essential animation and transitions.</small></span><input type="checkbox" checked={preferences.reduce_motion} onChange={(e)=>void update({reduce_motion:e.target.checked})}/></label>
        <label className="toggle-row"><span><strong>Keyboard hints</strong><small>Show shortcut labels in the interface.</small></span><input type="checkbox" checked={preferences.show_keyboard_hints} onChange={(e)=>void update({show_keyboard_hints:e.target.checked})}/></label>
        <div className="setting-note"><SettingsIcon /> Preferences are saved per firm membership when authentication is active and fall back locally during development.</div>
      </div>
    </aside>
  </div>;
}
