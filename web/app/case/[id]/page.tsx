import CaseView from "./case-view";

export default async function CasePage(props: PageProps<"/case/[id]">) {
  const { id } = await props.params; // in Next.js 16, params arrive as a Promise
  return <CaseView id={id} />;
}
