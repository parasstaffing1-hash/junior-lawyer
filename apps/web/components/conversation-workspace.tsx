"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ShieldIcon } from "@/components/icons";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  postConversationMessage,
  setConversationStatus,
  type AIProviderStatus,
  type AIRun,
  type Conversation,
  type ConversationMessage,
  type Matter,
} from "@/lib/api";

/**
 * Threaded legal Q&A.
 *
 * Every answer is still a verified AI run, so the citation and verification
 * state shown here is the same one the single-shot assistant produces — the
 * thread only adds continuity.
 */
export function ConversationWorkspace({
  matters,
  providers,
}: {
  matters: Matter[];
  providers: AIProviderStatus;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [runs, setRuns] = useState<Record<string, AIRun>>({});
  const [question, setQuestion] = useState("");
  const [matterId, setMatterId] = useState("");
  const [allowRemote, setAllowRemote] = useState(false);
  const [allowComplex, setAllowComplex] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  const loadList = useCallback(async () => {
    try { setConversations(await listConversations({ limit: 50 })); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load conversations"); }
  }, []);

  const openThread = useCallback(async (id: string) => {
    setError("");
    try {
      const detail = await getConversation(id);
      setActiveId(id);
      setMessages(detail.messages ?? []);
      setMatterId(detail.conversation.matter_id ?? "");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to open conversation"); }
  }, []);

  useEffect(() => { void loadList(); }, [loadList]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);

  async function startThread() {
    setError("");
    try {
      const created = await createConversation({ matter_id: matterId || undefined });
      await loadList();
      setActiveId(created.id);
      setMessages([]);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to start a conversation"); }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text) return;
    setBusy(true); setError("");
    let threadId = activeId;
    try {
      if (!threadId) {
        const created = await createConversation({ matter_id: matterId || undefined });
        threadId = created.id;
        setActiveId(threadId);
        setMessages([]);
      }
      const turn = await postConversationMessage(threadId, {
        question: text,
        allow_remote: allowRemote,
        allow_local_for_high_complexity: allowComplex,
      });
      setMessages((current) => [...current, turn.question, turn.answer]);
      setRuns((current) => ({ ...current, [turn.answer.id]: turn.run }));
      setQuestion("");
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The assistant could not answer");
    } finally { setBusy(false); }
  }

  async function archive(id: string) {
    try { await setConversationStatus(id, "archived"); await loadList(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to archive"); }
  }

  async function remove(id: string) {
    try {
      await deleteConversation(id);
      if (id === activeId) { setActiveId(""); setMessages([]); }
      await loadList();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to delete"); }
  }

  return (
    <div className="conversation-layout">
      <aside className="conversation-list">
        <div className="conversation-list-head">
          <h3>Conversations</h3>
          <button className="primary-button" type="button" onClick={startThread}>New</button>
        </div>
        {conversations.length === 0 ? (
          <p className="muted">No conversations yet. Ask a question to start one.</p>
        ) : (
          <ul>
            {conversations.map((conversation) => (
              <li key={conversation.id} className={conversation.id === activeId ? "active" : ""}>
                <button type="button" onClick={() => void openThread(conversation.id)}>
                  <strong>{conversation.title}</strong>
                  <small>{conversation.message_count} message{conversation.message_count === 1 ? "" : "s"}{conversation.status === "archived" ? " · archived" : ""}</small>
                </button>
                <span className="conversation-row-actions">
                  {conversation.status === "active" ? (
                    <button type="button" title="Archive" onClick={() => void archive(conversation.id)}>Archive</button>
                  ) : null}
                  <button type="button" title="Delete" onClick={() => void remove(conversation.id)}>Delete</button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="conversation-thread">
        {!providers.ai_enabled ? (
          <div className="notice-panel">
            No model is configured, so answers will be refused by the router.
            Set <code>AI_ENABLED</code> and a provider in the API environment.
          </div>
        ) : null}

        <div className="conversation-messages">
          {messages.length === 0 ? (
            <div className="conversation-empty">
              <h2>{active ? active.title : "Ask a legal question"}</h2>
              <p className="muted">
                Answers cite the sources they were built from. Follow-up questions keep the
                thread&apos;s context, so you can ask &ldquo;and if it is served late?&rdquo;
                without repeating yourself.
              </p>
            </div>
          ) : (
            messages.map((message) => {
              const run = message.run_id ? runs[message.id] : undefined;
              return (
                <article key={message.id} className={`conversation-message ${message.role}`}>
                  <div className="conversation-message-role">{message.role === "user" ? "You" : "Junior Lawyer"}</div>
                  <div className="conversation-message-body">{message.content || "—"}</div>
                  {run ? (
                    <div className="conversation-message-meta">
                      <span><ShieldIcon /> {run.verification_status}</span>
                      <span>{(run.sources ?? []).length} source{(run.sources ?? []).length === 1 ? "" : "s"}</span>
                      {run.model_name ? <span>{run.model_name}</span> : null}
                    </div>
                  ) : null}
                </article>
              );
            })
          )}
          <div ref={endRef} />
        </div>

        {error ? <div className="auth-error">{error}</div> : null}

        <form className="conversation-composer" onSubmit={send}>
          <div className="conversation-composer-controls">
            <label>Matter
              <select value={matterId} onChange={(e) => setMatterId(e.target.value)} disabled={Boolean(activeId)}>
                <option value="">No matter</option>
                {matters.map((matter) => <option key={matter.id} value={matter.id}>{matter.title}</option>)}
              </select>
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={allowComplex} onChange={(e) => setAllowComplex(e.target.checked)} />
              Allow local model for complex reasoning
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={allowRemote} onChange={(e) => setAllowRemote(e.target.checked)} />
              Allow remote model
            </label>
          </div>
          <div className="conversation-composer-row">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about a statute, a clause, a deadline, or this matter…"
              rows={3}
              required
            />
            <button className="primary-button" type="submit" disabled={busy}>
              {busy ? "Thinking…" : "Send"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
