import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

type SeoResult = {
  seo_title: string;
  url_slug: string;
  meta_description: string;
  article_tags: string[];
  internal_categories: string[];
  search_friendly_summary: string;
  social_media_caption: string;
};

export function SeoTab() {
  const [form, setForm] = useState({
    incident_summary: "",
    article_draft: "",
    main_keyword: "",
    secondary_keywords: "",
  });
  const [result, setResult] = useState<SeoResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (key: string, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const data = (await api.seo(form)) as SeoResult;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "SEO assist failed");
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!result) return;
    await api.savePost({
      content_type: "seo",
      raw_input: form,
      generated_output: result,
      keywords: form.main_keyword,
      seo_keywords: form.secondary_keywords,
      status: "draft",
    });
    alert("SEO output saved.");
  };

  return (
    <div>
      <EditorialBanner />
      <TwoColumnLayout
        left={
          <PanelCard title="SEO Assistant" description="Generate titles, slugs, meta tags, and social captions.">
            <div className="space-y-4">
              <FormField label="Incident summary">
                <Textarea
                  value={form.incident_summary}
                  onChange={(e) => update("incident_summary", e.target.value)}
                />
              </FormField>
              <FormField label="Article draft (optional)">
                <Textarea
                  value={form.article_draft}
                  onChange={(e) => update("article_draft", e.target.value)}
                />
              </FormField>
              <FormField label="Main keyword">
                <Input value={form.main_keyword} onChange={(e) => update("main_keyword", e.target.value)} />
              </FormField>
              <FormField label="Secondary keywords">
                <Input
                  value={form.secondary_keywords}
                  onChange={(e) => update("secondary_keywords", e.target.value)}
                />
              </FormField>
              <ActionRow>
                <Button onClick={run} disabled={loading}>
                  {loading ? "Generating…" : "Generate SEO pack"}
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
          <PanelCard title="SEO output">
            {result && (
              <>
                <OutputBlock title="SEO title">
                  <p>{result.seo_title}</p>
                </OutputBlock>
                <OutputBlock title="URL slug">
                  <p className="font-mono text-data">{result.url_slug}</p>
                </OutputBlock>
                <OutputBlock title="Meta description">
                  <p>{result.meta_description}</p>
                </OutputBlock>
                <OutputBlock title="Article tags">
                  <TagList items={result.article_tags} />
                </OutputBlock>
                <OutputBlock title="Internal categories">
                  <TagList items={result.internal_categories} />
                </OutputBlock>
                <OutputBlock title="Search-friendly summary">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.search_friendly_summary}</pre>
                </OutputBlock>
                <OutputBlock title="Social media caption">
                  <pre className="whitespace-pre-wrap font-mono text-sm">{result.social_media_caption}</pre>
                </OutputBlock>
              </>
            )}
          </PanelCard>
        }
      />
    </div>
  );
}
