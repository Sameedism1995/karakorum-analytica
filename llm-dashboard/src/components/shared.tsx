import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const EDITORIAL_WARNINGS = [
  "Do not publish unverified claims as confirmed.",
  "Grade D/E sources require caution and attribution.",
  "Casualty figures must be attributed unless officially confirmed.",
  "The system may assist writing but does not verify facts automatically.",
];

export function EditorialBanner() {
  return (
    <Alert variant="warning" className="mb-4 border-l-4 border-l-primary">
      <ShieldAlert className="h-4 w-4 text-primary" />
      <AlertTitle className="text-foreground">Editorial safeguards</AlertTitle>
      <AlertDescription>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          {EDITORIAL_WARNINGS.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

export function FormField({
  label,
  htmlFor,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

export function OutputBlock({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Card className="mb-3 border-gunmetal bg-background">
      <CardHeader className="pb-2 pt-4">
        <CardTitle className="font-mono text-xs uppercase tracking-wider text-steel">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-4 text-sm leading-relaxed">{children}</CardContent>
    </Card>
  );
}

export function TagList({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Badge key={item} variant="data">
          {item}
        </Badge>
      ))}
    </div>
  );
}

export function publishStatusBadge(status: string) {
  if (status === "safe_to_publish") return "safe" as const;
  if (status === "publish_with_caution") return "caution" as const;
  if (status === "needs_verification") return "verify" as const;
  return "block" as const;
}

export function TwoColumnLayout({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {left}
      {right}
    </div>
  );
}

export function PanelCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </CardHeader>
      <CardContent>{children}</CardContent>
      {footer && <div className="px-6 pb-6">{footer}</div>}
    </Card>
  );
}

export function ActionRow({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-2 pt-2">{children}</div>;
}
