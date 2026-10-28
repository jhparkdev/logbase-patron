import { createFileRoute } from "@tanstack/react-router";

// 개발 환경 확인용 임시 화면. 실제 첫 화면으로 교체한다.
export const Route = createFileRoute("/")({
  component: Home,
});

function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold text-brand">BASE Patron</h1>
      <p className="mt-2 text-ink-muted">프론트엔드 개발 환경이 동작합니다.</p>
    </main>
  );
}
