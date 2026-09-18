import { Explorer } from "@/components/explorer";
import { SiteHeader } from "@/components/site-header";
import { loadAppData } from "@/lib/load-data";

export default async function Page() {
  const data = await loadAppData();
  return (
    <>
      <SiteHeader summary={data.summary} />
      <Explorer data={data} />
    </>
  );
}
