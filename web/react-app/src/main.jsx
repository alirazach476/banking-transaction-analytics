import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/inter";
import Shell from "./app/Shell.jsx";
import { RangeProvider, ThemeProvider } from "./lib/context.jsx";
import "./style/app.css";

const client = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={client}>
    <BrowserRouter basename="/app">
      <ThemeProvider>
        <RangeProvider>
          <Shell />
        </RangeProvider>
      </ThemeProvider>
    </BrowserRouter>
  </QueryClientProvider>,
);
