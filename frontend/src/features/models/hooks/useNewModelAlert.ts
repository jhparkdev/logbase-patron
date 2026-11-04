import { useQuery } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";
import { newOpenRouterModelsQuery } from "../api/models";
import { hasUnseenNewModels } from "../lib/newModels";

const SEEN_KEY = "patron.newModelsSeenAt";
const SEEN_EVENT = "patron:new-models-seen";

// 브라우저 저장소는 막혀 있을 수 있다. 읽지 못하면 아직 안 본 것으로 둔다
function readSeen(): string | null {
  try {
    return localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

function writeSeen(value: string) {
  try {
    localStorage.setItem(SEEN_KEY, value);
  } catch {
    return;
  }
  window.dispatchEvent(new Event(SEEN_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(SEEN_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(SEEN_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function useLatestNewModelAt(): string | null {
  const { data } = useQuery(newOpenRouterModelsQuery);
  const items = data && Array.isArray(data.items) ? data.items : [];
  return items[0]?.created_at ?? null;
}

/** 아직 확인하지 않은 새 모델이 있는지. 사이드바 표시에 쓴다 */
export function useHasUnseenNewModels(): boolean {
  const latest = useLatestNewModelAt();
  const seen = useSyncExternalStore(subscribe, readSeen, () => null);
  return hasUnseenNewModels(latest, seen);
}

/** 모델 관리 화면을 열면 지금 보이는 새 모델까지 확인한 것으로 남긴다 */
export function useMarkNewModelsSeen() {
  const latest = useLatestNewModelAt();
  useEffect(() => {
    if (latest) writeSeen(latest);
  }, [latest]);
}
