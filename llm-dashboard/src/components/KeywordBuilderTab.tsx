import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  ActionRow,
  EditorialBanner,
  FormField,
  OutputBlock,
  PanelCard,
  TagList,
  TwoColumnLayout,
} from "./shared";

type KeywordResult = {
  headline_options: string[];
  short_posts: string[];
  full_news_update: string;
  hashtags: string[];
  recommended_caution_line: string;
  source_verification_checklist: string[];
  mode: string;
};

export function KeywordBuilderTab() {
  const [form, setForm] = useState({
    topic_keyword: "",
    seo_keywords: "",
    target_audience: "",
    region: "",
    time_sensitivity: "standard",
    verified_incident_text: "",
  });
  const [result, setResult] = useState<KeywordResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const run = async () => {
    if (!form.topic_keyword.trim()) {
      setError("Topic keyword is required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = (await api.keywordPost(form)) as KeywordResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Build failed");
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!result) return;
    await api.savePost({
      content_type: "keyword_builder",
      raw_input: form,
      generated_output: result,
      keywords: form.topic_keyword,
      seo_keywords: form.seo_keywords,
      region: form.region,
      status: "draft",
    });
    alert("Saved to database.");
  };

  return (
    <div>
      <EditorialBanner />
      <TwoColumnLayout
        left={
          <PanelCard
            title="Keyword-Based Post Builder"
            description="Without verified incident text, the system produces templates and verification checklists — not fake news posts."
          >
            <div className="space-y-4">
              <FormField label="Topic keyword">
                <Input
                  value={form.topic_keyword}
                  onChange={(e) => update("topic_keyword", e.target.value)}
                  placeholder="Balochistan security"
                />
              </FormField>
              <FormField label="SEO keywords">
                <Input value={form.seo_keywords} onChange={(e) => update("seo_keywords", e.target.value)} />
              </FormField>
              <FormField label="Target audience">
                <Input
                  value={form.target_audience}
                  onChange={(e) => update("target_audience", e.target.value)}
                />
              </FormField>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField label="Region">
                  <Input value={form.region} onChange={(e) => update("region", e.target.value)} />
                </FormField>
                <FormField label="Time sensitivity">
                  <Select
                    value={form.time_sensitivity}
                    onValueChange={(v) => update("time_sensitivity", v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="standard">Standard</SelectItem>
                      <SelectItem value="breaking">Breaking</SelectItem>
                      <SelectItem value="background">Background</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
              </div>
              <FormField label="Verified incident text (optional)">
                <Textarea
                  value={form.verified_incident_text}
                  onChange={(e) => update("verified_incident_text", e.target.value)}
                  placeholder="Paste corroborated source text here to enable news-style output"
                />
              </FormField>
              <ActionRow>
                <Button onClick={run} disabled={loading}>
                  {loading ? "Building…" : "Build posts"}
                </Button>
                {result && (
                  <Button variant="outline" onClick={save}>
                    Save output
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
          <PanelCard title="Output">
            {result?.mode === "template" && (
              <Alert variant="warning" className="mb-4">
                <AlertDescription>
                  Template / explainer mode — no verified incident text supplied.
                </AlertDescription>
              </Alert>
            )}
            {result && (
              <>
                <OutputBlock title="Headline options (5)">
                  <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
                    {result.headline_options.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ol>
                </OutputBlock>
                <OutputBlock title="Short posts (3)">
                  <div className="space-y-3">
                    {result.short_posts.map((p) => (
                      <pre key={p} className="whitespace-pre-wrap font-mono text-sm">
                        {p}
                      </pre>
                    ))}
                  </div>
                </OutputBlock>
                <OutputBlock title="Full news-style update">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.full_news_update}</pre>
                </OutputBlock>
                <OutputBlock title="Hashtags">
                  <TagList items={result.hashtags} />
                </OutputBlock>
                <OutputBlock title="Recommended caution line">
                  <p>{result.recommended_caution_line}</p>
                </OutputBlock>
                <OutputBlock title="Source verification checklist">
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                    {result.source_verification_checklist.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </OutputBlock>
              </>
            )}
          </PanelCard>
        }
      />
    </div>
  );
}
