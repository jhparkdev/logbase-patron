import { Badge } from "../../../shared/components/ui/Badge";
import { creatorBadge } from "../lib/creator";

export function ModelCreatorBadge({ creator }: { creator?: string }) {
  const badge = creatorBadge(creator);
  return (
    <span
      title={`모델 제작사: ${badge.label}`}
      className="inline-flex items-center"
    >
      <span className="sr-only">모델 제작사: </span>
      <Badge tone={badge.tone}>{badge.label}</Badge>
    </span>
  );
}
