"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createIntegrationConnection, getIntegrationCatalog, getIntegrationsDashboard, testIntegrationConnection,
  type IntegrationCatalogRecord, type IntegrationConnectionCreatePayload, type IntegrationDashboardRecord,
  type IntegrationProviderKind,
} from "@/lib/api";
import { GridIcon, ShieldIcon } from "@/components/icons";

const nice=(v:string)=>v.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const dt=(v:string|null)=>v?new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short"}).format(new Date(v)):"Never";
const PROVIDER_DEFAULTS:Record<IntegrationProviderKind,{config:Record<string,string>;secrets:string[]}>= {
  google_workspace:{config:{client_id:"",sender_email:"",calendar_id:"primary"},secrets:["client_secret","refresh_token"]},
  razorpay:{config:{key_id:""},secrets:["key_secret","webhook_secret"]},
  docusign:{config:{account_id:"",base_url:"https://demo.docusign.net"},secrets:["access_token","webhook_hmac_secret"]},
  generic_webhook:{config:{allowed_hosts:"hooks.example.com"},secrets:["outbound_hmac_secret","inbound_hmac_secret"]},
  official_legal_import:{config:{allowed_source_domains:"indiacode.nic.in,judgments.ecourts.gov.in,sci.gov.in"},secrets:[]},
};

type Form={provider:IntegrationProviderKind;connection_key:string;display_name:string;config:Record<string,string>;secrets:Record<string,string>};
function initialForm(provider:IntegrationProviderKind="google_workspace"):Form{
  const d=PROVIDER_DEFAULTS[provider]; return {provider,connection_key:"",display_name:"",config:{...d.config},secrets:Object.fromEntries(d.secrets.map(k=>[k,`env://JL_${k.toUpperCase()}`]))};
}

export function IntegrationsWorkspace(){
  const [data,setData]=useState<IntegrationDashboardRecord|null>(null);
  const [catalog,setCatalog]=useState<IntegrationCatalogRecord[]>([]);
  const [form,setForm]=useState<Form>(()=>initialForm());
  const [show,setShow]=useState(false); const [busy,setBusy]=useState(false); const [error,setError]=useState<string|null>(null); const [message,setMessage]=useState<string|null>(null);
  const healthById=useMemo(()=>Object.fromEntries((data?.health??[]).map(h=>[h.connection_id,h])),[data]);
  const refresh=useCallback(async()=>{try{const [d,c]=await Promise.all([getIntegrationsDashboard(),getIntegrationCatalog()]);setData(d);setCatalog(c);setError(null)}catch(e){setError(e instanceof Error?e.message:"Unable to load integrations")}},[]);
  useEffect(()=>{void refresh()},[refresh]);
  function switchProvider(provider:IntegrationProviderKind){setForm(initialForm(provider));}
  async function create(){setBusy(true);setError(null);try{
    const cfg:Record<string,unknown>={...form.config};
    if(form.provider==="official_legal_import") cfg.allowed_source_domains=(form.config.allowed_source_domains||"").split(",").map(x=>x.trim()).filter(Boolean);
    if(form.provider==="generic_webhook") cfg.allowed_hosts=(form.config.allowed_hosts||"").split(",").map(x=>x.trim()).filter(Boolean);
    const item=catalog.find(x=>x.provider===form.provider);
    const payload:IntegrationConnectionCreatePayload={connection_key:form.connection_key,display_name:form.display_name,provider:form.provider,capabilities:item?.capabilities??[],config:cfg,secrets:Object.entries(form.secrets).filter(([,v])=>v.trim()).map(([secret_key,reference])=>({secret_key,reference,required:true}))};
    await createIntegrationConnection(payload);setShow(false);setForm(initialForm(form.provider));setMessage("Connection profile created. Secret values remain outside Junior Lawyer; only references are stored.");await refresh();
  }catch(e){setError(e instanceof Error?e.message:"Unable to create integration")}finally{setBusy(false)}}
  async function test(id:string,live=false){setBusy(true);setError(null);try{const r=await testIntegrationConnection(id,live);setMessage(`${live?"Live":"Configuration"} check: ${nice(r.status)}${r.error?` · ${r.error}`:""}`);await refresh()}catch(e){setError(e instanceof Error?e.message:"Integration test failed")}finally{setBusy(false)}}
  return <main className="workspace-page integrations-workspace">
    <header className="workspace-header"><div><div className="eyebrow">External systems</div><h1>Integrations</h1><p>Email, calendar, payments, e-signature and approved data connectors with explicit secret and webhook boundaries.</p></div><div className="health-header-actions"><button className="secondary-button" onClick={()=>void refresh()}>Refresh</button><button className="primary-button" onClick={()=>setShow(true)}>New connection</button></div></header>
    {error?<div className="error-banner">{error}</div>:null}{message?<div className="jobs-message">{message}</div>:null}
    <section className="metrics-grid"><div className="metric-card"><span>Connections</span><strong>{data?.connections.length??0}</strong><small>Firm-scoped providers</small></div><div className="metric-card"><span>Connected</span><strong>{data?.connected_count??0}</strong><small>Latest health check passed</small></div><div className="metric-card"><span>Needs attention</span><strong>{data?.degraded_count??0}</strong><small>Missing/invalid runtime config</small></div><div className="metric-card"><span>Provider types</span><strong>{Object.keys(data?.provider_counts??{}).length}</strong><small>Google, payments, e-sign & data</small></div></section>
    <div className="deployment-grid"><section className="premium-panel"><div className="panel-title-row"><h2>Connections</h2><span>{data?.connections.length??0}</span></div>{data?.connections.length?data.connections.map(c=>{const h=healthById[c.id];return <div className="deployment-env" key={c.id}><div><strong>{c.display_name}</strong><small>{nice(c.provider)} · {c.connection_key} · checked {dt(h?.checked_at??null)}</small>{h?.checks_json?.length?<small>{h.checks_json.filter(x=>x.passed).length}/{h.checks_json.length} configuration checks passed</small>:null}</div><div className="health-header-actions"><span className={`release-pill ${c.status==="connected"?"passed":c.status==="degraded"?"failed":"pending"}`}>{nice(c.status)}</span><button className="ghost-button" disabled={busy} onClick={()=>void test(c.id,false)}>Check</button>{c.provider==="google_workspace"?<button className="secondary-button" disabled={busy} onClick={()=>void test(c.id,true)}>OAuth probe</button>:null}</div></div>}):<div className="empty-state compact"><div className="empty-state-title">No integrations configured</div><div className="empty-state-copy">Connections store public configuration and secret references only. Provider credentials remain in the runtime secret store.</div></div>}</section>
      <section className="premium-panel"><div className="panel-title-row"><h2>Connector catalog</h2><span>{catalog.length}</span></div>{catalog.map(item=><div className="deployment-service" key={item.provider}><span className="health-dot healthy"/><div><strong>{item.title}</strong><small>{item.description}</small><small>{item.capabilities.join(" · ")}</small></div><span>{item.required_secrets.length?`${item.required_secrets.length} secret refs`:"No secrets"}</span></div>)}</section></div>
    <section className="premium-panel"><div className="deployment-secret-note"><ShieldIcon/><div><strong>Credentials do not live in the application database.</strong><p>The built-in resolver accepts <code>env://NAME</code>. Vault/cloud secret-manager support remains an explicit adapter boundary. Provider webhook bodies are hashed and reduced to normalized event metadata rather than copied into logs.</p></div></div></section>
    {show?<div className="modal-backdrop" onMouseDown={e=>{if(e.currentTarget===e.target)setShow(false)}}><div className="modal-card deployment-create"><div className="panel-title-row"><h2>New integration</h2><button className="ghost-button" onClick={()=>setShow(false)}>Close</button></div><label>Provider<select value={form.provider} onChange={e=>switchProvider(e.target.value as IntegrationProviderKind)}>{catalog.map(x=><option value={x.provider} key={x.provider}>{x.title}</option>)}</select></label><label>Connection key<input placeholder="google-primary" value={form.connection_key} onChange={e=>setForm({...form,connection_key:e.target.value})}/></label><label>Display name<input placeholder="Primary Google Workspace" value={form.display_name} onChange={e=>setForm({...form,display_name:e.target.value})}/></label>{Object.entries(form.config).map(([k,v])=><label key={k}>{nice(k)}<input value={v} onChange={e=>setForm({...form,config:{...form.config,[k]:e.target.value}})}/></label>)}{Object.entries(form.secrets).map(([k,v])=><label key={k}>{nice(k)} reference<input value={v} onChange={e=>setForm({...form,secrets:{...form.secrets,[k]:e.target.value}})}/></label>)}<div className="deployment-create-note"><GridIcon/><span>Only references are stored. Put actual credentials in environment/Vault/cloud secret manager before running a live operation.</span></div><button className="primary-button" disabled={busy||!form.connection_key||!form.display_name} onClick={()=>void create()}>{busy?"Creating…":"Create connection"}</button></div></div>:null}
  </main>;
}
