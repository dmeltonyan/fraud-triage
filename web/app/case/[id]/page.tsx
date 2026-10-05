export default async function CasePage(props: PageProps<"/case/[id]">) {
  const { id } = await props.params; // in Next.js 16, params arrive as a Promise
  return (
    <section>
      <h1 className="text-2xl font-semibold">Case</h1>
      <p className="mt-2 font-mono text-sm text-muted">{id}</p>
    </section>
  );
}
