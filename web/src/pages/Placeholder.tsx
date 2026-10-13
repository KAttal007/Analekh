import { Badge, EmptyState, PageHeader } from "../components/ui";

export function Placeholder({ title, phase }: { title: string; phase: number }) {
  return (
    <div className="page">
      <PageHeader title={title} badges={<Badge tone="warn">Phase {phase}</Badge>} />
      <EmptyState icon="clock" title={`${title} is on the way`}>
        This screen arrives in Phase {phase} of the build plan (design doc section 26).
      </EmptyState>
    </div>
  );
}
