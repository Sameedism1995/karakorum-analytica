import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { AuditTab } from "./components/AuditTab";
import { KeywordBuilderTab } from "./components/KeywordBuilderTab";
import { PostGeneratorTab } from "./components/PostGeneratorTab";
import { SavedOutputsTab } from "./components/SavedOutputsTab";
import { SeoTab } from "./components/SeoTab";

export default function App() {
  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 py-6 md:px-6">
      <header className="mb-4 flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold uppercase tracking-[0.12em] text-foreground">
            Karakorum Analytica
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            LLM Newsroom Dashboard — internal OSINT editorial tools
          </p>
        </div>
        <Badge variant="outline" className="w-fit font-mono text-[10px] uppercase tracking-wider">
          Conflict monitoring · Verification first
        </Badge>
      </header>

      <Tabs defaultValue="generator" className="w-full">
        <TabsList className="mb-2 h-auto w-full flex-wrap justify-start gap-1 p-1">
          <TabsTrigger value="generator">Post Generator</TabsTrigger>
          <TabsTrigger value="keyword">Keyword Builder</TabsTrigger>
          <TabsTrigger value="audit">Audit & Verification</TabsTrigger>
          <TabsTrigger value="seo">SEO Assistant</TabsTrigger>
          <TabsTrigger value="saved">Saved Outputs</TabsTrigger>
        </TabsList>

        <Separator className="mb-4 bg-border" />

        <TabsContent value="generator">
          <PostGeneratorTab />
        </TabsContent>
        <TabsContent value="keyword">
          <KeywordBuilderTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditTab />
        </TabsContent>
        <TabsContent value="seo">
          <SeoTab />
        </TabsContent>
        <TabsContent value="saved">
          <SavedOutputsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
