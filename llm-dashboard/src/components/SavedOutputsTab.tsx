import { useCallback, useEffect, useState } from "react";
import { api, SavedPost } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ActionRow, EditorialBanner, PanelCard } from "./shared";

const STATUSES = ["draft", "reviewed", "ready", "rejected"];

export function SavedOutputsTab() {
  const [items, setItems] = useState<SavedPost[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listPosts();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load saved posts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updateStatus = async (id: number, status: string) => {
    await api.updateStatus(id, status);
    await load();
  };

  const remove = async (id: number) => {
    if (!confirm("Delete this saved output?")) return;
    await api.deletePost(id);
    await load();
  };

  return (
    <div>
      <EditorialBanner />
      <PanelCard
        title="Saved Outputs"
        description="SQLite-backed storage for generated posts and audits."
      >
        <ActionRow>
          <Button variant="outline" onClick={load} disabled={loading}>
            Refresh
          </Button>
        </ActionRow>

        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {loading && <p className="mt-4 text-sm text-muted-foreground">Loading…</p>}
        {!loading && items.length === 0 && (
          <p className="mt-4 text-sm text-muted-foreground">
            No saved outputs yet. Generate and save from other tabs.
          </p>
        )}
        {items.length > 0 && (
          <div className="mt-4 rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Region</TableHead>
                  <TableHead>Grade</TableHead>
                  <TableHead>Audit</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.id}</TableCell>
                    <TableCell className="font-mono text-xs">{item.content_type}</TableCell>
                    <TableCell>{item.region || "—"}</TableCell>
                    <TableCell>{item.source_grade || "—"}</TableCell>
                    <TableCell>{item.audit_score ?? "—"}</TableCell>
                    <TableCell>
                      <Select value={item.status} onValueChange={(v) => updateStatus(item.id, v)}>
                        <SelectTrigger className="h-8 w-[130px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {STATUSES.map((s) => (
                            <SelectItem key={s} value={s}>
                              {s}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell>
                      <Button variant="destructive" size="sm" onClick={() => remove(item.id)}>
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </PanelCard>
    </div>
  );
}
