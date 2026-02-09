import { SetDetailPage } from "@/components/pages/sets/SetDetailPage";

export default async function Page({
  params,
}: {
  params: Promise<{ setId: string }>;
}) {
  const { setId } = await params;
  return <SetDetailPage setId={setId} />;
}
