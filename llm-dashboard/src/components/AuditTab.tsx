import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  ActionRow,
  EditorialBanner,
  FormField,
  OutputBlock,
  PanelCard,
  TagList,
  TwoColumnLayout,
  publishStatusBadge,
} from "./shared";

type AuditResult = {
  risk_score: number;
  source_reliability_grade: string;
  unsupported_claims: string[];
  sensational_wording: string[];
  propaganda_wording: string[];
  legal_safety_risk: string[];
  safer_rewritten_version: string;
  publish_status: string;
  publish_status_label: string;
};

export function AuditTab() {
  const [form, setForm] = useState({
    draft_post: "",
    source_information: "",
    raw_report_text: "",
  });
  const [result, setResult] = useState<AuditResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const run = async () => {
    if (!form.draft_post.trim()) {
      setError("Draft post is required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = (await api.auditPost(form)) as AuditResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audit failed");
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!result) return;
    await api.savePost({
      content_type: "audit",
      raw_input: form,
      generated_output: result,
      source_grade: result.source_reliability_grade,
      audit_score: result.risk_score,
      status: result.publish_status === "do_not_publish" ? "rejected" : "reviewed",
    });
    alert("Audit saved.");
  };

  return (
    <div>
      <EditorialBanner />
      <TwoColumnLayout
        left={
          <PanelCard
            title="Audit & Verification"
            description="Score draft risk, flag unsupported claims, and get a safer rewrite."
          >
            <div className="space-y-4">
              <FormField label="Draft post">
                <Textarea value={form.draft_post} onChange={(e) => update("draft_post", e.target.value)} />
              </FormField>
              <FormField label="Source information">
                <Textarea
                  value={form.source_information}
                  onChange={(e) => update("source_information", e.target.value)}
                  placeholder="Include source name, URL, grade A–E"
                />
              </FormField>
              <FormField label="Raw report text">
                <Textarea
                  value={form.raw_report_text}
                  onChange={(e) => update("raw_report_text", e.target.value)}
                />
              </FormField>
              <ActionRow>
                <Button onClick={run} disabled={loading}>
                  {loading ? "Auditing…" : "Run audit"}
                </Button>
                {result && (
                  <Button variant="outline" onClick={save}>
                    Save audit
                  </Button>
                )}
              </ActionRow>
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
            </div>
          </PanelCard>
        }
        right={
          <PanelCard title="Audit results">
            {result && (
              <>
                <OutputBlock title="Risk score (0–100)">
                  <div className="font-mono text-4xl text-primary">{result.risk_score}</div>
                </OutputBlock>
                <OutputBlock title="Source reliability grade">
                  <Badge variant="data">{result.source_reliability_grade}</Badge>
                </OutputBlock>
                <OutputBlock title="Publish status">
                  <Badge variant={publishStatusBadge(result.publish_status)}>
                    {result.publish_status_label}
                  </Badge>
                </OutputBlock>
                <OutputBlock title="Unsupported claims">
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                    {(result.unsupported_claims.length ? result.unsupported_claims : ["None flagged"]).map(
                      (item) => (
                        <li key={item}>{item}</li>
                      ),
                    )}
                  </ul>
                </OutputBlock>
                <OutputBlock title="Sensational wording">
                  <TagList items={result.sensational_wording.length ? result.sensational_wording : ["None"]} />
                </OutputBlock>
                <OutputBlock title="Propaganda-style wording">
                  <TagList items={result.propaganda_wording.length ? result.propaganda_wording : ["None"]} />
                </OutputBlock>
                <OutputBlock title="Legal / safety risk">
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                    {(result.legal_safety_risk.length ? result.legal_safety_risk : ["None flagged"]).map(
                      (item) => (
                        <li key={item}>{item}</li>
                      ),
                    )}
                  </ul>
                </OutputBlock>
                <OutputBlock title="Safer rewritten version">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.safer_rewritten_version}</pre>
                </OutputBlock>
              </>
            )}
          </PanelCard>
        }
      />
    </div>
  );
}
