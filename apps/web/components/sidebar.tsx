"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArchiveIcon, BellIcon, BookIcon, CalendarIcon, DocumentIcon, FolderIcon, GridIcon, HomeIcon, PlusIcon, ScaleIcon, ShieldIcon, SparklesIcon, UsersIcon, ReceiptIcon, MessageIcon, SearchIcon, PulseIcon, XIcon } from "@/components/icons";
import { useExperience } from "@/components/experience-provider";

const items = [
  { key:"overview", label: "Overview", hi:"अवलोकन", href: "/", icon: HomeIcon },
  { key:"matters", label: "Matters", hi:"मामले", href: "/matters", icon: FolderIcon },
  { key:"cases", label: "Case Lookup", hi:"केस खोज", href: "/cases", icon: ScaleIcon },
  { key:"search", label: "Search", hi:"खोज", href: "/search", icon: SearchIcon },
  { key:"tools", label: "Tools", hi:"उपकरण", href: "/tools", icon: GridIcon },
  { key:"clients", label: "Clients", hi:"मुवक्किल", href: "/clients", icon: UsersIcon },
  { key:"research", label: "Research", hi:"कानूनी शोध", href: "/research", icon: BookIcon },
  { key:"legal-data", label: "Legal data", hi:"कानूनी डेटा", href: "/legal-data", icon: BookIcon },
  { key:"evidence", label: "Evidence", hi:"साक्ष्य", href: "/evidence", icon: ScaleIcon },
  { key:"knowledge", label: "Knowledge", hi:"ज्ञान", href: "/knowledge", icon: GridIcon },
  { key:"chat", label: "Ask", hi:"पूछें", href: "/chat", icon: SparklesIcon },
  { key:"assistant", label: "Assistant", hi:"सहायक", href: "/assistant", icon: SparklesIcon },
  { key:"contracts", label: "Contracts", hi:"अनुबंध", href: "/contracts", icon: DocumentIcon },
  { key:"drafting", label: "Drafting", hi:"ड्राफ्टिंग", href: "/drafting", icon: ArchiveIcon },
  { key:"calendar", label: "Calendar", hi:"कैलेंडर", href: "/calendar", icon: CalendarIcon },
  { key:"operations", label: "Operations", hi:"कार्य संचालन", href: "/operations", icon: BellIcon },
  { key:"jobs", label: "Jobs", hi:"जॉब्स", href: "/jobs", icon: ArchiveIcon },
  { key:"health", label: "System health", hi:"सिस्टम स्वास्थ्य", href: "/system-health", icon: PulseIcon },
  { key:"quality", label: "Quality", hi:"गुणवत्ता", href: "/qa", icon: ShieldIcon },
  { key:"release", label: "Release", hi:"रिलीज़", href: "/release", icon: PulseIcon },
  { key:"validation", label: "RC validation", hi:"आरसी सत्यापन", href: "/validation", icon: ShieldIcon },
  { key:"deployment", label: "Deployment", hi:"डिप्लॉयमेंट", href: "/deployment", icon: ShieldIcon },
  { key:"integrations", label: "Integrations", hi:"एकीकरण", href: "/integrations", icon: GridIcon },
  { key:"analytics", label: "Analytics", hi:"विश्लेषण", href: "/analytics", icon: GridIcon },
  { key:"billing", label: "Billing", hi:"बिलिंग", href: "/billing", icon: ReceiptIcon },
  { key:"money", label: "Client money", hi:"मुवक्किल धन", href: "/finance", icon: ScaleIcon },
  { key:"collaboration", label: "Collaboration", hi:"सहयोग", href: "/collaboration", icon: MessageIcon },
  { key:"security", label: "Security", hi:"सुरक्षा", href: "/security", icon: ShieldIcon },
];

function visibleLabel(label:string, hi:string, language:string) {
  if (language === "hi") return hi;
  if (language === "bilingual") return `${label} · ${hi}`;
  return label;
}

export function Sidebar({ mobileOpen=false, onClose }: { mobileOpen?: boolean; onClose?: () => void }) {
  const pathname = usePathname() ?? ""; const {preferences}=useExperience();
  return <>
    {mobileOpen ? <button className="mobile-nav-backdrop" aria-label="Close navigation" onClick={onClose} /> : null}
    <aside className={`sidebar${mobileOpen ? " mobile-open" : ""}`} aria-label="Primary navigation">
      <div className="sidebar-mobile-head"><div className="brand"><div className="brand-mark">JL</div><span>Junior Lawyer</span></div><button className="icon-button sidebar-close" type="button" aria-label="Close navigation" onClick={onClose}><XIcon/></button></div>
      <div className="brand desktop-brand"><div className="brand-mark">JL</div><span>Junior Lawyer</span><span className="brand-caret" aria-hidden="true">⌄</span></div>
      <div className="sidebar-quick-actions">
        <button className="sidebar-quick-action" type="button" onClick={() => window.dispatchEvent(new Event("jl:open-search"))}><SearchIcon/><span>{preferences.ui_language === "hi" ? "त्वरित खोज" : "Quick find"}</span><kbd>⌘K</kbd></button>
        <Link className="sidebar-quick-action" href="/matters"><PlusIcon/><span>{preferences.ui_language === "hi" ? "नया मामला" : "New matter"}</span></Link>
      </div>
      <div className="nav-label">{preferences.ui_language==='hi'?'कार्यस्थान':'Workspace'}</div>
      <nav className="sidebar-scroll">{items.map((item) => { const Icon=item.icon; const active=item.href==='/'?pathname==='/':pathname===item.href||pathname.startsWith(`${item.href}/`); const label=visibleLabel(item.label,item.hi,preferences.ui_language); return <Link aria-current={active?'page':undefined} title={label} className={`nav-item${active?' active':''}`} href={item.href} key={item.key}><Icon/><span>{label}</span></Link>; })}</nav>
      <div className="sidebar-bottom">
        <div className="nav-label">{preferences.ui_language==='hi'?'पुस्तकालय':'Library'}</div>
        <Link className="nav-item" href="/research"><ScaleIcon/><span>{visibleLabel('Legal sources','कानूनी स्रोत',preferences.ui_language)}</span></Link>
        <Link className="nav-item" href="/knowledge"><BookIcon/><span>{visibleLabel('Firm precedents','फर्म नज़ीरें',preferences.ui_language)}</span></Link>
        <Link className="nav-item" href="/contracts"><GridIcon/><span>{visibleLabel('Clause library','क्लॉज़ लाइब्रेरी',preferences.ui_language)}</span></Link>
      </div>
    </aside>
  </>;
}
