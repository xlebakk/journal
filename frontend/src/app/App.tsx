import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { RuledSkeleton } from "@/shared/ui";

import { HomePage } from "./HomePage";
import { NotFoundPage } from "./NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

// import.meta.env.DEV is a build-time constant: the styleguide is not in the production bundle.
const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [
      {
        path: "/dev/styleguide",
        Component: lazy(() => import("@/dev/StyleguidePage")),
      },
    ]
  : [];

const routes: RouteObject[] = [
  { path: "/", Component: HomePage },
  ...devRoutes,
  { path: "*", Component: NotFoundPage },
];

const router = createBrowserRouter(routes);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<RuledSkeleton />}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  );
}
