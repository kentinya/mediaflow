import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./shared/ui/styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("MediaFlow V2 root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
