"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "./AuthProvider";
import { ThemeProvider } from "./ThemeProvider";
import { Toaster } from "./Toaster";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 15_000 } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AuthProvider>
          <Toaster>{children}</Toaster>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
