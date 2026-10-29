import { Link } from "@tanstack/react-router";

type PageHeaderProps = {
  title: string;
  description?: string;
};

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-1">
      <nav
        aria-label="현재 위치"
        className="flex gap-1 text-label text-grey-600"
      >
        <Link to="/">홈</Link>
        <span aria-hidden="true">›</span>
        <span>{title}</span>
      </nav>
      <h1 className="text-title font-bold">{title}</h1>
      {description && <p className="text-grey-700">{description}</p>}
    </header>
  );
}
