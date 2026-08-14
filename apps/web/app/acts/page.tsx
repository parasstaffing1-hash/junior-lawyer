import { ActsWorkspace } from "@/components/acts-workspace";

export const metadata = {
  title: "Acts and statutes",
  description: "Browse and search bare acts, and read a provision in English or Hindi.",
};

export default function ActsPage() {
  return (
    <main className="page">
      <div className="hero-row">
        <div>
          <div className="eyebrow">Legal library</div>
          <h1 className="page-title">Acts</h1>
          <p className="page-subtitle">
            Central and state acts, searchable by title, short title or act number, in
            English and Hindi. Open an act to read its sections.
          </p>
        </div>
      </div>
      <ActsWorkspace />
    </main>
  );
}
