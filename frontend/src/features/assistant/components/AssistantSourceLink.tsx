import { Link } from "@tanstack/react-router";
import { type AssistantSource, assistantSourceLink } from "../lib/source-link";

export function AssistantSourceLink({ source }: { source: AssistantSource }) {
  const link = assistantSourceLink(source);
  return link.to === "/models" ? (
    <Link to={link.to} title={link.title} className="underline">
      {link.label}
    </Link>
  ) : link.to === "/customer-usage" ? (
    <Link
      to={link.to}
      search={link.search}
      title={link.title}
      className="underline"
    >
      {link.label}
    </Link>
  ) : link.to === "/internal-budget" ? (
    <Link
      to={link.to}
      search={link.search}
      title={link.title}
      className="underline"
    >
      {link.label}
    </Link>
  ) : (
    <Link
      to={link.to}
      search={link.search}
      title={link.title}
      className="underline"
    >
      {link.label}
    </Link>
  );
}
