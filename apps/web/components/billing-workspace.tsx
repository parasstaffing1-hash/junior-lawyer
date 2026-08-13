"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  BillingExpense, BillingInvoice, BillingOverview, BillingPayment, BillingProfile, CRMClient,
  createBillingExpense, createBillingInvoice, createBillingPayment, getBillingExpenses,
  getBillingInvoices, getBillingOverview, getBillingPayments, getBillingProfile, getCRMClients,
  issueBillingInvoice, reviewBillingInvoice, updateBillingProfile,
} from "@/lib/api";
import { ReceiptIcon, ShieldIcon } from "@/components/icons";

type Tab = "overview" | "invoices" | "expenses" | "settings";

const money = (value: string | number, currency = "INR") => {
  const number = Number(value || 0);
  try { return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(number); }
  catch { return `${currency} ${number.toFixed(2)}`; }
};
const today = () => new Date().toISOString().slice(0, 10);

export function BillingWorkspace() {
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [profile, setProfile] = useState<BillingProfile | null>(null);
  const [clients, setClients] = useState<CRMClient[]>([]);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [expenses, setExpenses] = useState<BillingExpense[]>([]);
  const [payments, setPayments] = useState<BillingPayment[]>([]);
  const [selected, setSelected] = useState<BillingInvoice | null>(null);
  const [composer, setComposer] = useState<"invoice" | "expense" | "payment" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [o, p, c, i, e, pay] = await Promise.all([
        getBillingOverview(), getBillingProfile(), getCRMClients(), getBillingInvoices(), getBillingExpenses(), getBillingPayments(),
      ]);
      setOverview(o); setProfile(p); setClients(c); setInvoices(i); setExpenses(e); setPayments(pay);
      setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load billing workspace"); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const openInvoices = useMemo(() => invoices.filter(i => ["issued", "partially_paid"].includes(i.status)), [invoices]);

  async function submitInvoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const f = new FormData(event.currentTarget);
    try {
      const invoice = await createBillingInvoice({
        client_id: String(f.get("client_id")), issue_date: String(f.get("issue_date")), currency: "INR",
        client_gstin: String(f.get("client_gstin") || "") || null,
        client_state_code: String(f.get("client_state_code") || "") || null,
        place_of_supply: String(f.get("place_of_supply") || "") || null,
        reverse_charge: f.get("reverse_charge") === "on",
        notes: String(f.get("notes") || "") || null,
        lines: [{
          kind: "fee", description: String(f.get("description")), service_code: String(f.get("service_code") || "") || null,
          quantity: Number(f.get("quantity") || 1), unit_price: Number(f.get("unit_price") || 0), discount_amount: Number(f.get("discount") || 0),
          cgst_rate: Number(f.get("cgst_rate") || 0), sgst_rate: Number(f.get("sgst_rate") || 0), igst_rate: Number(f.get("igst_rate") || 0), cess_rate: Number(f.get("cess_rate") || 0),
        }],
      });
      setComposer(null); await refresh(); setSelected(invoice); setTab("invoices");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create invoice"); }
    finally { setBusy(false); }
  }

  async function submitExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); const f = new FormData(event.currentTarget);
    try {
      await createBillingExpense({ client_id: String(f.get("client_id") || "") || null, expense_date: String(f.get("expense_date")), description: String(f.get("description")), category: String(f.get("category") || "") || null, amount: Number(f.get("amount") || 0), tax_amount: Number(f.get("tax_amount") || 0), currency: "INR", billable: f.get("billable") === "on", notes: String(f.get("notes") || "") || null });
      setComposer(null); await refresh(); setTab("expenses");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save expense"); }
    finally { setBusy(false); }
  }

  async function submitPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); const f = new FormData(event.currentTarget);
    const invoice = invoices.find(i => i.id === String(f.get("invoice_id")));
    try {
      await createBillingPayment({ client_id: invoice?.client_id || String(f.get("client_id")), invoice_id: String(f.get("invoice_id") || "") || null, amount: Number(f.get("amount") || 0), currency: invoice?.currency || "INR", payment_date: String(f.get("payment_date")), method: String(f.get("method") || "bank_transfer"), status: "cleared", reference: String(f.get("reference") || "") || null });
      setComposer(null); await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not record payment"); }
    finally { setBusy(false); }
  }

  async function review(invoice: BillingInvoice) {
    setBusy(true); try { const row = await reviewBillingInvoice(invoice.id, "Tax treatment and invoice particulars reviewed by billing user."); setSelected(row); await refresh(); } catch (err) { setError(err instanceof Error ? err.message : "Review failed"); } finally { setBusy(false); }
  }
  async function issue(invoice: BillingInvoice) {
    setBusy(true); try { const row = await issueBillingInvoice(invoice.id); setSelected(row); await refresh(); } catch (err) { setError(err instanceof Error ? err.message : "Issue failed"); } finally { setBusy(false); }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); const f = new FormData(event.currentTarget);
    try {
      const updated = await updateBillingProfile({
        legal_name: String(f.get("legal_name") || "") || null, billing_address: String(f.get("billing_address") || "") || null,
        city: String(f.get("city") || "") || null, state: String(f.get("state") || "") || null, state_code: String(f.get("state_code") || "") || null,
        country: "India", gstin: String(f.get("gstin") || "") || null, email: String(f.get("email") || "") || null, phone: String(f.get("phone") || "") || null,
        default_currency: "INR", invoice_prefix: String(f.get("invoice_prefix") || "INV"), default_payment_terms_days: Number(f.get("terms") || 15), bank_details: {}, tax_configuration: {},
      }); setProfile(updated);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update billing profile"); } finally { setBusy(false); }
  }

  return <main className="page billing-page">
    <div className="hero-row"><div><div className="eyebrow">Practice finance</div><h1 className="page-title">Billing & accounts</h1><p className="page-subtitle">Time, expenses, invoices and collections with reviewable tax treatment. Junior Lawyer calculates arithmetic; your firm chooses the legal/tax position.</p></div><button className="primary-button" onClick={() => setComposer("invoice")}><ReceiptIcon />New invoice</button></div>
    {error ? <div className="notice-panel billing-error"><strong>Attention</strong><span>{error}</span></div> : null}
    <div className="workspace-tabs billing-tabs">{(["overview","invoices","expenses","settings"] as Tab[]).map(t => <button key={t} className={`workspace-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>{t[0].toUpperCase()+t.slice(1)}</button>)}</div>

    {tab === "overview" ? <>
      <div className="metrics billing-metrics"><div className="metric"><div className="metric-label">Outstanding</div><div className="metric-value">{money(overview?.outstanding_amount || 0)}</div><div className="metric-note">Issued invoices only</div></div><div className="metric"><div className="metric-label">Overdue</div><div className="metric-value">{overview?.overdue_invoices ?? 0}</div><div className="metric-note">Past recorded due date</div></div><div className="metric"><div className="metric-label">Unbilled time</div><div className="metric-value">{Math.round((overview?.unbilled_minutes || 0)/60*10)/10}h</div><div className="metric-note">Time-entry foundation</div></div><div className="metric"><div className="metric-label">Approved expenses</div><div className="metric-value">{money(overview?.approved_expenses || 0)}</div><div className="metric-note">Not yet billed</div></div></div>
      <div className="grid-2"><section className="card"><div className="card-header"><div><div className="card-title">Receivables</div><div className="billing-copy">Issued and partially paid invoices</div></div><button className="secondary-button" onClick={() => setTab("invoices")}>View all</button></div>{openInvoices.length ? openInvoices.slice(0,6).map(i => <button className="billing-invoice-row" key={i.id} onClick={() => {setSelected(i);setTab("invoices")}}><div><strong>{i.invoice_number}</strong><small>{i.client_name} · due {i.due_date || "not set"}</small></div><span>{money(i.amount_due, i.currency)}</span></button>) : <div className="empty-state compact"><div className="empty-state-title">No open receivables</div></div>}</section><section className="card"><div className="card-header"><div className="card-title">Control layer</div></div><div className="billing-control-list"><div><ShieldIcon/><span><strong>Tax treatment is explicit</strong><small>No automatic GST applicability decision.</small></span></div><div><span className="billing-symbol">#</span><span><strong>Issued snapshots are hashed</strong><small>Drafts change; issued versions remain traceable.</small></span></div><div><span className="billing-symbol">₹</span><span><strong>Ledger-driven balances</strong><small>Payments reduce balances without rewriting issued totals.</small></span></div></div></section></div>
    </> : null}

    {tab === "invoices" ? <section className="card"><div className="card-header"><div><div className="card-title">Invoice register</div><div className="billing-copy">Draft → review → issue → collection</div></div><div className="billing-actions"><button className="secondary-button" onClick={() => setComposer("payment")}>Record payment</button><button className="primary-button" onClick={() => setComposer("invoice")}>New invoice</button></div></div>{invoices.length ? invoices.map(i => <button key={i.id} className="billing-invoice-table-row" onClick={() => setSelected(i)}><div><strong>{i.invoice_number}</strong><small>{i.client_name}</small></div><span>{i.issue_date || "Draft"}</span><span className={`billing-status ${i.status}`}>{i.status.replaceAll("_"," ")}</span><span>{money(i.grand_total,i.currency)}</span><span>{money(i.amount_due,i.currency)}</span></button>) : <div className="empty-state"><div className="empty-state-title">No invoices yet</div></div>}</section> : null}

    {tab === "expenses" ? <section className="card"><div className="card-header"><div><div className="card-title">Expenses</div><div className="billing-copy">Disbursements and recoverable client costs</div></div><button className="secondary-button" onClick={() => setComposer("expense")}>Add expense</button></div>{expenses.length ? expenses.map(e => <div className="billing-expense-row" key={e.id}><div><strong>{e.description}</strong><small>{e.category || "Uncategorised"} · {e.expense_date}</small></div><span className={`billing-status ${e.status}`}>{e.status}</span><span>{money(e.amount,e.currency)}</span></div>) : <div className="empty-state compact"><div className="empty-state-title">No expenses recorded</div></div>}</section> : null}

    {tab === "settings" && profile ? <section className="card billing-settings-card"><div className="card-header"><div><div className="card-title">Billing identity</div><div className="billing-copy">Supplier particulars used when drafting new invoices</div></div></div><form className="billing-form billing-settings" onSubmit={saveProfile}><div className="form-two"><label>Legal name<input name="legal_name" defaultValue={profile.legal_name || ""}/></label><label>GSTIN<input name="gstin" defaultValue={profile.gstin || ""} placeholder="Enter only when applicable"/></label></div><label>Billing address<textarea name="billing_address" defaultValue={profile.billing_address || ""} rows={3}/></label><div className="form-three"><label>City<input name="city" defaultValue={profile.city || ""}/></label><label>State<input name="state" defaultValue={profile.state || ""}/></label><label>State code<input name="state_code" defaultValue={profile.state_code || ""}/></label></div><div className="form-two"><label>Email<input name="email" defaultValue={profile.email || ""}/></label><label>Phone<input name="phone" defaultValue={profile.phone || ""}/></label></div><div className="form-two"><label>Invoice prefix<input name="invoice_prefix" defaultValue={profile.invoice_prefix}/></label><label>Default payment terms (days)<input name="terms" type="number" min="0" defaultValue={profile.default_payment_terms_days}/></label></div><div className="notice-panel"><strong>Tax configuration</strong><span>Rates and applicability are intentionally not inferred from client location or turnover. Verify them before issue.</span></div><button className="primary-button" disabled={busy}>Save billing profile</button></form></section> : null}

    {selected ? <div className="modal-backdrop" onMouseDown={() => setSelected(null)}><aside className="invoice-detail" onMouseDown={e=>e.stopPropagation()}><div className="client-detail-head"><div><div className="eyebrow">{selected.invoice_number}</div><h2>{selected.client_name}</h2><p>{selected.issue_date || "Draft invoice"} · {selected.currency}</p></div><button className="icon-button" onClick={()=>setSelected(null)}>×</button></div><div className="invoice-detail-body"><div className="invoice-total-card"><span>Amount due</span><strong>{money(selected.amount_due,selected.currency)}</strong><small>Total {money(selected.grand_total,selected.currency)} · Paid {money(selected.amount_paid,selected.currency)}</small></div><section><div className="section-kicker">Lines</div>{(selected.lines ?? []).map(line=><div className="invoice-line" key={line.id}><div><strong>{line.description}</strong><small>{line.service_code || "No service code"} · Qty {line.quantity}</small></div><span>{money(line.line_total,selected.currency)}</span></div>)}</section><section><div className="section-kicker">Tax components</div><div className="tax-grid"><span>CGST<strong>{money(selected.cgst_total)}</strong></span><span>SGST<strong>{money(selected.sgst_total)}</strong></span><span>IGST<strong>{money(selected.igst_total)}</strong></span><span>Cess<strong>{money(selected.cess_total)}</strong></span></div></section><section><div className="section-kicker">Review state</div><div className="detail-line"><span>Tax treatment reviewed</span><small>{selected.tax_treatment_reviewed ? "Yes" : "No"}</small></div><div className="detail-line"><span>Invoice state</span><small>{selected.status.replaceAll("_"," ")}</small></div></section>{["draft","review"].includes(selected.status) ? <div className="invoice-detail-actions">{!selected.tax_treatment_reviewed ? <button className="secondary-button" disabled={busy} onClick={()=>void review(selected)}>Mark tax treatment reviewed</button> : null}{selected.tax_treatment_reviewed ? <button className="primary-button" disabled={busy} onClick={()=>void issue(selected)}>Issue immutable invoice</button> : null}</div> : null}</div></aside></div> : null}

    {composer ? <div className="modal-backdrop" onMouseDown={()=>setComposer(null)}><div className="billing-modal" onMouseDown={e=>e.stopPropagation()}><div className="card-header"><div><div className="card-title">{composer === "invoice" ? "New invoice" : composer === "expense" ? "New expense" : "Record payment"}</div><div className="billing-copy">{composer === "invoice" ? "Tax components are manual and reviewable." : "Recorded inside the client ledger foundation."}</div></div><button className="icon-button" onClick={()=>setComposer(null)}>×</button></div>{composer === "invoice" ? <form className="billing-form" onSubmit={submitInvoice}><label>Client<select name="client_id" required defaultValue=""><option value="" disabled>Select client</option>{clients.map(c=><option key={c.id} value={c.id}>{c.display_name}</option>)}</select></label><div className="form-two"><label>Issue date<input name="issue_date" type="date" defaultValue={today()} required/></label><label>Service / SAC code<input name="service_code" placeholder="Firm-entered classification"/></label></div><label>Description<textarea name="description" rows={3} required placeholder="Professional legal services..."/></label><div className="form-three"><label>Quantity<input name="quantity" type="number" step="0.01" min="0.01" defaultValue="1" required/></label><label>Unit price<input name="unit_price" type="number" step="0.01" min="0" required/></label><label>Discount<input name="discount" type="number" step="0.01" min="0" defaultValue="0"/></label></div><div className="tax-rate-box"><div className="section-kicker">Tax components — enter only after determining treatment</div><div className="form-four"><label>CGST %<input name="cgst_rate" type="number" step="0.01" min="0" defaultValue="0"/></label><label>SGST %<input name="sgst_rate" type="number" step="0.01" min="0" defaultValue="0"/></label><label>IGST %<input name="igst_rate" type="number" step="0.01" min="0" defaultValue="0"/></label><label>Cess %<input name="cess_rate" type="number" step="0.01" min="0" defaultValue="0"/></label></div></div><div className="form-two"><label>Client GSTIN<input name="client_gstin"/></label><label>Client state code<input name="client_state_code"/></label></div><label>Place of supply<input name="place_of_supply"/></label><label className="check-label"><input name="reverse_charge" type="checkbox"/> Reverse charge marked by reviewer</label><label>Notes<textarea name="notes" rows={2}/></label><button className="primary-button" disabled={busy}>{busy?"Creating…":"Create review draft"}</button></form> : null}{composer === "expense" ? <form className="billing-form" onSubmit={submitExpense}><label>Client<select name="client_id" defaultValue=""><option value="">Internal / unassigned</option>{clients.map(c=><option key={c.id} value={c.id}>{c.display_name}</option>)}</select></label><div className="form-two"><label>Date<input name="expense_date" type="date" defaultValue={today()} required/></label><label>Category<input name="category" placeholder="Court fee, travel..."/></label></div><label>Description<input name="description" required/></label><div className="form-two"><label>Amount<input name="amount" type="number" min="0.01" step="0.01" required/></label><label>Tax included/recorded<input name="tax_amount" type="number" min="0" step="0.01" defaultValue="0"/></label></div><label className="check-label"><input name="billable" type="checkbox" defaultChecked/> Recoverable from client</label><label>Notes<textarea name="notes" rows={2}/></label><button className="primary-button" disabled={busy}>Save expense</button></form> : null}{composer === "payment" ? <form className="billing-form" onSubmit={submitPayment}><label>Invoice<select name="invoice_id" required defaultValue=""><option value="" disabled>Select issued invoice</option>{openInvoices.map(i=><option key={i.id} value={i.id}>{i.invoice_number} · {i.client_name} · {money(i.amount_due)}</option>)}</select></label><div className="form-two"><label>Payment date<input name="payment_date" type="date" defaultValue={today()} required/></label><label>Amount<input name="amount" type="number" min="0.01" step="0.01" required/></label></div><div className="form-two"><label>Method<select name="method"><option value="bank_transfer">Bank transfer</option><option value="upi">UPI</option><option value="cheque">Cheque</option><option value="cash">Cash</option><option value="card">Card</option><option value="other">Other</option></select></label><label>Reference<input name="reference"/></label></div><button className="primary-button" disabled={busy}>Record cleared payment</button></form> : null}</div></div> : null}
  </main>;
}
