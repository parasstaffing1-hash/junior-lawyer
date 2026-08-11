import { CaseDetailWorkspace } from "@/components/case-detail-workspace";
export default async function CasePage({params}:{params:Promise<{savedCaseId:string}>}){const {savedCaseId}=await params;return <CaseDetailWorkspace savedCaseId={savedCaseId}/>;}
