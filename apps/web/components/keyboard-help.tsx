"use client";
import { useEffect, useRef, useState } from "react";
import { HelpIcon, XIcon } from "@/components/icons";

const rows = [
  ["Ctrl/Cmd + K", "Universal search"], ["?", "Keyboard shortcuts"], ["Esc", "Close dialog"],
  ["↑ / ↓", "Move through command results"], ["Enter", "Open selected result"], ["G M", "Matters (command palette)"],
  ["G R", "Research (command palette)"], ["G E", "Evidence (command palette)"],
];
export function KeyboardHelp() {
  const [open,setOpen]=useState(false); const closeRef=useRef<HTMLButtonElement>(null);
  useEffect(()=>{ const key=(e:KeyboardEvent)=>{ if(e.key==='?' && !['INPUT','TEXTAREA','SELECT'].includes((e.target as HTMLElement)?.tagName)){e.preventDefault();setOpen(true);} }; const custom=()=>setOpen(true); window.addEventListener('keydown',key); window.addEventListener('jl:open-keyboard-help',custom); return()=>{window.removeEventListener('keydown',key);window.removeEventListener('jl:open-keyboard-help',custom);};},[]);
  useEffect(()=>{if(open) window.setTimeout(()=>closeRef.current?.focus(),20);},[open]);
  if(!open)return null;
  return <div className="command-overlay" role="presentation" onMouseDown={(e)=>{if(e.currentTarget===e.target)setOpen(false)}}><section className="shortcut-dialog" role="dialog" aria-modal="true" aria-labelledby="shortcut-title"><div className="drawer-header"><div><div className="eyebrow">Keyboard first</div><h2 id="shortcut-title">Shortcuts</h2></div><button ref={closeRef} className="icon-button" aria-label="Close keyboard shortcuts" onClick={()=>setOpen(false)}><XIcon/></button></div><div className="shortcut-list">{rows.map(([key,label])=><div className="shortcut-row" key={key}><kbd>{key}</kbd><span>{label}</span></div>)}</div><div className="setting-note"><HelpIcon/> Shortcuts never override typing inside form fields.</div></section></div>;
}
