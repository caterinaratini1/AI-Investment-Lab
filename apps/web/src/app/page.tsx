import { connection } from "next/server";

import { DashboardView } from "../components/dashboard-view";
import { getDashboardData } from "../lib/dashboard-data";

export default async function Home() {
  await connection();
  const data = await getDashboardData();
  return <DashboardView data={data} />;
}
