import { ConversationWorkspace } from "@/components/conversation-workspace";
import { getAIProviderStatus, getMatters } from "@/lib/server-api";

export const metadata = {
  title: "Ask Junior Lawyer",
  description: "Threaded legal questions and answers with cited sources.",
};

export default async function ChatPage() {
  let matters = [] as Awaited<ReturnType<typeof getMatters>>;
  let providers = null as Awaited<ReturnType<typeof getAIProviderStatus>> | null;
  let error = "";
  try {
    [matters, providers] = await Promise.all([getMatters(), getAIProviderStatus()]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Unable to load the assistant";
  }
  return (
    <main className="page">
      <div className="hero-row ai-hero">
        <div>
          <div className="eyebrow">Verified reasoning layer</div>
          <h1 className="page-title">Ask Junior Lawyer</h1>
          <p className="page-subtitle">
            Keep a thread on one question. Every answer records the sources it was built
            from, and follow-ups carry the earlier turns.
          </p>
        </div>
      </div>
      {error ? <div className="notice-panel">{error}</div> : null}
      {!error && providers ? <ConversationWorkspace matters={matters} providers={providers} /> : null}
    </main>
  );
}
