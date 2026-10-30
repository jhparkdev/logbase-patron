import { useRef, useState } from "react";

export function useCancellation() {
  const locks = useRef(new Set<string>());
  const [pending, setPending] = useState<string[]>([]);
  const [error, setError] = useState("");
  const send = async (key: string, action: () => void | Promise<void>) => {
    if (locks.current.has(key)) return;
    locks.current.add(key);
    setPending([...locks.current]);
    setError("");
    try {
      await action();
    } catch {
      setError(
        "취소 요청을 보내지 못했어요. 실행 상태를 확인한 뒤 다시 시도해 주세요.",
      );
    } finally {
      locks.current.delete(key);
      setPending([...locks.current]);
    }
  };
  return { pending, error, send };
}
