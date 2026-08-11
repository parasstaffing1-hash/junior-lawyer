import type { ReactNode, SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps & { children: ReactNode }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;
}

export const HomeIcon = (p: IconProps) => <IconBase {...p}><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13v-9.5"/><path d="M9.5 20v-6h5v6"/></IconBase>;
export const FolderIcon = (p: IconProps) => <IconBase {...p}><path d="M3.5 7.5h6l2-2h9v13h-17z"/></IconBase>;
export const BookIcon = (p: IconProps) => <IconBase {...p}><path d="M4 5.5c2.5-.7 5-.3 8 1.3v12c-3-1.6-5.5-2-8-1.3z"/><path d="M20 5.5c-2.5-.7-5-.3-8 1.3v12c3-1.6 5.5-2 8-1.3z"/></IconBase>;
export const DocumentIcon = (p: IconProps) => <IconBase {...p}><path d="M6 3.5h8l4 4V20.5H6z"/><path d="M14 3.5v4h4"/><path d="M9 12h6M9 15.5h6"/></IconBase>;
export const ArchiveIcon = (p: IconProps) => <IconBase {...p}><path d="M4 7h16v13H4z"/><path d="M3 4h18v3H3zM9 11h6"/></IconBase>;
export const CalendarIcon = (p: IconProps) => <IconBase {...p}><rect x="4" y="5.5" width="16" height="14" rx="2"/><path d="M8 3.5v4M16 3.5v4M4 9.5h16"/></IconBase>;
export const ScaleIcon = (p: IconProps) => <IconBase {...p}><path d="M12 4v16M7 20h10M5 7h14"/><path d="m5 7-3 6h6zM19 7l-3 6h6z"/></IconBase>;
export const GridIcon = (p: IconProps) => <IconBase {...p}><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></IconBase>;
export const BellIcon = (p: IconProps) => <IconBase {...p}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M10 20h4"/></IconBase>;
export const SearchIcon = (p: IconProps) => <IconBase {...p}><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></IconBase>;
export const PlusIcon = (p: IconProps) => <IconBase {...p}><path d="M12 5v14M5 12h14"/></IconBase>;
export const SparklesIcon = (p: IconProps) => <IconBase {...p}><path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4z"/><path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/></IconBase>;
export const ShieldIcon = (p: IconProps) => <IconBase {...p}><path d="M12 3.5 19 6v5.2c0 4.6-2.8 7.5-7 9.3-4.2-1.8-7-4.7-7-9.3V6z"/><path d="m9 12 2 2 4-4"/></IconBase>;
export const LockIcon = (p: IconProps) => <IconBase {...p}><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></IconBase>;
export const UsersIcon = (p: IconProps) => <IconBase {...p}><path d="M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20"/><circle cx="9.5" cy="7" r="3.5"/><path d="M17 10a3 3 0 0 0 0-6M21 20v-1.5a4 4 0 0 0-3-3.7"/></IconBase>;

export const ReceiptIcon = (p: IconProps) => <IconBase {...p}><path d="M6 3.5h12v17l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2-2 1.2z"/><path d="M9 8h6M9 12h6M9 16h4"/></IconBase>;
export const MessageIcon = (p: IconProps) => <IconBase {...p}><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></IconBase>;
export const PulseIcon = (p: IconProps) => <IconBase {...p}><path d="M3 12h4l2-5 4 10 2-5h6"/></IconBase>;
export const MenuIcon = (p: IconProps) => <IconBase {...p}><path d="M4 7h16M4 12h16M4 17h16"/></IconBase>;
export const XIcon = (p: IconProps) => <IconBase {...p}><path d="m6 6 12 12M18 6 6 18"/></IconBase>;
export const SettingsIcon = (p: IconProps) => <IconBase {...p}><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.7-.6-1.4.9-1.9-2.1-2.1-1.9.9-1.4-.6L10.5 3h-3l-.7 2-1.4.6-1.9-.9-2.1 2.1.9 1.9-.6 1.4-2 .7v3l2 .7.6 1.4-.9 1.9 2.1 2.1 1.9-.9 1.4.6.7 2h3l.7-2 1.4-.6 1.9.9 2.1-2.1-.9-1.9.6-1.4z" transform="translate(2.25 0) scale(.82 1)"/></IconBase>;
export const HelpIcon = (p: IconProps) => <IconBase {...p}><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 1 1 3.7 2c-1 .7-1.5 1.2-1.5 2.3M12 17h.01"/></IconBase>;
export const ChevronLeftIcon = (p: IconProps) => <IconBase {...p}><path d="m14.5 6-6 6 6 6"/></IconBase>;
export const ChevronRightIcon = (p: IconProps) => <IconBase {...p}><path d="m9.5 6 6 6-6 6"/></IconBase>;
export const ZoomInIcon = (p: IconProps) => <IconBase {...p}><circle cx="10.5" cy="10.5" r="5.5"/><path d="M8 10.5h5M10.5 8v5M15 15l5 5"/></IconBase>;
export const ZoomOutIcon = (p: IconProps) => <IconBase {...p}><circle cx="10.5" cy="10.5" r="5.5"/><path d="M8 10.5h5M15 15l5 5"/></IconBase>;
