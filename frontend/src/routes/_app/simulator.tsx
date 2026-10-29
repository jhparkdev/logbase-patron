import { createFileRoute } from "@tanstack/react-router";
import { SimulatorPage } from "../../features/simulator/components/SimulatorPage";
import { simulatorSearchSchema } from "../../features/simulator/lib/search";

export const Route = createFileRoute("/_app/simulator")({
  validateSearch: simulatorSearchSchema,
  component: SimulatorRoute,
});

function SimulatorRoute() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <SimulatorPage
      sort={{ key: search.sort, direction: search.direction }}
      onSort={(sort) => {
        void navigate({
          search: (previous) => ({
            ...previous,
            sort: sort.key,
            direction: sort.direction,
          }),
        });
      }}
    />
  );
}
