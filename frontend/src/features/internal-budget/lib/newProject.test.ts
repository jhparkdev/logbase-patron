import { describe, expect, test } from "vitest";
import {
  NEW_PROJECT_VALUE,
  resolveProject,
  sameProjectName,
} from "./newProject";

const PROJECTS = [
  { project_id: 1, name: "사내 챗봇 구축" },
  { project_id: 2, name: "Doc Summary" },
];

test("sameProjectName은 띄어쓰기(없는 것 포함)와 대소문자를 무시한다", () => {
  expect(sameProjectName("사내 챗봇 구축", "사내챗봇구축")).toBe(true);
  expect(sameProjectName("Doc Summary", " doc  summary ")).toBe(true);
  expect(sameProjectName("사내 챗봇", "사내 챗봇 구축")).toBe(false);
});

describe("resolveProject", () => {
  test("고른 프로젝트 번호나 미배분은 그대로 돌려준다", () => {
    expect(
      resolveProject({ project: "2", newProjectName: "" }, PROJECTS),
    ).toEqual({ projectId: 2 });
    expect(
      resolveProject({ project: "", newProjectName: "" }, PROJECTS),
    ).toEqual({ projectId: null });
  });

  test("새 프로젝트 이름이 선택지에 있으면 그 프로젝트를 고른 것으로 본다", () => {
    expect(
      resolveProject(
        { project: NEW_PROJECT_VALUE, newProjectName: "doc summary" },
        PROJECTS,
      ),
    ).toEqual({ projectId: 2 });
  });

  test("선택지에 없는 이름이면 만들 이름을 돌려준다", () => {
    expect(
      resolveProject(
        { project: NEW_PROJECT_VALUE, newProjectName: "신규 프로젝트" },
        PROJECTS,
      ),
    ).toEqual({ createName: "신규 프로젝트" });
  });
});
