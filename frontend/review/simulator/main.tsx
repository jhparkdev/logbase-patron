import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
  redirect,
} from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { PreviewLayout } from "./PreviewLayout";
import { SimulatorPreview } from "./SimulatorPreview";

const root = createRootRoute({
  component: PreviewLayout,
  beforeLoad: ({ location }) => {
    if (location.pathname !== "/simulator-preview.html")
      throw redirect({ href: location.href, reloadDocument: true });
  },
});
const previewRoute = createRoute({
  getParentRoute: () => root,
  path: "/simulator-preview.html",
  component: SimulatorPreview,
});
const router = createRouter({ routeTree: root.addChildren([previewRoute]) });

const element = document.getElementById("root");
if (!element) throw new Error("검토 화면을 표시할 요소가 없습니다.");

createRoot(element).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
