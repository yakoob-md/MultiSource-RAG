import { createBrowserRouter } from "react-router";
import { MainLayout } from "./components/MainLayout";
import { Dashboard } from "./components/screens/Dashboard";
import { AskAI } from "./components/screens/AskAI";
import { KnowledgeSources } from "./components/screens/KnowledgeSources";
import { UploadPDF } from "./components/screens/UploadPDF";
import { AddWebsite } from "./components/screens/AddWebsite";
import { AddYouTube } from "./components/screens/AddYouTube";
import { QueryHistory } from "./components/screens/QueryHistory";
import { Settings } from "./components/screens/Settings";
import { LegalSearch } from "./components/screens/LegalSearch";
import { UploadImage } from "./components/screens/UploadImage";
import { Landing } from "./components/screens/Landing";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Landing,
  },
  {
    path: "/app",
    Component: MainLayout,
    children: [
      { index: true, Component: AskAI },
      { path: "ask", Component: AskAI },
      { path: "sources", Component: KnowledgeSources },
      { path: "upload-pdf", Component: UploadPDF },
      { path: "add-website", Component: AddWebsite },
      { path: "add-youtube", Component: AddYouTube },
      { path: "history", Component: QueryHistory },
      { path: "settings", Component: Settings },
      { path: "legal", Component: LegalSearch },
      { path: "upload-image", Component: UploadImage },
    ],
  },
]);
