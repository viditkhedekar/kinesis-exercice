import ReportView from "@/components/ReportView";

export default function SessionReportPage({ params }: { params: { id: string } }) {
  return <ReportView sessionId={Number(params.id)} />;
}
