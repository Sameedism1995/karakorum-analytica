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

type GenerateResult = {
  short_x_post: string;
  website_post: string;
  seo_headline: string;
  meta_description: string;
  suggested_hashtags: string[];
  suggested_keywords: string[];
  verification_warning?: string;
  mode: string;
};

export function PostGeneratorTab() {
  const [form, setForm] = useState({
    raw_incident_text: "",
    main_keyword: "",
    seo_keywords: "",
    region: "",
    country: "Pakistan",
    city_district: "",
    incident_category: "",
    source_type: "",
    source_reliability_grade: "C",
    tone: "neutral",
    platform: "x",
  });
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const data = (await api.generatePost(form)) as GenerateResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!result) return;
    await api.savePost({
      content_type: "post_generator",
      raw_input: form,
      generated_output: result,
      source_grade: form.source_reliability_grade,
      keywords: form.main_keyword,
      seo_keywords: form.seo_keywords,
      region: form.region,
      category: form.incident_category,
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
            title="Post Generator"
            description="Generate platform-ready drafts from verified incident text. Without source text, outputs are templates only."
          >
            <div className="space-y-4">
              <FormField label="Raw incident / report text">
                <Textarea
                  value={form.raw_incident_text}
                  onChange={(e) => update("raw_incident_text", e.target.value)}
                />
              </FormField>
              <FormField label="Main keyword">
                <Input value={form.main_keyword} onChange={(e) => update("main_keyword", e.target.value)} />
              </FormField>
              <FormField label="SEO keywords (comma-separated)">
                <Input value={form.seo_keywords} onChange={(e) => update("seo_keywords", e.target.value)} />
              </FormField>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField label="Region">
                  <Input value={form.region} onChange={(e) => update("region", e.target.value)} />
                </FormField>
                <FormField label="Country">
                  <Input value={form.country} onChange={(e) => update("country", e.target.value)} />
                </FormField>
              </div>
              <FormField label="City / district">
                <Input value={form.city_district} onChange={(e) => update("city_district", e.target.value)} />
              </FormField>
              <FormField label="Incident category">
                <Input
                  value={form.incident_category}
                  onChange={(e) => update("incident_category", e.target.value)}
                />
              </FormField>
              <FormField label="Source type">
                <Input value={form.source_type} onChange={(e) => update("source_type", e.target.value)} />
              </FormField>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <FormField label="Source grade">
                  <Select
                    value={form.source_reliability_grade}
                    onValueChange={(v) => update("source_reliability_grade", v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["A", "B", "C", "D", "E"].map((g) => (
                        <SelectItem key={g} value={g}>
                          {g}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
                <FormField label="Tone">
                  <Select value={form.tone} onValueChange={(v) => update("tone", v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="neutral">Neutral</SelectItem>
                      <SelectItem value="urgent">Urgent</SelectItem>
                      <SelectItem value="detailed">Detailed</SelectItem>
                      <SelectItem value="short">Short</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
                <FormField label="Platform">
                  <Select value={form.platform} onValueChange={(v) => update("platform", v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="x">X / Twitter</SelectItem>
                      <SelectItem value="website">Website</SelectItem>
                      <SelectItem value="telegram">Telegram</SelectItem>
                      <SelectItem value="instagram">Instagram</SelectItem>
                    </SelectContent>
                  </Select>
                </FormField>
              </div>
              <ActionRow>
                <Button onClick={run} disabled={loading}>
                  {loading ? "Generating…" : "Generate posts"}
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
          <PanelCard title="Output" description="Results appear here after generation.">
            {result?.verification_warning && (
              <Alert variant="warning" className="mb-4">
                <AlertDescription>{result.verification_warning}</AlertDescription>
              </Alert>
            )}
            {result?.mode === "template" && (
              <Alert variant="warning" className="mb-4">
                <AlertDescription>Template mode — not a verified news report.</AlertDescription>
              </Alert>
            )}
            {result ? (
              <>
                <OutputBlock title="Short X / Twitter post">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.short_x_post}</pre>
                </OutputBlock>
                <OutputBlock title="Website / news post">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.website_post}</pre>
                </OutputBlock>
                <OutputBlock title="SEO headline">
                  <p>{result.seo_headline}</p>
                </OutputBlock>
                <OutputBlock title="Meta description">
                  <p>{result.meta_description}</p>
                </OutputBlock>
                <OutputBlock title="Suggested hashtags">
                  <TagList items={result.suggested_hashtags} />
                </OutputBlock>
                <OutputBlock title="Suggested keywords">
                  <TagList items={result.suggested_keywords} />
                </OutputBlock>
              </>
            ) : null}
          </PanelCard>
        }
      />
    </div>
  );
}
