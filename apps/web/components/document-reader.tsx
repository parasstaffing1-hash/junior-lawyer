"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronLeftIcon, ChevronRightIcon, SearchIcon, ZoomInIcon, ZoomOutIcon } from "@/components/icons";
import { findInDocument, getDocument, getDocumentPageWindow, type DocumentPageMatch, type DocumentPageWindow, type LegalDocument } from "@/lib/api";
import { useExperience } from "@/components/experience-provider";

function languageLabel(value: string) { return value === "hi" ? "हिन्दी" : value === "mixed" ? "English + हिन्दी" : value === "hinglish" ? "Hinglish" : value === "en" ? "English" : "Unknown"; }

export function DocumentReader({ documentId }: { documentId: string }) {
  const params=useSearchParams(); const {preferences,update}=useExperience();
  const requested=Math.max(1,Number(params?.get('page')||'1')||1);
  const [document,setDocument]=useState<LegalDocument|null>(null); const [windowData,setWindowData]=useState<DocumentPageWindow|null>(null);
  const [startPage,setStartPage]=useState(requested); const [busy,setBusy]=useState(true); const [error,setError]=useState("");
  const [query,setQuery]=useState(""); const [matches,setMatches]=useState<DocumentPageMatch[]>([]); const [searching,setSearching]=useState(false);
  const windowSize=Math.max(2,Math.min(30,preferences.document_page_window||8)); const zoom=preferences.document_text_zoom||100;

  const load=useCallback(async(page:number)=>{setBusy(true);setError("");try{const [doc,pages]=await Promise.all([document?Promise.resolve(document):getDocument(documentId),getDocumentPageWindow(documentId,page,windowSize)]);setDocument(doc);setWindowData(pages);setStartPage(pages.start_page);window.history.replaceState(null,"",`/documents/${documentId}?page=${pages.start_page}`);}catch(e){setError(e instanceof Error?e.message:"Unable to open document");}finally{setBusy(false);}},[document,documentId,windowSize]);
  useEffect(()=>{void load(requested);},[documentId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(()=>{if(!query.trim()){setMatches([]);return;} const timer=window.setTimeout(async()=>{setSearching(true);try{setMatches(await findInDocument(documentId,query.trim(),50));}catch{setMatches([]);}finally{setSearching(false);}},220);return()=>window.clearTimeout(timer);},[documentId,query]);

  const total=windowData?.total_pages||document?.page_count||0; const range=windowData?`${windowData.start_page}–${windowData.end_page}`:"…";
  const status=useMemo(()=>document?`${languageLabel(document.detected_language)} · ${document.page_count||0} pages · ${document.ocr_used?'OCR':'native text'}`:"Loading document…",[document]);
  return <div className="document-reader-page">
    <header className="reader-header">
      <div className="reader-title-group"><Link className="reader-back" href={document?`/matters/${document.matter_id}?tab=documents`:"/matters"}>← Back to matter</Link><h1>{document?.filename||"Document"}</h1><p>{status}</p></div>
      <div className="reader-controls" aria-label="Document reader controls">
        <button className="icon-button bordered" aria-label="Zoom out" disabled={zoom<=75} onClick={()=>void update({document_text_zoom:Math.max(75,zoom-10)})}><ZoomOutIcon/></button><span className="reader-zoom" aria-live="polite">{zoom}%</span><button className="icon-button bordered" aria-label="Zoom in" disabled={zoom>=175} onClick={()=>void update({document_text_zoom:Math.min(175,zoom+10)})}><ZoomInIcon/></button>
      </div>
    </header>
    <div className="reader-layout">
      <aside className="reader-sidebar" aria-label="Find in document">
        <label className="reader-search"><SearchIcon/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Find / खोजें" aria-label="Find text in document"/></label>
        <div className="reader-search-meta">{query.trim()?(searching?'Searching…':`${matches.length} matching pages`):'Search page text without loading the full document.'}</div>
        <div className="reader-match-list">{matches.map((match)=><button key={match.page_number} type="button" onClick={()=>void load(match.page_number)} className="reader-match"><strong>Page {match.page_number}</strong><span>{match.snippet}</span><small>{match.match_count} match{match.match_count===1?'':'es'}</small></button>)}</div>
      </aside>
      <section className="reader-document" aria-busy={busy} aria-label="Document pages">
        <div className="reader-pagination"><button className="secondary-button" disabled={!windowData?.has_previous||busy} onClick={()=>void load(Math.max(1,startPage-windowSize))}><ChevronLeftIcon/> Previous</button><span>Pages {range} of {total}</span><button className="secondary-button" disabled={!windowData?.has_next||busy} onClick={()=>void load((windowData?.end_page||startPage)+1)}>Next <ChevronRightIcon/></button></div>
        {error?<div className="error-state" role="alert"><strong>Unable to load document</strong><span>{error}</span><button className="secondary-button" onClick={()=>void load(startPage)}>Try again</button></div>:null}
        {busy&&!windowData?<div className="reader-skeleton" aria-label="Loading document"><div/><div/><div/></div>:null}
        <div className="reader-pages" style={{['--reader-zoom' as string]:String(zoom/100)}}>{windowData?.pages.map((page)=><article className="reader-page-sheet" data-document-page={page.page_number} id={`page-${page.page_number}`} key={page.id} aria-labelledby={`page-label-${page.page_number}`}><div className="reader-page-number" id={`page-label-${page.page_number}`}>Page {page.page_number}</div><pre lang={page.detected_language==='hi'?'hi':'en'}>{page.text||'[No extractable text on this page]'}</pre></article>)}</div>
        <div className="reader-pagination bottom"><button className="secondary-button" disabled={!windowData?.has_previous||busy} onClick={()=>void load(Math.max(1,startPage-windowSize))}><ChevronLeftIcon/> Previous</button><span>Pages {range} of {total}</span><button className="secondary-button" disabled={!windowData?.has_next||busy} onClick={()=>void load((windowData?.end_page||startPage)+1)}>Next <ChevronRightIcon/></button></div>
      </section>
    </div>
  </div>;
}
