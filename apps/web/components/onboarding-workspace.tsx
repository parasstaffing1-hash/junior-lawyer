"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BookIcon, DocumentIcon, FolderIcon, SearchIcon, SettingsIcon } from "@/components/icons";
import { getOnboardingProgress, updateOnboardingProgress, type OnboardingProgress } from "@/lib/api";

// The checklist renders before the API answers, so the local state carries only
// the fields the UI reads; `id`/`updated_at` exist on a persisted progress row
// but have no meaning until the first save.
type OnboardingProgressState = Pick<OnboardingProgress, "completed_steps_json" | "current_step" | "completed_at" | "dismissed_at">;
import { useExperience } from "@/components/experience-provider";

const steps = [
  { id:"profile", title:"Choose your workspace preferences", hi:"अपनी कार्यस्थान सेटिंग चुनें", copy:"Set interface language, text size, contrast and motion.", href:"#preferences", icon:SettingsIcon },
  { id:"first_matter", title:"Open your first matter", hi:"अपना पहला मामला खोलें", copy:"Create or open a matter so documents and legal work stay source-backed.", href:"/matters?new=1", icon:FolderIcon },
  { id:"first_document", title:"Add a legal document", hi:"कानूनी दस्तावेज़ जोड़ें", copy:"Upload PDF/DOCX/image files; scans can use local हिन्दी + English OCR.", href:"/matters", icon:DocumentIcon },
  { id:"search", title:"Try universal legal search", hi:"यूनिवर्सल कानूनी खोज आज़माएँ", copy:"Search matters, documents, statutes, judgments and firm precedent from one box.", href:"/search", icon:SearchIcon },
  { id:"keyboard", title:"Learn the keyboard workflow", hi:"कीबोर्ड वर्कफ़्लो सीखें", copy:"Use Ctrl/Cmd + K for universal navigation and ? for shortcut help.", href:"#keyboard", icon:BookIcon },
];

export function OnboardingWorkspace(){
  const {preferences,update}=useExperience(); const [progress,setProgress]=useState<OnboardingProgressState>({completed_steps_json:[],current_step:null,completed_at:null,dismissed_at:null}); const [saving,setSaving]=useState(false);
  useEffect(()=>{void getOnboardingProgress().then(setProgress).catch(()=>undefined)},[]);
  const completed=new Set(progress.completed_steps_json); const percent=Math.round((completed.size/steps.length)*100);
  const labels=useMemo(()=>preferences.ui_language==='hi'?{eyebrow:'शुरुआत',title:'Junior Lawyer सेट करें',sub:'लगभग पाँच छोटे चरण। सभी सेटिंग बाद में बदली जा सकती हैं।',done:'पूर्ण',mark:'पूर्ण चिह्नित करें'}:{eyebrow:'Getting started',title:'Set up Junior Lawyer',sub:'Five short steps. Everything can be changed later.',done:'Complete',mark:'Mark complete'},[preferences.ui_language]);
  async function toggle(id:string){setSaving(true);const next=completed.has(id)?progress.completed_steps_json.filter(x=>x!==id):[...progress.completed_steps_json,id]; const optimistic={...progress,completed_steps_json:next};setProgress(optimistic);try{setProgress(await updateOnboardingProgress({completed_steps:next,current_step:id}));}catch{}finally{setSaving(false)}}
  return <div className="page onboarding-page"><div className="hero-row"><div><div className="eyebrow">{labels.eyebrow}</div><h1 className="page-title">{labels.title}</h1><p className="page-subtitle">{labels.sub}</p></div><div className="onboarding-progress" aria-label={`${percent}% complete`}><strong>{percent}%</strong><span>{completed.size}/{steps.length} {labels.done}</span></div></div>
    <div className="progress-track" aria-hidden="true"><span style={{width:`${percent}%`}}/></div>
    <div className="onboarding-grid">{steps.map(({id,title,hi,copy,href,icon:Icon},index)=><article key={id} className={`onboarding-step${completed.has(id)?' complete':''}`}><div className="onboarding-step-index"><span>{index+1}</span><Icon/></div><div><h2>{preferences.ui_language==='hi'?hi:preferences.ui_language==='bilingual'?`${title} · ${hi}`:title}</h2><p>{copy}</p><div className="onboarding-step-actions">{href.startsWith('#')?<button className="secondary-button" type="button" onClick={()=>{if(id==='profile')window.dispatchEvent(new Event('jl:open-preferences'));else window.dispatchEvent(new Event('jl:open-keyboard-help'));}}>Open</button>:<Link className="secondary-button" href={href}>Open</Link>}<button className="quiet-action" disabled={saving} aria-pressed={completed.has(id)} onClick={()=>void toggle(id)}>{completed.has(id)?'✓ Completed':labels.mark}</button></div></div></article>)}</div>
    <section className="onboarding-tip" id="preferences"><strong>Privacy-first by default.</strong><span>Display preferences are per-user. Legal data, ethical-wall permissions and document access remain governed by the existing security layer.</span></section>
  </div>;
}
