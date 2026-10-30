import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { createHistoryPreviewRouter } from "./routes";

const router = createHistoryPreviewRouter();
const element = document.getElementById("root");
if (!element) throw new Error("예시 화면을 표시할 요소가 없습니다.");
createRoot(element).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
