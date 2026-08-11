import { DocumentReader } from "@/components/document-reader";

export default async function DocumentPage({ params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  return <DocumentReader documentId={documentId} />;
}
