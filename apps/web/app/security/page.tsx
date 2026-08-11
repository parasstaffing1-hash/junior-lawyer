import { SecurityWorkspace } from "@/components/security-workspace";

export default function SecurityPage() {
  return (
    <main className="page">
      <div className="hero-row security-hero">
        <div>
          <div className="eyebrow">Firm administration</div>
          <h1 className="page-title">Security & access</h1>
          <p className="page-subtitle">People, matter confidentiality, remote-AI policy, legal holds, retention and a tamper-evident security trail in one restrained workspace.</p>
        </div>
        <div className="security-hero-note"><ShieldIconProxy /><div><strong>Least privilege</strong><span>Ethical walls require explicit access</span></div></div>
      </div>
      <SecurityWorkspace />
    </main>
  );
}

function ShieldIconProxy() {
  return <span className="security-hero-shield" aria-hidden="true">✓</span>;
}
