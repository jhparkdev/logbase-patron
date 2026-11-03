import type { components } from "../../../shared/api/schema";

type Project = components["schemas"]["SubscriptionProject"];

/** 귀속 프로젝트 선택 상자에서 "새 프로젝트 추가…"를 고른 값. 번호나 빈 문자열(고르지 않음)과 겹치지 않는다. */
export const NEW_PROJECT_VALUE = "new";

const WHITESPACE = /\s+/g;

/** 선택 상자 값(프로젝트 번호 문자열)을 번호로 바꾼다. 빈 문자열(옛 미배분 구독료의 수정)은 null이다. */
export function projectIdOf(text: string): number | null {
  return text === "" ? null : Number(text);
}

/** 서버의 중복 판정과 같은 규칙으로 비교한다. 띄어쓰기(없는 것 포함)와 대소문자를 무시한다. */
export function sameProjectName(a: string, b: string): boolean {
  return (
    a.replace(WHITESPACE, "").toLowerCase() ===
    b.replace(WHITESPACE, "").toLowerCase()
  );
}

/**
 * 구독료를 귀속할 프로젝트를 정한다. 새 프로젝트 이름이 선택지에 이미 있으면 그 프로젝트를 고른 것으로
 * 보고, 없을 때만 만들 이름을 돌려준다. 같은 프로젝트를 띄어쓰기만 다르게 두 번 만들지 않기 위해서다.
 */
export function resolveProject(
  values: { project: string; newProjectName: string },
  projects: Project[],
): { projectId: number | null } | { createName: string } {
  if (values.project !== NEW_PROJECT_VALUE) {
    return { projectId: projectIdOf(values.project) };
  }
  const existing = projects.find((project) =>
    sameProjectName(project.name, values.newProjectName),
  );
  return existing === undefined
    ? { createName: values.newProjectName }
    : { projectId: existing.project_id };
}
