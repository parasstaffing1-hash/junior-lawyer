"use client";

import { BellIcon, HelpIcon, MenuIcon, SearchIcon, SettingsIcon } from "@/components/icons";
import { useExperience } from "@/components/experience-provider";

export function Topbar() {
  const {preferences, update}=useExperience();
  const hi=preferences.ui_language==='hi'; const both=preferences.ui_language==='bilingual';
  const searchLabel=hi?'मामले, कानून और दस्तावेज़ खोजें…':both?'Search / खोजें…':'Search matters, law, documents…';
  const languageLabel=hi?'साइट की भाषा':both?'Site language / साइट की भाषा':'Site language';
  return <header className="topbar">
    <div className="topbar-leading"><button className="icon-button mobile-menu-button" aria-label="Open navigation" type="button" onClick={()=>window.dispatchEvent(new Event('jl:toggle-nav'))}><MenuIcon/></button>
      <button className="search-button" type="button" aria-label={searchLabel} onClick={()=>window.dispatchEvent(new Event('jl:open-search'))}><SearchIcon/><span className="search-label">{searchLabel}</span>{preferences.show_keyboard_hints?<span className="search-shortcut">⌘K</span>:null}</button>
    </div>
    <div className="top-actions"><label className="language-switcher"><span className="sr-only">{languageLabel}</span><select aria-label={languageLabel} value={preferences.ui_language} onChange={(event)=>void update({ui_language:event.target.value as "en"|"hi"|"bilingual"})}><option value="en">EN</option><option value="hi">हिन्दी</option><option value="bilingual">EN + हिन्दी</option></select></label><button className="icon-button desktop-help" title="Keyboard shortcuts" aria-label="Keyboard shortcuts" type="button" onClick={()=>window.dispatchEvent(new Event('jl:open-keyboard-help'))}><HelpIcon/></button><button className="icon-button" title="Display settings" aria-label="Display and accessibility settings" type="button" onClick={()=>window.dispatchEvent(new Event('jl:open-preferences'))}><SettingsIcon/></button><button className="icon-button" aria-label="Notifications" type="button"><BellIcon/></button><div className="avatar" aria-label="Current user">WJ</div></div>
  </header>;
}
